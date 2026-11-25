"""CLI runner and inbox folder watcher automation."""

import argparse
import os
import shutil
import sys
import time
from datetime import datetime

import config
from core.parser import load_csv, calculate_summary, find_overdue_records
from core.exporter import build_excel
from core.integrations import upload_to_snowflake, trigger_power_automate

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def process_file(csv_path: str, run_integrations: bool = True) -> dict:
    """Run the full pipeline on a single CSV file."""
    print(f"\n[Tracker] Processing: {csv_path}")
    df = load_csv(csv_path)
    summary = calculate_summary(df)
    rows = df.fillna("").to_dict(orient="records")
    overdue = find_overdue_records(rows)

    excel_res = build_excel(df, summary)

    print(f"  Records   : {summary['total']} | Completed: {summary['certified']} ({summary['rate']}%)")
    print(f"  Overdue   : {len(overdue)} alert(s)")
    print(f"  Excel     : {excel_res['path']}")

    if run_integrations:
        sf = upload_to_snowflake(df)
        pa = trigger_power_automate(summary, excel_res["path"], overdue)
        print(f"  Snowflake : {sf['status']} ({sf.get('detail', '')})")
        print(f"  Automate  : {pa['status']} ({pa.get('detail', '')})")

    return {"summary": summary, "overdue": overdue, "excel": excel_res}


def watch_inbox(interval_sec: int = 5) -> None:
    """Watch inbox/ for new CSV files, process them, and move to archive/."""
    os.makedirs(config.INBOX_DIR, exist_ok=True)
    os.makedirs(config.ARCHIVE_DIR, exist_ok=True)
    print(f"Watching folder: {config.INBOX_DIR} (every {interval_sec}s, Ctrl+C to stop)")

    while True:
        try:
            files = sorted(
                f for f in os.listdir(config.INBOX_DIR)
                if f.lower().endswith(".csv")
            )
            for name in files:
                src = os.path.join(config.INBOX_DIR, name)
                try:
                    process_file(src, run_integrations=True)
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest = os.path.join(config.ARCHIVE_DIR, f"{stamp}_{name}")
                    shutil.move(src, dest)
                    print(f"  Archived  : {dest}")
                except Exception as exc:
                    print(f"  [ERROR] Failed {name}: {exc}")
            time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("\nWatcher stopped.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Learning Progress Tracker CLI & Watcher")
    parser.add_argument("--file", default=config.DEFAULT_INPUT_CSV, help="Path to CSV file")
    parser.add_argument("--watch", action="store_true", help="Watch inbox/ folder for new CSVs")
    parser.add_argument("--no-integrations", action="store_true", help="Skip Snowflake & Power Automate")
    args = parser.parse_args()

    if args.watch:
        watch_inbox()
    else:
        process_file(args.file, run_integrations=not args.no_integrations)


if __name__ == "__main__":
    main()
