"""Run reproducible simulation benchmarks; never label these as live CAD results."""
from __future__ import annotations

import copy
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"src") not in sys.path: sys.path.insert(0,str(ROOT/"src"))

from aec_copilot.audit import audit_model
from aec_copilot.compiler import compile_plan,expected_manifest
from aec_copilot.engines.sim import SimulationEngine
from aec_copilot.models import Plan
from aec_copilot.planner import Planner
from aec_copilot.reports import write_eval_reports
from aec_copilot.runner import Runner


class SilentOmissionEngine(SimulationEngine):
    """Test double: silently omits the first wall, then behaves normally."""
    def __init__(self,failures: int = 1) -> None:
        super().__init__("revit"); self.remaining=failures; self.calls=0
    def call(self,tool_name,arguments):
        self.calls+=1
        if self.remaining>0 and tool_name=="revit_create_wall":
            self.remaining-=1
            return {"ok":True,"element":{"id":arguments["id"],"omitted":True}}
        return super().call(tool_name,arguments)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run_all(output: Path | str = ROOT/"eval"/"results") -> dict:
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    rows=[]
    golden_dir=ROOT/"eval"/"golden"; golden_dir.mkdir(exist_ok=True)
    started=time.perf_counter()
    for path in sorted((ROOT/"eval"/"cases").glob("*.json")):
        case=load(path)
        plan=Plan.model_validate(case["plan"]) if case.get("plan") else Planner().parse(case["instruction"],case.get("engine"))
        calls=compile_plan(plan)
        golden=expected_manifest(calls)
        (golden_dir/f"{case['id']}.json").write_text(json.dumps(golden,ensure_ascii=False,indent=2),encoding="utf-8")
        case_start=time.perf_counter()
        result=Runner(SimulationEngine(plan.engine),output_root=output/"runs").run(plan,write_reports=False,max_attempts=3)
        elapsed=(time.perf_counter()-case_start)*1000
        counts=dict(Counter(e["type"] for e in golden))
        rows.append({"case_id":case["id"],"category":case["category"],"status":result.status,"first_pass":result.attempts[0].status=="passed","converged_within_3":result.status=="passed","attempts":len(result.attempts),"elements":len(result.elements),"expected_counts":counts,"elapsed_ms":round(elapsed,3),"token_usage":sum(a.token_usage.get("total_tokens",0) for a in result.attempts),"run_id":result.run_id})
    first=sum(r["first_pass"] for r in rows); converged=sum(r["converged_within_3"] for r in rows)
    # Independent deterministic replay check: new engine, same canonical plan.
    sample=load(ROOT/"eval"/"cases"/"01_wall.json")
    plan=Planner().parse(sample["instruction"])
    replay_a=Runner(SimulationEngine("revit"),output_root=output/"replay").run(plan,write_reports=False)
    replay_b=Runner(SimulationEngine("revit"),output_root=output/"replay").run(plan,write_reports=False)
    deterministic=replay_a.status==replay_b.status=="passed" and replay_a.elements==replay_b.elements
    recovery=[]
    for failures in (1,2,3):
        engine=SilentOmissionEngine(failures)
        result=Runner(engine,output_root=output/"recovery").run("在0,0画一面6m长的墙",write_reports=False,max_attempts=3)
        recovery.append({"injected_failures":failures,"status":result.status,"attempts":len(result.attempts),"rolled_back":sum(a.status=="rolled_back" for a in result.attempts),"clean_after_final_failure":len(engine.snapshot())==0 if result.status=="failed" else None})
    audit_rows=[]
    for path in sorted((ROOT/"eval"/"audit_cases").glob("*.json")):
        case=load(path); report=audit_model(case["elements"]); found={i.rule_id for i in report.issues}
        expected=set(case["seeded_rules"]); audit_rows.append({"case_id":case["id"],"expected_rules":sorted(expected),"found_rules":sorted(found),"detected":expected<=found,"issue_count":report.issue_count})
    audit_hits=sum(r["detected"] for r in audit_rows)
    summary={"backend":"simulation","modeling_cases":len(rows),"first_pass_cases":first,"first_pass_rate":round(first/len(rows),4) if rows else 0,"converged_cases":converged,"three_attempt_convergence_rate":round(converged/len(rows),4) if rows else 0,"audit_cases":len(audit_rows),"audit_hit_cases":audit_hits,"audit_hit_rate":round(audit_hits/len(audit_rows),4) if audit_rows else 0,"average_end_to_end_ms":round(sum(r["elapsed_ms"] for r in rows)/len(rows),3) if rows else 0,"deterministic_replay":deterministic,"reported_llm_tokens":sum(r["token_usage"] for r in rows),"recovery_tests":recovery,"total_evaluation_ms":round((time.perf_counter()-started)*1000,3),"scope":"Synthetic fixtures on the deterministic simulation engine. No live Revit/AutoCAD/SolidWorks validation. Audit thresholds are project rules, not statutory compliance."}
    reports=write_eval_reports(summary,rows,output)
    (output/"audit-results.json").write_text(json.dumps({"summary":{"cases":len(audit_rows),"hits":audit_hits,"hit_rate":summary["audit_hit_rate"]},"rows":audit_rows},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"summary":summary,"reports":reports},ensure_ascii=False,indent=2))
    return summary


if __name__=="__main__":
    run_all(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"eval"/"results")
