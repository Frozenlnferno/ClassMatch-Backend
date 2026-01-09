from flask import request, jsonify, g, Blueprint
from app.utils.auth import require_auth
from .service import create_group, join_group

bp = Blueprint("groups", __name__)

@bp.route("/", methods=["GET"])
def index():
    return jsonify("")

@bp.route("/create", methods=["POST"])
@require_auth
def create():
    user_id = g.user["sub"]
    try:
        create_group(
            user_id,
            request.form.get("groupName"),
            request.form.get("description"),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Group created successfully"}), 201

@bp.route("/join", methods=["GET"])
@require_auth
def join():
    user_id = g.user["sub"]
    join_code = request.args.get("join_code")

    try:
        status = join_group(user_id, join_code)
        if not status:
            return jsonify({"status": "User is already a member"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Group joined successfully"}), 200