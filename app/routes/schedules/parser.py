import re

COURSE_REGEX = re.compile(
    r"(.+?)\s+"                    # title (group 1)
    r"([A-Z]{2,4})\s*"             # subject (group 2)
    r"(\d{3})\s+"                  # number (group 3)
    r"([A-Za-z0-9]+)\s+"           # section (group 4)
    r"([\d.]+)\s+"                 # credit hours (group 5)
    r"(\d{5})\s+"                  # CRN (group 6)
    r"(\d{2}/\d{2}/\d{4})"         # start date (group 7)
    r"\s*-\s*"
    r"(\d{2}/\d{2}/\d{4})"         # end date (group 8)  
)

def parse_course_headers(text):
    matches = COURSE_REGEX.findall(text)

    return [
        {
            "Title": m[0],
            "Subject": m[1],
            "Subject Number": m[2],
            "Section": m[3],
            "Credit Hours": m[4],
            "CRN": m[5],
            "Start Date": m[6],
            "End Date": m[7]
        }
        for m in matches
    ]
