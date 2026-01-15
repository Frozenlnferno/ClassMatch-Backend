from PyPDF2 import PdfReader
from .parser import parse_schedule_pdf
from app.utils.db import get_cursor

def extract_courses_from_pdf(file):
    try:
        reader = PdfReader(file)
    except Exception as e:
        raise ValueError(f"Failed to read PDF file: {str(e)}. Please ensure the file is a valid PDF.")

    if len(reader.pages) == 0:
        raise ValueError("PDF file appears to be empty or corrupted.")

    text = ""
    for page in reader.pages:
        try:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        except Exception as e:
            print(f"Warning: Failed to extract text from page: {e}")
            continue

    if not text.strip():
        raise ValueError("No readable text found in PDF. The PDF may be image-based or corrupted.")

    courses, schedule_info = parse_schedule_pdf(text)

    return courses, schedule_info

def add_courses_by_pdf(uid, year, term, courses):
    with get_cursor() as cur:
        # Insert the schedule and get the ID
        cur.execute(
            """
                INSERT INTO schedules (user_id, year, term)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, term, year) DO UPDATE SET year=EXCLUDED.year
                RETURNING id
            """,
            (uid, year, term)
        )
        schedule_id = cur.fetchone()[0]

        # Delete existing schedule-class relationships for this schedule
        cur.execute(
            """
                DELETE FROM schedule_classes
                WHERE schedule_id = %s
            """,
            (schedule_id,)
        )

        # Insert each course
        for course in courses:
            # Insert the course, handling duplicates gracefully
            cur.execute(
                """
                    INSERT INTO classes (year, term, title, subject, number, section, crn)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (year, term, crn) DO UPDATE SET title=EXCLUDED.title
                    RETURNING id
                """,
                (year, term, course["Title"], course["Subject"], course["Subject Number"], course["Section"], course["CRN"])
            )
            class_id = cur.fetchone()[0]
            
            # Link the schedule to the class
            cur.execute(
                """
                    INSERT INTO schedule_classes (schedule_id, class_id)
                    VALUES (%s, %s)
                """,
                (schedule_id, class_id)
            )

# MIGHT NOT IMPLEMENT
def add_courses_by_crn(uid, year, term, crn):
    pass

def remove_schedule(uid, year, term):
    with get_cursor() as cur:
        cur.execute(
            """
                DELETE FROM schedules
                WHERE user_id = %s
                    AND year = %s
                    AND term = %s
            """,
            (uid, year, term)
        )

def remove_courses_from_schedule(uid, year, term, crns):
    with get_cursor() as cur:
        cur.execute(
            """
                DELETE FROM schedule_classes sc
                USING schedules s
                WHERE sc.schedule_id = s.id
                    AND s.user_id = %s
                    AND s.year = %s
                    AND s.term = %s
                    AND sc.class_id IN (
                        SELECT id FROM classes WHERE crn = ANY(%s)
                    )
            """,
            (uid, year, term, crns)
        )

def get_user_schedule(uid, year, term):
    with get_cursor() as cur:
        cur.execute(
            """
                SELECT c.*
                FROM schedules s
                JOIN schedule_classes sc ON sc.schedule_id = s.id
                JOIN classes c ON c.id = sc.class_id
                WHERE s.user_id = %s
                    AND s.year = %s
                    AND s.term = %s;
            """,
            (uid, year, term)
        )
        courses = cur.fetchall()
    return courses or []

def get_matching_classmates(uid, year, term, group_id):
    with get_cursor() as cur:
        cur.execute(
            """
                WITH me AS (
                  SELECT s.id AS my_schedule_id
                  FROM schedules s
                  WHERE s.user_id = %s
                    AND s.year = %s
                    AND s.term = %s
                  LIMIT 1
                ),
                my_classes AS (
                  SELECT sc.class_id
                  FROM schedule_classes sc
                  JOIN me ON me.my_schedule_id = sc.schedule_id
                ),
                group_users AS (
                  SELECT gm.user_id
                  FROM group_members gm
                  WHERE gm.group_id = %s
                ),
                group_schedules AS (
                  SELECT s.id AS schedule_id, s.user_id
                  FROM schedules s
                  JOIN group_users gu ON gu.user_id = s.user_id
                  WHERE s.year = %s
                    AND s.term = %s
                )
                SELECT
                  mc.class_id,
                  u.id   AS member_id,
                  u.name AS member_name
                FROM my_classes mc
                JOIN schedule_classes sc
                  ON sc.class_id = mc.class_id
                JOIN group_schedules gs
                  ON gs.schedule_id = sc.schedule_id
                JOIN users u
                  ON u.id = gs.user_id
                WHERE u.id <> %s
                ORDER BY mc.class_id, u.name;
            """,
            (uid, year, term, group_id, year, term, uid)
        )
        matches = cur.fetchall()
    return matches or []

