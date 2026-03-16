from app.routes.groups.groups_service import reassign_or_delete_group, remove_group_member
from app.utils.db import get_cursor
from app.utils.supabase_admin import get_supabase_admin_client


def get_self_info(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
                SELECT * FROM users WHERE id = %s
            """,
            (user_id,)
        )
        user = cur.fetchone()
    return {
        "id": user[0],
        "email": user[1],
        "name": user[2],
        "created_at": user[3],
        "bio": user[4],
        "avatar_url": user[5],
    }


def get_user_info(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
                SELECT id, name, created_at, bio, avatar_url FROM users WHERE id = %s
            """,
            (user_id,)
        )
        user = cur.fetchone()
    return {
        "id": user[0],
        "name": user[1],
        "created_at": user[2],
        "bio": user[3],
        "avatar_url": user[4],
    }


def update_self_info(user_id, name=None, bio=None, avatar_url=None):
    fields = []
    values = []

    if name is not None:
        fields.append("name = %s")
        values.append(name)

    if bio is not None:
        fields.append("bio = %s")
        values.append(bio)

    if avatar_url is not None:
        fields.append("avatar_url = %s")
        values.append(avatar_url)

    if not fields:
        return 0

    values.append(user_id)

    query = f"""
        UPDATE public.users
        SET {', '.join(fields)}
        WHERE id = %s
    """

    with get_cursor() as cur:
        cur.execute(query, values)


def _delete_supabase_auth_user(user_id):
    supabase_admin = get_supabase_admin_client()
    supabase_admin.auth.admin.delete_user(user_id)


def delete_self_account(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
                SELECT id
                FROM groups
                WHERE created_by = %s
                ORDER BY created_at ASC, id ASC;
            """,
            (user_id,)
        )
        owned_groups = cur.fetchall() or []

        for row in owned_groups:
            group_id = row[0]
            cur.execute(
                """
                    SELECT 1
                    FROM group_members
                    WHERE group_id = %s AND user_id = %s
                    LIMIT 1;
                """,
                (group_id, user_id)
            )
            if cur.fetchone():
                remove_group_member(cur, user_id, group_id)
            else:
                reassign_or_delete_group(cur, group_id)

        _delete_supabase_auth_user(user_id)
