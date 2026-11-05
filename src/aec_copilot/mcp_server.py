"""Unified MCP stdio server exposing Revit, AutoCAD, and SolidWorks contracts."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .audit import audit_model
from .compiler import compile_plan
from .engines.registry import create_engine
from .engines.sim import SimulationEngine
from .errors import AECError
from .models import Plan
from .planner import Planner
from .runner import Runner
from .tool_catalog import catalog


class UnifiedMCPServer:
    def __init__(self,backend: str = "simulation",mcp_config: str | None = None,output_root: str = "runs") -> None:
        self.backend,self.mcp_config,self.output_root=backend,mcp_config,output_root
        self.engines={name:create_engine(name,backend,mcp_config) for name in ("revit","acad","sw")} if backend=="simulation" else {}
        self.tools={tool["name"]:tool for tool in catalog()}

    def _engine(self,name: str):
        if name not in self.engines: self.engines[name]=create_engine(name,self.backend,self.mcp_config)
        return self.engines[name]

    def call_tool(self,name: str,args: dict[str, Any]) -> dict[str, Any]:
        if name=="aec_plan":
            planner=Planner()
            plan=planner.parse(args["instruction"],args.get("engine"))
            return {"plan":plan.model_dump(),"token_usage":planner.last_usage}
        if name=="aec_execute_plan":
            plan=Plan.model_validate(args["plan"])
            calls=compile_plan(plan)
            if args.get("preview",True): return {"preview":True,"calls":[c.model_dump() for c in calls]}
            engine=self._engine(args.get("engine",plan.engine))
            if engine.name!=plan.engine: raise AECError("E_CONSTRAINT","Engine does not match plan")
            with engine.transaction():
                results=[engine.call(c.name,c.arguments) for c in calls]
            return {"preview":False,"engine":engine.name,"backend":engine.backend,"results":results,"elements":engine.snapshot()}
        if name=="aec_run":
            result=Runner(output_root=self.output_root,max_attempts=args.get("max_attempts",3)).run(args["instruction"],engine=args.get("engine","revit"),backend=self.backend,mcp_config=self.mcp_config)
            return result.model_dump()
        if name=="aec_audit": return audit_model(args["elements"]).model_dump()
        if name=="aec_snapshot": return {"engine":args.get("engine","revit"),"elements":self._engine(args.get("engine","revit")).snapshot()}
        for engine in ("revit","acad","sw"):
            if name.startswith(engine+"_"):
                selected=self._engine(engine)
                with selected.transaction(): result=selected.call(name,args)
                return result
        raise AECError("E_NOT_FOUND",f"Unknown tool: {name}")

    def handle(self,message: dict[str, Any]) -> dict[str, Any] | None:
        method=message.get("method")
        request_id=message.get("id")
        if method=="notifications/initialized": return None
        if request_id is None: return None
        try:
            if method=="initialize": result={"protocolVersion":message.get("params",{}).get("protocolVersion","2025-03-26"),"capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"aec-copilot","version":"0.1.0"}}
            elif method=="ping": result={}
            elif method=="tools/list": result={"tools":catalog()}
            elif method=="tools/call":
                params=message.get("params",{})
                payload=self.call_tool(params["name"],params.get("arguments",{}))
                result={"content":[{"type":"text","text":json.dumps(payload,ensure_ascii=False)}],"structuredContent":payload,"isError":False}
            else:
                return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":f"Method not found: {method}"}}
            return {"jsonrpc":"2.0","id":request_id,"result":result}
        except AECError as exc:
            if method=="tools/call": return {"jsonrpc":"2.0","id":request_id,"result":{"content":[{"type":"text","text":json.dumps(exc.to_dict(),ensure_ascii=False)}],"isError":True}}
            return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32602,"message":exc.message,"data":exc.to_dict()}}
        except Exception as exc:
            error={"code":-32603,"message":"Internal error","data":{"type":type(exc).__name__,"message":str(exc)[:500]}}
            return {"jsonrpc":"2.0","id":request_id,"error":error}

    def serve(self) -> None:
        for line in sys.stdin:
            try: message=json.loads(line)
            except json.JSONDecodeError:
                continue
            response=self.handle(message)
            if response is not None:
                sys.stdout.write(json.dumps(response,ensure_ascii=False,separators=(",",":"))+"\n")
                sys.stdout.flush()
