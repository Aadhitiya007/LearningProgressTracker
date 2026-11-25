"""Formatted Excel report builder using openpyxl."""

import os
import shutil
from datetime import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import DoughnutChart, Reference
from openpyxl.chart.series import DataPoint

from config import REPORTS_DIR, ONEDRIVE_FOLDER, REPORT_NAME
from core.parser import COLUMNS

STATUS_COLORS = {
    "Completed": "C6EFCE",
    "In Progress": "FFEB9C",
    "Not Started": "F2DCDB",
    "Exempted": "E2D6F5",
}

HEADER_COLOR = "1F4E79"


def build_excel(df: pd.DataFrame, summary: dict) -> dict:
    """Build a multi-sheet styled Excel workbook in REPORTS_DIR and optionally copy to OneDrive."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{REPORT_NAME}_{timestamp}.xlsx"
    save_path = os.path.join(REPORTS_DIR, filename)

    wb = Workbook()
    thn = Side(style="thin", color="CCCCCC")
    bdr = Border(left=thn, right=thn, top=thn, bottom=thn)

    def hcell(ws, r, c, val, bg=HEADER_COLOR, fg="FFFFFF"):
        cell = ws.cell(row=r, column=c, value=val)
        cell.font = Font(name="Arial", bold=True, color=fg, size=11)
        cell.fill = PatternFill("solid", start_color=bg)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = bdr

    def dcell(ws, r, c, val, bg="FFFFFF", bold=False, align="left"):
        cell = ws.cell(row=r, column=c, value=val)
        cell.font = Font(name="Arial", size=10, bold=bold)
        cell.fill = PatternFill("solid", start_color=bg)
        cell.alignment = Alignment(horizontal=align, vertical="center")
        cell.border = bdr

    widths = [10, 18, 22, 14, 13, 14, 16, 18, 16, 20, 11, 14, 14]
    now_str = datetime.now().strftime("%d %b %Y  %I:%M %p")

    # Sheet 1: Progress Report
    ws1 = wb.active
    ws1.title = "Progress Report"
    ws1.sheet_properties.tabColor = HEADER_COLOR
    ws1.freeze_panes = "A4"

    ws1.merge_cells("A1:M1")
    title = ws1.cell(row=1, column=1, value=f"Learning Progress Report  |  Generated: {now_str}")
    title.font = Font(name="Arial", bold=True, size=13, color="FFFFFF")
    title.fill = PatternFill("solid", start_color=HEADER_COLOR)
    title.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 30

    ws1.merge_cells("A2:M2")
    info = ws1.cell(row=2, column=1, value=f"Report file: {filename}")
    info.font = Font(name="Arial", italic=True, size=9, color="555555")
    info.fill = PatternFill("solid", start_color="EAF0F6")
    info.alignment = Alignment(horizontal="left", vertical="center")
    ws1.row_dimensions[2].height = 16

    for ci, col in enumerate(COLUMNS, 1):
        hcell(ws1, 3, ci, col)
    ws1.row_dimensions[3].height = 18

    current_row = 4
    for status in ["Completed", "In Progress", "Not Started", "Exempted"]:
        group = df[df["CURRENT STATUS"] == status]
        if group.empty:
            continue

        ws1.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=13)
        sec = ws1.cell(
            row=current_row,
            column=1,
            value=f"  {status}  ({len(group)} employee{'s' if len(group) > 1 else ''})",
        )
        sec.font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
        sec.fill = PatternFill("solid", start_color=HEADER_COLOR)
        sec.alignment = Alignment(horizontal="left", vertical="center")
        ws1.row_dimensions[current_row].height = 22
        current_row += 1

        for ri, (_, row) in enumerate(group[COLUMNS].iterrows(), 1):
            alt = "FFFFFF" if ri % 2 == 0 else "F4F8FF"
            for ci, col in enumerate(COLUMNS, 1):
                val = row[col]
                bg = STATUS_COLORS.get(val, alt) if col == "CURRENT STATUS" else alt
                align = "right" if col in ("E-LEARNING COMPLETION %", "VILT COMPLETION %", "BEST SCORE") else "left"
                dcell(ws1, current_row, ci, val, bg=bg, align=align)
            ws1.row_dimensions[current_row].height = 16
            current_row += 1

        current_row += 1

    for ci, w in enumerate(widths, 1):
        ws1.column_dimensions[get_column_letter(ci)].width = w

    # Sheet 2: Summary
    ws2 = wb.create_sheet("Summary")
    ws2.sheet_properties.tabColor = "00B050"
    ws2.merge_cells("A1:C1")
    sh = ws2.cell(row=1, column=1, value="Summary Dashboard")
    sh.font = Font(name="Arial", bold=True, size=13, color="FFFFFF")
    sh.fill = PatternFill("solid", start_color="00B050")
    sh.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 28

    for ri, (label, val, color) in enumerate(
        [
            ("Total Employees", summary["total"], "BDD7EE"),
            ("Certified / Completed", summary["certified"], "C6EFCE"),
            ("In Progress", summary["in_progress"], "FFEB9C"),
            ("Not Started", summary["not_started"], "F2DCDB"),
            ("Exempted", summary["exempted"], "E2D6F5"),
            ("Avg Best Score", summary["avg_score"], "FCE4D6"),
            ("Completion Rate (%)", summary["rate"], "E2EFDA"),
        ],
        3,
    ):
        ws2.row_dimensions[ri].height = 26
        dcell(ws2, ri, 1, label, bg=color, bold=True)
        dcell(ws2, ri, 2, val, bg=color, bold=True, align="center")

    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 16

    # Sheet 3: Donut Chart
    ws_donut = wb.create_sheet("Donut Chart")
    ws_donut.sheet_properties.tabColor = "4472C4"
    ws_donut.merge_cells("A1:D1")
    dt = ws_donut.cell(row=1, column=1, value="Status Distribution — Donut Chart")
    dt.font = Font(name="Arial", bold=True, size=13, color="FFFFFF")
    dt.fill = PatternFill("solid", start_color="4472C4")
    dt.alignment = Alignment(horizontal="center", vertical="center")
    ws_donut.row_dimensions[1].height = 28

    for ci, h in enumerate(["Status", "Count", "Percentage (%)"], 1):
        hcell(ws_donut, 2, ci, h)

    donut_rows = [
        ("Completed", summary["certified"], "C6EFCE"),
        ("In Progress", summary["in_progress"], "FFEB9C"),
        ("Not Started", summary["not_started"], "F2DCDB"),
        ("Exempted", summary["exempted"], "E2D6F5"),
    ]
    ttl = summary["total"]
    for ri, (status_lbl, count, color_d) in enumerate(donut_rows, 3):
        pct = round((count / ttl * 100), 1) if ttl > 0 else 0
        ws_donut.row_dimensions[ri].height = 22
        dcell(ws_donut, ri, 1, status_lbl, bg=color_d, bold=True)
        dcell(ws_donut, ri, 2, count, bg=color_d, bold=True, align="center")
        dcell(ws_donut, ri, 3, pct, bg=color_d, bold=True, align="center")

    ws_donut.column_dimensions["A"].width = 18
    ws_donut.column_dimensions["B"].width = 10
    ws_donut.column_dimensions["C"].width = 16

    chart = DoughnutChart()
    chart.title = "Certification Status Distribution"
    chart.style = 10
    chart.holeSize = 50
    chart_data = Reference(ws_donut, min_col=2, min_row=2, max_row=6)
    chart_labels = Reference(ws_donut, min_col=1, min_row=3, max_row=6)
    chart.add_data(chart_data, titles_from_data=True)
    chart.set_categories(chart_labels)

    for i, hex_c in enumerate(["10B981", "F59E0B", "EF4444", "A78BFA"]):
        pt = DataPoint(idx=i)
        pt.graphicalProperties.solidFill = hex_c
        chart.series[0].dPt.append(pt)

    chart.width = 15
    chart.height = 14
    ws_donut.add_chart(chart, "F2")

    # Status-specific sheets
    for status, color in STATUS_COLORS.items():
        group = df[df["CURRENT STATUS"] == status]
        if group.empty:
            continue
        ws = wb.create_sheet(status[:31])
        ws.sheet_properties.tabColor = color
        ws.merge_cells("A1:M1")
        t = ws.cell(row=1, column=1, value=f"{status}  |  {len(group)} employee(s)  |  {now_str}")
        t.font = Font(name="Arial", bold=True, size=12, color="FFFFFF")
        t.fill = PatternFill("solid", start_color=HEADER_COLOR)
        t.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24
        for ci, col in enumerate(COLUMNS, 1):
            hcell(ws, 2, ci, col, bg=color, fg="000000")
        for ri, (_, row) in enumerate(group[COLUMNS].iterrows(), 3):
            bg = "FFFFFF" if ri % 2 == 0 else "F9F9F9"
            for ci, col in enumerate(COLUMNS, 1):
                dcell(ws, ri, ci, row[col], bg=bg)
            ws.row_dimensions[ri].height = 15
        for ci, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(ci)].width = w

    wb.save(save_path)

    onedrive_copy = ""
    if ONEDRIVE_FOLDER and "YourName" not in ONEDRIVE_FOLDER:
        if os.path.exists(os.path.dirname(ONEDRIVE_FOLDER)):
            os.makedirs(ONEDRIVE_FOLDER, exist_ok=True)
            onedrive_copy = os.path.join(ONEDRIVE_FOLDER, filename)
            shutil.copy2(save_path, onedrive_copy)

    return {"filename": filename, "path": save_path, "onedrive_path": onedrive_copy}
