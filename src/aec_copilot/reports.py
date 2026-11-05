"""Excel and PDF export for modeling runs, audits, and evaluations."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import AuditReport, RunResult


def _excel(elements: list[dict[str, Any]],path: Path,*,audit: AuditReport | None = None,run: RunResult | None = None) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb=Workbook()
    ws=wb.active
    ws.title="构件明细"
    headers=["ID","类型","引擎","关键尺寸 / 位置（mm）","宿主","标高（mm）"]
    ws.append(headers)
    for e in elements:
        ignored={"id","type","engine","host_id","elevation","level_id","_host"}
        geometry=json.dumps({k:v for k,v in e.items() if k not in ignored},ensure_ascii=False)
        ws.append([e.get("id"),e.get("type"),e.get("engine"),geometry,e.get("host_id"),e.get("elevation")])
    if run:
        summary=wb.create_sheet("运行摘要")
        rows=[("运行 ID",run.run_id),("状态",run.status),("后端",run.backend),("引擎",run.engine),("原始指令",run.instruction),("尝试次数",len(run.attempts)),("Token（供应商报告值）",sum(a.token_usage.get("total_tokens",0) for a in run.attempts)),("说明","模拟结果不构成 Revit/AutoCAD/SolidWorks 实机验收")]
        for row in rows: summary.append(row)
    if audit:
        issues=wb.create_sheet("审图问题")
        issues.append(["规则 ID","严重度","构件 ID","问题","建议","来源"])
        for issue in audit.issues: issues.append([issue.rule_id,issue.severity,issue.element_id,issue.message,issue.suggestion,issue.source])
        issues.append([])
        issues.append(["免责声明",audit.disclaimer])
    for sheet in wb.worksheets:
        sheet.freeze_panes="A2"
        sheet.auto_filter.ref=sheet.dimensions if sheet.max_row>1 else None
        for cell in sheet[1]:
            cell.font=Font(bold=True,color="FFFFFF")
            cell.fill=PatternFill("solid",fgColor="17324D")
            cell.alignment=Alignment(vertical="center")
        for column in range(1,sheet.max_column+1):
            values=[str(sheet.cell(row,column).value or "") for row in range(1,min(sheet.max_row,200)+1)]
            sheet.column_dimensions[get_column_letter(column)].width=min(60,max(12,max((len(v) for v in values),default=8)+2))
        for row in sheet.iter_rows():
            for cell in row: cell.alignment=Alignment(vertical="top",wrap_text=True)
        sheet.row_dimensions[1].height=26
    wb.save(path)


def _register_cjk() -> tuple[str,str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    regular=os.getenv("REPORTLAB_CJK_REGULAR_FONT","/usr/local/share/fonts/tabbit/NotoSansSC-Regular.ttf")
    bold=os.getenv("REPORTLAB_CJK_BOLD_FONT","/usr/local/share/fonts/tabbit/NotoSansSC-Bold.ttf")
    if not Path(regular).is_file():
        raise RuntimeError("Chinese PDF export needs REPORTLAB_CJK_REGULAR_FONT to point to a single-face CJK .ttf/.otf font")
    if "AEC-CJK" not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont("AEC-CJK",regular))
    if Path(bold).is_file():
        if "AEC-CJK-Bold" not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont("AEC-CJK-Bold",bold))
    else: bold=regular
    if "AEC-CJK-Bold" not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont("AEC-CJK-Bold",bold))
    return "AEC-CJK","AEC-CJK-Bold"


def _pdf(title: str,subtitle: str,sections: list[tuple[str,list[str]]],path: Path,*,table: list[list[str]] | None = None) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak,Paragraph,SimpleDocTemplate,Spacer,Table,TableStyle
    regular,bold=_register_cjk()
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=17*mm,title=title,author="AEC Copilot")
    body=ParagraphStyle("body",fontName=regular,fontSize=9.5,leading=15,textColor=colors.HexColor("#263645"),alignment=TA_LEFT,wordWrap="CJK")
    heading=ParagraphStyle("heading",fontName=bold,fontSize=14,leading=20,spaceBefore=12,spaceAfter=7,textColor=colors.HexColor("#17324D"))
    title_style=ParagraphStyle("title",fontName=bold,fontSize=22,leading=30,textColor=colors.HexColor("#17324D"),spaceAfter=6)
    small=ParagraphStyle("small",parent=body,fontSize=8,textColor=colors.HexColor("#5D6D7E"))
    table_head=ParagraphStyle("table-head",parent=small,fontName=bold,textColor=colors.white)
    story=[Paragraph(title,title_style),Paragraph(subtitle,small),Spacer(1,8*mm)]
    for heading_text,lines in sections:
        story.append(Paragraph(heading_text,heading))
        for line in lines:
            # Escape user/model text for ReportLab's paragraph mini-markup.
            safe=str(line).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br/>")
            story.append(Paragraph(safe,body)); story.append(Spacer(1,2*mm))
    if table:
        story.append(Paragraph("构件明细（前 80 条）",heading))
        wrapped=[[Paragraph(str(c).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"),table_head if row_index==0 else small) for c in row] for row_index,row in enumerate(table)]
        tbl=Table(wrapped,colWidths=[35*mm,22*mm,30*mm,80*mm],repeatRows=1,hAlign="LEFT")
        tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17324D")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),bold),("FONTNAME",(0,1),(-1,-1),regular),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#CBD5DF")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F3F6F8")]),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        story.append(tbl)
    def footer(canvas: Any,doc_: Any) -> None:
        canvas.saveState(); canvas.setFont(regular,8); canvas.setFillColor(colors.HexColor("#6C7A89")); canvas.drawString(18*mm,9*mm,"AEC Copilot · generated report"); canvas.drawRightString(192*mm,9*mm,f"第 {doc_.page} 页"); canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def write_run_reports(run: RunResult,output: str | Path) -> dict[str,str]:
    output=Path(output)
    xlsx=output/"model-schedule.xlsx"
    _excel(run.elements,xlsx,run=run)
    attempts=[f"第 {a.attempt} 轮：{a.status}，{a.elapsed_ms:.1f} ms，差异 {len(a.verification.differences)} 项。" for a in run.attempts]
    diffs=[f"{d.element_id or '-'} / {d.path or '-'}：{d.message}" for a in run.attempts for d in a.verification.differences]
    if not diffs: diffs=["确定性模型清单校验未发现差异。"]
    pdf=output/"modeling-report.pdf"
    schedule=[["ID","类型","标高(mm)","关键尺寸 / 位置（mm）"]]
    ignored={"id","type","engine","host_id","elevation","level_id","_host"}
    for element in run.elements[:80]:
        geometry=json.dumps({k:v for k,v in element.items() if k not in ignored},ensure_ascii=False)
        schedule.append([str(element.get("id","")),str(element.get("type","")),str(element.get("elevation","")),geometry])
    _pdf("AI 建筑师 Copilot｜建模报告",f"运行 {run.run_id} · {run.backend.upper()} · {run.engine}",[("任务与结果",[f"原始指令：{run.instruction}",f"状态：{run.status}；构件数：{len(run.elements)}；尝试次数：{len(run.attempts)}。","重要边界：模拟引擎结果只证明软件闭环，不构成 Revit、AutoCAD 或 SolidWorks 实机验收。"]),("执行轨迹",attempts),("校验结果",diffs)],pdf,table=schedule)
    return {"excel":str(xlsx),"pdf":str(pdf)}


def write_audit_reports(audit: AuditReport,elements: list[dict[str, Any]],output_dir: str | Path,stem: str = "audit-report") -> dict[str,str]:
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    xlsx=output/f"{stem}.xlsx"; pdf=output/f"{stem}.pdf"
    _excel(elements,xlsx,audit=audit)
    lines=[f"[{i.severity}] {i.rule_id} · {i.element_id or '模型'}：{i.message}；建议：{i.suggestion}" for i in audit.issues] or ["未触发当前项目规则。"]
    _pdf("AI 建筑师 Copilot｜审图报告",f"问题项 {audit.issue_count} · PROJECT RULES",[("审查结论",[f"共发现 {audit.issue_count} 个问题项。",audit.disclaimer]),("问题与建议",lines)],pdf)
    (output/f"{stem}.json").write_text(audit.model_dump_json(indent=2),encoding="utf-8")
    return {"excel":str(xlsx),"pdf":str(pdf),"json":str(output/f"{stem}.json")}


def write_eval_reports(summary: dict[str, Any],rows: list[dict[str, Any]],output_dir: str | Path) -> dict[str,str]:
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    xlsx=output/"evaluation.xlsx"
    wb=Workbook(); ws=wb.active; ws.title="汇总"
    for k,v in summary.items(): ws.append([k,json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v])
    detail=wb.create_sheet("逐例结果")
    headers=sorted({key for row in rows for key in row})
    detail.append(headers)
    for row in rows: detail.append([json.dumps(row.get(h),ensure_ascii=False) if isinstance(row.get(h),(dict,list)) else row.get(h) for h in headers])
    for sheet in wb.worksheets:
        for cell in sheet[1]: cell.font=Font(bold=True,color="FFFFFF"); cell.fill=PatternFill("solid",fgColor="17324D")
        sheet.freeze_panes="A2"
        for col in sheet.columns:
            letter=col[0].column_letter; sheet.column_dimensions[letter].width=min(55,max(12,max(len(str(c.value or "")) for c in col)+2))
    wb.save(xlsx)
    metrics=[f"{k}：{v}" for k,v in summary.items() if not isinstance(v,(dict,list))]
    pdf=output/"evaluation.pdf"
    _pdf("AI 建筑师 Copilot｜评测报告","SIMULATION · reproducible benchmark",[("指标",metrics),("口径说明",["一次通过率：首轮确定性校验通过的用例占比。","三轮内收敛率：最多三轮后最终通过的用例占比。","端到端耗时：规划、编译、模拟执行、截图、校验和报告的总耗时。","Token：仅汇总供应商 API 返回的 usage；确定性解析不计 Token，不是估算值。","本报告不包含真实工业软件验收结论。"])],pdf)
    (output/"evaluation.json").write_text(json.dumps({"summary":summary,"rows":rows},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"excel":str(xlsx),"pdf":str(pdf),"json":str(output/"evaluation.json")}
