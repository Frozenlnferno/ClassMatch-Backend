from app.utils import get_cursor

def create_group(uid, groupName, description):
    if not uid or not groupName:
        raise ValueError("Invalid input: uid and groupName are required")

    with get_cursor() as cur:
        cur.execute(
            """
                INSERT INTO groups (name, description, created_by)
                VALUES (%s, %s, %s)
            """,
            (groupName, description, uid)
        )
    return True