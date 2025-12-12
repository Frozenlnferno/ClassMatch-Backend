from PyPDF2 import PdfReader
from .parser import parse_course_headers

def extract_courses_from_pdf(file):
    reader = PdfReader(file)
    text = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"

    if not text.strip():
        raise ValueError("Invalid course schedule")

    return parse_course_headers(text)
