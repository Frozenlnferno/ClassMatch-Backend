from flask import request, jsonify, g, Blueprint
from app.utils.auth import require_auth
from .service import create_group, join_group, get_user_groups, leave_group, kick_member, get_group_members, change_group_role, change_group_joinable

bp = Blueprint("groups", __name__)

@bp.route("/", methods=["GET"])
@require_auth
def get_groups_route():
    # Get all groups the user is a member of
    user_id = g.user["sub"]
    try:
        groups = get_user_groups(user_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(groups), 200

@bp.route("/create", methods=["POST"])
@require_auth
def create_group_route():
    # Create a new group; user becomes owner
    user_id = g.user["sub"]
    try:
        # accept joinable flag from client (default True)
        data = request.get_json(silent=True) or {}
        joinable = data["joinable"] if "joinable" in data else None
        if joinable is None:
            joinable = True
        create_group(
            user_id,
            data["groupName"] if "groupName" in data else None,
            data["description"] if "description" in data else None,
            joinable,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Group created successfully"}), 201

@bp.route("/join", methods=["GET"])
@require_auth
def join_group_route():
    # Join a group using a join code
    user_id = g.user["sub"]
    join_code = request.args.get("join_code")

    try:
        status = join_group(user_id, join_code)
        if not status:
            return jsonify({"status": "User is already a member"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Group joined successfully"}), 200

@bp.route("/leave", methods=["POST"])
@require_auth
def leave_group_route():
    # Remove user from a group
    user_id = g.user["sub"]
    data = request.get_json(silent=True) or {}
    group_id = data["group_id"] if "group_id" in data else None

    try:
        leave_group(user_id, group_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Left group successfully"}), 200

@bp.route("/change-joinable", methods=["POST"])
@require_auth
def change_joinable_route():
    # Change a group's joinable status (admin/owner only)
    admin_id = g.user["sub"]
    data = request.get_json(silent=True) or {}
    group_id = data["group_id"] if "group_id" in data else None
    new_status = data["joinable"] if "joinable" in data else None

    try:
        change_group_joinable(admin_id, group_id, new_status)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Joinable status changed successfully"}), 200

@bp.route("/<group_id>/members", methods=["GET"])
@require_auth
def get_members_route(group_id):
    # Get all members in a group
    try:
        members = get_group_members(group_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(members), 200

@bp.route("/<group_id>/kick", methods=["POST"])
@require_auth
def kick_member_route(group_id):
    # Remove a member from group (admin/owner only)
    # group_id comes from the URL path
    admin_id = g.user["sub"]
    data = request.get_json(silent=True) or {}
    member_id = data["member_id"] if "member_id" in data else None

    try:
        kick_member(admin_id, member_id, group_id)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Member kicked successfully"}), 200

@bp.route("/<group_id>/change-role", methods=["POST"])
@require_auth
def change_role_route(group_id):
    # Change a member's role (admin/owner only)
    admin_id = g.user["sub"]
    data = request.get_json(silent=True) or {}
    member_id = data["member_id"] if "member_id" in data else None
    new_role = data["new_role"] if "new_role" in data else None

    try:
        change_group_role(admin_id, member_id, group_id, new_role)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "Role changed successfully"}), 200