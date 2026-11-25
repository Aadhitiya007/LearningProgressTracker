"""External integrations: Snowflake (multi-warehouse/table) and Power Automate."""

import re
from datetime import datetime
import pandas as pd
import requests

import config
from core.parser import normalize_dataframe

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _safe_ident(name: str, label: str) -> str:
    val = (name or "").strip().strip('"')
    if not val or not _IDENT_RE.match(val):
        raise ValueError(f"Invalid Snowflake {label} name: {name!r}")
    return val


def _connect_snowflake(warehouse: str = "", database: str = "", schema: str = ""):
    if not config.SNOWFLAKE_ACCOUNT or not config.SNOWFLAKE_USER or not config.SNOWFLAKE_PASSWORD:
        raise ValueError("Snowflake credentials not configured in .env")

    try:
        import snowflake.connector
    except ImportError as exc:
        raise RuntimeError("snowflake-connector-python is not installed") from exc

    kwargs = {
        "account": config.SNOWFLAKE_ACCOUNT,
        "user": config.SNOWFLAKE_USER,
        "password": config.SNOWFLAKE_PASSWORD,
    }
    wh = (warehouse or config.SNOWFLAKE_WAREHOUSE).strip()
    db = (database or config.SNOWFLAKE_DATABASE).strip()
    sc = (schema or config.SNOWFLAKE_SCHEMA).strip()
    if wh:
        kwargs["warehouse"] = _safe_ident(wh, "warehouse")
    if db:
        kwargs["database"] = _safe_ident(db, "database")
    if sc:
        kwargs["schema"] = _safe_ident(sc, "schema")
    return snowflake.connector.connect(**kwargs)


def list_snowflake_options(database: str = "", schema: str = "") -> dict:
    """List available Snowflake warehouses, databases, schemas, and tables."""
    conn = _connect_snowflake()
    try:
        cur = conn.cursor()
        cur.execute("SHOW WAREHOUSES")
        warehouses = [row[0] for row in cur.fetchall()]

        cur.execute("SHOW DATABASES")
        databases = [row[1] for row in cur.fetchall()]

        sel_db = (database or config.SNOWFLAKE_DATABASE or (databases[0] if databases else "")).strip()
        schemas = []
        if sel_db:
            cur.execute(f"SHOW SCHEMAS IN DATABASE {_safe_ident(sel_db, 'database')}")
            schemas = [row[1] for row in cur.fetchall()]

        sel_schema = (schema or config.SNOWFLAKE_SCHEMA or (schemas[0] if schemas else "")).strip()
        tables = []
        if sel_db and sel_schema:
            cur.execute(
                f"SHOW TABLES IN SCHEMA {_safe_ident(sel_db, 'database')}.{_safe_ident(sel_schema, 'schema')}"
            )
            tables = [row[1] for row in cur.fetchall()]

        cur.close()
        return {
            "warehouses": warehouses,
            "databases": databases,
            "schemas": schemas,
            "tables": tables,
            "defaults": {
                "warehouse": config.SNOWFLAKE_WAREHOUSE,
                "database": sel_db,
                "schema": sel_schema,
                "table": config.SNOWFLAKE_TABLE,
            },
        }
    finally:
        conn.close()


def fetch_from_snowflake(
    warehouse: str = "",
    database: str = "",
    schema: str = "",
    table: str = "",
    expected_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Pull records from the selected Snowflake warehouse/database/schema/table and normalize them."""
    sel_table = _safe_ident(table or config.SNOWFLAKE_TABLE, "table")
    conn = _connect_snowflake(warehouse=warehouse, database=database, schema=schema)
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {sel_table}")
        cols = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        cursor.close()
        raw_df = pd.DataFrame(data, columns=cols)
        if raw_df.empty:
            return raw_df
        return normalize_dataframe(raw_df, expected_columns=expected_columns)
    finally:
        conn.close()


def upload_to_snowflake(
    df: pd.DataFrame,
    warehouse: str = "",
    database: str = "",
    schema: str = "",
    table: str = "",
) -> dict:
    """Replace table rows inside a transaction so failures roll back cleanly."""
    if not config.SNOWFLAKE_ACCOUNT or not config.SNOWFLAKE_USER or not config.SNOWFLAKE_PASSWORD:
        return {"name": "Snowflake", "status": "skipped", "detail": "Credentials not configured in .env"}

    conn = None
    try:
        sel_table = _safe_ident(table or config.SNOWFLAKE_TABLE, "table")
        conn = _connect_snowflake(warehouse=warehouse, database=database, schema=schema)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            (
                str(r["EMP ID"] or ""),
                str(r["EMP NAME"] or ""),
                str(r["SKILL ASSIGNED"] or ""),
                str(r["PROFICIENCY"] or ""),
                str(r["TARGET DATE"] or ""),
                str(r["CURRENT STATUS"] or ""),
                str(r["LEARNING START DATE"] or ""),
                float(r["E-LEARNING COMPLETION %"] or 0),
                float(r["VILT COMPLETION %"] or 0),
                str(r["LEARNING COMPLETION DATE"] or ""),
                float(r["BEST SCORE"] or 0),
                str(r["CERTIFIED DATE"] or ""),
                str(r["EXEMPTED STATUS"] or ""),
                now,
            )
            for _, r in df.iterrows()
        ]

        cursor.execute("BEGIN")
        cursor.execute(f"DELETE FROM {sel_table}")
        insert_sql = f"""
            INSERT INTO {sel_table} (
                EMP_ID, EMP_NAME, SKILL_ASSIGNED, PROFICIENCY,
                TARGET_DATE, CURRENT_STATUS, LEARNING_START_DATE,
                ELEARNING_COMPLETION_PCT, VILT_COMPLETION_PCT,
                LEARNING_COMPLETION_DATE, BEST_SCORE,
                CERTIFIED_DATE, EXEMPTED_STATUS, REPORT_GENERATED_ON
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.executemany(insert_sql, rows)
        conn.commit()
        cursor.close()
        return {"name": "Snowflake", "status": "ok", "detail": f"Synced {len(rows)} rows to {sel_table}"}
    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"name": "Snowflake", "status": "error", "detail": str(exc)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def trigger_power_automate(summary: dict, report_path: str, overdue: list[dict] | None = None) -> dict:
    """Send summary metrics and overdue alerts to a Power Automate HTTP trigger."""
    if not config.POWER_AUTOMATE_URL or not config.MANAGER_EMAIL:
        return {"name": "Power Automate", "status": "skipped", "detail": "Webhook URL or email not configured in .env"}

    payload = {
        "manager_email": config.MANAGER_EMAIL,
        "manager_name": config.MANAGER_NAME,
        "report_path": report_path,
        "total": summary["total"],
        "certified": summary["certified"],
        "in_progress": summary["in_progress"],
        "not_started": summary["not_started"],
        "exempted": summary["exempted"],
        "avg_score": summary["avg_score"],
        "rate": summary["rate"],
        "overdue_count": len(overdue or []),
        "generated_on": datetime.now().strftime("%d %b %Y at %I:%M %p"),
    }

    try:
        resp = requests.post(
            config.POWER_AUTOMATE_URL,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code in (200, 202):
            return {"name": "Power Automate", "status": "ok", "detail": f"Sent to {config.MANAGER_EMAIL}"}
        return {"name": "Power Automate", "status": "error", "detail": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"name": "Power Automate", "status": "error", "detail": str(exc)}
