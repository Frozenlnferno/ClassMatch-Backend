from app.utils.db import get_cursor
import secrets
import string

ALPHABET = string.ascii_uppercase  # A–Z

def generate_join_code(length=10):
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))

def create_group(uid, groupName, description, joinable=True):
    if not uid or not groupName:
        raise ValueError("Invalid input: uid and groupName are required")

    with get_cursor() as cur:
        cur.execute(
            """
                INSERT INTO groups (name, description, created_by, join_code, joinable)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """,
            (groupName, description, uid, generate_join_code(), joinable)
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
            return -1 # User is already member
    return group_id

def leave_group(uid, group_id):
    if not uid or not group_id:
        raise ValueError("Invalid input: uid and group_id are required")

    with get_cursor() as cur:
        cur.execute(
            """
                SELECT role FROM group_members
                WHERE group_id = %s AND user_id = %s;
            """,
            (group_id, uid)
        )
        role = cur.fetchone()
        if not role:
            raise ValueError("User is not a member of the group")
        
        # Remove user from group
        cur.execute( 
            """
                DELETE FROM group_members
                WHERE group_id = %s AND user_id = %s;
            """,
            (group_id, uid)
        )

        if role[0] == 'owner':
            # Upon leaving, transfer ownership to oldest joining admin and if none, oldest member
            cur.execute(
                """
                    SELECT user_id FROM group_members
                    WHERE group_id = %s AND role = 'admin'
                    ORDER BY joined_at ASC
                    LIMIT 1;
                """,
                (group_id,)
            )
            admin_user_id = cur.fetchone()
            if admin_user_id:
                cur.execute(
                    """
                        UPDATE group_members
                        SET role = 'owner'
                        WHERE group_id = %s AND user_id = %s;
                    """,
                    (group_id, admin_user_id[0])
                )
            else:
                # Find oldest member to transfer ownership
                cur.execute(
                    """
                        SELECT user_id FROM group_members
                        WHERE group_id = %s AND role = 'member'
                        ORDER BY joined_at ASC
                        LIMIT 1;
                    """,
                    (group_id,)
                )
                oldest_member = cur.fetchone()
                if oldest_member:
                    cur.execute(
                        """
                            UPDATE group_members
                            SET role = 'owner'
                            WHERE group_id = %s AND user_id = %s;
                        """,
                        (group_id, oldest_member[0])
                    )
                else:
                    # No other members, delete group
                    cur.execute(
                        """
                            DELETE FROM groups
                            WHERE id = %s;
                        """,
                        (group_id,)
                    )
    return True

def change_group_info(admin_uid, group_id, name, description, joinable):
    if not admin_uid or not group_id:
        raise ValueError("Invalid input: admin_uid and group_id are required")

    fields = []
    values = []

    if name is not None:
        fields.append("name = %s")
        values.append(name)
    
    if description is not None:
        fields.append("description = %s")
        values.append(description)

    if joinable is not None and joinable == True or joinable == False:
        fields.append("joinable = %s")
        values.append(joinable)

    if not fields:
        return 0  # nothing to update
    
    values.append(group_id)

    query = f"""
        UPDATE groups
        SET {', '.join(fields)}
        WHERE id = %s
    """

    with get_cursor() as cur:
        # Check if admin_uid is an admin of the group
        cur.execute(
            """
                SELECT role FROM group_members
                WHERE group_id = %s AND user_id = %s;
            """,
            (group_id, admin_uid)
        )
        admin_data = cur.fetchone()
        if not admin_data or (admin_data[0] != 'admin' and admin_data[0] != 'owner'):
            raise PermissionError("User does not have permission to change group settings")

        # Update group's info
        cur.execute(query, values)
    return True

def kick_member(admin_uid, member_uid, group_id):
    if not admin_uid or not member_uid or not group_id:
        raise ValueError("Invalid input: admin_uid, member_uid, and group_id are required")

    with get_cursor() as cur:
        # Check if admin_uid is an admin of the group
        cur.execute(
            """
                SELECT role FROM group_members
                WHERE group_id = %s AND (user_id = %s OR user_id = %s);
            """,
            (group_id, admin_uid, member_uid)
        )
        admin_data = cur.fetchone()
        if not admin_data or (admin_data[0] != 'admin' and admin_data[0] != 'owner'):
            raise PermissionError("User does not have permission to kick members")

        # Check if admin_uid has the permission to kick member_uid (from role hierarchy)
        cur.execute(
            """
                SELECT role FROM group_members
                WHERE group_id = %s AND user_id = %s;
            """,
            (group_id, member_uid)
        )
        member_data = cur.fetchone()
        if not member_data or member_data[0] == 'owner' or (admin_data[0] != 'owner' and member_data[0] == 'admin'):
            raise PermissionError("Cannot kick this member")

        # Remove member_uid from the group
        cur.execute(
            """
                DELETE FROM group_members
                WHERE group_id = %s AND user_id = %s;
            """,
            (group_id, member_uid)
        )
    return True

def get_user_groups(uid):
    if not uid:
        raise ValueError("Invalid input: uid is required")

    with get_cursor() as cur:
        cur.execute(
            """
                SELECT
                g.id,
                g.name,
                g.join_code,
                gm.role,
                (
                    SELECT COUNT(*)
                    FROM group_members gm2
                    WHERE gm2.group_id = g.id
                ) AS member_count,
                g.joinable
                FROM groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = %s;
            """,
            (uid,)
        )
        rows = cur.fetchall() or []

    return [
        {
            "id": row[0],
            "name": row[1],
            "join_code": row[2],
            "role": row[3],
            "member_count": row[4],
            "joinable": row[5],
        }
        for row in rows
    ]

def get_group_members(group_id):
    if not group_id:
        raise ValueError("Invalid input: group_id is required")

    with get_cursor() as cur:
        cur.execute(
            """
                SELECT u.id, u.name, gm.role
                FROM users u
                JOIN group_members gm ON u.id = gm.user_id
                WHERE gm.group_id = %s;
            """,
            (group_id,)
        )
        rows = cur.fetchall() or []

    return [
        {
            "user_id": row[0],
            "name": row[1],
            "role": row[2],
        }
        for row in rows
    ]

def change_group_role(admin_uid, member_uid, group_id, new_role):
    if not admin_uid or not member_uid or not group_id or not new_role:
        raise ValueError("Invalid input: admin_uid, member_uid, group_id, and new_role are required")

    valid_roles = ['member', 'admin', 'owner']
    if new_role not in valid_roles:
        raise ValueError("Invalid role specified")

    with get_cursor() as cur:
        # Check if admin_uid is an admin of the group
        cur.execute(
            """
                SELECT role FROM group_members
                WHERE group_id = %s AND user_id = %s;
            """,
            (group_id, admin_uid)
        )
        admin_data = cur.fetchone()
        if not admin_data or (admin_data[0] != 'admin' and admin_data[0] != 'owner'):
            raise PermissionError("User does not have permission to change roles")

        # Check if admin_uid has the permission to change member_uid's role (from role hierarchy)
        cur.execute(
            """
                SELECT role FROM group_members
                WHERE group_id = %s AND user_id = %s;
            """,
            (group_id, member_uid)
        )
        member_data = cur.fetchone()
        if not member_data:
            raise ValueError("Member not found in the group")
        if member_data[0] == 'owner' or (admin_data[0] != 'owner' and member_data[0] == 'admin'):
            raise PermissionError("Cannot change this member's role")

        # Update member's role
        cur.execute(
            """
                UPDATE group_members
                SET role = %s
                WHERE group_id = %s AND user_id = %s;
            """,
            (new_role, group_id, member_uid)
        )
    return True