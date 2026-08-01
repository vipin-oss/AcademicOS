"""Use case: Bulk-import Publications from a bibliography (BibTeX / RIS / CSV).

FR-PUB-003. Parses the pasted/uploaded text with the framework-free
``bibliography`` service, runs duplicate detection per record, and creates
each non-duplicate through the existing ``CreatePublicationUseCase`` (single
write path — no duplicated creation logic). Duplicates are skipped and
reported; malformed records are collected as per-record errors. Nothing is
half-hidden: the result lists exactly what was created, skipped, and why.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.commands.create_publication import CreatePublicationCommand
from app.application.dtos.publication import (
    CreatePublicationInput,
    ImportPublicationsResult,
)
from app.application.exceptions import ApplicationError, ValidationError
from app.application.services import bibliography
from app.application.use_cases.publications.create_publication import (
    CreatePublicationUseCase,
    find_duplicates,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus


@dataclass
class ImportPublicationsCommand:
    """Intent to import bibliography text in the given format."""

    fmt: str
    text: str
    uploaded_by: str


def _to_create_input(record: dict, uploaded_by: str) -> CreatePublicationInput:
    """Map a parsed bibliography record onto the create boundary DTO."""
    pub_type = str(record.get("publication_type") or "other")
    if pub_type not in bibliography.PUBLICATION_TYPES:
        pub_type = "other"
    authors = tuple(
        {"name": name, "corresponding": name == record.get("corresponding_author")}
        for name in record.get("authors") or []
        if str(name).strip()
    )

    def as_int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def as_float(value) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return CreatePublicationInput(
        title=str(record.get("title") or "").strip(),
        publication_type=pub_type,
        uploaded_by=uploaded_by,
        status=ObjectStatus.DRAFT,
        authors=authors,
        affiliations=tuple(record.get("affiliations") or ()),
        abstract=record.get("abstract"),
        keywords=tuple(record.get("keywords") or ()),
        doi=record.get("doi"),
        isbn=record.get("isbn"),
        issn=record.get("issn"),
        publisher=record.get("publisher"),
        journal=record.get("journal"),
        conference=record.get("conference"),
        volume=record.get("volume"),
        issue=record.get("issue"),
        pages=record.get("pages"),
        year=as_int(record.get("year")),
        date=record.get("date"),
        language=record.get("language"),
        citation_count=as_int(record.get("citation_count")),
        impact_factor=as_float(record.get("impact_factor")),
        quartile=record.get("quartile") if record.get("quartile") in ("Q1", "Q2", "Q3", "Q4") else None,
        indexing=tuple(record.get("indexing") or ()),
        publisher_url=record.get("publisher_url"),
        notes=record.get("notes"),
        tags=tuple(record.get("tags") or ()),
        collections=tuple(record.get("collections") or ()),
        pipeline_stage="published" if record.get("journal") else None,
        links=None,
    )


class ImportPublicationsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: ImportPublicationsCommand) -> ImportPublicationsResult:
        fmt = (command.fmt or "").lower()
        if fmt not in bibliography.IMPORT_FORMATS:
            raise ValidationError(
                f"Unsupported import format: {fmt!r} "
                f"(expected one of {', '.join(bibliography.IMPORT_FORMATS)})."
            )
        if not command.text or not command.text.strip():
            raise ValidationError("Nothing to import: the pasted text is empty.")
        if not command.uploaded_by or not command.uploaded_by.strip():
            raise ValidationError("uploaded_by must identify an actor.")

        result = ImportPublicationsResult()
        creator = CreatePublicationUseCase(self._repository)

        try:
            records = bibliography.parse_records(command.text, fmt)
        except ValueError as exc:
            raise ValidationError(f"Could not parse the {fmt} input: {exc}") from exc

        if not records:
            raise ValidationError(f"No bibliography entries found in the {fmt} input.")

        for index, record in enumerate(records):
            title = str(record.get("title") or "").strip()
            if not title:
                result.errors.append(
                    {"index": index, "message": "Entry has no title; skipped."}
                )
                continue
            dupes = find_duplicates(
                self._repository, doi=record.get("doi"), title=title
            )
            if dupes:
                result.duplicates.append(
                    {
                        "index": index,
                        "title": title,
                        "doi": record.get("doi"),
                        "existing_id": str(dupes[0].id),
                    }
                )
                continue
            try:
                out = creator.execute(
                    CreatePublicationCommand(input=_to_create_input(record, command.uploaded_by))
                )
                result.created.append(out.id)
            except ApplicationError as exc:  # surface per-record, keep importing the rest
                result.errors.append({"index": index, "title": title, "message": str(exc)})
        return result
