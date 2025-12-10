from flask import Blueprint, jsonify, request
from PyPDF2 import PdfReader
import json
import re

from ..utils.auth import require_auth

bp = Blueprint("schedule", __name__)

@bp.route("/", methods=["GET"])
@require_auth
def test():
    return jsonify({"Done": True})

@bp.route("/upload", methods=["POST"])
@require_auth
def upload_schedule():
    user_id = request.user["sub"]

    pdf_file = request.files.get("pdf")
    if not pdf_file:
        return jsonify({"error": "no pdf uploaded"}), 400

    # parse pdf
    try:
        reader = PdfReader(pdf_file)
        pdf_text = ""
        course_list = []

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                pdf_text += extracted + "\n"

        if not pdf_text == "":
            regex = (
                r"(.+?)\s+"                    # title (group 1)
                r"([A-Z]{2,4})\s*"             # subject (group 2)
                r"(\d{3})\s+"                  # number (group 3)
                r"([A-Za-z0-9]+)\s+"           # section (group 4)
                r"([\d.]+)\s+"                 # credit hours (group 5)
                r"(\d{5})\s+"                  # CRN (group 6)
                r"(\d{2}/\d{2}/\d{4})"         # start date (group 7)
                r"\s*-\s*"
                r"(\d{2}/\d{2}/\d{4})"         # end date (group 8)
            )

            courses = re.findall(
                regex,
                pdf_text 
            )   

            if len(courses) == 0:
                return jsonify({"error": "Invalid course schedule!"}), 400

            for course in courses:
                course_list.append({
                    "Title" : course[0],
                    "Subject" : course[1],
                    "Subject Number" : course[2],
                    "Section" : course[3],
                    "Credit Hours" : course[4],
                    "CRN" : course[5],
                    "Start Date" : course[6],
                    "End Date" : course[7],
                })
        else:
            return jsonify({"error": "Invalid course schedule!"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "user_id": user_id,
        "Courses": course_list
    })