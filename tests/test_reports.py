from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook

from aec_copilot.audit import audit_model
from aec_copilot.reports import write_audit_reports


def test_audit_excel_and_pdf(tmp_path):
    elements=[{"id":"door 1","type":"door","host_id":"missing","width":600,"height":1800,"bottom":0,"offset":0}]
    report=audit_model(elements)
    files=write_audit_reports(report,elements,tmp_path)
    assert report.issue_count>=4
    wb=load_workbook(files["excel"])
    assert wb.sheetnames==["构件明细","审图问题"]
    assert wb["审图问题"].max_row>=6
    assert Path(files["pdf"]).read_bytes().startswith(b"%PDF")
    assert json.loads(Path(files["json"]).read_text(encoding="utf-8"))["issue_count"]==report.issue_count
