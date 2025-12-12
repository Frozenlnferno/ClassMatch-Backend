from flask import request, jsonify
from . import bp
from ...utils.auth import require_auth
from .service import extract_courses_from_pdf

@bp.route("/", methods=["GET"])
@require_auth
def index():
    return jsonify("Done")

@bp.route("/upload", methods=["POST"])
@require_auth
def upload_schedule():
    user_id = request.user["sub"]
    pdf = request.files.get("pdf")

    if not pdf:
        return jsonify({"error": "no pdf uploaded"}), 400

    try:
        courses = extract_courses_from_pdf(pdf)
        return jsonify({
            "user_id": user_id,
            "Courses": courses
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "server error"}), 500
