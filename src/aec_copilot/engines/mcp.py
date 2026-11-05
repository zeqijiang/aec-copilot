"""Generic MCP adapter for site-specific Revit/AutoCAD/SolidWorks bridges.

The adapter is intentionally configuration-driven: upstream tool names and
transaction hooks vary between MCP implementations. Live writes are rejected
unless begin/commit/rollback hooks are configured. Test on a document copy.
"""
from __future__ import annotations

import copy
import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any, Protocol

from ..errors import AECError, require
from .base import CallbackTransaction, Engine, Transaction


class MCPClient(Protocol):
    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...
    def close(self) -> None: ...


class StdioMCPClient:
    """Minimal newline-delimited JSON-RPC MCP stdio client.

    Configure ``command`` as an argument vector, never as a shell string. The
    initialize handshake follows MCP; no shell, credentials, or network is used.
    """

    def __init__(self, command: list[str], cwd: str | None = None, timeout: float = 60) -> None:
        require(bool(command), "E_ENGINE_DOWN", "MCP command is empty")
        self.timeout = timeout
        try:
            self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        except OSError as exc:
            raise AECError("E_ENGINE_DOWN", f"Cannot start MCP server: {exc}") from exc
        self._id = 0
        self._lock = threading.Lock()
        self._stderr: list[str] = []
        self._reader = threading.Thread(target=self._drain_stderr, daemon=True)
        self._reader.start()
        self._request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "aec-copilot", "version": "0.1.0"}})
        self._notify("notifications/initialized", {})

    def _drain_stderr(self) -> None:
        if self.process.stderr:
            for line in self.process.stderr:
                self._stderr.append(line.rstrip())
                del self._stderr[:-30]

    def _send(self, payload: dict[str, Any]) -> None:
        if not self.process.stdin or self.process.poll() is not None:
            raise AECError("E_ENGINE_DOWN", "MCP process is not running", stderr=self._stderr[-5:])
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        with self._lock:
            self._id += 1
            request_id = self._id
            self._send({"jsonrpc":"2.0","id":request_id,"method":method,"params":params})
            if not self.process.stdout:
                raise AECError("E_ENGINE_DOWN", "MCP stdout is unavailable")
            # This synchronous client expects one response per request and does
            # not support server-initiated requests. Use an SDK for advanced MCP.
            line = self.process.stdout.readline()
            if not line:
                raise AECError("E_ENGINE_DOWN", "MCP server closed the connection", stderr=self._stderr[-5:])
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AECError("E_ENGINE_DOWN", "MCP returned non-JSON output", output=line[:500]) from exc
            if response.get("id") != request_id:
                raise AECError("E_ENGINE_DOWN", "Unexpected MCP response ID", response=response)
            if "error" in response:
                raise AECError("E_ENGINE_DOWN", "MCP JSON-RPC error", engine_error=response["error"])
            return response.get("result")

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc":"2.0","method":method,"params":params})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return self._request("tools/call", {"name":name,"arguments":arguments})

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


class MCPTransaction(CallbackTransaction):
    pass


class MCPEngine(Engine):
    backend = "mcp"

    def __init__(self, name: str, client: MCPClient, config: dict[str, Any]) -> None:
        require(name in {"revit","acad","sw"}, "E_CONSTRAINT", "Unknown engine", engine=name)
        self.name, self.client, self.config = name, client, config
        self.tool_map: dict[str, str] = config.get("tools", {})
        self.transaction_map: dict[str, str] = config.get("transactions", {})
        self._elements: list[dict[str, Any]] = []

    @classmethod
    def from_config(cls, name: str, path: str | Path) -> "MCPEngine":
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        engine_config = config.get("engines", {}).get(name)
        require(isinstance(engine_config, dict), "E_ENGINE_DOWN", f"No MCP config for {name}", config=str(path))
        client = StdioMCPClient(engine_config["command"], engine_config.get("cwd"))
        return cls(name, client, engine_config)

    def transaction(self) -> Transaction:
        missing = [key for key in ("begin","commit","rollback") if key not in self.transaction_map]
        require(not missing, "E_ENGINE_DOWN", "Live MCP writes require native transaction hooks", missing=missing, engine=self.name)
        def invoke(key: str) -> None:
            result = self.client.call_tool(self.transaction_map[key], {"engine":self.name})
            require(not (isinstance(result,dict) and result.get("isError")), "E_ENGINE_DOWN", f"MCP transaction {key} failed", result=result)
        return MCPTransaction(lambda:invoke("begin"), lambda:invoke("commit"), lambda:invoke("rollback"))

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        require(tool_name in self.tool_map, "E_NOT_FOUND", f"No configured MCP mapping for {tool_name}", engine=self.name)
        # Copy prevents an adapter from mutating the replayable plan arguments.
        result = self.client.call_tool(self.tool_map[tool_name], copy.deepcopy(arguments))
        if isinstance(result, dict) and result.get("isError"):
            raise AECError("E_ENGINE_DOWN", "MCP tool returned an error", tool=tool_name, engine_error=result)
        return {"ok":True,"engine_result":result}

    def snapshot(self) -> list[dict[str, Any]]:
        # For semantic verification configure a read-only manifest tool. Never
        # infer live model state merely from successful write responses.
        manifest_tool = self.config.get("manifest_tool")
        require(bool(manifest_tool), "E_ENGINE_DOWN", "Live verification requires a manifest_tool returning the common element JSON schema")
        result = self.client.call_tool(manifest_tool, {"engine":self.name})
        content = result.get("content", []) if isinstance(result,dict) else []
        text = next((item.get("text") for item in content if item.get("type")=="text"), None)
        try:
            payload = json.loads(text) if text else result
            elements = payload.get("elements", payload) if isinstance(payload,dict) else payload
            require(isinstance(elements,list), "E_ENGINE_DOWN", "manifest_tool must return an element list")
            return copy.deepcopy(elements)
        except (json.JSONDecodeError, TypeError) as exc:
            raise AECError("E_ENGINE_DOWN", "Cannot decode MCP model manifest") from exc

    def capture(self, output: str | Path, *, title: str = "AEC Copilot") -> str:
        capture_tool = self.config.get("capture_tool")
        if capture_tool:
            result = self.client.call_tool(capture_tool, {"output":str(Path(output).resolve()),"format":"png"})
            require(Path(output).is_file(), "E_ENGINE_DOWN", "MCP capture tool did not create a PNG", result=result)
            return str(output)
        # Explicit fallback; image is marked as a manifest rendering, not native.
        return super().capture(output, title=f"{title} · MANIFEST RENDER")
