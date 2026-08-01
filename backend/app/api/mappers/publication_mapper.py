"""Pure mapping between API request/response shapes and Application DTOs.

Mirrors ``object_mapper.py`` / ``document_mapper.py``: framework-free so it
stays unit-testable without FastAPI/Pydantic/SQLAlchemy.
"""
from __future__ import annotations

from app.application.dtos.publication import (
    GROUP_TO_KIND,
    LINK_GROUPS,
    CreatePublicationInput,
    PublicationOutput,
    UpdatePublicationInput,
)
from app.domain.value_objects.enums import ObjectStatus
from app.domain.value_objects.object_id import ObjectId


def parse_authors_field(raw: list | None) -> tuple[dict, ...]:
    """Normalise the authors payload: each entry a string or an author object.

    Entries are strict — a blank name or a non-string/non-object entry is a
    ``ValueError`` ( surfaces as 422 ), never silently dropped. This mirrors
    the application-layer validator one-to-one: no data loss without a signal.
    """
    authors: list[dict] = []
    for entry in raw or []:
        if isinstance(entry, str):
            name = entry.strip()
            if not name:
                raise ValueError("Every author needs a non-empty name.")
            authors.append({"name": name, "corresponding": False})
        elif isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            if not name:
                raise ValueError("Every author needs a non-empty name.")
            authors.append(
                {
                    "name": name,
                    "orcid": (entry.get("orcid") or None),
                    "affiliation": (entry.get("affiliation") or None),
                    "corresponding": bool(entry.get("corresponding")),
                }
            )
        else:
            raise ValueError("authors must be name strings or {name, orcid, ...} objects.")
    return tuple(authors)


def parse_links_field(raw: dict | None) -> dict[str, tuple[ObjectId, ...]] | None:
    """Parse {group: [object_id, ...]} into typed ObjectId tuples."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"links must be an object of {{{', '.join(LINK_GROUPS)}: [ids]}}.")
    links: dict[str, tuple[ObjectId, ...]] = {}
    for group, ids in raw.items():
        if group not in GROUP_TO_KIND:
            raise ValueError(
                f"Unknown link group: {group!r} (expected one of {', '.join(LINK_GROUPS)})."
            )
        if not isinstance(ids, list):
            raise ValueError(f"links.{group} must be an array of Object ids.")
        links[group] = tuple(ObjectId.parse(str(oid)) for oid in ids)
    return links


def to_create_input(*, body: dict) -> CreatePublicationInput:
    """Convert the JSON create body into the Application ``CreatePublicationInput``."""
    authors = parse_authors_field(body.get("authors"))
    return CreatePublicationInput(
        title=str(body.get("title") or ""),
        publication_type=str(body.get("publication_type") or ""),
        uploaded_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        authors=authors,
        affiliations=tuple(str(a) for a in (body.get("affiliations") or [])),
        abstract=body.get("abstract"),
        keywords=tuple(str(k) for k in (body.get("keywords") or [])),
        doi=body.get("doi"),
        isbn=body.get("isbn"),
        issn=body.get("issn"),
        publisher=body.get("publisher"),
        journal=body.get("journal"),
        conference=body.get("conference"),
        volume=body.get("volume"),
        issue=body.get("issue"),
        pages=body.get("pages"),
        year=body.get("year"),
        date=body.get("date"),
        language=body.get("language"),
        citation_count=body.get("citation_count"),
        impact_factor=body.get("impact_factor"),
        quartile=body.get("quartile"),
        indexing=tuple(str(i) for i in (body.get("indexing") or [])),
        publisher_url=body.get("publisher_url"),
        notes=body.get("notes"),
        tags=tuple(str(t) for t in (body.get("tags") or [])),
        collections=tuple(str(c) for c in (body.get("collections") or [])),
        pipeline_stage=body.get("pipeline_stage"),
        links=parse_links_field(body.get("links")),
    )


def to_update_input(*, body: dict) -> UpdatePublicationInput:
    """Convert the JSON PUT/PATCH body into the Application ``UpdatePublicationInput``.

    Merge semantics: an absent key leaves the field untouched; a present key
    (even ``null`` for scalars, ``[]`` for lists) replaces the stored value.
    """
    def present(name: str):
        return body[name] if name in body else None

    return UpdatePublicationInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        publication_type=present("publication_type"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        pipeline_stage=present("pipeline_stage"),
        authors=parse_authors_field(body["authors"]) if "authors" in body else None,
        affiliations=(
            tuple(str(a) for a in body["affiliations"]) if "affiliations" in body else None
        ),
        abstract=present("abstract"),
        keywords=(tuple(str(k) for k in body["keywords"]) if "keywords" in body else None),
        doi=present("doi"),
        isbn=present("isbn"),
        issn=present("issn"),
        publisher=present("publisher"),
        journal=present("journal"),
        conference=present("conference"),
        volume=present("volume"),
        issue=present("issue"),
        pages=present("pages"),
        year=present("year"),
        date=present("date"),
        language=present("language"),
        citation_count=present("citation_count"),
        impact_factor=present("impact_factor"),
        quartile=present("quartile"),
        indexing=(tuple(str(i) for i in body["indexing"]) if "indexing" in body else None),
        publisher_url=present("publisher_url"),
        notes=present("notes"),
        tags=(tuple(str(t) for t in body["tags"]) if "tags" in body else None),
        collections=(
            tuple(str(c) for c in body["collections"]) if "collections" in body else None
        ),
        links=parse_links_field(body["links"]) if "links" in body else None,
    )


def to_response(out: PublicationOutput, *, pdf_url: str | None = None) -> dict:
    """Project an Application ``PublicationOutput`` into a JSON-serialisable dict."""
    return {
        "id": out.id,
        "title": out.title,
        "publication_type": out.publication_type,
        "pipeline_stage": out.pipeline_stage,
        "authors": out.authors,
        "affiliations": out.affiliations,
        "abstract": out.abstract,
        "keywords": out.keywords,
        "doi": out.doi,
        "isbn": out.isbn,
        "issn": out.issn,
        "publisher": out.publisher,
        "journal": out.journal,
        "conference": out.conference,
        "volume": out.volume,
        "issue": out.issue,
        "pages": out.pages,
        "year": out.year,
        "date": out.date,
        "language": out.language,
        "citation_count": out.citation_count,
        "impact_factor": out.impact_factor,
        "quartile": out.quartile,
        "indexing": out.indexing,
        "publisher_url": out.publisher_url,
        "notes": out.notes,
        "tags": out.tags,
        "collections": out.collections,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.uploaded_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "pdf_file_name": out.pdf_file_name,
        "pdf_file_size": out.pdf_file_size,
        "pdf_mime_type": out.pdf_mime_type,
        "pdf_url": pdf_url,
        "links": out.links,
        "metadata": out.metadata,
        "events": out.events,
    }
