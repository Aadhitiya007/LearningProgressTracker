"""Stateless secondary database connectors (PostgreSQL, MySQL, SQL Server, SQLite, etc.)."""

import re
import pandas as pd
from sqlalchemy import create_engine, inspect, text

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _safe_table(name: str) -> str:
    val = (name or "").strip().strip('"').strip("`").strip("[]")
    if not val or not _IDENT_RE.match(val):
        raise ValueError(f"Invalid table name: {name!r}")
    return val


def list_tables(db_url: str, schema: str = "") -> list[str]:
    """List available tables from any SQLAlchemy-compatible database URL."""
    if not db_url or not db_url.strip():
        raise ValueError("Database connection URL is required.")
    engine = create_engine(db_url.strip(), pool_pre_ping=True)
    try:
        insp = inspect(engine)
        return insp.get_table_names(schema=schema.strip() or None)
    finally:
        engine.dispose()


def fetch_table(db_url: str, table_name: str, schema: str = "", limit: int = 5000) -> pd.DataFrame:
    """Fetch rows from a secondary database table into a DataFrame (read-only, stateless)."""
    if not db_url or not db_url.strip():
        raise ValueError("Database connection URL is required.")
    tbl = _safe_table(table_name)
    full_tbl = f"{_safe_table(schema)}.{tbl}" if schema and schema.strip() else tbl

    engine = create_engine(db_url.strip(), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            query = text(f"SELECT * FROM {full_tbl}")
            df = pd.read_sql_query(query, conn)
            if limit and len(df) > limit:
                df = df.head(limit)
            return df
    finally:
        engine.dispose()


def join_with_learning_data(
    learning_df: pd.DataFrame,
    secondary_df: pd.DataFrame,
    left_key: str = "EMP ID",
    right_key: str = "",
) -> pd.DataFrame:
    """Left-join learning progress data with a secondary HR/Project/Company table."""
    if secondary_df is None or secondary_df.empty:
        return learning_df.copy()

    l_key = left_key.strip()
    if l_key not in learning_df.columns:
        raise ValueError(f"Join column {l_key!r} not found in learning data.")

    r_key = right_key.strip()
    if not r_key:
        # Auto-detect matching column name case-insensitively
        norm_l = re.sub(r"[\s_]+", "", l_key.lower())
        for c in secondary_df.columns:
            if re.sub(r"[\s_]+", "", str(c).lower()) == norm_l:
                r_key = str(c)
                break
        if not r_key:
            raise ValueError("Could not auto-detect join key in secondary table. Specify right_key.")
    elif r_key not in secondary_df.columns:
        raise ValueError(f"Join column {r_key!r} not found in secondary table.")

    left = learning_df.copy()
    right = secondary_df.copy()
    left["_join_key"] = left[l_key].astype(str).str.strip().str.upper()
    right["_join_key"] = right[r_key].astype(str).str.strip().str.upper()

    # Avoid duplicate column collisions
    overlap = [c for c in right.columns if c in left.columns and c != "_join_key"]
    right = right.drop(columns=overlap)

    merged = left.merge(right, on="_join_key", how="left").drop(columns=["_join_key"])
    return merged
