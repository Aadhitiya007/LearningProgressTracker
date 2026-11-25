"""Central configuration loaded from .env (if present) and environment variables."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
INBOX_DIR = os.path.join(BASE_DIR, "inbox")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")
DEFAULT_INPUT_CSV = os.path.join(BASE_DIR, "LearningAdoptionReport.csv")


def _load_dotenv(env_path: str) -> None:
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv(os.path.join(BASE_DIR, ".env"))

ONEDRIVE_FOLDER = os.getenv("ONEDRIVE_FOLDER", "").strip()
REPORT_NAME = os.getenv("REPORT_NAME", "Learning_Progress_Report").strip()

POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_URL", "").strip()
MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "").strip()
MANAGER_NAME = os.getenv("MANAGER_NAME", "").strip()

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT", "").strip()
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER", "").strip()
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD", "").strip()
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "TRACKER_WH").strip()
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "LEARNING_TRACKER").strip()
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "CERTIFICATION_DATA").strip()
SNOWFLAKE_TABLE = os.getenv("SNOWFLAKE_TABLE", "EMPLOYEE_CERTIFICATIONS").strip()

PASSING_SCORE = float(os.getenv("PASSING_SCORE", "50"))
OVERDUE_WARN_DAYS = int(os.getenv("OVERDUE_WARN_DAYS", "7"))
