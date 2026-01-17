from flask import Blueprint, request, jsonify, g
from app.utils.auth import require_auth

bp = Blueprint("users", __name__)

@bp.route("/me", methods=["GET"])
@require_auth
def get_current_user_info():
    pass