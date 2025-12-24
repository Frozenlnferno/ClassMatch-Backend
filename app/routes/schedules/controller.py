from flask import request, jsonify, g
from . import bp
from app.utils.auth import require_auth
from .service import extract_courses_from_pdf, add_courses_by_pdf, get_user_schedule

@bp.route("/", methods=["GET"])
@require_auth
def get_schedule():
    user_id = g.user["sub"]
    term = request.args.get("term")
    year = request.args.get("year")
    
    if not term or term not in {"fall", "winter", "spring", "summer"}:
        return jsonify({"error": "Invalid term"}), 400
    
    if not year:
        return jsonify({"error": "Invalid year"}), 400
    
    try: 
        year = int(year)
        if year < 2000 or year > 2100:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Invalid year"}), 400

    courses = get_user_schedule(user_id, year, term)
    return jsonify(courses)

@bp.route("/upload", methods=["POST"])
@require_auth
def upload_schedule():
    user_id = g.user["sub"]
    pdf = request.files.get("pdf")

    if not pdf:
        return jsonify({"error": "no pdf uploaded"}), 400

    try:
        courses, schedule_info = extract_courses_from_pdf(pdf)
        add_courses_by_pdf(user_id, schedule_info["year"], schedule_info["term"], courses)
        
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
