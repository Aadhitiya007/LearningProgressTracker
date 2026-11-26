"""Stateless Flask API for Learning Progress Tracker."""

import json
import os
import tempfile
from datetime import datetime
import pandas as pd
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

import config
from core.parser import load_csv, calculate_summary, find_overdue_records
from core.exporter import build_excel
from core.integrations import (
    upload_to_snowflake,
    trigger_power_automate,
    fetch_from_snowflake,
    list_snowflake_options,
)
from core.connectors import list_tables, fetch_table, join_with_learning_data
from core.ml_engine import run_full_analysis

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


@app.route("/api/process", methods=["POST"])
def process():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename or not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "error": "Please upload a .csv file."}), 400

    run_snowflake = request.form.get("snowflake", "true").lower() == "true"
    run_automate = request.form.get("automate", "true").lower() == "true"
    run_excel = request.form.get("excel", "true").lower() == "true"

    sf_wh = request.form.get("warehouse", "").strip()
    sf_db = request.form.get("database", "").strip()
    sf_sc = request.form.get("schema", "").strip()
    sf_tbl = request.form.get("table", "").strip()

    expected_columns = None
    raw_expected = request.form.get("expected_columns", "").strip()
    if raw_expected:
        try:
            parsed_cols = json.loads(raw_expected)
            if isinstance(parsed_cols, list):
                expected_columns = parsed_cols
        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "Invalid expected_columns JSON."}), 400

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
        uploaded.save(tmp)
        tmp_path = tmp.name

    steps = []
    try:
        df = load_csv(tmp_path, expected_columns=expected_columns)
        summary = calculate_summary(df)
        rows = df.fillna("").to_dict(orient="records")
        overdue = find_overdue_records(rows)

        excel_filename = ""
        excel_path = ""
        if run_excel:
            try:
                res = build_excel(df, summary)
                excel_filename = res["filename"]
                excel_path = res["path"]
                detail = res["onedrive_path"] or res["path"]
                steps.append({"name": "Excel / OneDrive", "status": "ok", "detail": detail})
            except Exception as exc:
                steps.append({"name": "Excel / OneDrive", "status": "error", "detail": str(exc)})
        else:
            steps.append({"name": "Excel / OneDrive", "status": "skipped"})

        if run_snowflake:
            steps.append(upload_to_snowflake(df, warehouse=sf_wh, database=sf_db, schema=sf_sc, table=sf_tbl))
        else:
            steps.append({"name": "Snowflake", "status": "skipped"})

        if run_automate:
            steps.append(trigger_power_automate(summary, excel_path, overdue))
        else:
            steps.append({"name": "Power Automate", "status": "skipped"})

        return jsonify({
            "success": True,
            "summary": summary,
            "rows": rows,
            "overdue": overdue,
            "steps": steps,
            "excel_file": excel_filename,
            "count": len(rows),
        })

    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.route("/api/snowflake/options", methods=["GET"])
def api_snowflake_options():
    database = request.args.get("database", "").strip()
    schema = request.args.get("schema", "").strip()
    try:
        opts = list_snowflake_options(database=database, schema=schema)
        return jsonify({"success": True, **opts})
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "defaults": {
                "warehouse": config.SNOWFLAKE_WAREHOUSE,
                "database": config.SNOWFLAKE_DATABASE,
                "schema": config.SNOWFLAKE_SCHEMA,
                "table": config.SNOWFLAKE_TABLE,
            },
        }), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/snowflake/pull", methods=["GET", "POST"])
def api_snowflake_pull():
    payload = request.get_json(silent=True) or {}
    warehouse = (payload.get("warehouse") or request.args.get("warehouse") or "").strip()
    database = (payload.get("database") or request.args.get("database") or "").strip()
    schema = (payload.get("schema") or request.args.get("schema") or "").strip()
    table = (payload.get("table") or request.args.get("table") or "").strip()
    expected_columns = payload.get("expected_columns")

    try:
        df = fetch_from_snowflake(
            warehouse=warehouse,
            database=database,
            schema=schema,
            table=table,
            expected_columns=expected_columns,
        )
        if df.empty:
            return jsonify({"success": False, "error": "No records found in selected Snowflake table."}), 404
        summary = calculate_summary(df)
        rows = df.fillna("").to_dict(orient="records")
        overdue = find_overdue_records(rows)
        return jsonify({
            "success": True,
            "summary": summary,
            "rows": rows,
            "overdue": overdue,
            "count": len(rows),
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/connectors/tables", methods=["POST"])
def api_connector_tables():
    payload = request.get_json(silent=True) or {}
    db_url = (payload.get("db_url") or "").strip()
    schema = (payload.get("schema") or "").strip()
    try:
        tables = list_tables(db_url, schema=schema)
        return jsonify({"success": True, "tables": tables})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/analysis/run", methods=["POST"])
def api_analysis_run():
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows") or []
    if not rows:
        return jsonify({"success": False, "error": "No learning data rows provided."}), 400

    db_url = (payload.get("db_url") or "").strip()
    table_name = (payload.get("table") or "").strip()
    schema = (payload.get("schema") or "").strip()
    left_key = (payload.get("left_key") or "EMP ID").strip()
    right_key = (payload.get("right_key") or "").strip()

    try:
        df = pd.DataFrame(rows)
        joined_info = "None (Learning data only)"
        if db_url and table_name:
            sec_df = fetch_table(db_url, table_name, schema=schema)
            df = join_with_learning_data(df, sec_df, left_key=left_key, right_key=right_key)
            joined_info = f"{table_name} ({len(sec_df)} rows)"

        analysis = run_full_analysis(df)
        analysis["joined_source"] = joined_info
        return jsonify({"success": True, **analysis})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/export/excel", methods=["POST"])
def api_export_excel():
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows") or []
    if not rows:
        return jsonify({"success": False, "error": "No rows provided to export."}), 400
    try:
        df = pd.DataFrame(rows)
        summary = calculate_summary(df)
        res = build_excel(df, summary)
        return send_file(
            res["path"],
            as_attachment=True,
            download_name=res["filename"],
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/download/<filename>")
def download(filename):
    safe_name = secure_filename(filename)
    if not safe_name or not safe_name.lower().endswith(".xlsx"):
        return jsonify({"success": False, "error": "Invalid filename."}), 400
    full_path = os.path.join(config.REPORTS_DIR, safe_name)
    if not os.path.isfile(full_path):
        return jsonify({"success": False, "error": "Report not found."}), 404
    return send_from_directory(config.REPORTS_DIR, safe_name, as_attachment=True)


if __name__ == "__main__":
    print("\n" + "=" * 58)
    print("  Learning Tracker — Flask API")
    print("  Open  http://localhost:5000  in your browser")
    print("=" * 58 + "\n")
    app.run(debug=False, port=5000)
