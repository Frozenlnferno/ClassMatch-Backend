from app.utils.db import get_cursor
import secrets
import string

ALPHABET = string.ascii_uppercase  # A–Z

def generate_join_code(length=10):
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))

def create_group(uid, groupName, description):
    if not uid or not groupName:
        raise ValueError("Invalid input: uid and groupName are required")

    with get_cursor() as cur:
        cur.execute(
            """
                INSERT INTO groups (name, description, created_by, join_code)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """,
            (groupName, description, uid, generate_join_code())
        )
        group_id = cur.fetchone()[0]
        cur.execute(
            """
                INSERT INTO group_members (group_id, user_id, role)
                VALUES (%s, %s, %s)
            """,
            (group_id, uid, 'owner')
        )
    return True



