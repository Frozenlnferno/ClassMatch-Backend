from flask import request, jsonify
from . import bp
from app.utils.auth import require_auth
from .service import extract_courses_from_pdf, upload_schedule_to_db
from app.utils.db import db_conn

@bp.route("/", methods=["GET"])
@require_auth
def index():
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users;")
            return cur.fetchall()

@bp.route("/upload", methods=["POST"])
@require_auth
def upload_schedule():
    user_id = request.user["sub"]
    pdf = request.files.get("pdf")

    if not pdf:
        return jsonify({"error": "no pdf uploaded"}), 400

    try:
        courses, schedule_info = extract_courses_from_pdf(pdf)
        upload_schedule_to_db(user_id, schedule_info["year"], schedule_info["term"], courses)
        
        return jsonify({
            "user_id": user_id,
            "Courses": courses,
            "Term": schedule_info["term"],
            "Year": schedule_info["year"]
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500
