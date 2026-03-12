import re

TERM_REGEX = re.compile(r"\b(Fall|Winter|Spring|Summer)\s+(\d{4})\b", re.IGNORECASE)
COURSE_ROW_REGEX = re.compile(
    r"\b(?P<subject>[A-Z]{2,5})\s*(?P<number>\d{3})\s+"
    r"(?P<section>[A-Z0-9][A-Z0-9-]*)\s+"
    r"(?P<credits>\d+(?:\.\d+)?)\s+"
    r"(?P<crn>\d{5})\s+"
    r"(?P<start>\d{2}/\d{2}/\d{4})\s*-\s*(?P<end>\d{2}/\d{2}/\d{4})\b",
    re.IGNORECASE,
)


def _normalize_whitespace(value):
    return re.sub(r"\s+", " ", value).strip()


def _normalize_term(term):
    normalized = term.lower()
    if normalized == "winter":
        raise ValueError(
            "Unsupported term in PDF: winter. UIUC public course data is only available for spring, summer, and fall."
        )
    return normalized


def _build_candidate_rows(text):
    lines = [_normalize_whitespace(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    candidates = []

    for index, line in enumerate(lines):
        candidates.append(line)
        if index + 1 < len(lines):
            candidates.append(f"{line} {lines[index + 1]}")

    return candidates


def _extract_course_identifiers(text):
    seen_courses = set()
    courses = []

    for candidate in _build_candidate_rows(text):
        match = COURSE_ROW_REGEX.search(candidate)
        if not match:
            continue

        subject = match.group("subject").upper()
        course_number = match.group("number")
        crn = match.group("crn")
        dedupe_key = (subject, course_number, crn)

        if dedupe_key in seen_courses:
            continue

        seen_courses.add(dedupe_key)
        courses.append(
            {
                "Subject": subject,
                "Subject Number": course_number,
                "CRN": crn,
            }
        )

    return courses


def parse_schedule_pdf(text):
    term_match = TERM_REGEX.search(text)
    if not term_match:
        raise ValueError(
            "Could not find term and year information in the PDF. Please ensure your schedule PDF contains a supported term and year."
        )

    try:
        term = _normalize_term(term_match.group(1))
        year = int(term_match.group(2))
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Invalid term/year format in PDF: {exc}") from exc

    course_identifiers = _extract_course_identifiers(text)
    if not course_identifiers:
        raise ValueError(
            "Could not find course identifiers in the PDF. Please ensure each course row includes subject, course number, CRN, and surrounding schedule details."
        )

    return course_identifiers, {"term": term, "year": year}
