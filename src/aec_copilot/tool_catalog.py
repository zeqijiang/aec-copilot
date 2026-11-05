"""Single source of truth for public unified MCP tools."""
from __future__ import annotations

from typing import Any

from .models import ATOMIC_OPS


def catalog() -> list[dict[str, Any]]:
    tools=[]
    common={"type":"object","required":["id"],"properties":{"id":{"type":"string"}},"additionalProperties":True}
    for engine in ("revit","acad","sw"):
        for op in sorted(ATOMIC_OPS):
            if engine=="revit" and op in {"draw_polyline","create_part","create_assembly"}: continue
            if engine=="acad" and op!="draw_polyline": continue
            if engine=="sw" and op not in {"create_part","create_assembly"}: continue
            tools.append({"name":f"{engine}_{op}","description":f"{op.replace('_',' ')} in the {engine} engine (mm units; transaction required for writes)","inputSchema":common})
    tools.extend([
        {"name":"aec_plan","description":"Parse Chinese into validated JSON DSL without touching an engine","inputSchema":{"type":"object","required":["instruction"],"properties":{"instruction":{"type":"string"},"engine":{"enum":["revit","acad","sw"]}}}},
        {"name":"aec_execute_plan","description":"Compile and execute a validated plan atomically; preview=true never writes","inputSchema":{"type":"object","required":["plan"],"properties":{"plan":{"type":"object"},"preview":{"type":"boolean","default":True},"engine":{"enum":["revit","acad","sw"]}}}},
        {"name":"aec_run","description":"Run the bounded plan/execute/capture/verify/retry loop in the selected backend","inputSchema":{"type":"object","required":["instruction"],"properties":{"instruction":{"type":"string"},"engine":{"enum":["revit","acad","sw"]},"max_attempts":{"type":"integer","minimum":1,"maximum":3}}}},
        {"name":"aec_audit","description":"Run documented project-rule checks against a common model manifest","inputSchema":{"type":"object","required":["elements"],"properties":{"elements":{"type":"array","items":{"type":"object"}}}}},
        {"name":"aec_snapshot","description":"Read the simulation model manifest for one engine","inputSchema":{"type":"object","properties":{"engine":{"enum":["revit","acad","sw"]}}}},
    ])
    return tools
