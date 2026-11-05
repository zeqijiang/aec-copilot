"""Export one diverse successful plan per category into the local few-shot index."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from aec_copilot.models import Plan
from aec_copilot.planner import Planner


def main() -> None:
    seen=set(); records=[]
    for path in sorted((ROOT/"eval"/"cases").glob("*.json")):
        case=json.loads(path.read_text(encoding="utf-8"))
        if case["category"] in seen: continue
        plan=Plan.model_validate(case["plan"]) if case.get("plan") else Planner().parse(case["instruction"],case.get("engine"))
        records.append({"id":case["id"],"instruction":case["instruction"],"plan":plan.model_dump(),"source":"eval/cases; simulation-verified"})
        seen.add(case["category"])
    output=ROOT/"knowledge"/"successful_plans.jsonl"
    output.parent.mkdir(exist_ok=True)
    output.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in records),encoding="utf-8")
    print(f"Exported {len(records)} diverse plans to {output}")


if __name__=="__main__": main()
