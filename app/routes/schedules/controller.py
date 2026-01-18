from flask import request, jsonify, g, Blueprint
from app.utils.auth import require_auth
from .service import extract_courses_from_pdf, add_courses_by_pdf, get_user_schedule, get_matching_classmates, remove_schedule, remove_courses_from_schedule
from app.utils.validators import validate_year_term

bp = Blueprint("schedule", __name__)

@bp.route("/", methods=["GET"])
@require_auth
def get_schedule_route():
    user_id = g.user["sub"]
    year, term, error_response, error_code = validate_year_term()
    
    if error_response:
        return error_response, error_code
    
    try:
        courses = get_user_schedule(user_id, year, term)
        return jsonify(courses)
    except Exception as e:
        print(f"Error getting user schedule: {e}")
        return jsonify({"error": "Failed to retrieve schedule"}), 500

@bp.route("/", methods=["POST"])
@require_auth
def create_schedule():
    user_id = g.user["sub"]
    pdf = request.files.get("pdf")

    if not pdf:
        return jsonify({"error": "No PDF file uploaded"}), 400

    # Validate file type
    if not pdf.filename or not pdf.filename.lower().endswith('.pdf'):
        return jsonify({"error": "File must be a PDF"}), 400

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
        # PDF parsing errors (empty PDF, invalid format, etc.)
        print(f"PDF parsing error: {e}")
        return jsonify({"error": f"Failed to parse PDF: {str(e)}"}), 400
    except Exception as e:
        # Database errors, unexpected exceptions
        print(f"Unexpected error uploading schedule: {e}")
        return jsonify({"error": "Failed to upload schedule. Please try again."}), 500

@bp.route("/", methods=["DELETE"])
@require_auth
def delete_schedule():
    user_id = g.user["sub"]
    year, term, error_response, error_code = validate_year_term()
    
    if error_response:
        return error_response, error_code

    try:
        remove_schedule(user_id, year, term)
        return jsonify({"message": "Schedule deleted successfully"})
    except Exception as e:
        print(f"Error deleting schedule: {e}")
        return jsonify({"error": "Failed to delete schedule"}), 500

@bp.route("/courses", methods=["DELETE"])
@require_auth
def delete_schedule_courses():
    user_id = g.user["sub"]
    data = request.get_json(silent=True) or {}
    crns = data["crns"] if "crns" in data else []
    year, term, error_response, error_code = validate_year_term()
    
    if error_response:
        return error_response, error_code

    if not isinstance(crns, list) or not all(isinstance(crn, str) for crn in crns):
        return jsonify({"error": "Invalid crns"}), 400

    try:
        remove_courses_from_schedule(user_id, year, term, crns)
        return jsonify({"message": "Courses removed successfully"})
    except Exception as e:
        print(f"Error removing courses: {e}")
        return jsonify({"error": "Failed to remove courses"}), 500

@bp.route("/matching-classmates", methods=["GET"])
@require_auth
def get_matching_classmates_route():
    user_id = g.user["sub"]
    group_id = request.args.get("group_id")
    
    year, term, error_response, error_code = validate_year_term()
    if error_response:
        return error_response, error_code
    
    if not group_id:
        return jsonify({"error": "Invalid group_id"}), 400
    
    try:
        matches = get_matching_classmates(user_id, year, term, group_id)
        return jsonify(matches)
    except Exception as e:
        print(e)
        return jsonify({"error": "Internal server error"}), 500