from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import audit_model
from .compiler import compile_plan
from .engines.registry import create_engine
from .errors import AECError
from .models import Plan
from .planner import Planner
from .reports import write_audit_reports
from .runner import Runner
from .tool_catalog import catalog


def _plan_file(path: str) -> Plan:
    return Plan.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="aec",description="AI 建筑师 Copilot / 蓝图智匠")
    parser.add_argument("--version",action="version",version=__version__)
    sub=parser.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run",help="中文指令 → DSL → 执行 → 截图 → 校验 → 重试")
    run.add_argument("instruction",nargs="?",help="Chinese modeling instruction")
    run.add_argument("--plan",help="Execute a validated plan JSON instead of parsing text")
    run.add_argument("--engine",choices=["revit","acad","sw"],default="revit")
    run.add_argument("--backend",choices=["simulation","mcp"],default="simulation")
    run.add_argument("--mcp-config",help="Site-specific live MCP mapping JSON")
    run.add_argument("--attempts",type=int,default=3,choices=[1,2,3])
    run.add_argument("--output",default="runs")
    preview=sub.add_parser("preview",help="只生成计划和原子调用，不写模型")
    preview.add_argument("instruction")
    preview.add_argument("--engine",choices=["revit","acad","sw"],default="revit")
    audit=sub.add_parser("audit",help="对通用模型清单 JSON 执行项目规则审图")
    audit.add_argument("model",help="Element list JSON, or an object containing elements")
    audit.add_argument("--output",default="runs/audit")
    serve=sub.add_parser("serve",help="本地 Web API（默认模拟引擎）")
    serve.add_argument("--host",default="127.0.0.1")
    serve.add_argument("--port",type=int,default=8000)
    serve.add_argument("--output",default="runs")
    mcp=sub.add_parser("mcp",help="启动统一 MCP stdio server")
    mcp.add_argument("--backend",choices=["simulation","mcp"],default="simulation")
    mcp.add_argument("--mcp-config")
    mcp.add_argument("--output",default="runs")
    sub.add_parser("tools",help="输出统一工具目录 JSON")
    evaluate=sub.add_parser("eval",help="运行建模和审图基准（模拟引擎）")
    evaluate.add_argument("--output",default="eval/results")
    return parser


def main(argv: list[str] | None = None) -> int:
    args=build_parser().parse_args(argv)
    try:
        if args.command=="run":
            if not args.instruction and not args.plan: raise AECError("E_CONSTRAINT","Provide an instruction or --plan")
            source=_plan_file(args.plan) if args.plan else args.instruction
            result=Runner(output_root=args.output,max_attempts=args.attempts).run(source,engine=args.engine,backend=args.backend,mcp_config=args.mcp_config)
            print(json.dumps({"run_id":result.run_id,"status":result.status,"backend":result.backend,"elements":len(result.elements),"attempts":len(result.attempts),"output_dir":result.output_dir,"reports":result.reports},ensure_ascii=False,indent=2))
            return 0 if result.status=="passed" else 2
        if args.command=="preview":
            plan=Planner().parse(args.instruction,args.engine)
            print(json.dumps({"plan":plan.model_dump(),"calls":[c.model_dump() for c in compile_plan(plan)]},ensure_ascii=False,indent=2)); return 0
        if args.command=="audit":
            data=json.loads(Path(args.model).read_text(encoding="utf-8")); elements=data.get("elements") if isinstance(data,dict) else data
            if not isinstance(elements,list): raise AECError("E_CONSTRAINT","Model JSON must be an element list or contain elements")
            report=audit_model(elements); files=write_audit_reports(report,elements,args.output)
            print(json.dumps({"issue_count":report.issue_count,"reports":files,"disclaimer":report.disclaimer},ensure_ascii=False,indent=2)); return 1 if any(i.severity=="error" for i in report.issues) else 0
        if args.command=="serve":
            from .server import serve
            serve(args.host,args.port,args.output); return 0
        if args.command=="mcp":
            from .mcp_server import UnifiedMCPServer
            UnifiedMCPServer(args.backend,args.mcp_config,args.output).serve(); return 0
        if args.command=="tools": print(json.dumps(catalog(),ensure_ascii=False,indent=2)); return 0
        if args.command=="eval":
            from eval.run_eval import run_all
            summary=run_all(Path(args.output)); print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0
    except (AECError,ValueError,FileNotFoundError,json.JSONDecodeError) as exc:
        payload=exc.to_dict() if isinstance(exc,AECError) else {"ok":False,"error":{"code":"E_CONSTRAINT","message":str(exc)}}
        print(json.dumps(payload,ensure_ascii=False,indent=2),file=sys.stderr); return 2
    return 0

if __name__=="__main__": raise SystemExit(main())
