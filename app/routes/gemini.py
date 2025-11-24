from flask import Blueprint, jsonify, request
import json

bp = Blueprint("gemini", __name__)

from google import genai

client = genai.Client(api_key="AIzaSyD4YlvN3H7BeAjdYYXfvPMcl_13Ou-TXwo")

@bp.route("/")
def index():
    prompt = """
    Create a JSON object describing a course:

    {
      "title": "",
      "course_code": "",
      "days": []
    }

    Return ONLY valid JSON. No explanation, no code block formatting.
    Output must begin with { and end with }.

    """

    res = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    # Extract text
    text_output = res.text
    

    # Convert to actual Python object
    obj = json.loads(text_output)
    # Return as real JSON to frontend
    return jsonify(obj)
