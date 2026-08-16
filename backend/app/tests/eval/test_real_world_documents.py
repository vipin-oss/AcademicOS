"""Real-World Academic Document Validation Tests (Revision #11).

Tests the complete document intelligence pipeline with realistic academic
documents. Documents represent actual university faculty workflows.

These tests verify:
- Classification accuracy
- Field extraction correctness
- False positive prevention
- Short document handling
- Multiple document type coverage
"""

from __future__ import annotations

import pytest

from app.application.services.document_classifier import DocumentClassifier
from app.application.services.document_intake import DocumentIntakeService
from app.application.services.claim_service import ClaimService
from app.application.services.prose_extractor import prose_fields
from app.application.knowledge.extraction_schemas import fields_for
from app.infrastructure.persistence.claim_store import SQLClaimStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.infrastructure.db.models.object_model import Base


# --- Test Corpus ---

RESEARCH_PAPER = """Title: Machine Learning Approaches for Predicting Crop Yield in Semi-Arid Regions
Authors: Dr. Vipin Kumar, Prof. Anita Sharma, Dr. Ravi Patel
Journal: Agricultural Systems
Year: 2024
DOI: 10.1016/j.agsy.2024.103456
Volume: 198
Pages: 1-15
Publisher: Elsevier

Abstract: This paper presents a comprehensive study on machine learning approaches
for predicting crop yield in semi-arid regions of India.

Keywords: machine learning, crop yield, prediction, semi-arid, LSTM
"""

ACCEPTANCE_LETTER = """Dear Dr. Vipin Kumar,

We are pleased to inform you that your manuscript entitled
"Machine Learning Approaches for Predicting Crop Yield in Semi-Arid Regions"
has been accepted for publication in Agricultural Systems.

Manuscript ID: AGSY-2024-1234
Reference: AGSY-2024-1234

Please complete the copyright transfer form within 14 days.

Best regards,
Dr. Sarah Chen
Editor-in-Chief
Agricultural Systems
"""

CONFERENCE_CERT = """CERTIFICATE OF PARTICIPATION

This is to certify that
Dr. Vipin Kumar
has participated in the
International Conference on Machine Learning and Applications (ICMLA 2024)
held at IIT Delhi, New Delhi, India
on December 15-17, 2024

Certificate No: ICMLA-2024-0456
Track: Oral Presentation

The participant presented a paper entitled:
"Deep Learning for Agricultural Image Analysis"
"""

GRANT_SANCTION = """Government of India
Ministry of Education
Department of Higher Education

Sanction Order

File Number: F.40-1/2024-R&D
Sanction Order No: SO/2024/GR/56789
Date: 15 June 2024

Subject: Sanction of Research Grant

Principal Investigator: Dr. Vipin Kumar
Co-PI: Dr. Anita Sharma
Project Title: AI-Based Smart Agriculture for Sustainable Farming
Funding Agency: SERB (Science and Engineering Research Board)
Sanctioned Amount: Rs. 35,00,000
Duration: 36 months
Start Date: 01 August 2024
End Date: 31 July 2027

Department: Computer Science and Engineering
Institution: Indian Institute of Technology Delhi
"""

UNIVERSITY_NOTICE = """UNIVERSITY OF DELHI
Office of the Registrar

NOTICE

Date: 10 January 2025

Subject: Deadline for Promotion Applications

All faculty members are hereby informed that the deadline for submitting
promotion applications for the academic year 2024-25 is 28 February 2025.

Issued by:
Prof. Meera Singh
Registrar
University of Delhi
"""

APPOINTMENT_LETTER = """Office Order

No. Admin/2024/APPT/001
Date: 1 July 2024

Subject: Appointment as Assistant Professor

Dr. Vipin Kumar is hereby appointed as Assistant Professor in the
Department of Computer Science and Engineering with effect from
1 August 2024.

Designation: Assistant Professor
Department: Computer Science and Engineering
Institution: Indian Institute of Technology Delhi
Pay Level: Academic Level 10

By order of the Vice Chancellor
Registrar
"""

AWARD_CERTIFICATE = """CERTIFICATE

This is to certify that Dr. Vipin Kumar has been awarded the Best Paper Award
for the paper entitled Novel Approaches to Sentiment Analysis in Hindi Text
at the National Conference on Computational Linguistics (NCCL 2024)
held at IIIT Hyderabad on 20-22 November 2024

Awarded by: Indian Association for Computational Linguistics
"""

# --- Helpers ---

def _analyze(text: str, filename: str) -> dict:
    """Run the full document intelligence pipeline."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    store = SQLClaimStore(session)
    service = DocumentIntakeService(ClaimService(store), store)
    result = service.analyze(text=text, filename=filename, document_id="test", version=1, acl_scope=None)
    return {
        "type": result.document_type_id,
        "confidence": result.confidence,
        "fields": {f.predicate_id: f.value for f in result.fields},
        "review_required": result.review_required,
    }


# --- Classification Tests ---

class TestClassification:
    """Verify correct document type classification."""

    def test_research_paper(self):
        result = _analyze(RESEARCH_PAPER, "paper.txt")
        assert result["type"] == "publication"

    def test_acceptance_letter(self):
        result = _analyze(ACCEPTANCE_LETTER, "acceptance.txt")
        assert result["type"] == "acceptance_letter"

    def test_conference_certificate(self):
        result = _analyze(CONFERENCE_CERT, "certificate.txt")
        assert result["type"] == "conference_certificate"

    def test_grant_sanction(self):
        result = _analyze(GRANT_SANCTION, "sanction.txt")
        assert result["type"] == "grant_sanction_letter"

    def test_university_notice(self):
        result = _analyze(UNIVERSITY_NOTICE, "notice.txt")
        assert result["type"] == "university_notice"

    def test_appointment_letter(self):
        result = _analyze(APPOINTMENT_LETTER, "order.txt")
        # Office orders containing appointments may be classified as office_order
        assert result["type"] in ("appointment", "office_order")


# --- Extraction Tests ---

class TestResearchPaperExtraction:
    """Verify research paper field extraction."""

    def test_title_extracted(self):
        result = _analyze(RESEARCH_PAPER, "paper.txt")
        assert "publication_title" in result["fields"]
        assert "Crop Yield" in result["fields"]["publication_title"]

    def test_authors_extracted(self):
        result = _analyze(RESEARCH_PAPER, "paper.txt")
        assert "authors" in result["fields"]
        assert "Vipin Kumar" in result["fields"]["authors"]

    def test_journal_extracted(self):
        result = _analyze(RESEARCH_PAPER, "paper.txt")
        assert "journal_name" in result["fields"]
        assert "Agricultural Systems" in result["fields"]["journal_name"]

    def test_doi_extracted(self):
        result = _analyze(RESEARCH_PAPER, "paper.txt")
        assert "doi" in result["fields"]
        assert "10.1016" in result["fields"]["doi"]


class TestAcceptanceLetterExtraction:
    """Verify acceptance letter field extraction."""

    def test_manuscript_id(self):
        result = _analyze(ACCEPTANCE_LETTER, "acceptance.txt")
        assert "manuscript_id" in result["fields"]
        assert "AGSY-2024-1234" in result["fields"]["manuscript_id"]

    def test_title_from_prose(self):
        result = _analyze(ACCEPTANCE_LETTER, "acceptance.txt")
        assert "publication_title" in result["fields"]
        assert "Crop Yield" in result["fields"]["publication_title"]

    def test_journal_from_prose(self):
        result = _analyze(ACCEPTANCE_LETTER, "acceptance.txt")
        assert "journal_name" in result["fields"]
        assert "Agricultural Systems" in result["fields"]["journal_name"]


class TestGrantSanctionExtraction:
    """Verify grant sanction field extraction."""

    def test_project_title(self):
        result = _analyze(GRANT_SANCTION, "sanction.txt")
        assert "project_title" in result["fields"]
        assert "AI-Based Smart Agriculture" in result["fields"]["project_title"]

    def test_funding_agency(self):
        result = _analyze(GRANT_SANCTION, "sanction.txt")
        assert "funding_agency" in result["fields"]
        assert "SERB" in result["fields"]["funding_agency"]

    def test_principal_investigator(self):
        result = _analyze(GRANT_SANCTION, "sanction.txt")
        assert "principal_investigator" in result["fields"]
        assert "Vipin Kumar" in result["fields"]["principal_investigator"]

    def test_sanctioned_amount(self):
        result = _analyze(GRANT_SANCTION, "sanction.txt")
        assert "sanctioned_amount" in result["fields"]
        assert result["fields"]["sanctioned_amount"] == 3500000.0

    def test_duration(self):
        result = _analyze(GRANT_SANCTION, "sanction.txt")
        assert "project_duration_months" in result["fields"]
        assert result["fields"]["project_duration_months"] == 36.0


class TestConferenceCertExtraction:
    """Verify conference certificate field extraction."""

    def test_certificate_number(self):
        result = _analyze(CONFERENCE_CERT, "cert.txt")
        assert "certificate_number" in result["fields"]
        assert "ICMLA-2024-0456" in result["fields"]["certificate_number"]

    def test_recipient(self):
        result = _analyze(CONFERENCE_CERT, "cert.txt")
        assert "recipient" in result["fields"]
        assert "Vipin Kumar" in result["fields"]["recipient"]


class TestAppointmentExtraction:
    """Verify appointment letter field extraction."""

    def test_designation(self):
        result = _analyze(APPOINTMENT_LETTER, "order.txt")
        assert "designation" in result["fields"]
        assert "Assistant Professor" in result["fields"]["designation"]

    def test_institution(self):
        result = _analyze(APPOINTMENT_LETTER, "order.txt")
        assert "institution" in result["fields"]
        assert "Indian Institute of Technology Delhi" in result["fields"]["institution"]

    def test_department(self):
        result = _analyze(APPOINTMENT_LETTER, "order.txt")
        assert "department" in result["fields"]
        assert "Computer Science and Engineering" in result["fields"]["department"]


# --- False Positive Prevention ---

class TestFalsePositivePrevention:
    """Verify known false positive patterns are prevented."""

    def test_award_does_not_get_duration(self):
        """Year from 'NCCL 2024' must not be extracted as duration."""
        result = _analyze(AWARD_CERTIFICATE, "award.txt")
        # The award type should NOT have project_duration_months
        if "project_duration_months" in result["fields"]:
            # If present, it must not be 2024 (the year)
            assert result["fields"]["project_duration_months"] != 2024.0

    def test_notice_heading_not_institution(self):
        """'UNIVERSITY OF DELHI' heading should not be extracted as institution."""
        result = _analyze(UNIVERSITY_NOTICE, "notice.txt")
        if "institution" in result["fields"]:
            # Should not be just "OF DELHI" (broken extraction)
            assert "OF DELHI" not in result["fields"]["institution"]

    def test_no_duplicate_title_as_field(self):
        """Title should not appear as a separate field value."""
        result = _analyze(RESEARCH_PAPER, "paper.txt")
        # Title should be in publication_title, not duplicated elsewhere
        for key, val in result["fields"].items():
            if key != "publication_title":
                assert "Machine Learning Approaches" not in str(val)
