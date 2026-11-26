"""ML models for training priority prediction and company growth forecasting."""

from datetime import datetime, date
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression


def _parse_date(val: str) -> date | None:
    s = str(val or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _prof_num(val: str) -> int:
    v = str(val or "").lower()
    if "adv" in v:
        return 3
    if "int" in v:
        return 2
    if "beg" in v:
        return 1
    return 1


def predict_training_priority(df: pd.DataFrame, ref_date: date | None = None) -> tuple[list[dict], str]:
    """
    Identify employees who need training and rank them by ML-predicted risk of missing completion.
    Uses RandomForestClassifier when enough completed/incomplete samples exist; otherwise uses
    weighted risk scoring.
    """
    today = ref_date or date.today()
    work = df.copy()

    el = pd.to_numeric(work.get("E-LEARNING COMPLETION %", 0), errors="coerce").fillna(0.0)
    vilt = pd.to_numeric(work.get("VILT COMPLETION %", 0), errors="coerce").fillna(0.0)
    score = pd.to_numeric(work.get("BEST SCORE", 0), errors="coerce").fillna(0.0)
    prof = work.get("PROFICIENCY", pd.Series(["Beginner"] * len(work))).apply(_prof_num)

    days_left = []
    for td in work.get("TARGET DATE", pd.Series([""] * len(work))):
        dt = _parse_date(td)
        days_left.append((dt - today).days if dt else 30)
    days_series = pd.Series(days_left, index=work.index)

    X = pd.DataFrame({
        "el": el,
        "vilt": vilt,
        "score": score,
        "prof": prof,
        "days_left": days_series,
    })

    # Binary label: 1 = needs training / at-risk (Not Started or In Progress), 0 = Completed
    status_series = work.get("CURRENT STATUS", pd.Series([""] * len(work)))
    non_exempt = status_series != "Exempted"
    y = (status_series.isin(["Not Started", "In Progress"])).astype(int)

    model_used = "Weighted Risk Heuristic (<10 samples)"
    risk_probs = np.zeros(len(work))

    if non_exempt.sum() >= 10 and y[non_exempt].nunique() == 2:
        clf = RandomForestClassifier(n_estimators=60, max_depth=4, random_state=42)
        clf.fit(X[non_exempt], y[non_exempt])
        probs = clf.predict_proba(X)
        # Probability of class 1 (needs training / at-risk)
        class_idx = list(clf.classes_).index(1)
        risk_probs = probs[:, class_idx]
        model_used = "RandomForestClassifier (scikit-learn)"
    else:
        # Transparent statistical risk score for small datasets
        avg_prog = (el + vilt) / 2.0
        time_pressure = np.clip((30.0 - days_series) / 45.0, 0.0, 1.0)
        prog_gap = np.clip((100.0 - avg_prog) / 100.0, 0.0, 1.0)
        risk_probs = np.clip(0.65 * prog_gap + 0.35 * time_pressure, 0.05, 0.99)

    results = []
    for idx, row in work.iterrows():
        st = str(row.get("CURRENT STATUS", ""))
        if st in ("Completed", "Exempted"):
            continue

        risk_pct = round(float(risk_probs[idx]) * 100, 1)
        d_left = int(days_series.loc[idx])
        el_v = float(el.loc[idx])
        vilt_v = float(vilt.loc[idx])

        # Blend ML probability with urgency if already overdue
        if d_left < 0:
            risk_pct = max(risk_pct, 85.0)
        elif st == "Not Started":
            risk_pct = max(risk_pct, 70.0)

        if risk_pct >= 75:
            priority = "High"
        elif risk_pct >= 45:
            priority = "Medium"
        else:
            priority = "Low"

        reasons = []
        if st == "Not Started":
            reasons.append("Not started yet")
        if d_left < 0:
            reasons.append(f"Overdue by {abs(d_left)}d")
        elif d_left <= 14:
            reasons.append(f"Due in {d_left}d")
        if el_v < 50:
            reasons.append(f"eLearning {int(el_v)}%")
        if vilt_v < 50:
            reasons.append(f"VILT {int(vilt_v)}%")

        dept = ""
        for col_cand in ("Department", "DEPARTMENT", "department", "Team", "TEAM"):
            if col_cand in work.columns and str(row.get(col_cand, "")).strip():
                dept = str(row.get(col_cand, "")).strip()
                break

        results.append({
            "emp_id": str(row.get("EMP ID", "")),
            "emp_name": str(row.get("EMP NAME", "")),
            "skill": str(row.get("SKILL ASSIGNED", "")),
            "proficiency": str(row.get("PROFICIENCY", "")),
            "department": dept,
            "status": st,
            "target_date": str(row.get("TARGET DATE", "")),
            "elearning_pct": el_v,
            "vilt_pct": vilt_v,
            "risk_score": risk_pct,
            "priority": priority,
            "reason": ", ".join(reasons) or "In progress",
        })

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return results, model_used


def forecast_company_growth(df: pd.DataFrame, months_ahead: int = 4) -> dict:
    """
    Aggregate monthly certification progress and forecast company readiness growth
    using scikit-learn LinearRegression.
    """
    total = len(df)
    if total == 0:
        return {"labels": [], "actual": [], "forecast": [], "readiness_pct": 0.0, "projected_pct": 0.0, "model": "None"}

    completed_df = df[df["CURRENT STATUS"] == "Completed"].copy()
    month_counts: dict[str, int] = {}

    for _, row in completed_df.iterrows():
        dt = _parse_date(row.get("CERTIFIED DATE")) or _parse_date(row.get("LEARNING COMPLETION DATE")) or _parse_date(row.get("LEARNING START DATE"))
        if dt:
            ym = dt.strftime("%Y-%m")
            month_counts[ym] = month_counts.get(ym, 0) + 1

    if not month_counts:
        # Fallback if no completion dates exist yet: build current month baseline
        ym_now = date.today().strftime("%Y-%m")
        month_counts[ym_now] = len(completed_df)

    sorted_months = sorted(month_counts.keys())
    cum_counts = []
    running = 0
    for m in sorted_months:
        running += month_counts[m]
        cum_counts.append(round((running / total) * 100, 1))

    # Fit LinearRegression on cumulative readiness %
    X_idx = np.arange(len(sorted_months)).reshape(-1, 1)
    y_pct = np.array(cum_counts)

    if len(sorted_months) >= 2:
        reg = LinearRegression()
        reg.fit(X_idx, y_pct)
        slope = float(reg.coef_[0])
        # Ensure non-negative growth trajectory if slope is flat
        if slope <= 0:
            slope = max(2.5, round((100.0 - y_pct[-1]) / max(months_ahead, 1), 1))
        model_name = "LinearRegression (scikit-learn)"
    else:
        # Single month baseline: project steady improvement from in-progress learners
        in_prog = int((df["CURRENT STATUS"] == "In Progress").sum())
        slope = round(max(4.0, (in_prog / total) * 25.0), 1)
        model_name = "Baseline Velocity Projection"

    last_y, last_m = map(int, sorted_months[-1].split("-"))
    future_labels = []
    future_vals = []
    last_actual = cum_counts[-1]

    for step in range(1, months_ahead + 1):
        nm = last_m + step
        ny = last_y + (nm - 1) // 12
        nm = ((nm - 1) % 12) + 1
        future_labels.append(f"{ny:04d}-{nm:02d}")
        proj = min(100.0, round(last_actual + slope * step, 1))
        future_vals.append(proj)

    labels = sorted_months + future_labels
    actual_series = cum_counts + [None] * len(future_labels)
    forecast_series = [None] * (len(cum_counts) - 1) + [cum_counts[-1]] + future_vals

    return {
        "labels": labels,
        "actual": actual_series,
        "forecast": forecast_series,
        "readiness_pct": cum_counts[-1],
        "projected_pct": future_vals[-1] if future_vals else cum_counts[-1],
        "monthly_velocity_pct": round(slope, 1),
        "model": model_name,
    }


def compute_skill_gaps(df: pd.DataFrame) -> list[dict]:
    """Compute completed vs. needing-training headcount per skill (or department)."""
    if "SKILL ASSIGNED" not in df.columns or df.empty:
        return []

    gaps = []
    for skill, grp in df.groupby("SKILL ASSIGNED"):
        skill_name = str(skill or "").strip() or "Unassigned"
        total = len(grp)
        done = int((grp["CURRENT STATUS"] == "Completed").sum())
        needs_train = int(grp["CURRENT STATUS"].isin(["Not Started", "In Progress"]).sum())
        rate = round((done / total) * 100, 1) if total > 0 else 0.0
        gaps.append({
            "skill": skill_name,
            "total": total,
            "completed": done,
            "needs_training": needs_train,
            "readiness_pct": rate,
        })

    gaps.sort(key=lambda x: x["needs_training"], reverse=True)
    return gaps


def run_full_analysis(df: pd.DataFrame) -> dict:
    """Run both ML models and skill-gap analysis on a normalized DataFrame."""
    training_list, risk_model = predict_training_priority(df)
    growth = forecast_company_growth(df)
    skill_gaps = compute_skill_gaps(df)

    high_risk = sum(1 for r in training_list if r["priority"] == "High")
    return {
        "training_priority": training_list,
        "growth": growth,
        "skill_gaps": skill_gaps,
        "models": {
            "risk_model": risk_model,
            "growth_model": growth["model"],
        },
        "kpis": {
            "total_employees": len(df),
            "needs_training_count": len(training_list),
            "high_risk_count": high_risk,
            "current_readiness_pct": growth["readiness_pct"],
            "projected_readiness_pct": growth["projected_pct"],
        },
    }
