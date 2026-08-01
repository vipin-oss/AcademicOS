"""Data Transfer Objects for the Publication use cases.

Mirrors ``dtos/document.py``: plain framework-free dataclasses. A Publication
is a Universal Object with ``object_type = publication`` (Blueprint §2);
every bibliographic field rides in the seven-layer metadata record, and every
"Linked X" is an asserted relationship edge (Blueprint §3.1/§4).

Link groups (the reference-manager "Linked Projects/Grants/People/Org" panes)
are typed edges; the *group* of an edge is derived from the target's
``object_type`` — so nothing is ever stored twice and the graph stays the
single source of truth.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId

# ---------------------------------------------------------------------------
# Metadata keys (frozen convention, same style as the documents module)
# ---------------------------------------------------------------------------
KEY_PUBLICATION_TYPE = "publication_type"
KEY_PIPELINE_STAGE = "pipeline_stage"  # FR-PUB-001 lifecycle (metadata, §1.4)
KEY_AUTHORS = "authors"  # JSON list of author objects (see below)
KEY_AFFILIATIONS = "affiliations"  # JSON list[str]
KEY_ABSTRACT = "abstract"
KEY_KEYWORDS = "keywords"  # JSON list[str]
KEY_DOI = "doi"
KEY_ISBN = "isbn"
KEY_ISSN = "issn"
KEY_PUBLISHER = "publisher"
KEY_JOURNAL = "journal"
KEY_CONFERENCE = "conference"
KEY_VOLUME = "volume"
KEY_ISSUE = "issue"
KEY_PAGES = "pages"
KEY_YEAR = "year"
KEY_DATE = "date"
KEY_LANGUAGE = "language"
KEY_CITATION_COUNT = "citation_count"
KEY_IMPACT_FACTOR = "impact_factor"
KEY_QUARTILE = "quartile"
KEY_INDEXING = "indexing"  # JSON list[str] (Scopus, WoS, PubMed, ...)
KEY_PUBLISHER_URL = "publisher_url"
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list[str]
KEY_COLLECTIONS = "collections"  # JSON list[str] (Zotero-style folders)
# Primary PDF attachment (supplementary files = linked Document objects)
KEY_PDF_FILE_NAME = "pdf_file_name"
KEY_PDF_FILE_SIZE = "pdf_file_size"
KEY_PDF_MIME_TYPE = "pdf_mime_type"
KEY_PDF_FILE_PATH = "pdf_file_path"

# ---------------------------------------------------------------------------
# Link groups -> relationship kind used when the edge is written.
# Group membership on read is derived from the TARGET object_type.
# ---------------------------------------------------------------------------
GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "projects": RelationshipKind.REPORTS,      # Publication reports Project (Blueprint §2)
    "grants": RelationshipKind.REPORTS,        # Publication reports Grant   (Blueprint §2)
    "students": RelationshipKind.AUTHORED_BY,  # internal student co-author
    "faculty": RelationshipKind.AUTHORED_BY,   # internal faculty co-author
    "departments": RelationshipKind.BELONGS_TO,
    "events": RelationshipKind.PRESENTED_AT,   # Blueprint §2
    "committees": RelationshipKind.BELONGS_TO,
}

LINK_GROUPS = tuple(GROUP_TO_KIND.keys())

_TYPE_TO_GROUP: dict[ObjectType, str] = {
    ObjectType.RESEARCH_PROJECT: "projects",
    ObjectType.GRANT: "grants",
    ObjectType.STUDENT: "students",
    ObjectType.FACULTY: "faculty",
    ObjectType.SPACE: "departments",
    ObjectType.RESEARCH_AREA: "departments",
    ObjectType.LABORATORY: "departments",
    ObjectType.EVENT: "events",
    ObjectType.COMMITTEE: "committees",
}


def encode_json_list(values: list | tuple) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return [v.strip() for v in raw.split(",") if v.strip()]
    return value if isinstance(value, list) else []


def parse_authors(raw: str | None) -> list[dict]:
    """Author objects: {name, orcid?, affiliation?, corresponding?}."""
    authors = []
    for entry in parse_json_list(raw):
        if isinstance(entry, dict) and entry.get("name"):
            authors.append(
                {
                    "name": str(entry["name"]),
                    "orcid": entry.get("orcid") or None,
                    "affiliation": entry.get("affiliation") or None,
                    "corresponding": bool(entry.get("corresponding")),
                }
            )
        elif isinstance(entry, str) and entry.strip():
            authors.append(
                {"name": entry.strip(), "orcid": None, "affiliation": None, "corresponding": False}
            )
    return authors


def grouped_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    """Denormalised relationship edges grouped for the response payload."""
    links: dict[str, list[dict]] = {group: [] for group in LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = _TYPE_TO_GROUP.get(target.object_type)
        if group is None:
            continue
        links[group].append(
            {
                "id": str(target.id),
                "title": target.title,
                "object_type": target.object_type.value,
                "kind": rel.kind.value,
            }
        )
    return links


def linked_target_ids(obj: UniversalObject, kind: RelationshipKind | None = None) -> list[ObjectId]:
    """Ids of Objects this publication links out to (optionally by kind)."""
    return [r.target for r in obj.relationships if kind is None or r.kind == kind]


@dataclass
class CreatePublicationInput:
    """Boundary input for registering a Publication (manual entry / import)."""

    title: str
    publication_type: str
    uploaded_by: str
    status: ObjectStatus = ObjectStatus.DRAFT
    authors: tuple[dict, ...] = ()
    affiliations: tuple[str, ...] = ()
    abstract: str | None = None
    keywords: tuple[str, ...] = ()
    doi: str | None = None
    isbn: str | None = None
    issn: str | None = None
    publisher: str | None = None
    journal: str | None = None
    conference: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    year: int | None = None
    date: str | None = None
    language: str | None = None
    citation_count: int | None = None
    impact_factor: float | None = None
    quartile: str | None = None
    indexing: tuple[str, ...] = ()
    publisher_url: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] = ()
    collections: tuple[str, ...] = ()
    pipeline_stage: str | None = None
    links: dict[str, tuple[ObjectId, ...]] | None = None


@dataclass
class UpdatePublicationInput:
    """Boundary input for updating a Publication (partial semantics).

    Optional fields stay untouched when ``None``. ``links`` uses group-merge
    semantics: groups present in the dict are replaced with exactly the given
    ids; absent groups are left untouched.
    """

    actor: str
    title: str | None = None
    publication_type: str | None = None
    status: ObjectStatus | None = None
    pipeline_stage: str | None = None
    authors: tuple[dict, ...] | None = None
    affiliations: tuple[str, ...] | None = None
    abstract: str | None = None
    keywords: tuple[str, ...] | None = None
    doi: str | None = None
    isbn: str | None = None
    issn: str | None = None
    publisher: str | None = None
    journal: str | None = None
    conference: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    year: int | None = None
    date: str | None = None
    language: str | None = None
    citation_count: int | None = None
    impact_factor: float | None = None
    quartile: str | None = None
    indexing: tuple[str, ...] | None = None
    publisher_url: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] | None = None
    collections: tuple[str, ...] | None = None
    links: dict[str, tuple[ObjectId, ...]] | None = None


@dataclass
class PublicationOutput:
    """Boundary output for every Publication use case (single response shape)."""

    id: str
    title: str
    publication_type: str
    pipeline_stage: str | None
    authors: list[dict]
    affiliations: list[str]
    abstract: str | None
    keywords: list[str]
    doi: str | None
    isbn: str | None
    issn: str | None
    publisher: str | None
    journal: str | None
    conference: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    year: int | None
    date: str | None
    language: str | None
    citation_count: int
    impact_factor: float | None
    quartile: str | None
    indexing: list[str]
    publisher_url: str | None
    notes: str | None
    tags: list[str]
    collections: list[str]
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    pdf_file_name: str | None = None
    pdf_file_size: int = 0
    pdf_mime_type: str | None = None
    pdf_file_path: str | None = None
    links: dict[str, list[dict]] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> PublicationOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}

        def as_int(key: str) -> int | None:
            raw = meta.get(key)
            if raw in (None, ""):
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        def as_float(key: str) -> float | None:
            raw = meta.get(key)
            if raw in (None, ""):
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        return PublicationOutput(
            id=str(obj.id),
            title=obj.title,
            publication_type=meta.get(KEY_PUBLICATION_TYPE, "other"),
            pipeline_stage=meta.get(KEY_PIPELINE_STAGE),
            authors=parse_authors(meta.get(KEY_AUTHORS)),
            affiliations=[str(a) for a in parse_json_list(meta.get(KEY_AFFILIATIONS))],
            abstract=meta.get(KEY_ABSTRACT),
            keywords=[str(k) for k in parse_json_list(meta.get(KEY_KEYWORDS))],
            doi=meta.get(KEY_DOI),
            isbn=meta.get(KEY_ISBN),
            issn=meta.get(KEY_ISSN),
            publisher=meta.get(KEY_PUBLISHER),
            journal=meta.get(KEY_JOURNAL),
            conference=meta.get(KEY_CONFERENCE),
            volume=meta.get(KEY_VOLUME),
            issue=meta.get(KEY_ISSUE),
            pages=meta.get(KEY_PAGES),
            year=as_int(KEY_YEAR),
            date=meta.get(KEY_DATE),
            language=meta.get(KEY_LANGUAGE),
            citation_count=as_int(KEY_CITATION_COUNT) or 0,
            impact_factor=as_float(KEY_IMPACT_FACTOR),
            quartile=meta.get(KEY_QUARTILE),
            indexing=[str(i) for i in parse_json_list(meta.get(KEY_INDEXING))],
            publisher_url=meta.get(KEY_PUBLISHER_URL),
            notes=meta.get(KEY_NOTES),
            tags=[str(t) for t in parse_json_list(meta.get(KEY_TAGS))],
            collections=[str(c) for c in parse_json_list(meta.get(KEY_COLLECTIONS))],
            status=obj.status.value,
            version=obj.version,
            uploaded_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat()
                if obj.audit is not None and obj.audit.updated_at is not None
                else None
            ),
            pdf_file_name=meta.get(KEY_PDF_FILE_NAME),
            pdf_file_size=as_int(KEY_PDF_FILE_SIZE) or 0,
            pdf_mime_type=meta.get(KEY_PDF_MIME_TYPE),
            pdf_file_path=meta.get(KEY_PDF_FILE_PATH),
            links=grouped_links(obj, linked_by_id or {}),
            metadata=meta,
            events=[event.__class__.__name__ for event in events],
        )

    def to_record(self) -> dict:
        """Primitive bibliographic record for bibliography/citation services."""
        return {
            "publication_type": self.publication_type,
            "title": self.title,
            "authors": [a["name"] for a in self.authors],
            "corresponding_author": next(
                (a["name"] for a in self.authors if a.get("corresponding")), None
            ),
            "affiliations": list(self.affiliations),
            "abstract": self.abstract,
            "keywords": list(self.keywords),
            "doi": self.doi,
            "isbn": self.isbn,
            "issn": self.issn,
            "publisher": self.publisher,
            "journal": self.journal,
            "conference": self.conference,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "year": self.year,
            "date": self.date,
            "language": self.language,
            "citation_count": self.citation_count,
            "impact_factor": self.impact_factor,
            "quartile": self.quartile,
            "indexing": list(self.indexing),
            "publisher_url": self.publisher_url,
            "notes": self.notes,
            "tags": list(self.tags),
            "collections": list(self.collections),
        }


@dataclass
class ListPublicationsResult:
    """Boundary result for a paginated listing of Publications."""

    items: list[PublicationOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class ImportPublicationsResult:
    """Boundary result of a bulk bibliography import."""

    created: list[str] = field(default_factory=list)
    duplicates: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
