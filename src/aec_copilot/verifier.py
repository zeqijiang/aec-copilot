"""Deterministic semantic verification with an optional, explicitly gated VLM."""
from __future__ import annotations

import base64
import json
import math
import os
import urllib.request
from pathlib import Path
from typing import Any

from .compiler import expected_manifest
from .models import Difference, ToolCall, VerificationReport


def _equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected,(int,float)) and not isinstance(expected,bool) and isinstance(actual,(int,float)) and not isinstance(actual,bool):
        return math.isclose(float(expected),float(actual),rel_tol=1e-7,abs_tol=0.01)  # 0.01 mm tolerance
    if isinstance(expected,list) and isinstance(actual,list):
        return len(expected)==len(actual) and all(_equal(a,b) for a,b in zip(expected,actual))
    if isinstance(expected,dict) and isinstance(actual,dict):
        return all(k in actual and _equal(v,actual[k]) for k,v in expected.items())
    return expected==actual


def compare_manifest(calls: list[ToolCall], actual_elements: list[dict[str, Any]]) -> list[Difference]:
    """Compare every expected public field; never mutate expectations to match output."""
    expected=expected_manifest(calls)
    actual={e.get("id"):e for e in actual_elements if isinstance(e,dict)}
    differences=[]
    for wanted in expected:
        element_id=wanted["id"]
        found=actual.get(element_id)
        if found is None:
            differences.append(Difference(code="MISSING_ELEMENT",element_id=element_id,expected=wanted["type"],actual=None,message=f"Missing {wanted['type']} {element_id}",suggestion="Re-execute the canonical operation in a fresh transaction"))
            continue
        for key,value in wanted.items():
            if key not in found:
                differences.append(Difference(code="MISSING_FIELD",element_id=element_id,path=key,expected=value,actual=None,message=f"{element_id}.{key} is missing",suggestion="Return the common manifest schema from the engine adapter"))
            elif not _equal(value,found[key]):
                differences.append(Difference(code="VALUE_MISMATCH",element_id=element_id,path=key,expected=value,actual=found[key],message=f"{element_id}.{key} differs from the immutable request",suggestion="Rollback and re-execute the canonical operation; do not relax the requested constraint"))
    return differences


class VLMReviewer:
    """OpenAI-compatible visual reviewer.

    Advisory mode is the safe default: screenshots cannot override geometry. Set
    ``enforce=True`` only after evaluating false positives on your own dataset.
    """

    def __init__(self, *, enforce: bool = False) -> None:
        self.base=os.getenv("AEC_VLM_BASE_URL",os.getenv("AEC_LLM_BASE_URL","https://api.openai.com/v1")).rstrip("/")
        self.model=os.getenv("AEC_VLM_MODEL",os.getenv("AEC_LLM_MODEL",""))
        self.api_key=os.getenv("AEC_VLM_API_KEY",os.getenv("AEC_LLM_API_KEY",""))
        self.enforce=enforce
        self.last_usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}

    @property
    def configured(self) -> bool:
        return bool(self.model and self.api_key)

    def review(self,instruction: str,screenshot: str | Path) -> tuple[list[Difference],dict[str, Any],dict[str,int]]:
        image=base64.b64encode(Path(screenshot).read_bytes()).decode()
        prompt=("Review this model rendering against the Chinese instruction. Return JSON only: "
                '{"passed":true,"differences":[{"element_id":"optional","message":"observable difference","suggestion":"correction"}]}. '
                "Do not infer dimensions that are not visible. Deterministic geometry remains authoritative.\n"+instruction)
        body=json.dumps({"model":self.model,"temperature":0,"response_format":{"type":"json_object"},"messages":[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{image}"}}]}]}).encode()
        req=urllib.request.Request(f"{self.base}/chat/completions",data=body,headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=120) as response: payload=json.load(response)
        usage=payload.get("usage",{})
        self.last_usage={k:int(usage.get(k,0)) for k in self.last_usage}
        raw=json.loads(payload["choices"][0]["message"]["content"])
        differences=[Difference(code="VLM_OBSERVATION",element_id=d.get("element_id"),message=str(d.get("message","Visual difference")),suggestion=d.get("suggestion")) for d in raw.get("differences",[])]
        advisory={"passed":bool(raw.get("passed",not differences)),"enforce":self.enforce,"raw":raw}
        return differences,advisory,self.last_usage


def verify(calls: list[ToolCall],actual: list[dict[str, Any]], *, screenshot: str | None = None,instruction: str = "",vlm: VLMReviewer | None = None) -> VerificationReport:
    differences=compare_manifest(calls,actual)
    visual_differences=[]
    advisory=None
    if vlm and vlm.configured and screenshot:
        visual_differences,advisory,_=vlm.review(instruction,screenshot)
        if vlm.enforce: differences.extend(visual_differences)
    return VerificationReport(passed=not differences,method="deterministic+vlm" if advisory else "deterministic",differences=differences,screenshot=screenshot,vlm_advisory=advisory)
