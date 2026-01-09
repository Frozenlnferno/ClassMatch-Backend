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

def join_group(uid, join_code):
    if not uid or not join_code:
        raise ValueError("Invalid input: uid and join_code are required")

    with get_cursor() as cur:
        # Check if group with join_code exists
        cur.execute(
            """
                SELECT id, joinable FROM groups WHERE join_code = %s;
            """,
            (join_code,)
        )
        group_data = cur.fetchone()
        if not group_data:
            raise ValueError("Invalid join code")

        # Check if open
        group_id = group_data[0]
        is_joinable = group_data[1]
        if not is_joinable:
            raise ValueError("Group is not joinable")

        # Try to add user as member
        cur.execute(
            """
                INSERT INTO group_members (group_id, user_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (group_id, user_id) DO NOTHING
                RETURNING group_id;
            """,
            (group_id, uid, 'member')
        )
        result = cur.fetchone()
        if not result:
            return False # User is already member
    return True

