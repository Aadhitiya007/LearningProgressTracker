import os
import io
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS


from tracker import (
    load_csv,
    calculate_summary,
    build_excel,
    upload_to_snowflake,
    trigger_power_automate,
    create_save_folder,
    ONEDRIVE_FOLDER,
    REPORT_NAME,
)

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
        return jsonify({"success": False,
                        "error": "No file uploaded."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"success": False,
                        "error": "Please upload a .csv file."}), 400

    
    run_snowflake  = request.form.get("snowflake",  "true").lower() == "true"
    run_automate   = request.form.get("automate",   "true").lower() == "true"
    run_excel      = request.form.get("excel",      "true").lower() == "true"

    
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False,
                                     mode="wb") as tmp:
        uploaded.save(tmp)
        tmp_path = tmp.name

    steps = []  

    try:
       
        import pandas as pd

        
        import tracker as _t
        _orig = _t.INPUT_CSV
        _t.INPUT_CSV = tmp_path

        df = load_csv()
        _t.INPUT_CSV = _orig      

        summary = calculate_summary(df)

        
        excel_path = None
        excel_step = {"name": "Excel / OneDrive", "status": "skipped"}
        if run_excel:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename  = f"{REPORT_NAME}_{timestamp}.xlsx"

               
                if ONEDRIVE_FOLDER and "YourName" not in ONEDRIVE_FOLDER:
                    os.makedirs(ONEDRIVE_FOLDER, exist_ok=True)
                    excel_path = os.path.join(ONEDRIVE_FOLDER, filename)
                else:
                    excel_path = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), filename)

                build_excel(df, summary, excel_path)
                excel_step = {"name": "Excel / OneDrive",
                              "status": "ok",
                              "detail": excel_path}
            except Exception as e:
                excel_step = {"name": "Excel / OneDrive",
                              "status": "error",
                              "detail": str(e)}
        steps.append(excel_step)

        
        sf_step = {"name": "Snowflake", "status": "skipped"}
        if run_snowflake:
            try:
                upload_to_snowflake(df)
                sf_step = {"name": "Snowflake", "status": "ok"}
            except SystemExit:
                sf_step = {"name": "Snowflake", "status": "skipped",
                           "detail": "Credentials not configured"}
            except Exception as e:
                sf_step = {"name": "Snowflake", "status": "error",
                           "detail": str(e)}
        steps.append(sf_step)

        
        pa_step = {"name": "Power Automate", "status": "skipped"}
        if run_automate and excel_path:
            try:
                trigger_power_automate(summary, excel_path)
                pa_step = {"name": "Power Automate", "status": "ok"}
            except SystemExit:
                pa_step = {"name": "Power Automate", "status": "skipped",
                           "detail": "URL or email not configured"}
            except Exception as e:
                pa_step = {"name": "Power Automate", "status": "error",
                           "detail": str(e)}
        steps.append(pa_step)

       
        rows = df.fillna("").to_dict(orient="records")

        return jsonify({
            "success":  True,
            "summary":  summary,
            "rows":     rows,
            "steps":    steps,
            "excel":    excel_path or "",
            "count":    len(df),
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass



@app.route("/api/download/<path:filename>")
def download(filename):
    directory = os.path.dirname(os.path.abspath(filename))
    base      = os.path.basename(filename)
    return send_from_directory(directory, base, as_attachment=True)



if __name__ == "__main__":
    print("\n" + "=" * 58)
    print("  Learning Tracker — Flask API")
    print("  Open  http://localhost:5000  in your browser")
    print("=" * 58 + "\n")
    app.run(debug=True, port=5000)