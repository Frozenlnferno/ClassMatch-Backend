from PyPDF2 import PdfReader
from .parser import parse_schedule_pdf
from app.extensions import db_pool
from app.utils.db import db_conn

def extract_courses_from_pdf(file):
    reader = PdfReader(file)
    text = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"

    if not text.strip():
        raise ValueError("Invalid course schedule")
    courses, schedule_info = parse_schedule_pdf(text) 

    return courses, schedule_info

def upload_schedule_to_db(uid, year, term, courses):
    with db_conn() as conn:
        try:
            with conn.cursor() as cur:
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
                            ON CONFLICT DO NOTHING
                        """,
                        (schedule_id, class_id)
                    )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e