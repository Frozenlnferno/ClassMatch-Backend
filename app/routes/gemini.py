from flask import Blueprint, jsonify, request
import json
import os

bp = Blueprint("gemini", __name__)

from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
