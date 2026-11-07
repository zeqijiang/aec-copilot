"""事务语义：preview → commit → rollback（方案 §3.1④）。

- preview：只编译+校验，绝不触碰引擎写接口
- commit ：引擎在一个事务内执行；revit 由桥保证 all-or-nothing（任一步失败整体回滚，
           成功可一次 Ctrl+Z）；acad 离线模式以 DXF 文件为事务边界（失败不落盘）
- rollback：commit 抛错时引擎自行回滚；这里记录审计日志
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .compiler import compile_plan
from .errors import AecError, ErrorCode
from .plan import Plan


class Transaction:
    """把「预览 → 提交 → 审计」包成一个可重放单元。"""

    def __init__(self, engine: Any, run_dir: str | Path | None = None) -> None:
        self.engine = engine
        self.run_dir = Path(run_dir) if run_dir else None
        self.journal: list[dict[str, Any]] = []

    def _log(self, event: str, data: dict[str, Any]) -> None:
        entry = {"t": time.time(), "event": event, **data}
        self.journal.append(entry)
        if self.run_dir:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            (self.run_dir / "journal.json").write_text(
                json.dumps(self.journal, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def preview(self, plan: Plan, engine_name: str) -> dict[str, Any]:
        steps = compile_plan(plan, engine_name)
        dry = self.engine.dry_run(steps) if hasattr(self.engine, "dry_run") else {"steps": steps}
        self._log("preview", {"engine": engine_name, "n_steps": len(steps)})
        return {"engine": engine_name, "n_steps": len(steps), "steps": steps, **dry}

    def commit(self, plan: Plan, engine_name: str, *, preview_result: dict[str, Any] | None = None) -> dict[str, Any]:
        steps = (preview_result or {}).get("steps") or compile_plan(plan, engine_name)
        t0 = time.perf_counter()
        self._log("commit_start", {"engine": engine_name, "n_steps": len(steps)})
        try:
            result = self.engine.execute(steps)
        except AecError as e:
            self._log("commit_failed", {"engine": engine_name, "error": e.to_dict()})
            # 引擎内部已回滚（revit 桥事务 / acad 文件边界）；这里只补审计
            raise
        except Exception as e:  # noqa: BLE001 - 统一收口
            raise AecError.wrap(e, ErrorCode.E_INTERNAL, f"{engine_name} 引擎执行失败: {e}")
        dur_ms = int((time.perf_counter() - t0) * 1000)
        self._log("commit_ok", {"engine": engine_name, "duration_ms": dur_ms})
        return {"engine": engine_name, "duration_ms": dur_ms, "result": result}

    def run(self, plan: Plan, engine_name: str, *, preview_only: bool = False) -> dict[str, Any]:
        prev = self.preview(plan, engine_name)
        if preview_only:
            return {"preview": prev, "committed": None}
        out = self.commit(plan, engine_name, preview_result=prev)
        return {"preview": prev, "committed": out}
