from app.utils.db import get_cursor

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
        return 0  # nothing to update

    values.append(user_id)

    query = f"""
        UPDATE public.users
        SET {', '.join(fields)}
        WHERE id = %s
    """

    with get_cursor() as cur:
        cur.execute(query, values)

