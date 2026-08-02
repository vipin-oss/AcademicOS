"""Unit tests for the Teaching CSV import/export service (header auto-mapping)."""
from __future__ import annotations

from app.application.services import teaching_csv


def test_parse_students_csv_maps_spec_headers():
    text = (
        "Roll No,Name,Email,Section,Programme,Semester\n"
        "101,Asha Verma,asha@univ.edu,A,BSc Mathematics,1\n"
        "102,Ravi Kumar,ravi@univ.edu,A,BSc Mathematics,1\n"
    )
    rows = teaching_csv.parse_students_csv(text)
    assert len(rows) == 2
    assert rows[0]["roll_number"] == "101"
    assert rows[0]["name"] == "Asha Verma"
    assert rows[0]["email"] == "asha@univ.edu"
    assert rows[0]["section"] == "A"
    assert rows[0]["programme"] == "BSc Mathematics"
    assert rows[0]["semester"] == "1"


def test_parse_students_csv_normalises_header_variants():
    text = (
        "ROLLNO,Student Name,Mobile,Regd No,University Enrollment,Sem,Prog,Dept\n"
        "BSc-7,Meena Iyer,999,REG-77,UNIV-2026-7,3,BSc CS,Computer Science\n"
    )
    (row,) = teaching_csv.parse_students_csv(text)
    assert row["roll_number"] == "BSc-7"
    assert row["name"] == "Meena Iyer"
    assert row["phone"] == "999"
    assert row["registration_number"] == "REG-77"
    assert row["university_enrollment"] == "UNIV-2026-7"
    assert row["semester"] == "3"
    assert row["programme"] == "BSc CS"
    assert row["department"] == "Computer Science"


def test_parse_csv_rows_ignores_blank_lines_and_strips_cells():
    headers, rows = teaching_csv.parse_csv_rows("A, B\n\n 1 , 2 \n,\n3,4\n")
    assert headers == ["A", "B"]
    assert rows == [{"A": "1", "B": "2"}, {"A": "3", "B": "4"}]


def test_parse_students_csv_empty_text_returns_no_rows():
    assert teaching_csv.parse_students_csv("") == []
    assert teaching_csv.parse_students_csv("Roll No,Name\n") == []


def test_parse_marks_csv_maps_roll_marks_feedback():
    text = (
        "Roll No,Marks Obtained,Feedback\n"
        "101,17.5,Good work\n"
        "102,absent,\n"
    )
    rows = teaching_csv.parse_marks_csv(text)
    assert rows[0] == {"roll_number": "101", "marks": "17.5", "feedback": "Good work"}
    assert rows[1]["roll_number"] == "102"
    assert rows[1]["marks"] == "absent"  # parse stays raw; the use case flags it


def test_parse_attendance_csv_canonical_states():
    text = "Roll No,Status\n101,P\n102,a\n103,Late\n104,ML\n105,present\n"
    rows = teaching_csv.parse_attendance_csv(text)
    assert [r["status"] for r in rows] == [
        "present", "absent", "late", "medical_leave", "present",
    ]


def test_parse_attendance_csv_unknown_status_becomes_empty():
    (row,) = teaching_csv.parse_attendance_csv("Roll No,Status\n101,on-leave-tomorrow\n")
    assert row["status"] == ""


def test_parse_roster_csv_roll_and_email():
    text = "Roll No,Email\n101,asha@univ.edu\n,ravi@univ.edu\n"
    rows = teaching_csv.parse_roster_csv(text)
    assert rows[0]["roll_number"] == "101"
    assert rows[0]["email"] == "asha@univ.edu"
    assert rows[1]["roll_number"] == ""
    assert rows[1]["email"] == "ravi@univ.edu"


def test_export_students_csv_header_and_rows():
    text = teaching_csv.export_students_csv(
        [
            {
                "roll_number": "101", "name": "Asha Verma", "email": "a@u.edu",
                "phone": None, "student_type": "ug", "programme": "BSc Math",
                "department": "Maths", "semester": 1, "section": "A",
                "batch": "2026-30", "admission_date": "2026-07-01",
                "expected_graduation": "2030-05",
            }
        ]
    )
    lines = text.strip().split("\n")
    assert lines[0].startswith("Roll No,Name,Email,Phone")
    assert lines[1].startswith("101,Asha Verma,a@u.edu,")
    assert lines[1].endswith("2026-07-01,2030-05")


def test_export_gradebook_csv_shape():
    text = teaching_csv.export_gradebook_csv(
        [{"title": "A1"}, {"title": "Quiz 1"}],
        [
            {
                "student_roll": "101", "student_name": "Asha",
                "cells": [{"marks": 18.0}, {"marks": None}],
                "average_percent": 90.0, "grade": "A+",
            }
        ],
    )
    lines = text.strip().split("\n")
    assert lines[0] == "Roll No,Name,A1,Quiz 1,Internal %,Grade"
    assert lines[1] == "101,Asha,18.0,,90.0,A+"


def test_student_export_round_trips_through_parser():
    """Export -> re-import produces the same canonical records (PART F loop)."""
    original = {
        "roll_number": "101", "name": "Asha Verma", "email": "a@u.edu",
        "phone": "", "student_type": "ug", "programme": "BSc Math",
        "department": "Maths", "semester": 1, "section": "A",
        "batch": "2026-30", "admission_date": "2026-07-01",
        "expected_graduation": "2030-05",
    }
    csv_text = teaching_csv.export_students_csv([original])
    (row,) = teaching_csv.parse_students_csv(csv_text)
    assert row["roll_number"] == "101"
    assert row["name"] == "Asha Verma"
    assert row["programme"] == "BSc Math"
    assert row["semester"] == "1"
