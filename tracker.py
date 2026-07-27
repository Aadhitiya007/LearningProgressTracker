import os
import sys
import re
from datetime import datetime


try:
    import pandas as pd
except ImportError:
    print("❌  pandas not installed. Run:  pip install pandas")
    sys.exit(1)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils  import get_column_letter
except ImportError:
    print("❌  openpyxl not installed. Run:  pip install openpyxl")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌  requests not installed. Run:  pip install requests")
    sys.exit(1)

try:
    import snowflake.connector
    
except ImportError:
    print("❌  Snowflake connector not installed.")
    print("    Run:  pip install snowflake-connector-python")
    sys.exit(1)



INPUT_CSV = "LearningAdoptionReport.csv"


ONEDRIVE_FOLDER = r"C:\Users\aadhitiya.m\OneDrive - Mphasis\LearningProgressReports"
REPORT_NAME     = "Learning_Progress_Report"



POWER_AUTOMATE_URL = ""
MANAGER_EMAIL      = ""
MANAGER_NAME       = ""

SNOWFLAKE_ACCOUNT   = ""  
SNOWFLAKE_USER      = ""
SNOWFLAKE_PASSWORD  = ""
SNOWFLAKE_WAREHOUSE = "TRACKER_WH"
SNOWFLAKE_DATABASE  = "LEARNING_TRACKER"
SNOWFLAKE_SCHEMA    = "CERTIFICATION_DATA"
SNOWFLAKE_TABLE     = "EMPLOYEE_CERTIFICATIONS"



COL_MAP = {
    "EMP ID": [
        "emp id", "employee id", "empid", "emp_id", "emp. id"
    ],
    "EMP NAME": [
        "emp name", "employee name", "name", "empname", "emp_name"
    ],
    "SKILL ASSIGNED": [
        "skill assigned", "skill", "skills assigned", "skill name"
    ],
    "PROFICIENCY": [
        "proficiency", "level", "proficiency level", "prof"
    ],
    "TARGET DATE": [
        "target date", "target_date", "target completion date"
    ],
    "CURRENT STATUS": [
        "current status", "status", "current_status"
    ],
    "LEARNING START DATE": [
        "learning start date", "start date", "learning_start_date"
    ],
    "E-LEARNING COMPLETION %": [
        "e-learning completion %", "elearning completion %",
        "elearning completion percentage",
        "e-learning completion percentage",
        "e learning completion percentage",
        "elearningcompletionpercentage",
        "elearning%", "e-learning%", "e learning completion %",
    ],
    "VILT COMPLETION %": [
        "vilt completion %", "vilt %", "vilt completion",
        "vilt completion percentage", "viltcompletionpercentage",
    ],
    "LEARNING COMPLETION DATE": [
        "learning completion date", "completion date"
    ],
    "BEST SCORE": [
        "best score", "score", "best_score", "top score"
    ],
    "CERTIFIED DATE": [
        "certified date", "certification date", "cert date"
    ],
    "EXEMPTED STATUS": [
        "exempted status", "exempted", "exempt status", "exempt"
    ],
}

COLUMNS = list(COL_MAP.keys())

STATUS_COLORS = {
    "Completed":   "C6EFCE",
    "In Progress": "FFEB9C",
    "Not Started": "F2DCDB",
    "Exempted":    "E2D6F5",
}

HEADER_COLOR = "1F4E79"



def create_save_folder():
   

    if "YourName" in ONEDRIVE_FOLDER:
        print("\n❌  ONEDRIVE_FOLDER not configured!")
        print("    Open tracker.py and set your OneDrive path.")
        print("    Example:")
        print(r"    C:\Users\Aadhitiya\OneDrive - Company\LearningReports")
        import sys; sys.exit(1)

   
    onedrive_root = os.path.dirname(ONEDRIVE_FOLDER)
    if not os.path.exists(onedrive_root):
        print(f"\n❌  OneDrive path not found: {onedrive_root}")
        print("    Make sure OneDrive is installed and signed in.")
        import sys; sys.exit(1)

  
    if not os.path.exists(ONEDRIVE_FOLDER):
        os.makedirs(ONEDRIVE_FOLDER)
        print(f"📁  OneDrive folder created : {ONEDRIVE_FOLDER}")
    else:
        print(f"📁  Saving to OneDrive      : {ONEDRIVE_FOLDER}")

    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{REPORT_NAME}_{timestamp}.xlsx"
    full_path = os.path.join(ONEDRIVE_FOLDER, filename)

    return full_path



def load_csv():

    
    print(f"\n📂  Reading : {INPUT_CSV}")

    if not os.path.exists(INPUT_CSV):
        print(f"\n❌  File not found: {INPUT_CSV}")
        sys.exit(1)

    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    

    def norm(s):
        return re.sub(r"[\s\-_./% ]", "", s.lower())

    rename = {}
    for std_col, variants in COL_MAP.items():
        for raw_col in df.columns:
            raw_n = norm(raw_col)
            if (raw_col.lower().strip() in variants
                    or any(norm(v) == raw_n for v in variants)
                    or any(raw_n in norm(v) or norm(v) in raw_n
                           for v in variants)):
                rename[raw_col] = std_col
                break

    df.rename(columns=rename, inplace=True)

    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        print("❌  Missing columns:")
        for m in missing:
            print(f"    • {m}")
        sys.exit(1)

    def fix_pct(val):
        try:
            return min(100, max(0,
                float(str(val).replace("%", "").strip())))
        except:
            return 0.0

    df["E-LEARNING COMPLETION %"] = (
        df["E-LEARNING COMPLETION %"].apply(fix_pct))
    df["VILT COMPLETION %"] = (
        df["VILT COMPLETION %"].apply(fix_pct))

    df["BEST SCORE"] = pd.to_numeric(
        df["BEST SCORE"].astype(str)
                        .str.replace(r"[^0-9.]", "", regex=True),
        errors="coerce"
    ).fillna(0)

    def derive_status(row):
        el   = float(row["E-LEARNING COMPLETION %"] or 0)
        vilt = float(row["VILT COMPLETION %"]       or 0)
        sc   = float(row["BEST SCORE"]              or 0)
        ex   = str(row["EXEMPTED STATUS"]).lower()

        
        if "yes" in ex or "exempt" in ex:
            return "Exempted"

     
        if sc > 50:
            return "Completed"


        if el == 0 and vilt == 0 and sc == 0:
            return "Not Started"

        if el < 50 and vilt < 50 and sc == 0:
            return "In Progress"

        return "In Progress"

    df["CURRENT STATUS"] = df.apply(derive_status, axis=1)

    def fix_prof(val):
        v = str(val).lower()
        if "adv" in v: return "Advanced"
        if "int" in v: return "Intermediate"
        if "beg" in v or "nov" in v: return "Beginner"
        return str(val).title()

    df["PROFICIENCY"] = df["PROFICIENCY"].apply(fix_prof)

    print(f"✅  Loaded    : {len(df)} employee records")
    return df



def calculate_summary(df):
    total  = len(df)
    cert   = int((df["CURRENT STATUS"] == "Completed").sum())
    inp    = int((df["CURRENT STATUS"] == "In Progress").sum())
    ns     = int((df["CURRENT STATUS"] == "Not Started").sum())
    ex     = int((df["CURRENT STATUS"] == "Exempted").sum())
    scores = df[df["BEST SCORE"] > 0]["BEST SCORE"]
    avg    = round(float(scores.mean()), 1) if len(scores) > 0 else 0.0
    rate   = round((cert / total) * 100, 1) if total > 0 else 0.0

    return {
        "total":       total,
        "certified":   cert,
        "in_progress": inp,
        "not_started": ns,
        "exempted":    ex,
        "avg_score":   avg,
        "rate":        rate,
    }



def build_excel(df, summary, save_path):
    print("📊  Building Excel report...")

    wb  = Workbook()
    thn = Side(style="thin", color="CCCCCC")
    bdr = Border(left=thn, right=thn, top=thn, bottom=thn)

    def hcell(ws, r, c, val, bg=HEADER_COLOR, fg="FFFFFF"):
        cell = ws.cell(row=r, column=c, value=val)
        cell.font      = Font(name="Arial", bold=True,
                               color=fg, size=11)
        cell.fill      = PatternFill("solid", start_color=bg)
        cell.alignment = Alignment(horizontal="center",
                                    vertical="center",
                                    wrap_text=True)
        cell.border    = bdr

    def dcell(ws, r, c, val, bg="FFFFFF",
              bold=False, align="left"):
        cell = ws.cell(row=r, column=c, value=val)
        cell.font      = Font(name="Arial", size=10, bold=bold)
        cell.fill      = PatternFill("solid", start_color=bg)
        cell.alignment = Alignment(horizontal=align,
                                    vertical="center")
        cell.border    = bdr

    WIDTHS = [10, 18, 22, 14, 13, 14, 16, 18, 16, 20, 11, 14, 14]
    NOW    = datetime.now().strftime("%d %b %Y  %I:%M %p")

    
    ws1       = wb.active
    ws1.title = "Progress Report"
    ws1.sheet_properties.tabColor = "1F4E79"
    ws1.freeze_panes = "A4"

    ws1.merge_cells("A1:M1")
    title = ws1.cell(row=1, column=1,
                value=f"Learning Progress Report  |  Generated: {NOW}")
    title.font      = Font(name="Arial", bold=True,
                           size=13, color="FFFFFF")
    title.fill      = PatternFill("solid", start_color=HEADER_COLOR)
    title.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 30

    ws1.merge_cells("A2:M2")
    info = ws1.cell(row=2, column=1,
                value=f"Saved to: {save_path}")
    info.font      = Font(name="Arial", italic=True,
                          size=9, color="555555")
    info.fill      = PatternFill("solid", start_color="EAF0F6")
    info.alignment = Alignment(horizontal="left", vertical="center")
    ws1.row_dimensions[2].height = 16

    for ci, col in enumerate(COLUMNS, 1):
        hcell(ws1, 3, ci, col)
    ws1.row_dimensions[3].height = 18

    current_row = 4
    for status in ["Completed", "In Progress",
                   "Not Started", "Exempted"]:
        group = df[df["CURRENT STATUS"] == status]
        if group.empty:
            continue

        ws1.merge_cells(
            start_row=current_row, start_column=1,
            end_row=current_row,   end_column=13)
        sec = ws1.cell(row=current_row, column=1,
                value=(f"  {status}  ("
                       f"{len(group)} employee"
                       f"{'s' if len(group) > 1 else ''})"))
        sec.font      = Font(name="Arial", bold=True,
                             size=11, color="FFFFFF")
        sec.fill      = PatternFill("solid",
                                    start_color=HEADER_COLOR)
        sec.alignment = Alignment(horizontal="left",
                                  vertical="center")
        ws1.row_dimensions[current_row].height = 22
        current_row += 1

        for ri, (_, row) in enumerate(
                group[COLUMNS].iterrows(), 1):
            alt = "FFFFFF" if ri % 2 == 0 else "F4F8FF"
            for ci, col in enumerate(COLUMNS, 1):
                val   = row[col]
                bg    = (STATUS_COLORS.get(val, alt)
                         if col == "CURRENT STATUS" else alt)
                align = ("right"
                         if col in ("E-LEARNING COMPLETION %",
                                    "VILT COMPLETION %",
                                    "BEST SCORE")
                         else "left")
                dcell(ws1, current_row, ci, val,
                      bg=bg, align=align)
            ws1.row_dimensions[current_row].height = 16
            current_row += 1

        current_row += 1

    for ci, w in enumerate(WIDTHS, 1):
        ws1.column_dimensions[get_column_letter(ci)].width = w

   
    ws2       = wb.create_sheet("Summary")
    ws2.sheet_properties.tabColor = "00B050"

    ws2.merge_cells("A1:C1")
    sh = ws2.cell(row=1, column=1, value="Summary Dashboard")
    sh.font      = Font(name="Arial", bold=True,
                        size=13, color="FFFFFF")
    sh.fill      = PatternFill("solid", start_color="00B050")
    sh.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 28

    for ri, (label, val, color) in enumerate([
        ("Total Employees",       summary["total"],       "BDD7EE"),
        ("Certified / Completed", summary["certified"],   "C6EFCE"),
        ("In Progress",           summary["in_progress"], "FFEB9C"),
        ("Not Started",           summary["not_started"], "F2DCDB"),
        ("Exempted",              summary["exempted"],    "E2D6F5"),
        ("Avg Best Score",        summary["avg_score"],   "FCE4D6"),
        ("Completion Rate (%)",   summary["rate"],        "E2EFDA"),
    ], 3):
        ws2.row_dimensions[ri].height = 26
        dcell(ws2, ri, 1, label, bg=color, bold=True)
        dcell(ws2, ri, 2, val,   bg=color, bold=True, align="center")

    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 16

    
    from openpyxl.chart        import DoughnutChart, Reference
    from openpyxl.chart.series import DataPoint

    ws_donut = wb.create_sheet("Donut Chart")
    ws_donut.sheet_properties.tabColor = "4472C4"

    ws_donut.merge_cells("A1:D1")
    dt           = ws_donut.cell(row=1, column=1,
                    value="Status Distribution — Donut Chart")
    dt.font      = Font(name="Arial", bold=True, size=13, color="FFFFFF")
    dt.fill      = PatternFill("solid", start_color="4472C4")
    dt.alignment = Alignment(horizontal="center", vertical="center")
    ws_donut.row_dimensions[1].height = 28

    for ci, h in enumerate(["Status","Count","Percentage (%)"], 1):
        hcell(ws_donut, 2, ci, h)

    donut_rows = [
        ("Completed",   summary["certified"],   "C6EFCE"),
        ("In Progress", summary["in_progress"], "FFEB9C"),
        ("Not Started", summary["not_started"], "F2DCDB"),
        ("Exempted",    summary["exempted"],    "E2D6F5"),
    ]
    ttl = summary["total"]
    for ri, (status_lbl, count, color_d) in enumerate(donut_rows, 3):
        pct = round((count / ttl * 100), 1) if ttl > 0 else 0
        ws_donut.row_dimensions[ri].height = 22
        dcell(ws_donut, ri, 1, status_lbl, bg=color_d, bold=True)
        dcell(ws_donut, ri, 2, count,      bg=color_d, bold=True, align="center")
        dcell(ws_donut, ri, 3, pct,        bg=color_d, bold=True, align="center")

    ws_donut.column_dimensions["A"].width = 18
    ws_donut.column_dimensions["B"].width = 10
    ws_donut.column_dimensions["C"].width = 16

    
    chart = DoughnutChart()
    chart.title    = "Certification Status Distribution"
    chart.style    = 10
    chart.holeSize = 50

    chart_data   = Reference(ws_donut, min_col=2, min_row=2, max_row=6)
    chart_labels = Reference(ws_donut, min_col=1, min_row=3, max_row=6)
    chart.add_data(chart_data, titles_from_data=True)
    chart.set_categories(chart_labels)

    
    slice_colors = ["10B981", "F59E0B", "EF4444", "A78BFA"]
    for i, hex_c in enumerate(slice_colors):
        pt = DataPoint(idx=i)
        pt.graphicalProperties.solidFill = hex_c
        chart.series[0].dPt.append(pt)

    chart.width  = 15
    chart.height = 14
    ws_donut.add_chart(chart, "F2")
    
    for status, color in STATUS_COLORS.items():
        group = df[df["CURRENT STATUS"] == status]
        if group.empty:
            continue
        ws = wb.create_sheet(status[:31])
        ws.sheet_properties.tabColor = color
        ws.merge_cells("A1:M1")
        t = ws.cell(row=1, column=1,
                value=f"{status}  |  {len(group)} employee(s)  |  {NOW}")
        t.font      = Font(name="Arial", bold=True,
                           size=12, color="FFFFFF")
        t.fill      = PatternFill("solid", start_color=HEADER_COLOR)
        t.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24
        for ci, col in enumerate(COLUMNS, 1):
            hcell(ws, 2, ci, col, bg=color, fg="000000")
        for ri, (_, row) in enumerate(
                group[COLUMNS].iterrows(), 3):
            bg = "FFFFFF" if ri % 2 == 0 else "F9F9F9"
            for ci, col in enumerate(COLUMNS, 1):
                dcell(ws, ri, ci, row[col], bg=bg)
            ws.row_dimensions[ri].height = 15
        for ci, w in enumerate(WIDTHS, 1):
            ws.column_dimensions[get_column_letter(ci)].width = w

    wb.save(save_path)
    print(f"✅  Excel saved  : {save_path}")



def upload_to_snowflake(df):
   
    
    if "your_account" in SNOWFLAKE_ACCOUNT:
        print("\n⚠️   Snowflake credentials not filled in.")
        print("    Open tracker.py and fill in your Snowflake details.")
        print("    Skipping Snowflake upload.")
        return

    print(f"\n❄️   Connecting to Snowflake...")

    try:
       
        conn = snowflake.connector.connect(
            account   = SNOWFLAKE_ACCOUNT,
            user      = SNOWFLAKE_USER,
            password  = SNOWFLAKE_PASSWORD,
            warehouse = SNOWFLAKE_WAREHOUSE,
            database  = SNOWFLAKE_DATABASE,
            schema    = SNOWFLAKE_SCHEMA,
        )
        print("✅  Connected to Snowflake")

        cursor = conn.cursor()

        
        cursor.execute(f"DELETE FROM {SNOWFLAKE_TABLE}")
        print("🗑️   Old data cleared")

       
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(r["EMP ID"]                   or ""),
                str(r["EMP NAME"]                 or ""),
                str(r["SKILL ASSIGNED"]            or ""),
                str(r["PROFICIENCY"]               or ""),
                str(r["TARGET DATE"]               or ""),
                str(r["CURRENT STATUS"]            or ""),
                str(r["LEARNING START DATE"]       or ""),
                float(r["E-LEARNING COMPLETION %"] or 0),
                float(r["VILT COMPLETION %"]       or 0),
                str(r["LEARNING COMPLETION DATE"]  or ""),
                float(r["BEST SCORE"]              or 0),
                str(r["CERTIFIED DATE"]            or ""),
                str(r["EXEMPTED STATUS"]           or ""),
                now,
            ))

        
        insert_sql = f"""
            INSERT INTO {SNOWFLAKE_TABLE} (
                EMP_ID, EMP_NAME, SKILL_ASSIGNED, PROFICIENCY,
                TARGET_DATE, CURRENT_STATUS, LEARNING_START_DATE,
                ELEARNING_COMPLETION_PCT, VILT_COMPLETION_PCT,
                LEARNING_COMPLETION_DATE, BEST_SCORE,
                CERTIFIED_DATE, EXEMPTED_STATUS,
                REPORT_GENERATED_ON
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """
        cursor.executemany(insert_sql, rows)

       
        cursor.execute(f"SELECT COUNT(*) FROM {SNOWFLAKE_TABLE}")
        count = cursor.fetchone()[0]

        print(f"✅  Uploaded to Snowflake!")
        print(f"    Table : {SNOWFLAKE_DATABASE}."
              f"{SNOWFLAKE_SCHEMA}.{SNOWFLAKE_TABLE}")
        print(f"    Rows  : {count} records in table")

        cursor.close()
        conn.close()
        print("🔒  Snowflake connection closed")

    except snowflake.connector.errors.DatabaseError as e:
        print(f"❌  Snowflake database error: {e}")
    except snowflake.connector.errors.OperationalError as e:
        print(f"❌  Snowflake connection error: {e}")
        print("    Check your SNOWFLAKE_ACCOUNT, USER, PASSWORD")
    except Exception as e:
        print(f"❌  Unexpected error: {e}")


def trigger_power_automate(summary, save_path):
    if "PASTE_YOUR" in POWER_AUTOMATE_URL:
        print("\n⚠️   POWER_AUTOMATE_URL not set — skipping email.")
        return

    if "manager@company" in MANAGER_EMAIL:
        print("\n⚠️   MANAGER_EMAIL not set — skipping email.")
        return

    payload = {
        "manager_email": MANAGER_EMAIL,
        "manager_name":  MANAGER_NAME,
        "report_path":   save_path,
        "total":         summary["total"],
        "certified":     summary["certified"],
        "in_progress":   summary["in_progress"],
        "not_started":   summary["not_started"],
        "exempted":      summary["exempted"],
        "avg_score":     summary["avg_score"],
        "rate":          summary["rate"],
        "generated_on":  datetime.now().strftime(
                            "%d %b %Y at %I:%M %p"),
    }

    print(f"\n📤  Triggering Power Automate...")
    try:
        response = requests.post(
            POWER_AUTOMATE_URL,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code in (200, 202):
            print(f"✅  Power Automate triggered!")
            print(f"    Email → {MANAGER_EMAIL}")
        else:
            print(f"❌  Power Automate error: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌  Cannot connect to Power Automate")
    except requests.exceptions.Timeout:
        print("❌  Request timed out")
    except Exception as e:
        print(f"❌  Error: {e}")


def print_summary(df, summary):
    print("\n" + "=" * 58)
    print("   LEARNING PROGRESS TRACKER — SUMMARY")
    print("=" * 58)

    for status in ["Completed", "In Progress",
                   "Not Started", "Exempted"]:
        group = df[df["CURRENT STATUS"] == status]
        if group.empty:
            continue
        print(f"\n  ▶  {status}  ({len(group)} employee(s))")
        print(f"     {'EMP ID':<10} {'Name':<20} "
              f"{'Skill':<22} {'Score':>6}")
        print("     " + "-" * 60)
        for _, r in group.iterrows():
            sc = (int(r["BEST SCORE"])
                  if r["BEST SCORE"] > 0 else "—")
            print(f"     {str(r['EMP ID']):<10} "
                  f"{str(r['EMP NAME']):<20} "
                  f"{str(r['SKILL ASSIGNED']):<22} "
                  f"{str(sc):>6}")

    print("\n" + "=" * 58)
    print("   METRICS")
    print("=" * 58)
    for label, val in [
        ("Total Employees",      summary["total"]),
        ("Certified",            summary["certified"]),
        ("In Progress",          summary["in_progress"]),
        ("Not Started",          summary["not_started"]),
        ("Exempted",             summary["exempted"]),
        ("Avg Best Score",       summary["avg_score"]),
        ("Completion Rate (%)",  summary["rate"]),
    ]:
        print(f"   {label:<28}: {val}")
    print("=" * 58)


def main():
    print("\n" + "=" * 58)
    print("  Learning Progress Tracker")
    print("=" * 58)

   
    save_path = create_save_folder()
    df = load_csv()
    
    summary = calculate_summary(df)
    print_summary(df, summary)
    build_excel(df, summary, save_path)
    upload_to_snowflake(df)
    trigger_power_automate(summary, save_path)
    

    print(f"\n{'='*58}")
    print(f"  ✅  All done!")
    print(f"  📁  Excel    : {save_path}")
    print(f"  ❄️   Snowflake: {SNOWFLAKE_DATABASE}."
          f"{SNOWFLAKE_SCHEMA}.{SNOWFLAKE_TABLE}")
    print(f"  👥  Employees: {summary['total']}")
    print(f"  📈  Rate     : {summary['rate']}% completion")
    print(f"{'='*58}\n")



if __name__ == "__main__":
    main()
