"""V3 M6 golden documents — labelled ground truth (evaluation DATA, not rules).

Wave 1 golden corpus: three grant/sanction letters and three office orders,
each carrying the exact facts the typed extractor must recover. Ground-truth
values are stored in the *normalized* form the claim store produces (money /
number -> float, date / text -> str) so the M6 gate test compares like-for-like.

This is data only — the extractor and classifier under test own all logic.
"""

from __future__ import annotations

#: (filename, document_type_id, text, ground_truth)
GOLDEN_DOCUMENTS: tuple[tuple[str, str, str, dict[str, object]], ...] = (
    (
        "grant_sanction_letter_1.txt",
        "grant_sanction_letter",
        """Government of India
Ministry of Education
File Number: F.40-1/2024-R&D
Sanction Order Number: SO/2024/GR/12345
Date: 2024-06-15

Subject: Sanction of Research Grant under Major Research Project scheme

Principal Investigator: Dr. Anita Sharma
Co-Investigator: Dr. Ravi Kumar
Project Title: Quantum Materials for Energy Storage
Funding Agency: SERB
Scheme Name: Major Research Project
Sanctioned Amount: Rs. 50,00,000
Duration: 36 months
Project Start Date: 2024-08-01
Project End Date: 2027-07-31
Overhead Amount: Rs. 2,50,000
First Year Amount: Rs. 20,00,000
Recurring Amount: Rs. 10,00,000
Grant Category: Major Research Project
Department: Physics
Institution: University of Delhi
""",
        {
            "sanctioned_amount": 5000000.0,
            "principal_investigator": "Dr. Anita Sharma",
            "co_investigator": "Dr. Ravi Kumar",
            "project_title": "Quantum Materials for Energy Storage",
            "funding_agency": "SERB",
            "scheme_name": "Major Research Project",
            "sanction_order_number": "SO/2024/GR/12345",
            "file_number": "F.40-1/2024-R&D",
            "project_duration_months": 36.0,
            "project_start_date": "2024-08-01",
            "project_end_date": "2027-07-31",
            "overhead_amount": 250000.0,
            "first_year_amount": 2000000.0,
            "recurring_amount": 1000000.0,
            "grant_category": "Major Research Project",
            "department": "Physics",
            "institution": "University of Delhi",
        },
    ),
    (
        "grant_2.txt",
        "grant_sanction_letter",
        """File Number: F.50-2/2025-R&D
Sanction Order Number: SO/2025/GR/67890
Date: 2025-03-10
Principal Investigator: Dr. Vikram Mehta
Co-Investigator: Dr. Priya Rao
Project Title: Machine Learning for Crop Yield Prediction
Funding Agency: ICSSR
Scheme Name: Minor Research Project
Sanctioned Amount: Rs. 8,00,000
Duration: 24 months
Project Start Date: 2025-05-01
Project End Date: 2027-04-30
Department: Computer Science
Institution: IIT Delhi
""",
        {
            "sanctioned_amount": 800000.0,
            "principal_investigator": "Dr. Vikram Mehta",
            "co_investigator": "Dr. Priya Rao",
            "project_title": "Machine Learning for Crop Yield Prediction",
            "funding_agency": "ICSSR",
            "scheme_name": "Minor Research Project",
            "sanction_order_number": "SO/2025/GR/67890",
            "file_number": "F.50-2/2025-R&D",
            "project_duration_months": 24.0,
            "project_start_date": "2025-05-01",
            "project_end_date": "2027-04-30",
            "department": "Computer Science",
            "institution": "IIT Delhi",
        },
    ),
    (
        "grant_award_3.txt",
        "grant_sanction_letter",
        """Date: 2026-01-05
Principal Investigator: Dr. S. Iyer
Sanctioned Amount: Rs. 15,00,000
Funding Agency: DST
Duration: 18 months
Department: Chemistry
""",
        {
            "issue_date": "2026-01-05",
            "principal_investigator": "Dr. S. Iyer",
            "sanctioned_amount": 1500000.0,
            "funding_agency": "DST",
            "project_duration_months": 18.0,
            "department": "Chemistry",
        },
    ),
    (
        "office_order_1.txt",
        "office_order",
        """Office Order

Order Number: OO/2024/ADM/101
Order Date: 2024-11-01
Issuing Authority: Registrar
Addressee: All Heads of Departments
Subject: Revised working hours
Effective Date: 2024-12-01
Purpose: Standardisation of office timings
Circular Number: CIR/2024/55
Department: Administration
File Number: F.ADM/2024/90
""",
        {
            "order_number": "OO/2024/ADM/101",
            "order_date": "2024-11-01",
            "issuing_authority": "Registrar",
            "addressee": "All Heads of Departments",
            "subject": "Revised working hours",
            "effective_date": "2024-12-01",
            "purpose": "Standardisation of office timings",
            "circular_number": "CIR/2024/55",
            "department": "Administration",
            "file_number": "F.ADM/2024/90",
        },
    ),
    (
        "office_order_2.txt",
        "office_order",
        """Office Order

Order Number: OO/2025/FIN/207
Order Date: 2025-02-14
Issuing Authority: Director
Addressee: Finance Officer
Subject: Budget allocation for library
Effective Date: 2025-03-01
Compliance Deadline: 2025-03-31
Approval Reference: EC/2025/12
Department: Finance
""",
        {
            "order_number": "OO/2025/FIN/207",
            "order_date": "2025-02-14",
            "issuing_authority": "Director",
            "addressee": "Finance Officer",
            "subject": "Budget allocation for library",
            "effective_date": "2025-03-01",
            "compliance_deadline": "2025-03-31",
            "approval_reference": "EC/2025/12",
            "department": "Finance",
        },
    ),
    (
        "office_order_3.txt",
        "office_order",
        """Memorandum

Circular Number: CIR/2025/07
Order Number: OO/2025/HR/330
Order Date: 2025-06-01
Issuing Authority: Registrar
Subject: Extension of leave rules
Purpose: Clarification of encashment policy
Department: Human Resources
""",
        {
            "circular_number": "CIR/2025/07",
            "order_number": "OO/2025/HR/330",
            "order_date": "2025-06-01",
            "issuing_authority": "Registrar",
            "subject": "Extension of leave rules",
            "purpose": "Clarification of encashment policy",
            "department": "Human Resources",
        },
    ),
)


def grant_golden() -> tuple[tuple[str, str, str, dict[str, object]], ...]:
    return tuple(g for g in GOLDEN_DOCUMENTS if g[1] == "grant_sanction_letter")


def office_order_golden() -> tuple[tuple[str, str, str, dict[str, object]], ...]:
    return tuple(g for g in GOLDEN_DOCUMENTS if g[1] == "office_order")


__all__ = ["GOLDEN_DOCUMENTS", "grant_golden", "office_order_golden"]
