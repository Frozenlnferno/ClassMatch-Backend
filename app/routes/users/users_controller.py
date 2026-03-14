from flask import Blueprint, request, jsonify, g
from app.utils.auth import require_auth
from app.utils.logger import get_logger

from .users_service import get_self_info, get_user_info, update_self_info

bp = Blueprint("users", __name__)
logger = get_logger(__name__)

@bp.route("/me", methods=["GET"])
@require_auth
def get_current_user_info():
    try:
        user_id = g.user["sub"]
        user_info = get_self_info(user_id)
    except Exception as e:
        logger.exception("Error getting self info", extra={"error": str(e)})
        return jsonify({"error": "Failed to retrieve self info"}), 500
    return jsonify(user_info)

@bp.route("/me", methods=["PATCH"])
@require_auth
def update_current_user_info():
    try:
        user_id = g.user["sub"]
        data = request.get_json(silent=True) or {}

        name = data["name"] if "name" in data else None
        bio = data["bio"] if "bio" in data else None
        avatar_url = data["avatar_url"] if "avatar_url" in data else None
        update_self_info(user_id, name, bio, avatar_url)
    except Exception as e:
        logger.exception("Error updating self info", extra={"error": str(e)})
        return jsonify({"error": "Failed to update self info"}), 500
    return jsonify({"status": "Successfully updated self info"}), 200

@bp.route("/<user_id>", methods=["GET"])
@require_auth
def get_public_user_info(user_id):
    try:
        user_info = get_user_info(user_id)
    except Exception as e:
        logger.exception("Error getting user info", extra={"error": str(e)})
        return jsonify({"error": "Failed to retrieve user info"}), 500
    return jsonify(user_info)

