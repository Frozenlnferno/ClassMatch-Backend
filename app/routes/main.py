from flask import Blueprint, jsonify, request

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    return "Server is running."

