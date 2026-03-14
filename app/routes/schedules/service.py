import xml.etree.ElementTree as ET

import requests
from PyPDF2 import PdfReader

from app.utils.db import get_cursor

from .parser import parse_schedule_pdf

UIUC_EXPLORER_URL = "https://courses.illinois.edu/cisapp/explorer/schedule/{year}/{term}/{subject}/{course}/{crn}.xml"
UIUC_API_TIMEOUT_SECONDS = 10


def _normalize_text(value):
    return " ".join(value.split()) if value else ""


def _local_name(tag_name):
    return tag_name.split("}", 1)[-1]


def _iter_named_elements(root, names):
    for element in root.iter():
        if _local_name(element.tag) in names:
            yield element


def _find_first_text(root, names):
    for element in _iter_named_elements(root, names):
        text = _normalize_text("".join(element.itertext()))
        if text:
            return text
    return ""


def _find_first_attribute(root, element_names, attribute_names):
    for element in _iter_named_elements(root, element_names):
        for attribute_name in attribute_names:
            value = _normalize_text(element.attrib.get(attribute_name, ""))
            if value:
                return value
    return ""


def _find_all_text(root, names):
    values = []
    for element in _iter_named_elements(root, names):
        text = _normalize_text("".join(element.itertext()))
        if text:
            values.append(text)
    return values


def _extract_subject_code(root):
    subject_code = _find_first_text(root, {"subjectCode", "subject"})
    if subject_code.isupper() and 2 <= len(subject_code) <= 5:
        return subject_code

    subject_code = _find_first_attribute(root, {"subject"}, {"id", "code"})
    return subject_code.upper()


def _extract_course_number(root):
    course_number = _find_first_text(root, {"courseNumber", "number"})
    if course_number:
        return course_number

    return _find_first_attribute(root, {"course"}, {"id", "number"})


def _extract_course_title(root):
    title = _find_first_text(root, {"courseTitle", "title", "label"})
    if title:
        return title

    for element in _iter_named_elements(root, {"course"}):
        title = _normalize_text("".join(element.itertext()))
        if title:
            return title

        title = _normalize_text(element.attrib.get("label", ""))
        if title:
            return title

    return ""


def _extract_section(root):
    section = _find_first_text(root, {"sectionNumber", "sectionId"})
    if section:
        return section

    section = _find_first_attribute(root, {"section", "detailedSection"}, {"id", "sectionNumber"})
    if section:
        return section

    return ""


def _extract_crn(root):
    crn = _find_first_text(root, {"referenceNumber", "crn"})
    if crn:
        return crn

    return _find_first_attribute(root, {"section", "detailedSection"}, {"id"})


def _extract_course_type(root):
    return _find_first_text(root, {"sectionType", "type", "typeCode"})


def _extract_instructors(root):
    instructors = _find_all_text(root, {"instructor", "name"})
    unique_instructors = []
    for instructor in instructors:
        if instructor not in unique_instructors:
            unique_instructors.append(instructor)
    return ", ".join(unique_instructors)


def _extract_building(root):
    return _find_first_text(root, {"buildingName", "building"})


def _extract_room_number(root):
    return _find_first_text(root, {"roomNumber", "room"})


def _extract_meeting_time(root, tag_names):
    raw_value = _find_first_text(root, tag_names)
    if not raw_value:
        return None

    for time_format in ("%H:%M", "%H:%M:%S"):
        try:
            import datetime
            return datetime.datetime.strptime(raw_value, time_format).time()
        except ValueError:
            continue

    return None


def _extract_days_of_week(root):
    return _find_first_text(root, {"daysOfWeek", "days"})


def extract_schedule_identifiers_from_pdf(file):
    try:
        reader = PdfReader(file)
    except Exception as exc:
        raise ValueError(f"Failed to read PDF file: {str(exc)}. Please ensure the file is a valid PDF.") from exc

    if len(reader.pages) == 0:
        raise ValueError("PDF file appears to be empty or corrupted.")

    text = ""
    for page in reader.pages:
        try:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        except Exception as exc:
            print(f"Warning: Failed to extract text from page: {exc}")
            continue

    if not text.strip():
        raise ValueError("No readable text found in PDF. The PDF may be image-based or corrupted.")

    return parse_schedule_pdf(text)


def _fetch_uiuc_course(year, term, identifier):
    subject = identifier["Subject"]
    course_number = identifier["Subject Number"]
    crn = identifier["CRN"]
    url = UIUC_EXPLORER_URL.format(
        year=year,
        term=term,
        subject=subject,
        course=course_number,
        crn=crn,
    )

    try:
        response = requests.get(url, timeout=UIUC_API_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise ValueError(
            f"Failed to reach the UIUC course API for {subject} {course_number} CRN {crn}: {exc}"
        ) from exc

    if response.status_code == 404:
        raise ValueError(
            f"UIUC course not found for {subject} {course_number} CRN {crn} in {term} {year}."
        )

    if response.status_code != 200:
        raise ValueError(
            f"UIUC course API request failed for {subject} {course_number} CRN {crn} with status {response.status_code}."
        )

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise ValueError(
            f"UIUC course API returned malformed XML for {subject} {course_number} CRN {crn}."
        ) from exc

    title = _extract_course_title(root)
    section = _extract_section(root)
    api_subject = _extract_subject_code(root) or subject
    api_course_number = _extract_course_number(root) or course_number
    api_crn = _extract_crn(root) or crn

    if not title:
        raise ValueError(
            f"UIUC course API response was missing the course title for {subject} {course_number} CRN {crn}."
        )

    if not section:
        raise ValueError(
            f"UIUC course API response was missing the section for {subject} {course_number} CRN {crn}."
        )

    if api_subject.upper() != subject.upper() or api_course_number != course_number or api_crn != crn:
        raise ValueError(
            f"UIUC course API returned mismatched data for {subject} {course_number} CRN {crn}."
        )

    return {
        "Title": title,
        "Subject": api_subject.upper(),
        "Subject Number": api_course_number,
        "Section": section,
        "CRN": api_crn,
        "Course Type": _extract_course_type(root) or None,
        "Instructor": _extract_instructors(root) or None,
        "Building": _extract_building(root) or None,
        "Room Number": _extract_room_number(root) or None,
        "Start Time": _extract_meeting_time(root, {"startTime"}) ,
        "End Time": _extract_meeting_time(root, {"endTime"}),
        "Days of Week": _extract_days_of_week(root) or None,
    }


def resolve_courses_from_uiuc(year, term, course_identifiers):
    return [_fetch_uiuc_course(year, term, identifier) for identifier in course_identifiers]


def add_courses_by_pdf(uid, year, term, courses):
    with get_cursor() as cur:
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

        cur.execute(
            """
                DELETE FROM schedule_sections
                WHERE schedule_id = %s
            """,
            (schedule_id,)
        )

        for course in courses:
            cur.execute(
                """
                    INSERT INTO classes (subject, number, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (subject, number) DO UPDATE
                    SET title = EXCLUDED.title
                    RETURNING id
                """,
                (
                    course["Subject"],
                    course["Subject Number"],
                    course["Title"],
                )
            )
            class_id = cur.fetchone()[0]

            cur.execute(
                """
                    INSERT INTO sections (
                        class_id,
                        year,
                        term,
                        section,
                        crn,
                        course_type,
                        instructor,
                        building,
                        room_number,
                        start_time,
                        end_time,
                        days_of_week
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (year, term, crn) DO UPDATE
                    SET class_id = EXCLUDED.class_id,
                        section = EXCLUDED.section,
                        course_type = EXCLUDED.course_type,
                        instructor = EXCLUDED.instructor,
                        building = EXCLUDED.building,
                        room_number = EXCLUDED.room_number,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        days_of_week = EXCLUDED.days_of_week
                    RETURNING id
                """,
                (
                    class_id,
                    year,
                    term,
                    course["Section"],
                    course["CRN"],
                    course["Course Type"],
                    course["Instructor"],
                    course["Building"],
                    course["Room Number"],
                    course["Start Time"],
                    course["End Time"],
                    course["Days of Week"],
                )
            )
            section_id = cur.fetchone()[0]

            cur.execute(
                """
                    INSERT INTO schedule_sections (schedule_id, section_id)
                    VALUES (%s, %s)
                """,
                (schedule_id, section_id)
            )


def add_courses_by_crn(uid, year, term, course_identifiers):
    if not course_identifiers:
        raise ValueError("No courses were provided.")

    courses = resolve_courses_from_uiuc(year, term, course_identifiers)

    with get_cursor() as cur:
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

        for course in courses:
            cur.execute(
                """
                    INSERT INTO classes (subject, number, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (subject, number) DO UPDATE
                    SET title = EXCLUDED.title
                    RETURNING id
                """,
                (
                    course["Subject"],
                    course["Subject Number"],
                    course["Title"],
                )
            )
            class_id = cur.fetchone()[0]

            cur.execute(
                """
                    INSERT INTO sections (
                        class_id,
                        year,
                        term,
                        section,
                        crn,
                        course_type,
                        instructor,
                        building,
                        room_number,
                        start_time,
                        end_time,
                        days_of_week
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (year, term, crn) DO UPDATE
                    SET class_id = EXCLUDED.class_id,
                        section = EXCLUDED.section,
                        course_type = EXCLUDED.course_type,
                        instructor = EXCLUDED.instructor,
                        building = EXCLUDED.building,
                        room_number = EXCLUDED.room_number,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        days_of_week = EXCLUDED.days_of_week
                    RETURNING id
                """,
                (
                    class_id,
                    year,
                    term,
                    course["Section"],
                    course["CRN"],
                    course["Course Type"],
                    course["Instructor"],
                    course["Building"],
                    course["Room Number"],
                    course["Start Time"],
                    course["End Time"],
                    course["Days of Week"],
                )
            )
            section_id = cur.fetchone()[0]

            cur.execute(
                """
                    INSERT INTO schedule_sections (schedule_id, section_id)
                    VALUES (%s, %s)
                    ON CONFLICT (schedule_id, section_id) DO NOTHING
                """,
                (schedule_id, section_id)
            )

    return courses


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
                DELETE FROM schedule_sections ss
                USING schedules s
                WHERE ss.schedule_id = s.id
                    AND s.user_id = %s
                    AND s.year = %s
                    AND s.term = %s
                    AND ss.section_id IN (
                        SELECT id FROM sections WHERE year = %s AND term = %s AND crn = ANY(%s)
                    )
            """,
            (uid, year, term, year, term, crns)
        )


def get_user_schedule(uid, year, term):
    with get_cursor() as cur:
        cur.execute(
            """
                SELECT
                    c.id,
                    c.subject,
                    c.number,
                    c.title,
                    c.created_at,
                    sec.id AS section_id,
                    sec.year,
                    sec.term,
                    sec.section,
                    sec.crn,
                    sec.course_type,
                    sec.instructor,
                    sec.building,
                    sec.room_number,
                    sec.start_time,
                    sec.end_time,
                    sec.days_of_week,
                    sec.created_at AS section_created_at
                FROM schedules s
                JOIN schedule_sections ss ON ss.schedule_id = s.id
                JOIN sections sec ON sec.id = ss.section_id
                JOIN classes c ON c.id = sec.class_id
                WHERE s.user_id = %s
                    AND s.year = %s
                    AND s.term = %s
                ORDER BY c.subject, c.number, sec.section;
            """,
            (uid, year, term)
        )
        rows = cur.fetchall() or []

    return [
        {
            "id": row[0],
            "subject": row[1],
            "number": row[2],
            "title": row[3],
            "created_at": row[4],
            "section_id": row[5],
            "year": row[6],
            "term": row[7],
            "section": row[8],
            "crn": row[9],
            "course_type": row[10],
            "instructor": row[11],
            "building": row[12],
            "room_number": row[13],
            "start_time": row[14],
            "end_time": row[15],
            "days_of_week": row[16],
            "section_created_at": row[17],
        }
        for row in rows
    ]


def get_all_schedules(uid):
    with get_cursor() as cur:
        cur.execute(
            """
                SELECT
                    s.term,
                    s.year,
                    COUNT(ss.section_id) AS class_count
                FROM schedules s
                LEFT JOIN schedule_sections ss
                    ON ss.schedule_id = s.id
                WHERE s.user_id = %s
                GROUP BY s.id, s.year, s.term
                ORDER BY s.year DESC, s.term DESC;
            """,
            (uid,)
        )
        rows = cur.fetchall() or []

    return [
        {
            "term": row[0],
            "year": row[1],
            "class_count": row[2],
        }
        for row in rows
    ]


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
                my_sections AS (
                  SELECT ss.section_id
                  FROM schedule_sections ss
                  JOIN me ON me.my_schedule_id = ss.schedule_id
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
                  ms.section_id,
                  u.id   AS member_id,
                  u.name AS member_name
                FROM my_sections ms
                JOIN schedule_sections ss
                  ON ss.section_id = ms.section_id
                JOIN group_schedules gs
                  ON gs.schedule_id = ss.schedule_id
                JOIN users u
                  ON u.id = gs.user_id
                WHERE u.id <> %s
                ORDER BY ms.section_id, u.name;
            """,
            (uid, year, term, group_id, year, term, uid)
        )
        rows = cur.fetchall() or []

    return [
        {
            "section_id": row[0],
            "member_id": row[1],
            "member_name": row[2],
        }
        for row in rows
    ]
