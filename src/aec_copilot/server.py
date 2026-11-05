"""Dependency-free local HTTP API for the Next.js console and CLI clients."""
from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote,urlparse

from .audit import audit_model
from .errors import AECError
from .models import Plan
from .planner import Planner
from .reports import write_audit_reports
from .runner import Runner


def make_handler(output_root: Path):
    output_root=output_root.resolve()
    output_root.mkdir(parents=True,exist_ok=True)
    class Handler(BaseHTTPRequestHandler):
        server_version="AEC-Copilot/0.1"
        def _json(self,status: int,payload: Any) -> None:
            body=json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body)))
            origin=os.getenv("AEC_WEB_ORIGIN","http://localhost:3000")
            self.send_header("Access-Control-Allow-Origin",origin); self.send_header("Vary","Origin"); self.end_headers(); self.wfile.write(body)
        def _body(self) -> dict[str, Any]:
            try: length=int(self.headers.get("Content-Length","0"))
            except ValueError: raise AECError("E_CONSTRAINT","Invalid Content-Length")
            if length<=0 or length>1_000_000: raise AECError("E_CONSTRAINT","JSON body must be between 1 byte and 1 MB")
            try: value=json.loads(self.rfile.read(length))
            except json.JSONDecodeError as exc: raise AECError("E_CONSTRAINT","Malformed JSON") from exc
            if not isinstance(value,dict): raise AECError("E_CONSTRAINT","JSON body must be an object")
            return value
        def do_OPTIONS(self) -> None:
            self.send_response(204); self.send_header("Access-Control-Allow-Origin",os.getenv("AEC_WEB_ORIGIN","http://localhost:3000")); self.send_header("Access-Control-Allow-Headers","Content-Type"); self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS"); self.end_headers()
        def do_GET(self) -> None:
            path=unquote(urlparse(self.path).path)
            try:
                if path=="/api/health": return self._json(200,{"ok":True,"version":"0.1.0","backend":"simulation","live_engines_verified":False})
                if path.startswith("/api/runs/"):
                    run_id=path.rsplit("/",1)[-1]
                    if not run_id.replace("-","").replace("_","").isalnum(): return self._json(400,{"error":"Invalid run ID"})
                    file=output_root/run_id/"run.json"
                    if not file.is_file(): return self._json(404,{"error":"Run not found"})
                    return self._json(200,json.loads(file.read_text(encoding="utf-8")))
                if path.startswith("/artifacts/"):
                    parts=path.split("/")
                    if len(parts)!=4: return self._json(404,{"error":"Not found"})
                    _,_,run_id,filename=parts
                    allowed={"plan.json","elements.json","run.json","model-schedule.xlsx","modeling-report.pdf","attempt-1.png","attempt-2.png","attempt-3.png"}
                    if filename not in allowed or not run_id.replace("-","").isalnum(): return self._json(404,{"error":"Not found"})
                    file=(output_root/run_id/filename).resolve()
                    if output_root not in file.parents or not file.is_file(): return self._json(404,{"error":"Not found"})
                    data=file.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(filename)[0] or "application/octet-stream"); self.send_header("Content-Length",str(len(data))); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(data); return
                return self._json(404,{"error":"Not found"})
            except Exception as exc: return self._json(500,{"error":type(exc).__name__,"message":str(exc)[:500]})
        def do_POST(self) -> None:
            try:
                path=urlparse(self.path).path; body=self._body()
                if path=="/api/plan":
                    plan=Planner().parse(body.get("instruction",""),body.get("engine"))
                    from .compiler import compile_plan
                    return self._json(200,{"plan":plan.model_dump(),"calls":[c.model_dump() for c in compile_plan(plan)]})
                if path=="/api/run":
                    if body.get("backend","simulation")!="simulation":
                        return self._json(400,{"error":"Live MCP is CLI-only in this package; configure and validate docs/local-integration.md first"})
                    result=Runner(output_root=output_root,max_attempts=int(body.get("max_attempts",3))).run(body.get("instruction",""),engine=body.get("engine","revit"),backend="simulation",write_reports=body.get("write_reports",True))
                    return self._json(200 if result.status=="passed" else 422,result.model_dump())
                if path=="/api/audit":
                    elements=body.get("elements")
                    if not isinstance(elements,list): raise AECError("E_CONSTRAINT","elements must be an array")
                    report=audit_model(elements)
                    files=write_audit_reports(report,elements,output_root/"audits"/"latest") if body.get("write_reports",False) else {}
                    return self._json(200,{**report.model_dump(),"reports":files})
                return self._json(404,{"error":"Not found"})
            except AECError as exc: return self._json(400,exc.to_dict())
            except Exception as exc: return self._json(500,{"error":type(exc).__name__,"message":str(exc)[:500]})
        def log_message(self,format: str,*args: Any) -> None:
            print(f"[web-api] {self.address_string()} {format%args}")
    return Handler


def serve(host: str = "127.0.0.1",port: int = 8000,output_root: str = "runs") -> None:
    server=ThreadingHTTPServer((host,port),make_handler(Path(output_root)))
    print(f"AEC Copilot API: http://{host}:{port} (simulation; no live-engine claim)")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
