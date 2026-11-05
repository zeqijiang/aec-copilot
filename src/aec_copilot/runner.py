"""Planner -> compiler -> transaction -> capture -> verify -> bounded retry."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .compiler import compile_plan
from .engines.base import Engine
from .engines.registry import create_engine
from .errors import AECError
from .models import AttemptRecord, Difference, Plan, RunResult, VerificationReport, expect_rollback_safe
from .planner import Planner
from .reports import write_run_reports
from .verifier import VLMReviewer, verify


class Runner:
    def __init__(self,engine: Engine | None = None,*, output_root: str | Path = "runs",planner: Planner | None = None,vlm: VLMReviewer | None = None,max_attempts: int = 3) -> None:
        self.engine=engine
        self.output_root=Path(output_root)
        self.planner=planner or Planner()
        self.vlm=vlm
        self.max_attempts=max(1,min(max_attempts,3))

    def preview(self,instruction: str,*,engine: str = "revit",use_llm: bool = True) -> tuple[Plan,list[dict[str, Any]]]:
        plan=self.planner.parse(instruction,engine,use_llm)
        calls=compile_plan(plan)
        return plan,[{"name":c.name,"arguments":c.arguments} for c in calls]

    def run(self,instruction: str | Plan,*,engine: str = "revit",backend: str = "simulation",mcp_config: str | None = None,max_attempts: int | None = None,write_reports: bool = True) -> RunResult:
        if isinstance(instruction,Plan):
            plan=instruction
            usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
        else:
            plan=self.planner.parse(instruction,engine,use_llm=True)
            usage=dict(self.planner.last_usage)
        calls=compile_plan(plan)
        selected=self.engine or create_engine(plan.engine,backend,mcp_config)
        if selected.name!=plan.engine: raise AECError("E_CONSTRAINT",f"Runner engine {selected.name} does not match plan engine {plan.engine}")
        run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+hashlib.sha256((plan.instruction+uuid.uuid4().hex).encode()).hexdigest()[:8]
        output=self.output_root/run_id
        output.mkdir(parents=True,exist_ok=False)
        attempts=[]
        last_elements=[]
        screenshot=None
        limit=max_attempts or self.max_attempts
        limit=max(1,min(limit,3))
        status="failed"
        for attempt in range(1,limit+1):
            started=time.perf_counter()
            report=None
            vlm_usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
            tx=selected.transaction()
            try:
                with tx:
                    for call in calls: selected.call(call.name,call.arguments)
                    last_elements=selected.snapshot()
                    screenshot=selected.capture(output/f"attempt-{attempt}.png",title="AEC Copilot")
                    report=verify(calls,last_elements,screenshot=screenshot,instruction=plan.instruction,vlm=self.vlm)
                    if self.vlm and self.vlm.configured:
                        vlm_usage=dict(self.vlm.last_usage)
                    if not report.passed:
                        # Raising triggers __exit__ rollback; requirements stay immutable.
                        raise _VerificationFailed(report)
                status="passed"
                attempt_usage={key:(usage.get(key,0) if attempt==1 else 0)+vlm_usage.get(key,0) for key in usage}
                attempts.append(AttemptRecord(attempt=attempt,status="passed",elapsed_ms=(time.perf_counter()-started)*1000,verification=report,token_usage=attempt_usage))
                break
            except Exception as exc:
                if isinstance(exc,_VerificationFailed):
                    report=exc.report
                    error=None
                else:
                    error=expect_rollback_safe(exc)
                    report=VerificationReport(passed=False,differences=[Difference(code=error.code,message=error.message,suggestion="Check the adapter and retry in a clean transaction")],screenshot=screenshot)
                attempt_usage={key:(usage.get(key,0) if attempt==1 else 0)+vlm_usage.get(key,0) for key in usage}
                attempts.append(AttemptRecord(attempt=attempt,status="failed" if attempt==limit else "rolled_back",elapsed_ms=(time.perf_counter()-started)*1000,verification=report,token_usage=attempt_usage))
                # Keep structured diagnostics in the plan without weakening it.
                plan.metadata.setdefault("repair_history",[]).append({"attempt":attempt,"difference_codes":[d.code for d in report.differences],"action":"rollback_and_reexecute_canonical_dsl"})
                if error and error.code in {"E_UNIT","E_GEOM","E_CONSTRAINT","E_NOT_FOUND"}:
                    break
        # A failed attempt was rolled back. Do not return its discarded elements
        # as if they were the final model; preserve diagnostics in attempts instead.
        final_elements=last_elements if status=="passed" else []
        result=RunResult(run_id=run_id,status=status,backend=selected.backend,engine=selected.name,instruction=plan.instruction,plan=plan,attempts=attempts,elements=final_elements,output_dir=str(output),screenshot=screenshot)
        (output/"plan.json").write_text(plan.model_dump_json(indent=2),encoding="utf-8")
        (output/"elements.json").write_text(json.dumps(final_elements,ensure_ascii=False,indent=2),encoding="utf-8")
        (output/"run.json").write_text(result.model_dump_json(indent=2),encoding="utf-8")
        if write_reports:
            result.reports=write_run_reports(result,output)
            (output/"run.json").write_text(result.model_dump_json(indent=2),encoding="utf-8")
        return result


class _VerificationFailed(Exception):
    def __init__(self,report: VerificationReport) -> None:
        self.report=report
