"""Project-rule drawing/model review. Not a statutory code-compliance engine."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .models import AuditReport, Issue
from .units import distance


def audit_model(elements: list[dict[str, Any]]) -> AuditReport:
    issues: list[Issue]=[]
    by_id={}
    ids=Counter(str(e.get("id","")) for e in elements)
    for element_id,count in ids.items():
        if not element_id or count>1:
            issues.append(Issue(rule_id="AEC-ID-001",severity="error",element_id=element_id or None,message=f"Element ID is empty or duplicated ({count})",suggestion="Assign a unique stable ID to every element"))
    for e in elements:
        if isinstance(e,dict) and e.get("id"): by_id.setdefault(e["id"],e)
    for e in elements:
        eid=e.get("id")
        typ=e.get("type")
        if not eid or not re.match(r"^[A-Za-z0-9_\-\u4e00-\u9fff]+$",str(eid)):
            issues.append(Issue(rule_id="AEC-NAME-001",severity="warning",element_id=eid,message="Element ID does not follow the project naming convention",suggestion="Use letters, digits, Chinese characters, underscore or hyphen"))
        if typ=="wall":
            thickness=e.get("thickness")
            height=e.get("height")
            if not isinstance(thickness,(int,float)) or thickness<=0:
                issues.append(Issue(rule_id="AEC-WALL-001",severity="error",element_id=eid,message=f"Invalid wall thickness: {thickness}",suggestion="Set a positive thickness in millimetres"))
            elif thickness<100:
                issues.append(Issue(rule_id="AEC-WALL-002",severity="warning",element_id=eid,message=f"Wall thickness {thickness}mm is below the 100mm project review threshold",suggestion="Confirm the intended wall assembly; this is a project rule, not a universal code limit"))
            if not isinstance(height,(int,float)) or height<=0:
                issues.append(Issue(rule_id="AEC-WALL-003",severity="error",element_id=eid,message=f"Invalid wall height: {height}",suggestion="Set a positive wall height"))
            try:
                if distance(e.get("start",[]),e.get("end",[]))<=0:
                    issues.append(Issue(rule_id="AEC-GEOM-001",severity="error",element_id=eid,message="Wall has zero length",suggestion="Move the wall endpoints apart"))
            except (TypeError,ValueError):
                issues.append(Issue(rule_id="AEC-GEOM-002",severity="error",element_id=eid,message="Wall endpoint coordinates are malformed",suggestion="Provide two numeric 3D coordinates"))
        if typ in {"door","window"}:
            width,height,bottom=e.get("width"),e.get("height"),e.get("bottom",0)
            if not isinstance(width,(int,float)) or width<=0:
                issues.append(Issue(rule_id="AEC-OPEN-001",severity="error",element_id=eid,message="Opening width must be positive",suggestion="Correct the opening width"))
            if not isinstance(height,(int,float)) or height<=0:
                issues.append(Issue(rule_id="AEC-OPEN-002",severity="error",element_id=eid,message="Opening height must be positive",suggestion="Correct the opening height"))
            if typ=="door" and isinstance(height,(int,float)) and 0<height<2000:
                issues.append(Issue(rule_id="AEC-DOOR-001",severity="warning",element_id=eid,message=f"Door clear height {height}mm is below the 2000mm project review threshold",suggestion="Confirm the required clear height and applicable local standard"))
            if typ=="door" and isinstance(width,(int,float)) and 0<width<700:
                issues.append(Issue(rule_id="AEC-DOOR-002",severity="warning",element_id=eid,message=f"Door width {width}mm is below the 700mm project review threshold",suggestion="Confirm the use and egress requirements"))
            host=by_id.get(e.get("host_id"))
            if not host or host.get("type")!="wall":
                issues.append(Issue(rule_id="AEC-HOST-001",severity="error",element_id=eid,message=f"Opening host wall not found: {e.get('host_id')}",suggestion="Attach the opening to an existing wall"))
            elif all(isinstance(e.get(k),(int,float)) for k in ("width","height","bottom","offset")):
                length=distance(host.get("start",[]),host.get("end",[]))
                if e["offset"]<0 or e["offset"]+e["width"]>length:
                    issues.append(Issue(rule_id="AEC-HOST-002",severity="error",element_id=eid,message="Opening extends beyond the host wall length",suggestion="Reduce width or move the opening within the host"))
                if e["bottom"]<0 or e["bottom"]+e["height"]>host.get("height",0):
                    issues.append(Issue(rule_id="AEC-HOST-003",severity="error",element_id=eid,message="Opening extends beyond the host wall height",suggestion="Reduce height or adjust sill/bottom elevation"))
        if typ=="column":
            for field in ("width","depth","height"):
                if not isinstance(e.get(field),(int,float)) or e[field]<=0:
                    issues.append(Issue(rule_id=f"AEC-COL-{field.upper()}",severity="error",element_id=eid,message=f"Column {field} must be positive",suggestion=f"Set a positive {field} in millimetres"))
        if typ=="slab" and (not isinstance(e.get("thickness"),(int,float)) or e["thickness"]<=0):
            issues.append(Issue(rule_id="AEC-SLAB-001",severity="error",element_id=eid,message="Slab thickness must be positive",suggestion="Set a positive slab thickness"))
        if typ=="grid" and not e.get("name"):
            issues.append(Issue(rule_id="AEC-GRID-001",severity="warning",element_id=eid,message="Grid has no display name",suggestion="Assign a unique grid name"))
    levels=sorted((e for e in elements if e.get("type")=="level"),key=lambda e:e.get("elevation",0))
    elevations=[e.get("elevation") for e in levels]
    if len(elevations)!=len(set(elevations)):
        issues.append(Issue(rule_id="AEC-LEVEL-001",severity="error",message="Multiple levels share the same elevation",suggestion="Remove duplicate levels or correct their elevations"))
    for level in levels:
        if not level.get("name"):
            issues.append(Issue(rule_id="AEC-LEVEL-002",severity="warning",element_id=level.get("id"),message="Level has no name",suggestion="Assign a readable level name"))
    grid_names=[e.get("name") for e in elements if e.get("type")=="grid" and e.get("name")]
    duplicates=[name for name,count in Counter(grid_names).items() if count>1]
    if duplicates:
        issues.append(Issue(rule_id="AEC-GRID-002",severity="error",message=f"Duplicate grid names: {', '.join(duplicates)}",suggestion="Make grid names unique within the model"))
    return AuditReport(issue_count=len(issues),issues=issues)
