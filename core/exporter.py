"""Colorful, well-aligned Excel report builder with embedded Donut Charts."""

import os
import shutil
from datetime import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import DoughnutChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint

from config import REPORTS_DIR, ONEDRIVE_FOLDER, REPORT_NAME
from core.parser import COLUMNS

HEADER_BG = "1F4E79"

STATUS_STYLES = {
    "Completed":   {"banner": "198754", "cell": "D1E7DD", "font": "0F5132", "slice": "10B981"},
    "In Progress": {"banner": "D97706", "cell": "FEF3C7", "font": "92400E", "slice": "F59E0B"},
    "Not Started": {"banner": "DC2626", "cell": "FEE2E2", "font": "991B1B", "slice": "EF4444"},
    "Exempted":    {"banner": "6D28D9", "cell": "EDE9FE", "font": "5B21B6", "slice": "8B5CF6"},
}

PROF_COLORS = {
    "Advanced": "3B82F6",
    "Intermediate": "F97316",
    "Beginner": "64748B",
    "Unknown": "94A3B8",
}

CENTER_COLS = {
    "EMP ID", "PROFICIENCY", "TARGET DATE", "CURRENT STATUS",
    "LEARNING START DATE", "LEARNING COMPLETION DATE",
    "CERTIFIED DATE", "EXEMPTED STATUS",
}
RIGHT_COLS = {"E-LEARNING COMPLETION %", "VILT COMPLETION %", "BEST SCORE"}


def _auto_fit_columns(ws, cols: list[str], rows_data: list[list], min_w: int = 12, max_w: int = 34) -> None:
    for ci, col_name in enumerate(cols, 1):
        best = len(str(col_name))
        for r in rows_data:
            if ci - 1 < len(r):
                val_len = len(str(r[ci - 1] or ""))
                if val_len > best:
                    best = val_len
        ws.column_dimensions[get_column_letter(ci)].width = max(min_w, min(max_w, best + 4))


def _col_alignment(col: str) -> str:
    if col in RIGHT_COLS:
        return "right"
    if col in CENTER_COLS:
        return "center"
    return "left"


def build_excel(df: pd.DataFrame, summary: dict) -> dict:
    """Build a styled multi-sheet Excel workbook with Summary Donut Charts and aligned tables."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{REPORT_NAME}_{timestamp}.xlsx"
    save_path = os.path.join(REPORTS_DIR, filename)

    wb = Workbook()
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def hcell(ws, r, c, val, bg=HEADER_BG, fg="FFFFFF"):
        cell = ws.cell(row=r, column=c, value=val)
        cell.font = Font(name="Calibri", bold=True, color=fg, size=11)
        cell.fill = PatternFill("solid", start_color=bg)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        return cell

    def dcell(ws, r, c, val, bg="FFFFFF", fg="1E293B", bold=False, align="left", wrap=False, num_fmt=None):
        cell = ws.cell(row=r, column=c, value=val)
        cell.font = Font(name="Calibri", size=10, bold=bold, color=fg)
        cell.fill = PatternFill("solid", start_color=bg)
        cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
        cell.border = border
        if num_fmt:
            cell.number_format = num_fmt
        return cell

    now_str = datetime.now().strftime("%d %b %Y  %I:%M %p")

    # Determine active columns (standard + any custom columns from manager)
    extra_cols = [c for c in df.columns if c not in COLUMNS]
    active_cols = list(COLUMNS) + extra_cols
    total_cols = len(active_cols)

    # =========================================================================
    # Sheet 1: Summary Dashboard (KPIs + 2 Embedded Donut Charts)
    # =========================================================================
    ws_sum = wb.active
    ws_sum.title = "Summary Dashboard"
    ws_sum.sheet_properties.tabColor = "1F4E79"
    ws_sum.views.sheetView[0].showGridLines = True

    ws_sum.merge_cells("A1:N1")
    t1 = ws_sum.cell(row=1, column=1, value=f"Learning Progress Tracker — Executive Summary  |  {now_str}")
    t1.font = Font(name="Calibri", bold=True, size=14, color="FFFFFF")
    t1.fill = PatternFill("solid", start_color=HEADER_BG)
    t1.alignment = Alignment(horizontal="center", vertical="center")
    ws_sum.row_dimensions[1].height = 34

    # KPI Table (A3:B10)
    hcell(ws_sum, 3, 1, "Key Metric")
    hcell(ws_sum, 3, 2, "Value")
    ws_sum.row_dimensions[3].height = 24

    kpi_rows = [
        ("Total Employees",       summary["total"],       "DBEAFE", "1E3A8A", "0"),
        ("Completed / Certified", summary["certified"],   "D1E7DD", "0F5132", "0"),
        ("In Progress",           summary["in_progress"], "FEF3C7", "92400E", "0"),
        ("Not Started",           summary["not_started"], "FEE2E2", "991B1B", "0"),
        ("Exempted",              summary["exempted"],    "EDE9FE", "5B21B6", "0"),
        ("Average Best Score",    summary["avg_score"],   "FFEDD5", "9A3412", "0.0"),
        ("Completion Rate (%)",   summary["rate"],        "DCFCE7", "166534", '0.0"%"'),
    ]
    for ri, (label, val, bg, fg, fmt) in enumerate(kpi_rows, 4):
        ws_sum.row_dimensions[ri].height = 24
        dcell(ws_sum, ri, 1, label, bg=bg, fg=fg, bold=True, align="left")
        dcell(ws_sum, ri, 2, val, bg=bg, fg=fg, bold=True, align="center", num_fmt=fmt)

    # Status Distribution Table (D3:F7)
    hcell(ws_sum, 3, 4, "Status")
    hcell(ws_sum, 3, 5, "Count")
    hcell(ws_sum, 3, 6, "Share (%)")

    ttl = summary["total"] or 1
    status_items = [
        ("Completed", summary["certified"]),
        ("In Progress", summary["in_progress"]),
        ("Not Started", summary["not_started"]),
        ("Exempted", summary["exempted"]),
    ]
    for idx, (st_lbl, cnt) in enumerate(status_items, 4):
        st_cfg = STATUS_STYLES[st_lbl]
        pct = round((cnt / ttl) * 100, 1) if summary["total"] > 0 else 0.0
        dcell(ws_sum, idx, 4, st_lbl, bg=st_cfg["cell"], fg=st_cfg["font"], bold=True, align="center")
        dcell(ws_sum, idx, 5, cnt, bg=st_cfg["cell"], fg=st_cfg["font"], bold=True, align="center", num_fmt="0")
        dcell(ws_sum, idx, 6, pct, bg=st_cfg["cell"], fg=st_cfg["font"], bold=True, align="center", num_fmt='0.0"%"')

    # Status Donut Chart anchored at H3
    chart1 = DoughnutChart()
    chart1.title = "Status Distribution"
    chart1.style = 10
    chart1.holeSize = 52
    chart1.add_data(Reference(ws_sum, min_col=5, min_row=3, max_row=7), titles_from_data=True)
    chart1.set_categories(Reference(ws_sum, min_col=4, min_row=4, max_row=7))
    chart1.dataLabels = DataLabelList()
    chart1.dataLabels.showPercent = True
    chart1.dataLabels.showVal = True
    chart1.dataLabels.showCatName = False
    for i, (st_lbl, _) in enumerate(status_items):
        pt = DataPoint(idx=i)
        pt.graphicalProperties.solidFill = STATUS_STYLES[st_lbl]["slice"]
        chart1.series[0].dPt.append(pt)
    chart1.width = 14
    chart1.height = 11
    ws_sum.add_chart(chart1, "H3")

    # Proficiency Breakdown Table (D10:F...)
    prof_counts = df["PROFICIENCY"].value_counts().to_dict() if "PROFICIENCY" in df.columns else {}
    prof_order = [p for p in ("Advanced", "Intermediate", "Beginner", "Unknown") if prof_counts.get(p, 0) > 0]
    for k in prof_counts:
        if k not in prof_order:
            prof_order.append(k)

    if prof_order:
        hcell(ws_sum, 10, 4, "Proficiency", bg="0F766E")
        hcell(ws_sum, 10, 5, "Count", bg="0F766E")
        hcell(ws_sum, 10, 6, "Share (%)", bg="0F766E")
        ws_sum.row_dimensions[10].height = 24

        for idx, p_lbl in enumerate(prof_order, 11):
            cnt = int(prof_counts[p_lbl])
            pct = round((cnt / ttl) * 100, 1) if summary["total"] > 0 else 0.0
            bg = "F0FDFA" if idx % 2 == 1 else "FFFFFF"
            ws_sum.row_dimensions[idx].height = 22
            dcell(ws_sum, idx, 4, p_lbl, bg=bg, bold=True, align="center")
            dcell(ws_sum, idx, 5, cnt, bg=bg, bold=True, align="center", num_fmt="0")
            dcell(ws_sum, idx, 6, pct, bg=bg, bold=True, align="center", num_fmt='0.0"%"')

        max_p_row = 10 + len(prof_order)
        chart2 = DoughnutChart()
        chart2.title = "Proficiency Breakdown"
        chart2.style = 10
        chart2.holeSize = 52
        chart2.add_data(Reference(ws_sum, min_col=5, min_row=10, max_row=max_p_row), titles_from_data=True)
        chart2.set_categories(Reference(ws_sum, min_col=4, min_row=11, max_row=max_p_row))
        chart2.dataLabels = DataLabelList()
        chart2.dataLabels.showPercent = True
        chart2.dataLabels.showVal = True
        chart2.dataLabels.showCatName = False
        for i, p_lbl in enumerate(prof_order):
            pt = DataPoint(idx=i)
            pt.graphicalProperties.solidFill = PROF_COLORS.get(p_lbl, "64748B")
            chart2.series[0].dPt.append(pt)
        chart2.width = 14
        chart2.height = 11
        ws_sum.add_chart(chart2, "H22")

    ws_sum.column_dimensions["A"].width = 26
    ws_sum.column_dimensions["B"].width = 14
    ws_sum.column_dimensions["C"].width = 4
    ws_sum.column_dimensions["D"].width = 18
    ws_sum.column_dimensions["E"].width = 12
    ws_sum.column_dimensions["F"].width = 14

    # =========================================================================
    # Sheet 2: Progress Report (Grouped, Auto-Fit, Color-Coded, Aligned)
    # =========================================================================
    ws1 = wb.create_sheet("Progress Report")
    ws1.sheet_properties.tabColor = "2563EB"
    ws1.freeze_panes = "A4"
    ws1.page_setup.orientation = ws1.ORIENTATION_LANDSCAPE
    ws1.page_setup.fitToWidth = 1

    ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    title = ws1.cell(row=1, column=1, value=f"Learning Progress Report  |  Generated: {now_str}")
    title.font = Font(name="Calibri", bold=True, size=14, color="FFFFFF")
    title.fill = PatternFill("solid", start_color=HEADER_BG)
    title.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 32

    ws1.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
    info = ws1.cell(row=2, column=1, value=f"Total Records: {summary['total']}   |   Completion Rate: {summary['rate']}%   |   Avg Score: {summary['avg_score']}")
    info.font = Font(name="Calibri", italic=True, size=10, color="334155")
    info.fill = PatternFill("solid", start_color="E2E8F0")
    info.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[2].height = 20

    for ci, col in enumerate(active_cols, 1):
        hcell(ws1, 3, ci, col)
    ws1.row_dimensions[3].height = 28

    current_row = 4
    all_written_rows = []
    for status in ["Completed", "In Progress", "Not Started", "Exempted"]:
        group = df[df["CURRENT STATUS"] == status]
        if group.empty:
            continue

        st_cfg = STATUS_STYLES[status]
        ws1.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=total_cols)
        sec = ws1.cell(
            row=current_row,
            column=1,
            value=f"  {status.upper()}  ({len(group)} employee{'s' if len(group) > 1 else ''})",
        )
        sec.font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
        sec.fill = PatternFill("solid", start_color=st_cfg["banner"])
        sec.alignment = Alignment(horizontal="left", vertical="center")
        ws1.row_dimensions[current_row].height = 24
        current_row += 1

        for ri, (_, row) in enumerate(group[active_cols].iterrows(), 1):
            alt = "FFFFFF" if ri % 2 == 0 else "F8FAFC"
            row_vals = []
            for ci, col in enumerate(active_cols, 1):
                val = row[col]
                row_vals.append(val)
                align = _col_alignment(col)
                bg = alt
                fg = "1E293B"
                bold = False
                fmt = None
                wrap = col in ("EMP NAME", "SKILL ASSIGNED") or col in extra_cols

                if col == "CURRENT STATUS":
                    bg = st_cfg["cell"]
                    fg = st_cfg["font"]
                    bold = True
                elif col == "BEST SCORE":
                    sc_val = float(val or 0)
                    fmt = "0"
                    bold = sc_val > 0
                    fg = "0F5132" if sc_val >= 80 else ("B45309" if sc_val >= 50 else ("B91C1C" if sc_val > 0 else "64748B"))
                elif col in ("E-LEARNING COMPLETION %", "VILT COMPLETION %"):
                    fmt = '0"%"'

                dcell(ws1, current_row, ci, val, bg=bg, fg=fg, bold=bold, align=align, wrap=wrap, num_fmt=fmt)
            all_written_rows.append(row_vals)
            ws1.row_dimensions[current_row].height = 22
            current_row += 1

        current_row += 1

    _auto_fit_columns(ws1, active_cols, all_written_rows)

    # =========================================================================
    # Sheet 3+: Status-Specific Sheets (with AutoFilter & Alignment)
    # =========================================================================
    for status, st_cfg in STATUS_STYLES.items():
        group = df[df["CURRENT STATUS"] == status]
        if group.empty:
            continue
        ws = wb.create_sheet(status[:31])
        ws.sheet_properties.tabColor = st_cfg["banner"]
        ws.freeze_panes = "A3"
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.fitToWidth = 1

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
        t = ws.cell(row=1, column=1, value=f"{status}  |  {len(group)} employee(s)  |  {now_str}")
        t.font = Font(name="Calibri", bold=True, size=13, color="FFFFFF")
        t.fill = PatternFill("solid", start_color=st_cfg["banner"])
        t.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 28

        for ci, col in enumerate(active_cols, 1):
            hcell(ws, 2, ci, col, bg=st_cfg["cell"], fg=st_cfg["font"])
        ws.row_dimensions[2].height = 26

        written = []
        for ri, (_, row) in enumerate(group[active_cols].iterrows(), 3):
            bg = "FFFFFF" if ri % 2 == 0 else "F8FAFC"
            row_vals = []
            for ci, col in enumerate(active_cols, 1):
                val = row[col]
                row_vals.append(val)
                fmt = '0"%"' if col in ("E-LEARNING COMPLETION %", "VILT COMPLETION %") else ("0" if col == "BEST SCORE" else None)
                dcell(
                    ws, ri, ci, val, bg=bg,
                    align=_col_alignment(col),
                    wrap=(col in ("EMP NAME", "SKILL ASSIGNED") or col in extra_cols),
                    num_fmt=fmt,
                )
            written.append(row_vals)
            ws.row_dimensions[ri].height = 22

        ws.auto_filter.ref = f"A2:{get_column_letter(total_cols)}{2 + len(group)}"
        _auto_fit_columns(ws, active_cols, written)

    wb.save(save_path)

    onedrive_copy = ""
    if ONEDRIVE_FOLDER and "YourName" not in ONEDRIVE_FOLDER:
        if os.path.exists(os.path.dirname(ONEDRIVE_FOLDER)):
            os.makedirs(ONEDRIVE_FOLDER, exist_ok=True)
            onedrive_copy = os.path.join(ONEDRIVE_FOLDER, filename)
            shutil.copy2(save_path, onedrive_copy)

    return {"filename": filename, "path": save_path, "onedrive_path": onedrive_copy}
