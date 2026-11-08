"""造价引擎：真模型工程量 → GB50500 清单映射 → 组价 → 费用分析 → 报告。

设计：
- 工程量来自 Revit 真实构件几何（逐构件可溯源，见 mcp_full.aec_quantity）
- 清单编码对齐 GB50854-2013《房屋建筑与装饰工程工程量计算规范》常用项
- 单价默认用演示价目表（data/price-table.demo.json，量级对标信息价）；
  支持导入真实定额（同 schema）自动替换——软件不含受版权保护的定额数据
- 措施费（模板）按接触面积计价；规费+税金按费率汇总

输出：与竞品同构的报告（项目概况/清单明细/费用结构/报告状态）+ Excel。
"""

from __future__ import annotations

import json
from pathlib import Path

# 构件 → 清单项映射（GB50854 编码，MVP 覆盖墙/板/柱/模板措施）
MAPPING = {
    "wall": {"code": "010504001", "name": "直形墙", "unit": "m³", "qty_key": "volume_m3"},
    "floor": {"code": "010505003", "name": "平板", "unit": "m³", "qty_key": "volume_m3"},
    "column": {"code": "010502001", "name": "矩形柱", "unit": "m³", "qty_key": "volume_m3"},
}
FORMWORK = {"code": "011702002", "name": "直形墙模板", "unit": "m²", "qty_key": "formwork_m2",
            "is_measure": True}  # 措施项目

DEFAULT_RATES = {"管理费利润": 0.13, "规费": 0.025, "税金": 0.09}


def load_prices(path: Path | None = None) -> dict[str, dict]:
    """价目表：{code: {"综合单价": 元, "备注": ...}}。默认演示价目。"""
    p = path or Path(__file__).resolve().parents[2] / "data" / "price-table.demo.json"
    if not Path(p).exists():
        p = Path(__file__).resolve().parents[2] / "data" / "price-table.demo.json"
    return json.loads(Path(p).read_text(encoding="utf-8"))


def estimate(quantity: dict, *, gfa: float | None = None, prices: dict[str, dict] | None = None) -> dict:
    """quantity = aec_quantity 的输出（walls/totals/floor_area…）。返回造价报告 dict。"""
    prices = prices or load_prices()
    totals = quantity.get("totals") or {}
    wall_volume = totals.get("wall_volume_m3", 0.0)
    formwork_m2 = totals.get("wall_formwork_m2", 0.0)
    floor_area_m2 = totals.get("floor_area_m2", 0.0)
    floors = max(int(totals.get("floors_count") or 1), 1)
    gfa = float(gfa or quantity.get("gfa") or 0) or floor_area_m2

    items: list[dict] = []

    def add(code: str, name: str, unit: str, qty: float, *, measure: bool = False, note: str = ""):
        price_row = prices.get(code) or {}
        unit_price = float(price_row.get("综合单价", 0))
        amount = round(qty * unit_price, 2)
        items.append({"编码": code, "名称": name, "单位": unit,
                      "工程量": round(qty, 2), "综合单价": unit_price, "合价": amount,
                      "类别": "措施项目" if measure else "分部分项", "备注": note or price_row.get("备注", "")})

    # 分部分项：墙（直形墙混凝土）、板（平板混凝土，板厚按 120mm 演示假设）
    wall = MAPPING["wall"]
    add(wall["code"], wall["name"], wall["unit"], wall_volume, note="真模型墙体逐构件汇总")
    slab_volume = floor_area_m2 * 0.12 / max(floors, 1) * floors  # 每层板厚 120mm 演示
    slab_volume = floor_area_m2 * 0.12  # 全部楼板合计（含多层板面积已含）
    add(MAPPING["floor"]["code"], MAPPING["floor"]["name"], MAPPING["floor"]["unit"], round(slab_volume, 2),
        note="板厚 120mm 演示假设（板参数读取为 M3 扩展）")
    # 措施：模板
    add(FORMWORK["code"], FORMWORK["name"], FORMWORK["unit"], formwork_m2, measure=True, note="两侧大面+顶面")

    sub_total = round(sum(i["合价"] for i in items if i["类别"] == "分部分项"), 2)
    measure_total = round(sum(i["合价"] for i in items if i["类别"] == "措施项目"), 2)
    fee_base = sub_total + measure_total
    mgmt = round(fee_base * DEFAULT_RATES["管理费利润"], 2)
    statutory = round((fee_base + mgmt) * DEFAULT_RATES["规费"], 2)
    tax = round((fee_base + mgmt + statutory) * DEFAULT_RATES["税金"], 2)
    total = round(fee_base + mgmt + statutory + tax, 2)

    structure = {}
    for i in items:
        structure[i["类别"]] = round(structure.get(i["类别"], 0) + i["合价"], 2)
    structure_pct = {k: f"{v / total * 100:.1f}%" for k, v in structure.items()} if total else {}

    return {
        "项目概况": {"建筑面积_m2": round(gfa, 1) if gfa else None, "楼层数": floors,
                     "数据来源": "Revit 真实构件几何（逐构件可溯源）"},
        "清单明细": items,
        "汇总": {"分部分项": sub_total, "措施项目": measure_total, "管理费利润": mgmt,
                 "规费": statutory, "税金": tax, "总造价": total},
        "费用结构": structure_pct,
        "报告状态": {"清单项": len(items), "价目表": "演示价目（导入真实定额自动替换）",
                     "工程量来源": "真模型几何推算，逐构件可溯源"},
        "免责声明": "演示用途：综合单价为演示数据，不构成计价依据；导入真实定额后结果方可用于参考估算。",
    }


def to_markdown(report: dict) -> str:
    lines = ["# 工程计价报告（真模型工程量）", ""]
    g = report["项目概况"]
    lines += [f"- 建筑面积：{g['建筑面积_m2']} m²　楼层数：{g['楼层数']}　数据来源：{g['数据来源']}", "",
              "| 编码 | 名称 | 单位 | 工程量 | 综合单价 | 合价 | 类别 |", "|---|---|---|---|---|---|---|"]
    for i in report["清单明细"]:
        lines.append(f"| {i['编码']} | {i['名称']} | {i['单位']} | {i['工程量']} | {i['综合单价']} | {i['合价']} | {i['类别']} |")
    s = report["汇总"]
    lines += ["", f"**分部分项 {s['分部分项']} + 措施 {s['措施项目']} + 管理利润 {s['管理费利润']} + 规费 {s['规费']} + 税金 {s['税金']} = 总造价 ¥{s['总造价']:,.2f}**", ""]
    lines.append("费用结构：" + "　".join(f"{k} {v}" for k, v in report["费用结构"].items()))
    lines += ["", "> " + report["免责声明"]]
    return "\n".join(lines) + "\n"


def to_excel(report: dict, out_path: Path) -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "清单明细"
    ws.append(["编码", "名称", "单位", "工程量", "综合单价", "合价", "类别", "备注"])
    for i in report["清单明细"]:
        ws.append([i["编码"], i["名称"], i["单位"], i["工程量"], i["综合单价"], i["合价"], i["类别"], i["备注"]])
    ws.append([])
    ws.append(["汇总", "", "", "", "", "", "", ""])
    for k, v in report["汇总"].items():
        ws.append([k, "", "", "", "", v])
    ws.append([])
    ws.append(["免责声明", report["免责声明"]])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
