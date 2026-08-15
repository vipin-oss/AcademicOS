"""Domain-record router (V3 ADR-068).

Maps a classified + extracted document into ACTUAL AcademicOS domain records,
reusing the existing create use cases (which own validation, duplicate
detection, relationships and events). This is the "automatic placement" layer
the document-intake pipeline was missing — previously it only wrote claims.

Mapping (actual record vs claim-only):

    conference / conference_* / event / university_notice -> Event (type=conference/event)
    publication / journal_article / book_chapter / patent  -> Publication
    grant / grant_sanction_letter / research_project        -> Research Project
    committee                                              -> Committee

Everything else (award, appointment, experience, promotion, teaching/course,
syllabus, timetable, student_record, phd_progress, finance_invoice, purchase,
certificate, correspondence, general_document) has NO dedicated create entity
matching the extraction surface today, so it stays CLAIM-ONLY (a structured
fact bound to the source document) — never a fabricated entity.

Duplicate detection reuses the frozen ``find_*_duplicates`` helpers; a match
skips creation and reports the existing record. Conflicts (same identity,
different value) are treated as duplicates for safety: never silently
overwritten, never silently duplicated. Provenance is a ``RELATED_TO`` edge
from the record back to the source document, plus the claims' source binding.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.commands.create_committee import CreateCommitteeCommand
from app.application.commands.create_event import CreateEventCommand
from app.application.commands.create_project import CreateProjectCommand
from app.application.commands.create_publication import CreatePublicationCommand
from app.application.dtos.committee import CreateCommitteeInput
from app.application.dtos.events import CreateEventInput
from app.application.dtos.publication import CreatePublicationInput
from app.application.dtos.research import CreateProjectInput
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.use_cases.committees.create_committee import (
    CreateCommitteeUseCase,
    find_committee_duplicates,
)
from app.application.use_cases.events.create_event import (
    CreateEventUseCase,
    find_event_duplicates,
)
from app.application.use_cases.publications.create_publication import (
    CreatePublicationUseCase,
)
from app.application.use_cases.publications.create_publication import (
    find_duplicates as find_publication_duplicates,
)
from app.application.use_cases.research.create_project import (
    CreateProjectUseCase,
    find_project_duplicates,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.object_id import ObjectId

#: document type_id -> target module record kind the router can create.
ROUTABLE: dict[str, str] = {
    "conference": "event",
    "conference_certificate": "event",
    "conference_participation": "event",
    "conference_presentation": "event",
    "event": "event",
    "university_notice": "event",
    "publication": "publication",
    "journal_article": "publication",
    "book_chapter": "publication",
    "patent": "publication",
    "grant": "project",
    "grant_sanction_letter": "project",
    "research_project": "project",
    "committee": "committee",
}


@dataclass(frozen=True)
class RouteOutcome:
    module: str            # "event" | "publication" | "project" | "committee" | "claim_only"
    kind: str              # "created" | "duplicate" | "claim_only" | "skipped"
    object_id: str = ""
    existing_id: str = ""
    reason: str = ""


def _f(fields: dict[str, object], key: str) -> str | None:
    v = fields.get(key)
    return str(v) if v not in (None, "") else None


class DomainRecordRouter:
    """Create actual domain records from an extracted document."""

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def route(
        self,
        *,
        type_ids: tuple[str, ...],
        fields: dict[str, object],
        created_by: str,
        source_document_id: str,
        confidence: float,
    ) -> list[RouteOutcome]:
        """Route the primary document type to its module; return outcomes."""
        primary = type_ids[0] if type_ids else ""
        module = ROUTABLE.get(primary)
        if module is None:
            return [RouteOutcome(module="claim_only", kind="claim_only",
                                 reason=f"no domain entity for type {primary!r}")]
        handler = {
            "event": self._route_event,
            "publication": self._route_publication,
            "project": self._route_project,
            "committee": self._route_committee,
        }[module]
        outcome = handler(fields, created_by, source_document_id, confidence)
        return [outcome]

    # ------------------------------------------------------------- events
    def _route_event(self, fields, created_by, source_document_id, confidence):
        title = _f(fields, "conference_name") or _f(fields, "event_title")
        if not title:
            return RouteOutcome("event", "skipped", reason="no conference/event title")
        start = _f(fields, "start_date")
        dups = find_event_duplicates(
            self._repository, title=title, event_code=None,
            department=_f(fields, "department"), start_date=start,
        )
        if dups:
            return RouteOutcome("event", "duplicate", existing_id=str(dups[0].id),
                                reason="existing event")
        try:
            out = CreateEventUseCase(self._repository).execute(
                CreateEventCommand(input=CreateEventInput(
                    title=title, created_by=created_by,
                    event_type="conference" if "conference" in fields.get("__types__", ()) else "custom",
                    organizer=_f(fields, "conference_organizer"),
                    venue=_f(fields, "venue"),
                    start_date=start,
                    end_date=_f(fields, "end_date"),
                    department=_f(fields, "department"),
                ))
            )
        except (ValidationError, ObjectAlreadyExistsError, ValueError):
            return RouteOutcome("event", "skipped", reason="event creation failed")
        self._link_source(out.id, source_document_id, created_by)
        return RouteOutcome("event", "created", object_id=out.id)

    # ------------------------------------------------------- publications
    def _route_publication(self, fields, created_by, source_document_id, confidence):
        title = _f(fields, "publication_title")
        if not title:
            return RouteOutcome("publication", "skipped", reason="no publication title")
        doi = _f(fields, "doi")
        dups = find_publication_duplicates(self._repository, doi=doi, title=title)
        if dups:
            return RouteOutcome("publication", "duplicate", existing_id=str(dups[0].id),
                                reason="existing publication")
        try:
            out = CreatePublicationUseCase(self._repository).execute(
                CreatePublicationCommand(input=CreatePublicationInput(
                    title=title, publication_type="journal_article",
                    uploaded_by=created_by,
                    authors=tuple({"name": n.strip(), "corresponding": False}
                                  for n in (fields.get("authors") or "").split(",") if n.strip()),
                    doi=doi,
                    journal=_f(fields, "journal_name"),
                    volume=_f(fields, "volume"),
                    issue=_f(fields, "issue"),
                    pages=_f(fields, "pages"),
                    year=int(fields["publication_year"]) if _f(fields, "publication_year") else None,
                    publisher=_f(fields, "publisher"),
                    issn=_f(fields, "issn"),
                ))
            )
        except (ValidationError, ObjectAlreadyExistsError, ValueError):
            return RouteOutcome("publication", "skipped", reason="publication creation failed")
        self._link_source(out.id, source_document_id, created_by)
        return RouteOutcome("publication", "created", object_id=out.id)

    # ----------------------------------------------------------- projects
    def _route_project(self, fields, created_by, source_document_id, confidence):
        title = _f(fields, "project_title")
        if not title:
            return RouteOutcome("project", "skipped", reason="no project title")
        code = _f(fields, "sanction_order_number") or _f(fields, "order_number")
        dups = find_project_duplicates(self._repository, project_code=code)
        if dups:
            return RouteOutcome("project", "duplicate", existing_id=str(dups[0].id),
                                reason="existing project")
        try:
            out = CreateProjectUseCase(self._repository).execute(
                CreateProjectCommand(input=CreateProjectInput(
                    title=title, created_by=created_by,
                    project_code=code,
                    department=_f(fields, "department"),
                    start_date=_f(fields, "start_date"),
                    end_date=_f(fields, "end_date"),
                    duration=_f(fields, "project_duration_months"),
                    budget_approved=(float(fields["sanctioned_amount"])
                                     if fields.get("sanctioned_amount") is not None else None),
                ))
            )
        except (ValidationError, ObjectAlreadyExistsError, ValueError):
            return RouteOutcome("project", "skipped", reason="project creation failed")
        self._link_source(out.id, source_document_id, created_by)
        return RouteOutcome("project", "created", object_id=out.id)

    # --------------------------------------------------------- committees
    def _route_committee(self, fields, created_by, source_document_id, confidence):
        name = _f(fields, "committee_name")
        if not name:
            return RouteOutcome("committee", "skipped", reason="no committee name")
        dups = find_committee_duplicates(
            self._repository, name=name, committee_code=None,
            committee_type=None, department=_f(fields, "department"),
        )
        if dups:
            return RouteOutcome("committee", "duplicate", existing_id=str(dups[0].id),
                                reason="existing committee")
        try:
            out = CreateCommitteeUseCase(self._repository).execute(
                CreateCommitteeCommand(input=CreateCommitteeInput(
                    name=name, created_by=created_by,
                    description=_f(fields, "committee_purpose"),
                    constitution_date=_f(fields, "order_date"),
                    department=_f(fields, "department"),
                ))
            )
        except (ValidationError, ObjectAlreadyExistsError, ValueError):
            return RouteOutcome("committee", "skipped", reason="committee creation failed")
        self._link_source(out.id, source_document_id, created_by)
        return RouteOutcome("committee", "created", object_id=out.id)

    # -------------------------------------------------------- provenance
    def _link_source(self, record_id: str, source_document_id: str, actor: str) -> None:
        """RELATED_TO edge from the domain record to the source document."""
        try:
            record = self._repository.get_by_id(ObjectId(record_id))
            if record is None:
                return
            record.add_relationship(
                ObjectId(source_document_id), RelationshipKind.RELATED_TO,
                Provenance.ASSERTED, actor=actor,
            )
            self._repository.save(record)
        except Exception:  # noqa: BLE001 - provenance link is best-effort
            pass


__all__ = ["ROUTABLE", "DomainRecordRouter", "RouteOutcome"]
