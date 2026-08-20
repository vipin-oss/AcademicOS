"""Extraction schemas (ADR-067 — data, not code).

Maps each document type to the fields it should extract, each field to a
predicate (the structured-fact store key) and a deterministic extractor kind.
The orchestrator (DocumentIntakeService) reads these schemas; adding a field
or a type is an additive data change.

Extractor kinds:
- ``label``   — "Label: value" / "Label value" prose line via field synonyms
- ``doi``     — DOI regex
- ``email``   — email regex
- ``url``     — http(s) URL regex
- ``date``    — date regex, then normalized
- ``amount``  — currency regex, then normalized
- ``number``  — plain number regex
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    field_name: str
    predicate_id: str
    extractor: str = "label"
    required: bool = False
    synonyms: tuple[str, ...] = ()


def _f(field_name, predicate_id, extractor="label", required=False, synonyms=()):
    return FieldSpec(field_name, predicate_id, extractor, required, synonyms or (field_name,))


CONFERENCE_FIELDS = (
    _f("conference_name", "conference_name", "label", True,
       ("conference", "conference name", "conference title", "symposium", "workshop")),
    _f("conference_acronym", "conference_acronym", "label",
       False, ("acronym", "short name")),
    _f("conference_organizer", "conference_organizer", "label",
       False, ("organizer", "organised by", "organized by", "hosted by")),
    _f("venue", "venue", "label", False, ("venue",)),
    _f("city", "city", "label", False, ("city",)),
    _f("country", "country", "label", False, ("country",)),
    _f("start_date", "start_date", "date", False, ("start date", "from", "date of commencement")),
    _f("end_date", "end_date", "date", False, ("end date", "to")),
    _f("participation_type", "participation_type", "label",
       False, ("participation", "participation type", "attended as")),
    _f("presentation_title", "presentation_title", "label",
       False, ("presentation title", "title of the paper", "title of paper presented")),
    _f("presentation_type", "presentation_type", "label",
       False, ("presentation type", "oral", "poster")),
    _f("event_url", "event_url", "url", False, ()),
    _f("certificate_number", "certificate_number", "label",
       False, ("certificate number", "certificate no", "cert no")),
)

PUBLICATION_FIELDS = (
    _f("title", "publication_title", "label", True, ("title", "paper title", "article title")),
    _f("authors", "authors", "label", False, ("authors", "author")),
    _f("journal", "journal_name", "label", False, ("journal", "journal name", "published in", "venue of publication")),
    _f("volume", "volume", "label", False, ("volume",)),
    _f("issue", "issue", "label", False, ("issue",)),
    _f("pages", "pages", "label", False, ("pages", "page range")),
    _f("year", "publication_year", "label", False, ("year", "publication year")),
    _f("doi", "doi", "doi", False, ()),
    _f("publisher", "publisher", "label", False, ("publisher",)),
    _f("issn", "issn", "label", False, ("issn",)),
    _f("status", "publication_status", "label", False, ("status", "publication status")),
)

AWARD_FIELDS = (
    _f("award_title", "award_title", "label", True, ("award", "award title", "achievement")),
    _f("awarding_body", "awarding_body", "label", False, ("awarding body", "conferred by", "by")),
    _f("recipient", "recipient", "label", False, ("recipient", "awarded to", "presented to")),
    _f("date", "award_date", "date", False, ()),
    _f("category", "award_category", "label", False, ("category",)),
    _f("reference_number", "reference_number", "label", False, ("reference number", "citation", "award number")),
)

PROJECT_FIELDS = (
    _f("project_title", "project_title", "label", True, ("project title", "title of the project", "project")),
    _f("funding_agency", "funding_agency", "label", False, ("funding agency", "sponsoring agency", "agency")),
    _f("pi", "principal_investigator", "label", False, ("principal investigator", "pi")),
    _f("co_investigators", "co_investigator", "label", False, ("co-investigator", "co investigator", "co-pi")),
    _f("sanction_number", "sanction_order_number", "label", False, ("sanction number", "sanction order number", "sanction no")),
    _f("sanction_date", "issue_date", "date", False, ()),
    _f("amount", "sanctioned_amount", "amount", False, ()),
    _f("duration", "project_duration_months", "number", False, ("duration", "project duration", "period")),
    _f("start_date", "start_date", "date", False, ("start date", "project start date")),
    _f("end_date", "end_date", "date", False, ("end date", "project end date")),
    _f("status", "project_status", "label", False, ("status", "project status")),
)

COMMITTEE_FIELDS = (
    _f("committee_name", "committee_name", "label", True, ("committee", "committee name", "board", "council")),
    _f("order_number", "order_number", "label", False, ("order number", "order no", "notification number")),
    _f("order_date", "order_date", "date", False, ()),
    _f("members", "committee_members", "label", False, ("members", "constituted with", "the following")),
    _f("role", "committee_role", "label", False, ("role", "member", "chairperson", "convenor")),
    _f("tenure", "tenure", "label", False, ("tenure", "term", "period")),
    _f("purpose", "committee_purpose", "label", False, ("purpose", "mandate", "to")),
)

APPOINTMENT_FIELDS = (
    _f("person", "recipient", "label", False, ("name", "appointed", "mr", "dr", "prof")),
    _f("institution", "institution", "label", False, ("institution", "college", "university")),
    _f("designation", "designation", "label", True, ("designation", "post", "appointed as")),
    _f("department", "department", "label", False, ("department", "dept")),
    _f("joining_date", "joining_date", "date", False, ()),
    _f("relieving_date", "relieving_date", "date", False, ()),
    _f("appointment_type", "appointment_type", "label", False, ("appointment type", "nature of appointment")),
    _f("reference_number", "reference_number", "label", False, ("reference number", "letter number", "order number")),
)

PHD_PROGRESS_FIELDS = (
    _f("scholar", "scholar_name", "label", False, ("scholar", "name of the scholar", "candidate")),
    _f("supervisor", "supervisor_name", "label", False, ("supervisor", "guide")),
    _f("research_topic", "research_topic", "label", False, ("research topic", "topic", "title")),
    _f("reporting_period", "reporting_period", "label", False, ("reporting period", "period", "progress for")),
    _f("status", "phd_status", "label", False, ("status", "approved", "satisfactory", "recommendation")),
)

NOTICE_FIELDS = (
    _f("title", "event_title", "label", False, ("subject", "title", "notice")),
    _f("issuing_authority", "issuing_authority", "label", False, ("issuing authority", "issued by", "registrar", "director")),
    _f("date", "issue_date", "date", False, ()),
    _f("event_date", "event_date", "date", False, ()),
    _f("venue", "venue", "label", False, ("venue",)),
    _f("deadline", "deadline", "date", False, ()),
    _f("reference_number", "reference_number", "label", False, ("reference number", "order number", "no")),
)

INVOICE_FIELDS = (
    _f("invoice_number", "invoice_number", "label", True, ("invoice number", "invoice no", "bill number")),
    _f("amount", "invoice_amount", "amount", False, ()),
    _f("vendor", "vendor_name", "label", False, ("vendor", "supplier", "billed to", "from")),
    _f("date", "issue_date", "date", False, ()),
)

ACCEPTANCE_FIELDS = (
    _f("paper_title", "publication_title", "label", True,
       ("title", "paper title", "article title", "manuscript title", "manuscript entitled")),
    _f("authors", "authors", "label", False, ("authors", "author", "dear dr", "dear prof")),
    _f("journal", "journal_name", "label", False, ("journal", "journal name")),
    _f("manuscript_id", "manuscript_id", "label", False, ("manuscript id", "manuscript number", "paper id", "reference number", "reference id")),
    _f("editor", "editor_name", "label", False, ("editor", "editor-in-chief")),
    _f("acceptance_date", "acceptance_date", "date", False, ()),
)

#: type_id -> field specs (data; additive).
EXTRACTION_SCHEMAS: dict[str, tuple[FieldSpec, ...]] = {
    "conference": CONFERENCE_FIELDS,
    "conference_certificate": CONFERENCE_FIELDS,
    "conference_participation": CONFERENCE_FIELDS,
    "conference_presentation": CONFERENCE_FIELDS,
    "acceptance_letter": ACCEPTANCE_FIELDS,
    "publication": PUBLICATION_FIELDS,
    "journal_article": PUBLICATION_FIELDS,
    "book_chapter": PUBLICATION_FIELDS,
    "patent": PUBLICATION_FIELDS,
    "award": AWARD_FIELDS,
    "research_project": PROJECT_FIELDS,
    "grant": PROJECT_FIELDS,
    "grant_sanction_letter": PROJECT_FIELDS,
    "office_order": NOTICE_FIELDS,
    "committee": COMMITTEE_FIELDS,
    "appointment": APPOINTMENT_FIELDS,
    "experience": APPOINTMENT_FIELDS,
    "promotion": APPOINTMENT_FIELDS,
    "phd_progress": PHD_PROGRESS_FIELDS,
    "university_notice": NOTICE_FIELDS,
    "event": NOTICE_FIELDS,
    "finance_invoice": INVOICE_FIELDS,
    "purchase": INVOICE_FIELDS,
    "certificate": AWARD_FIELDS,
    "correspondence": (),
    "general_document": (),
}


def fields_for(type_id: str) -> tuple[FieldSpec, ...]:
    return EXTRACTION_SCHEMAS.get(type_id, ())


__all__ = ["EXTRACTION_SCHEMAS", "FieldSpec", "fields_for"]
