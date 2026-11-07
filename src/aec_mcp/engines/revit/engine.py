"""Revit 引擎：Revit Command Bridge 文件队列客户端（协议 revit-command-bridge/2.0）。

传输：写 ``inbox/{id}.request.json``（先写临时文件再原子重命名），
轮询 ``outbox/{id}.result.json``。Revit 在主线程串行执行，
execute_plan 的写步骤在一个 Transaction 内 all-or-nothing。

桥接根目录：``%LOCALAPPDATA%\\RevitCommandBridge\\<year>``，
可用环境变量 ``AEC_REVIT_BRIDGE_ROOT`` / ``AEC_REVIT_YEAR`` 覆盖。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from ..base import BaseEngine
from ...errors import AecError, ErrorCode

PROTOCOL = "revit-command-bridge/2.0"
HEARTBEAT_MAX_AGE_S = 180.0


class RevitEngine(BaseEngine):
    name = "revit"
    capabilities = (
        "query_document", "query_catalog", "query_elements", "select_elements",
        "create_level", "create_grid", "create_wall", "create_floor", "create_room",
        "create_column", "create_model_curve", "create_direct_shape", "create_text",
        "export_image", "save_document",
    )

    def __init__(self, bridge_root: str | Path | None = None, year: str = "2024", wait_seconds: float | None = None) -> None:
        root = bridge_root or os.environ.get("AEC_REVIT_BRIDGE_ROOT") or (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData\\Local"))) / "RevitCommandBridge"
        )
        self.year = os.environ.get("AEC_REVIT_YEAR", year)
        self.root = Path(root) / self.year
        # 桥偶发空转数分钟（Revit 空闲事件调度），批跑可用 AEC_REVIT_WAIT 拉长等待
        self.wait_seconds = float(wait_seconds or os.environ.get("AEC_REVIT_WAIT", 120))

    # ------------------------------------------------------------------ 健康
    def health(self) -> dict[str, Any]:
        status = self.root / "status.json"
        if not self.root.exists():
            return {"ok": False, "state": "not_installed",
                    "message": f"桥接目录不存在: {self.root}",
                    "hint": "确认 Revit Command Bridge 插件已安装（Revit 2024）"}
        if not status.exists():
            return {"ok": False, "state": "no_status", "message": f"缺少 {status}", "root": str(self.root)}
        try:
            data = None
            for _ in range(4):  # 桥写入 status.json 时有瞬时文件锁，退避重读
                try:
                    data = json.loads(status.read_text(encoding="utf-8"))
                    break
                except PermissionError:
                    time.sleep(0.3)
                except json.JSONDecodeError:
                    time.sleep(0.3)
            if data is None:
                return {"ok": False, "state": "corrupt_status", "message": "status.json 读取失败（多次重试后仍锁/损坏）", "root": str(self.root)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "state": "corrupt_status", "message": str(e)}
        state = data.get("state", "unknown")
        # 心跳年龄：优先文件 mtime（C# 时间戳带 7 位小数，文本解析易碎），ISO 解析作对照
        age = _age_seconds(status.stat().st_mtime, data.get("updated_utc"))
        ok = state == "running" and age is not None and age <= HEARTBEAT_MAX_AGE_S
        hint = None
        if not ok:
            hint = "启动 Revit 2024 并等待命令桥加载（状态心跳恢复 running）"
        return {"ok": ok, "state": state, "heartbeat_age_s": age, "root": str(self.root), "hint": hint}

    # ------------------------------------------------------------------ 执行
    def execute(self, steps: list[dict[str, Any]], *, preview: bool = False, document_title: str | None = None) -> dict[str, Any]:
        self.ensure_up()
        steps = self._autofill_wall_type(steps)
        return self.send({"operation": "execute_plan", "args": {"steps": steps}, "preview": preview, "document_title": document_title})

    def _autofill_wall_type(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """query 先行：create_wall 缺 type 时查项目真实墙类型补默认值。

        桥的默认类型解析依赖英文 "Basic Wall" 命名，中式样板（基本墙/墙 1）会
        报 "只支持 Basic WallType"。显式传第一个可用类型名，模板无关。
        """
        if not any(s.get("operation") == "create_wall" and not (s.get("args") or {}).get("type") for s in steps):
            return steps
        types = self.send({"operation": "list_wall_types", "args": {}}, wait_seconds=60).get("data", {}).get("wall_types") or []
        if not types:
            raise AecError(ErrorCode.E_NOT_FOUND, "项目中没有可用墙类型，无法补默认 type")
        filled = [dict(s) for s in steps]
        default_type = types[0].get("name")
        for s in filled:
            if s.get("operation") == "create_wall" and not (s.get("args") or {}).get("type"):
                s.setdefault("args", {})["type"] = default_type
        return filled

    def send(self, command: dict[str, Any], *, wait_seconds: float | None = None) -> dict[str, Any]:
        """向桥接队列投递任意顶层命令并等待结果（供 revit_execute_plan / health / new_project 等使用）。"""
        inbox = self.root / "inbox"
        outbox = self.root / "outbox"
        processing = self.root / "processing"
        for d in (inbox, outbox, processing):
            d.mkdir(parents=True, exist_ok=True)
        cid = uuid.uuid4().hex[:12]
        request = {"id": cid, "source": "aec-mcp", "created_utc": _utcnow(), **command}
        tmp = inbox / f"{cid}.tmp"
        target = inbox / f"{cid}.request.json"
        payload = json.dumps(request, ensure_ascii=False, indent=2)
        last_err: Exception | None = None
        for _ in range(4):  # Defender/杀软偶发瞬时锁，退避重试
            try:
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, target)  # 原子投递
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                time.sleep(0.5)
        if last_err is not None:
            raise AecError(ErrorCode.E_ENGINE_DOWN, f"无法写入桥接 inbox（权限/杀软拦截）: {last_err}", {"path": str(target)})

        deadline = time.time() + (wait_seconds or self.wait_seconds)
        result_path = outbox / f"{cid}.result.json"
        while time.time() < deadline:
            if result_path.exists():
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                except Exception as e:  # noqa: BLE001
                    raise AecError(ErrorCode.E_INTERNAL, f"结果文件损坏: {e}", {"path": str(result_path)})
                self._map_failure(result)
                return result
            time.sleep(0.5)
        still_processing = (processing / f"{cid}.processing.json").exists()
        raise AecError(
            ErrorCode.E_ENGINE_TIMEOUT,
            f"等待 Revit 结果超时（{wait_seconds or self.wait_seconds:.0f}s），{'Revit 已领取仍在执行' if still_processing else '请求未被领取'}",
            {"request": str(target), "processing": still_processing},
        )

    def _map_failure(self, result: dict[str, Any]) -> None:
        err = _bridge_error(result)
        if err is not None:
            raise err

    def dry_run(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        # 真预览：交给桥接校验（不写模型）。桥不在线时退化为本地静态校验。
        if self.health().get("ok"):
            try:
                result = self.send({"operation": "execute_plan", "args": {"steps": steps}, "preview": True}, wait_seconds=60)
                return {"steps": steps, "bridge_preview": result.get("data", result)}
            except AecError as e:
                if e.code == ErrorCode.E_ENGINE_TIMEOUT:
                    return {"steps": steps, "warnings": ["桥接预览超时，仅本地校验"]}
                raise
        return {"steps": steps, "warnings": ["Revit 桥不在线：仅本地静态校验（提交时需要桥在线）"]}


# --------------------------------------------------------------------- 工具
def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _age_seconds(mtime: float, iso: str | None) -> float | None:
    """心跳年龄：mtime 为主（秒精度足够），ISO 文本解析为对照。"""
    from datetime import datetime, timezone

    try:
        return (datetime.now(timezone.utc).timestamp() - mtime) if mtime else None
    except Exception:  # noqa: BLE001
        pass
    if not iso:
        return None
    for candidate in (iso, iso.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds()
        except Exception:  # noqa: BLE001
            continue
    return None


def _bridge_error(result: dict[str, Any]) -> AecError | None:
    """桥协议 2.0 字段：ok / state / message；兼容 success。"""
    if result.get("state") == "failed":
        return _fbr_ok(result)
    ok = result.get("ok")
    if ok is None:
        ok = result.get("success")
    if ok is None and "state" in result:
        ok = result.get("state") != "failed"
    if ok is None:
        ok = not result.get("error")
    if ok:
        return None
    return _fbr_ok(result)


def _fbr_ok(result: dict[str, Any]) -> AecError | None:
    from ...errors import from_bridge_result as _fbr

    return _fbr(result)
