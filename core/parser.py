"""CSV parsing, column normalization, status derivation, and summary metrics."""

import os
import re
from datetime import datetime, date
import pandas as pd

from config import PASSING_SCORE, OVERDUE_WARN_DAYS

COL_MAP = {
    "EMP ID": [
        "emp id", "employee id", "empid", "emp_id", "emp. id", "empno", "emp no",
    ],
    "EMP NAME": [
        "emp name", "employee name", "name", "empname", "emp_name", "emp. name", "employee",
    ],
    "SKILL ASSIGNED": [
        "skill assigned", "skill", "skills assigned", "skill name", "skill_assigned", "assigned skill",
    ],
    "PROFICIENCY": [
        "proficiency", "level", "proficiency level", "prof", "profiency",
    ],
    "TARGET DATE": [
        "target date", "target_date", "target completion date", "targetdate", "target dt",
    ],
    "CURRENT STATUS": [
        "current status", "status", "current_status", "currentstatus",
    ],
    "LEARNING START DATE": [
        "learning start date", "start date", "learning_start_date", "startdate", "learning start dt",
    ],
    "E-LEARNING COMPLETION %": [
        "e-learning completion %", "elearning completion %",
        "elearning completion percentage", "e-learning completion percentage",
        "e learning completion percentage", "elearningcompletionpercentage",
        "elearning%", "e-learning%", "e learning completion %",
        "elearning %", "e-learning %", "online learning %",
    ],
    "VILT COMPLETION %": [
        "vilt completion %", "vilt %", "vilt completion",
        "vilt completion percentage", "viltcompletionpercentage",
        "vilt%", "vilt complete %",
    ],
    "LEARNING COMPLETION DATE": [
        "learning completion date", "completion date", "learning_completion_date",
    ],
    "BEST SCORE": [
        "best score", "score", "best_score", "top score", "bestscore",
    ],
    "CERTIFIED DATE": [
        "certified date", "certification date", "cert date", "certified_date",
    ],
    "EXEMPTED STATUS": [
        "exempted status", "exempted", "exempt status", "exempt", "is exempted",
    ],
}

COLUMNS = list(COL_MAP.keys())


def _norm(text: str) -> str:
    return re.sub(r"[\s\-_./% ]", "", str(text).lower())


def _fix_pct(val) -> float:
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return min(100.0, max(0.0, float(cleaned))) if cleaned else 0.0
    except Exception:
        return 0.0


def _derive_status(row: pd.Series) -> str:
    el = float(row["E-LEARNING COMPLETION %"] or 0)
    vilt = float(row["VILT COMPLETION %"] or 0)
    sc = float(row["BEST SCORE"] or 0)
    ex = str(row["EXEMPTED STATUS"] or "").lower()
    raw_status = str(row["CURRENT STATUS"] or "").strip().lower()

    if "yes" in ex or "exempt" in ex:
        return "Exempted"
    if sc > PASSING_SCORE or (el >= 100 and vilt >= 100) or raw_status == "completed":
        return "Completed"
    if el == 0 and vilt == 0 and sc == 0:
        return "Not Started"
    return "In Progress"


def _fix_prof(val) -> str:
    v = str(val or "").lower()
    if "adv" in v:
        return "Advanced"
    if "int" in v:
        return "Intermediate"
    if "beg" in v or "nov" in v:
        return "Beginner"
    return str(val or "").strip().title() or "Unknown"


def normalize_dataframe(df: pd.DataFrame, expected_columns: list[str] | None = None) -> pd.DataFrame:
    """Normalize column names, percentages, scores, proficiency, and derived status."""
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()

    active_cols = [c.strip() for c in expected_columns if str(c).strip()] if expected_columns is not None else list(COLUMNS)
    if not active_cols:
        raise ValueError("Expected columns list cannot be empty.")

    rename = {}
    matched_targets = set()
    for target_col in active_cols:
        variants = COL_MAP.get(target_col.upper(), [target_col.lower()])
        if target_col.lower() not in variants:
            variants = [target_col.lower()] + list(variants)

        for raw_col in df.columns:
            if raw_col in rename:
                continue
            raw_n = _norm(raw_col)
            if (
                raw_col.lower().strip() in variants
                or any(_norm(v) == raw_n for v in variants)
                or any(raw_n in _norm(v) or _norm(v) in raw_n for v in variants)
            ):
                std_name = target_col.upper() if target_col.upper() in COL_MAP else target_col
                rename[raw_col] = std_name
                matched_targets.add(target_col)
                break

    missing = [c for c in active_cols if c not in matched_targets]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    df.rename(columns=rename, inplace=True)

    # Ensure standard columns exist with safe defaults if removed by manager
    for std_col in COLUMNS:
        if std_col not in df.columns:
            df[std_col] = 0.0 if std_col in ("E-LEARNING COMPLETION %", "VILT COMPLETION %", "BEST SCORE") else ""

    subset_cols = [c for c in ("EMP ID", "EMP NAME") if c in df.columns]
    if subset_cols:
        df = df.dropna(subset=subset_cols, how="all").copy()
    if df.empty:
        raise ValueError("No valid employee rows found.")

    df["E-LEARNING COMPLETION %"] = df["E-LEARNING COMPLETION %"].apply(_fix_pct)
    df["VILT COMPLETION %"] = df["VILT COMPLETION %"].apply(_fix_pct)
    df["BEST SCORE"] = (
        pd.to_numeric(
            df["BEST SCORE"].astype(str).str.replace(r"[^0-9.]", "", regex=True),
            errors="coerce",
        )
        .fillna(0.0)
    )

    for text_col in [
        "EMP ID", "EMP NAME", "SKILL ASSIGNED", "TARGET DATE",
        "LEARNING START DATE", "LEARNING COMPLETION DATE",
        "CERTIFIED DATE", "EXEMPTED STATUS",
    ]:
        df[text_col] = df[text_col].fillna("").astype(str).str.strip()

    df["CURRENT STATUS"] = df.apply(_derive_status, axis=1)
    df["PROFICIENCY"] = df["PROFICIENCY"].apply(_fix_prof)

    return df


def load_csv(csv_path: str, expected_columns: list[str] | None = None) -> pd.DataFrame:
    """Load, normalize, and validate a learning progress CSV file."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    return normalize_dataframe(df, expected_columns=expected_columns)


def calculate_summary(df: pd.DataFrame) -> dict:
    """Compute aggregate metrics from a normalized DataFrame."""
    total = len(df)
    cert = int((df["CURRENT STATUS"] == "Completed").sum())
    inp = int((df["CURRENT STATUS"] == "In Progress").sum())
    ns = int((df["CURRENT STATUS"] == "Not Started").sum())
    ex = int((df["CURRENT STATUS"] == "Exempted").sum())
    scores = df[df["BEST SCORE"] > 0]["BEST SCORE"]
    avg = round(float(scores.mean()), 1) if len(scores) > 0 else 0.0
    rate = round((cert / total) * 100, 1) if total > 0 else 0.0

    return {
        "total": total,
        "certified": cert,
        "in_progress": inp,
        "not_started": ns,
        "exempted": ex,
        "avg_score": avg,
        "rate": rate,
    }


def find_overdue_records(rows: list[dict], today: date | None = None) -> list[dict]:
    """Return records that are past target date or due within OVERDUE_WARN_DAYS."""
    ref_day = today or date.today()
    alerts = []
    for r in rows:
        status = r.get("CURRENT STATUS", "")
        if status in ("Completed", "Exempted"):
            continue
        target_str = str(r.get("TARGET DATE", "")).strip()
        if not target_str:
            continue
        try:
            target_dt = datetime.strptime(target_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue

        days_left = (target_dt - ref_day).days
        if days_left <= OVERDUE_WARN_DAYS:
            alerts.append({
                "emp_id": r.get("EMP ID", ""),
                "emp_name": r.get("EMP NAME", ""),
                "skill": r.get("SKILL ASSIGNED", ""),
                "status": status,
                "target_date": target_str[:10],
                "days_left": days_left,
                "severity": "overdue" if days_left < 0 else "due_soon",
            })
    alerts.sort(key=lambda x: x["days_left"])
    return alerts
