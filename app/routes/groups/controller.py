from flask import request, jsonify, g, Blueprint

bp = Blueprint("groups", __name__)

@bp.route("/", method=["GET"])
def index():
    return jsonify("")

@bp.route("/create", method=["POST"])
def create():
    
    return jsonify("")