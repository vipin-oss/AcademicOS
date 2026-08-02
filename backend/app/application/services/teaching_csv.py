"""CSV import/export for Teaching & Students (first-class, PART F).

Faculty CSVs come from Excel exports, ERP dumps and Google Form responses —
headers vary ("Roll No", "Roll_Number", "ROLLNO"). This module normalises
headers through an alias map (case/space/underscore-insensitive) so records
map automatically; unmapped headers are preserved but never required.

Pure and framework-free (stdlib ``csv`` only — same module the bibliography
service uses), so it stays inside the Application layer's dependency rules.
"""
from __future__ import annotations

import csv
import io
import re


# ---------------------------------------------------------------------------
# Header normalisation: strip case, spaces, underscores, dots, punctuation
# ---------------------------------------------------------------------------
def _normalise_header(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (raw or "").strip().lower())


# Canonical field -> accepted header aliases (after normalisation).
STUDENT_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "studentname", "fullname"),
    "roll_number": ("rollno", "rollnumber", "roll", "rollnos"),
    "registration_number": ("registrationno", "registrationnumber", "regno", "regdno"),
    "university_enrollment": ("enrollmentno", "enrollmentnumber", "universityenrollment",
                              "enrolmentno", "univno", "universityno"),
    "email": ("email", "emailid", "mail", "studentemail"),
    "phone": ("phone", "phoneno", "phonenumber", "mobile", "mobileno", "contact", "contactno"),
    "student_type": ("studenttype", "type", "programmetype", "level"),
    "programme": ("programme", "program", "prog", "course", "degree"),
    "department": ("department", "dept"),
    "semester": ("semester", "sem"),
    "section": ("section", "sec"),
    "batch": ("batch", "cohort", "yearofadmission", "admissionyear"),
    "admission_date": ("admissiondate", "dateofadmission", "admittedon"),
    "expected_graduation": ("expectedgraduation", "graduationyear", "expectedgraduationyear"),
    "research_area": ("researcharea", "researchtopic", "researchinterest"),
    "orcid": ("orcid", "orcidid"),
    "google_scholar": ("googlescholar", "scholar", "scholarlink", "googlescholarurl"),
    "notes": ("notes", "note", "remarks", "remark"),
    "tags": ("tags", "tag", "labels"),
}

MARKS_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "roll_number": STUDENT_HEADER_ALIASES["roll_number"],
    "name": STUDENT_HEADER_ALIASES["name"],
    "marks": ("marks", "marksobtained", "score", "markssecured", "obtained"),
    "feedback": ("feedback", "remarks", "comments", "remark", "facultyfeedback"),
}

ATTENDANCE_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "roll_number": STUDENT_HEADER_ALIASES["roll_number"],
    "name": STUDENT_HEADER_ALIASES["name"],
    "status": ("status", "attendance", "attendancestatus", "pa", "presence"),
}

ROSTER_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "roll_number": STUDENT_HEADER_ALIASES["roll_number"],
    "email": STUDENT_HEADER_ALIASES["email"],
}

# Attendance value aliases -> canonical state (PART I vocabulary).
ATTENDANCE_VALUE_ALIASES: dict[str, str] = {
    "p": "present", "present": "present", "yes": "present", "y": "present", "1": "present",
    "a": "absent", "absent": "absent", "no": "absent", "n": "absent", "0": "absent",
    "l": "late", "late": "late",
    "ml": "medical_leave", "m": "medical_leave", "medical": "medical_leave",
    "medicalleave": "medical_leave", "leave": "medical_leave", "od": "medical_leave",
}


def parse_csv_rows(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Split CSV text into (headers, rows of raw-string dicts). Strips cells."""
    reader = csv.reader(io.StringIO(text or ""))
    rows = [list(row) for row in reader if row and any(cell.strip() for cell in row)]
    if not rows:
        return [], []
    headers = [cell.strip() for cell in rows[0]]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        record = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            record[header] = row[index].strip() if index < len(row) else ""
        records.append(record)
    return headers, records


def remap_record(record: dict[str, str], aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """Map a raw CSV row onto canonical fields via the alias table."""
    normalised = {_normalise_header(header): value for header, value in record.items()}
    out: dict[str, str] = {}
    for field_name, accepted in aliases.items():
        for alias in accepted:
            value = normalised.get(alias)
            if value:
                out[field_name] = value.strip()
                break
    return out


def parse_students_csv(text: str) -> list[dict[str, str]]:
    """Roster CSV -> canonical student dicts (PART C/F)."""
    _, rows = parse_csv_rows(text)
    return [remap_record(row, STUDENT_HEADER_ALIASES) for row in rows]


def parse_marks_csv(text: str) -> list[dict[str, str]]:
    """Marks CSV (Google Forms export / manual) -> {roll_number, marks, feedback?}."""
    _, rows = parse_csv_rows(text)
    return [remap_record(row, MARKS_HEADER_ALIASES) for row in rows]


def parse_attendance_csv(text: str) -> list[dict[str, str]]:
    """Attendance CSV -> {roll_number, status} with canonical states."""
    _, rows = parse_csv_rows(text)
    out = []
    for record in (remap_record(row, ATTENDANCE_HEADER_ALIASES) for row in rows):
        state = ATTENDANCE_VALUE_ALIASES.get(
            record.get("status", "").strip().lower()
        )
        out.append(
            {
                "roll_number": record.get("roll_number", ""),
                "name": record.get("name", ""),
                "status": state or "",
            }
        )
    return out


def parse_roster_csv(text: str) -> list[dict[str, str]]:
    """Enrollment CSV -> {roll_number, email} (either value resolves a student)."""
    _, rows = parse_csv_rows(text)
    out = []
    for record in (remap_record(row, ROSTER_HEADER_ALIASES) for row in rows):
        out.append(
            {
                "roll_number": record.get("roll_number", ""),
                "email": record.get("email", ""),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Export (students list / gradebook → CSV download)
# ---------------------------------------------------------------------------
STUDENT_EXPORT_HEADERS = (
    "Roll No",
    "Name",
    "Email",
    "Phone",
    "Student Type",
    "Programme",
    "Department",
    "Semester",
    "Section",
    "Batch",
    "Admission Date",
    "Expected Graduation",
)

_STUDENT_EXPORT_KEYS = (
    "roll_number",
    "name",
    "email",
    "phone",
    "student_type",
    "programme",
    "department",
    "semester",
    "section",
    "batch",
    "admission_date",
    "expected_graduation",
)


def export_students_csv(records: list[dict]) -> str:
    """Students -> CSV for ERP/Google-Sheets round-trips."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(STUDENT_EXPORT_HEADERS)
    for record in records:
        writer.writerow(["" if record.get(key) is None else record.get(key) for key in _STUDENT_EXPORT_KEYS])
    return buffer.getvalue()


def export_gradebook_csv(assignment_headers: list[dict], rows: list[dict]) -> str:
    """Gradebook matrix -> CSV (university-format marks sheet foundation)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    header = ["Roll No", "Name"] + [a["title"] for a in assignment_headers] + ["Internal %", "Grade"]
    writer.writerow(header)
    for row in rows:
        line = [row.get("student_roll") or "", row["student_name"]]
        line += ["" if cell.get("marks") is None else cell["marks"] for cell in row["cells"]]
        line += [row["average_percent"], row["grade"]]
        writer.writerow(line)
    return buffer.getvalue()
