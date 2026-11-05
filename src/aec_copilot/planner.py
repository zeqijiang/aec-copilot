"""Hybrid Chinese planner: deterministic parser first, optional constrained LLM fallback."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from .errors import AECError
from .models import Plan

NUM = r"([-+]?\d+(?:\.\d+)?)"
UNIT = r"(mm|cm|m|毫米|厘米|米)?"
DIM = rf"\s*{NUM}\s*{UNIT}"
PAIR = re.compile(rf"{DIM}\s*[×xX*]\s*{DIM}")
CN_NUM = {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}


def _length(number: str, unit: str | None, default: str = "m") -> str:
    return f"{number}{unit or default}"


def _pair(text: str, default: str = "m") -> tuple[str,str] | None:
    match = PAIR.search(text)
    if not match:
        return None
    return _length(match.group(1),match.group(2),default),_length(match.group(3),match.group(4),default)


def _field(text: str, labels: str, default_unit: str = "m") -> str | None:
    match = re.search(rf"(?:{labels})\s*(?:为|是|：|:)?\s*{DIM}",text,re.IGNORECASE)
    return _length(match.group(1),match.group(2),default_unit) if match else None


def _floors(text: str) -> int:
    match = re.search(r"([一二两三四五六七八九十\d]+)\s*层",text)
    if not match: return 2
    token = match.group(1)
    return int(token) if token.isdigit() else CN_NUM.get(token,2)


class Planner:
    def __init__(self) -> None:
        self.last_usage = {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}

    def parse(self, instruction: str, engine: str | None = None, use_llm: bool = True) -> Plan:
        self.last_usage = {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
        try:
            return self._deterministic(instruction,engine)
        except AECError:
            if use_llm and os.getenv("AEC_LLM_API_KEY") and os.getenv("AEC_LLM_MODEL"):
                return self._llm(instruction,engine or "revit")
            raise

    def _deterministic(self, instruction: str, engine: str | None = None) -> Plan:
        text = re.sub(r"\s+"," ",instruction.strip())
        if not text: raise AECError("E_CONSTRAINT","Instruction is empty")
        selected = engine or ("sw" if re.search(r"solidworks|零件|装配",text,re.I) else "acad" if re.search(r"autocad|多段线|二维图",text,re.I) else "revit")
        if selected == "sw": return self._sw(text)
        if selected == "acad": return self._acad(text)
        if re.search(r"框架|排柱|柱网",text): return self._frame(text)
        if re.search(r"一栋|小楼|建筑物|两层|多层",text): return self._building(text)
        if "房间" in text: return self._room(text)
        # Standalone Revit elements are explicit; no vague instruction is guessed.
        if "多段线" in text: return self._acad(text)
        if re.search(r"墙",text):
            pair = _pair(text,"mm")
            length = _field(text,"长|长度","mm")
            if not length and pair: length = pair[0]
            if not length:
                match = re.search(rf"{DIM}\s*长",text)
                if match: length = _length(match.group(1),match.group(2),"mm")
            if not length: raise AECError("E_CONSTRAINT","Wall instruction needs an explicit length, e.g. 6m长")
            start = [0,0,0]
            origin = re.search(rf"(?:在|起点)\s*{NUM}\s*[,，]\s*{NUM}",text)
            if origin: start = [float(origin.group(1))*1000,float(origin.group(2))*1000,0]
            # Standalone dimensions use the common mm convention; 6m remains explicit.
            length_mm = self._to_mm(length)
            end = [start[0]+length_mm,start[1],start[2]]
            ops: list[dict[str,Any]] = [{"op":"create_wall","id":"wall_1","start":start,"end":end,"height":_field(text,"层高|高度|高","m") or "3.6m","thickness":_field(text,"墙厚|外墙|厚度|厚","mm") or "200mm"}]
            return Plan(instruction=instruction,engine="revit",operations=ops,metadata={"planner":"deterministic"})
        if "楼板" in text or "板" == text:
            pair = _pair(text,"m")
            if not pair: raise AECError("E_CONSTRAINT","Slab needs width × depth")
            w,d = (self._to_mm(v) for v in pair)
            elevation = self._to_mm(_field(text,"标高","m") or "0m")
            return Plan(instruction=instruction,engine="revit",operations=[{"op":"create_slab","id":"slab_1","boundary":[[0,0,elevation],[w,0,elevation],[w,d,elevation],[0,d,elevation]],"elevation":elevation,"thickness":_field(text,"板厚|厚度|厚","mm") or "120mm"}],metadata={"planner":"deterministic"})
        if "柱" in text:
            pair = _pair(text,"mm")
            w,d = (self._to_mm(v) for v in pair) if pair else (400,400)
            height = self._to_mm(_field(text,"高度|高","m") or "3.6m")
            return Plan(instruction=instruction,engine="revit",operations=[{"op":"create_column","id":"column_1","center":[0,0,0],"width":w,"depth":d,"height":height}],metadata={"planner":"deterministic"})
        if "标高" in text:
            values = re.findall(rf"{DIM}",text)
            elevations = [self._to_mm(_length(m[0],m[1],"m")) for m in values]
            if not elevations: raise AECError("E_CONSTRAINT","Level needs an elevation")
            return Plan(instruction=instruction,engine="revit",operations=[{"op":"create_level","id":f"level_{i+1}","name":f"L{i+1}","elevation":z} for i,z in enumerate(elevations)],metadata={"planner":"deterministic"})
        raise AECError("E_CONSTRAINT","Cannot parse instruction deterministically. Use a supported example or configure the constrained LLM fallback.",instruction=instruction)

    @staticmethod
    def _to_mm(value: str) -> float:
        from .units import mm
        return mm(value)

    def _room(self,text: str) -> Plan:
        pair = _pair(text,"m")
        if not pair: raise AECError("E_CONSTRAINT","Room needs width × depth, e.g. 6m×4m")
        op: dict[str,Any] = {"op":"create_room","id":"room","width":pair[0],"depth":pair[1],"height":_field(text,"层高|高度|高","m") or "3.6m","thickness":_field(text,"墙厚|外墙|厚度|厚","mm") or "200mm","include_slab":"楼板" in text}
        ops = [op]
        ops.extend(self._openings(text,"room"))
        return Plan(instruction=text,engine="revit",operations=ops,metadata={"planner":"deterministic"})

    def _frame(self,text: str) -> Plan:
        pair = _pair(text,"m")
        if not pair: raise AECError("E_CONSTRAINT","Frame needs width × depth")
        op = {"op":"create_frame","id":"frame","width":pair[0],"depth":pair[1],"height":_field(text,"层高|高度|高","m") or "3.6m","column_size":_field(text,"柱宽|柱尺寸","mm") or "400mm","include_slab":"无楼板" not in text}
        return Plan(instruction=text,engine="revit",operations=[op],metadata={"planner":"deterministic"})

    def _building(self,text: str) -> Plan:
        pair = _pair(text,"m")
        if not pair: raise AECError("E_CONSTRAINT","Building needs width × depth")
        op: dict[str,Any] = {"op":"create_building","id":"building","width":pair[0],"depth":pair[1],"floors":_floors(text),"floor_height":_field(text,"层高","m") or "3.6m","wall_thickness":_field(text,"外墙|墙厚|厚度","mm") or "200mm","partition":bool(re.search("隔墙|隔断",text)),"corner_columns":bool(re.search("角.*柱|四角.*柱|放柱|加柱",text)),"include_grids":"无轴网" not in text,"entrance_door":"门" in text and not re.search(r"[东南西北]墙[^。；;]*门",text)}
        if _field(text,"柱宽|柱尺寸","mm"): op["column_size"] = _field(text,"柱宽|柱尺寸","mm")
        ops = [op]
        ops.extend(self._openings(text,"building_f1"))
        return Plan(instruction=text,engine="revit",operations=ops,metadata={"planner":"deterministic"})

    def _openings(self,text: str,prefix: str) -> list[dict[str,Any]]:
        ops=[]
        directions={"南":"s","东":"e","北":"n","西":"w"}
        for cn,label in directions.items():
            host=f"{prefix}_wall_{label}"
            door=re.search(rf"{cn}墙[^。；;]*?{DIM}\s*(?:宽)?[^。；;]*?门",text)
            if door:
                width=_length(door.group(1),door.group(2),"mm")
                height=_field(door.group(0),"高度|高","mm") or "2100mm"
                ops.append({"op":"create_door","id":f"door_{label}","host_id":host,"width":width,"height":height,"bottom":0})
            window=re.search(rf"{cn}墙[^。；;]*?{DIM}\s*[×xX*]\s*{DIM}[^。；;]*?窗",text)
            if window:
                ops.append({"op":"create_window","id":f"window_{label}","host_id":host,"width":_length(window.group(1),window.group(2),"mm"),"height":_length(window.group(3),window.group(4),"mm"),"bottom":_field(window.group(0),"窗台|底高","mm") or "900mm"})
        return ops

    def _acad(self,text: str) -> Plan:
        # "在AutoCAD中绘制(0,0),(6000,0),(6000,4000)的闭合多段线"
        coords = [match.group(0) for match in re.finditer(rf"[（(]\s*{NUM}\s*[,，]\s*{NUM}(?:\s*[,，]\s*{NUM})?\s*[)）]",text)]
        points=[[float(v) for v in re.findall(NUM,c)] for c in coords]
        if len(points)>=2:
            return Plan(instruction=text,engine="acad",operations=[{"op":"draw_polyline","id":"polyline_1","points":points,"closed":"闭合" in text}],metadata={"planner":"deterministic"})
        pair=_pair(text,"mm")
        if pair and "矩形" in text:
            w,d=(self._to_mm(v) for v in pair)
            return Plan(instruction=text,engine="acad",operations=[{"op":"draw_polyline","id":"rectangle_1","points":[[0,0,0],[w,0,0],[w,d,0],[0,d,0]],"closed":True}],metadata={"planner":"deterministic"})
        raise AECError("E_CONSTRAINT","AutoCAD demo supports a rectangle or explicit coordinate polyline")

    def _sw(self,text: str) -> Plan:
        ids=re.findall(r"[A-Za-z][A-Za-z0-9_\-]+",text)
        if "装配" in text:
            parts=[v for v in ids if v.lower() not in {"solidworks","m","mm","cm"}]
            if len(parts)<1: raise AECError("E_CONSTRAINT","Assembly instruction needs part IDs, e.g. 将p1和p2创建装配体")
            return Plan(instruction=text,engine="sw",operations=[{"op":"create_assembly","id":"assembly_1","parts":parts}],metadata={"planner":"deterministic"})
        pair=_pair(text,"mm")
        triple=re.search(rf"{DIM}\s*[×xX*]\s*{DIM}\s*[×xX*]\s*{DIM}",text)
        if triple:
            shape="box"; size=[_length(triple.group(i),triple.group(i+1),"mm") for i in (1,3,5)]
            op={"op":"create_part","id":"part_1","shape":shape,"width":size[0],"depth":size[1],"height":size[2]}
        elif pair and "圆柱" in text:
            op={"op":"create_part","id":"part_1","shape":"cylinder","diameter":pair[0],"height":_field(text,"高度|高","mm") or pair[1]}
        else: raise AECError("E_CONSTRAINT","Part needs 100mm×50mm×20mm or 圆柱直径×高度")
        return Plan(instruction=text,engine="sw",operations=[op],metadata={"planner":"deterministic"})

    def _llm(self,instruction: str,engine: str) -> Plan:
        """OpenAI-compatible JSON fallback. The returned plan is never executed raw."""
        base=os.getenv("AEC_LLM_BASE_URL","https://api.openai.com/v1").rstrip("/")
        schema_hint='{"schema_version":"1.0","instruction":"...","engine":"revit","units":"mm","operations":[{"op":"create_room","id":"room","width":"6m","depth":"4m","height":"3.6m","thickness":200}]}'
        prompt=("Translate the Chinese AEC instruction into the constrained JSON modeling DSL. "
                "Return JSON only. Never invent API calls. Allowed intent ops: create_building/create_room/create_frame; "
                "atomic ops: create_level/create_grid/create_wall/create_column/create_slab/create_door/create_window. "
                f"Schema example: {schema_hint}\nInstruction: {instruction}")
        body=json.dumps({"model":os.environ["AEC_LLM_MODEL"],"messages":[{"role":"system","content":"You output only validated AEC modeling DSL JSON."},{"role":"user","content":prompt}],"temperature":0,"response_format":{"type":"json_object"}}).encode()
        request=urllib.request.Request(f"{base}/chat/completions",data=body,headers={"Authorization":f"Bearer {os.environ['AEC_LLM_API_KEY']}","Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(request,timeout=90) as response: payload=json.load(response)
        except Exception as exc: raise AECError("E_ENGINE_DOWN",f"LLM planner request failed: {type(exc).__name__}") from exc
        usage=payload.get("usage",{})
        self.last_usage={k:int(usage.get(k,0)) for k in ("prompt_tokens","completion_tokens","total_tokens")}
        try:
            content=payload["choices"][0]["message"]["content"]
            data=json.loads(content)
            data.update({"instruction":instruction,"engine":engine,"units":"mm","schema_version":"1.0"})
            data["metadata"]={**data.get("metadata",{}),"planner":"llm-constrained"}
            return Plan.model_validate(data)
        except Exception as exc: raise AECError("E_CONSTRAINT","LLM returned an invalid modeling plan",detail=str(exc)[:500]) from exc
