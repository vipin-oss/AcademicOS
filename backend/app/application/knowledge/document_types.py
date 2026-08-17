"""Document-type registry (ADR-053, extended by ADR-067 — data, not code).

The full academic-administration taxonomy. Each type carries the three
deterministic rule families the classifier consults (filename patterns, heading
keywords, issuer keywords) AND the AcademicOS target module its structured
records route to. Adding/tuning a type is a data change, never code.

One document may legitimately match MULTIPLE types (a conference certificate
can also be a participation + award); the classifier returns a primary type
plus secondary types with per-type confidence, never a single forced bucket.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentTypeSpec:
    type_id: str
    name: str
    description: str
    target_module: str  # AcademicOS module the records route to
    filename_patterns: tuple[str, ...]
    heading_keywords: tuple[str, ...]
    issuer_keywords: tuple[str, ...]


def _t(type_id, name, target_module, filename, heading, issuer, description=""):
    return DocumentTypeSpec(
        type_id=type_id, name=name, description=description or name,
        target_module=target_module,
        filename_patterns=filename, heading_keywords=heading,
        issuer_keywords=issuer,
    )


DOCUMENT_TYPES: tuple[DocumentTypeSpec, ...] = (
    _t("conference", "Conference", "research",
       ("conference", "conferences", "symposium", "workshop", "seminar"),
       ("conference", "symposium", "workshop", "seminar", "international conference"),
       ("conference", "symposium", "workshop", "seminar", "proceedings")),
    _t("conference_certificate", "Conference Certificate", "events",
       ("certificate", "certif", "participation_cert", "icist", "icit", "ieee", "acm"),
       ("certificate", "certificate of participation", "certificate of presentation",
        "this is to certify that", "participation certificate", "certificate of attendance"),
       ("certificate", "participated", "presented", "conference", "this is to certify")),
    _t("conference_participation", "Conference Participation", "research",
       ("participation", "attended"),
       ("participation", "participated", "attended"),
       ("participated", "attended", "participation")),
    _t("conference_presentation", "Conference Presentation", "research",
       ("presentation", "paper"),
       ("presentation", "paper presented", "oral presentation", "poster"),
       ("presented", "oral", "poster", "paper")),
    _t("acceptance_letter", "Acceptance Letter", "publications",
       ("acceptance_letter", "acceptance-letter", "paper_accepted", "acceptance"),
       ("acceptance letter", "paper accepted", "manuscript accepted",
        "article accepted", "submission accepted",
        "has been accepted for publication"),
       ("accepted for publication", "editor", "review", "manuscript", "congratulations")),
    _t("publication", "Publication", "publications",
       ("publication", "paper", "article", "journal", "manuscript"),
       ("publication", "journal", "article", "manuscript", "paper"),
       ("journal", "volume", "issue", "pages", "doi", "publisher")),
    _t("journal_article", "Journal Article", "publications",
       ("article",),
       ("journal article", "article"),
       ("journal", "volume", "issue", "doi", "issn")),
    _t("book_chapter", "Book Chapter", "publications",
       ("chapter", "book"),
       ("book chapter", "chapter"),
       ("chapter", "book", "editor", "isbn")),
    _t("patent", "Patent", "publications",
       ("patent",),
       ("patent", "invention"),
       ("patent", "inventor", "filing", "granted", "application number")),
    _t("award", "Award", "faculty",
       ("award", "achievement", "recognition", "honour", "honor"),
       ("award", "achievement", "recognition"),
       ("award", "awarded", "recognition", "achievement")),
    _t("appointment", "Appointment", "faculty",
       ("appointment", "joining", "offer"),
       ("appointment", "appointment letter", "offer of appointment"),
       ("appointment", "designation", "joining date", "department")),
    _t("experience", "Experience", "faculty",
       ("experience", "service"),
       ("experience", "service certificate", "experience certificate"),
       ("experience", "served", "designation", "relieving")),
    _t("promotion", "Promotion", "faculty",
       ("promotion",),
       ("promotion", "promoted"),
       ("promotion", "promoted", "cadre", "grade")),
    _t("teaching", "Teaching", "teaching",
       ("teaching", "course", "syllabus", "timetable", "lecture"),
       ("teaching", "course", "syllabus"),
       ("teaching", "course", "syllabus", "lecture", "tutorial")),
    _t("course", "Course", "teaching",
       ("course",),
       ("course", "course outline", "course structure"),
       ("course", "credits", "syllabus", "lecture")),
    _t("syllabus", "Syllabus", "teaching",
       ("syllabus",),
       ("syllabus", "course syllabus"),
       ("syllabus", "unit", "module", "credits")),
    _t("timetable", "Timetable", "teaching",
       ("timetable", "schedule", "time table"),
       ("timetable", "time table", "schedule"),
       ("timetable", "period", "slot", "room")),
    _t("student_record", "Student Record", "students",
       ("student", "marksheet", "grade", "transcript", "enrollment", "enrolment"),
       ("student", "transcript", "marksheet", "grade"),
       ("student", "enrollment", "roll number", "grade", "cgpa")),
    _t("phd_progress", "PhD Progress", "research",
       ("phd", "progress", "doctoral"),
       ("phd", "progress report", "doctoral progress"),
       ("phd", "supervisor", "progress report", "doctoral", "research topic")),
    _t("research_project", "Research Project", "research",
       ("project", "research"),
       ("research project", "project"),
       ("research project", "principal investigator", "objectives", "milestone")),
    _t("grant", "Grant", "research",
       ("grant",),
       ("grant", "research grant", "sanction"),
       ("grant", "funding", "sanctioned", "amount")),
    _t("grant_sanction_letter", "Sanction Letter", "research",
       ("sanction", "sanction letter", "sanctioned", "grant", "award", "fund"),
       ("sanction", "grant", "research grant", "sanction order", "sanction letter"),
       ("sanctioned amount", "sanction order", "principal investigator", "funding agency",
        "file number", "co-investigator", "research grant")),
    _t("office_order", "Office Order", "events",
       ("order", "circular", "memo", "notification"),
       ("office order", "circular", "memorandum", "notification", "memo"),
       ("office order", "issued", "competent authority", "registrar", "director",
        "in continuation", "circular")),
    _t("committee", "Committee", "committees",
       ("committee", "board", "council"),
       ("committee", "board", "council", "constituted"),
       ("committee", "constituted", "members", "chairperson", "tenure")),
    _t("university_notice", "University Notice", "events",
       ("notice", "circular", "notification", "memo"),
       ("notice", "circular", "notification", "office order"),
       ("notice", "circular", "issued", "registrar", "all concerned")),
    _t("event", "Event", "events",
       ("event", "programme", "program", "inauguration"),
       ("event", "programme", "inauguration", "celebration"),
       ("event", "inauguration", "programme", "venue", "schedule")),
    _t("finance_invoice", "Invoice", "finance",
       ("invoice", "bill", "voucher"),
       ("invoice", "bill", "tax invoice"),
       ("invoice", "bill", "gst", "vendor", "tax invoice")),
    _t("purchase", "Purchase Order", "finance",
       ("purchase", "po", "procurement"),
       ("purchase order", "purchase", "procurement"),
       ("purchase order", "vendor", "quotation", "supply")),
    _t("certificate", "Certificate", "general_document",
       ("certificate",),
       ("certificate",),
       ("certificate", "this is to certify")),
    # Fallback types: deliberately NO filename/heading patterns, so a generic
    # "letter"/"doc" substring can never out-rank a specific administrative
    # type (a "sanction letter" is a sanction letter, not mere correspondence).
    _t("correspondence", "Correspondence", "general_document",
       ("correspondence",),
       ("correspondence",),
       ("dear sir", "dear madam", "yours faithfully", "yours sincerely",
        "sincerely", "kind regards", "regards")),
    _t("general_document", "General Document", "general_document",
       (), (), ()),
)

_BY_ID: dict[str, DocumentTypeSpec] = {spec.type_id: spec for spec in DOCUMENT_TYPES}


def get_document_type(type_id: str) -> DocumentTypeSpec | None:
    return _BY_ID.get(type_id)


#: The module a document type's structured records route to (data; the
#: route/analysis surface uses this to report the target module).
def target_module(type_id: str) -> str:
    spec = _BY_ID.get(type_id)
    return spec.target_module if spec else "general_document"


__all__ = ["DOCUMENT_TYPES", "DocumentTypeSpec", "get_document_type", "target_module"]
