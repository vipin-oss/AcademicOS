"""Crossref adapter for the MetadataLookup port (FR-PUB-006).

The first concrete adapter in the pre-planned ``infrastructure/external``
slot (Scopus / Web of Science / PubMed / ORCID plug into the same port later).
Maps a Crossref ``works`` response onto the plain record shape the
bibliography service and the DOI-lookup route consume. No domain logic here —
only third-party plumbing.
"""
from __future__ import annotations

import httpx

from app.application.ports.metadata_lookup import MetadataLookup

_API = "https://api.crossref.org/works"
_TIMEOUT = 10.0
_USER_AGENT = "AcademicOS/0.1 (metadata lookup; mailto:admin@localhost)"

_CROSSREF_TYPE_MAP = {
    "journal-article": "journal_article",
    "proceedings-article": "conference_paper",
    "book-chapter": "book_chapter",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "posted-content": "preprint",
    "report": "technical_report",
    "report-series": "technical_report",
    "standard": "technical_report",
    "dissertation": "thesis",
}


class CrossrefMetadataLookup(MetadataLookup):
    def lookup(self, doi: str) -> dict | None:
        doi = (doi or "").strip()
        if not doi:
            return None
        try:
            response = httpx.get(
                f"{_API}/{doi}",
                timeout=_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Crossref is unreachable: {exc}") from exc
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(f"Crossref returned HTTP {response.status_code}.")
        message = response.json().get("message", {})
        return _map_crossref_record(message)


def _map_crossref_record(m: dict) -> dict:
    def first(key: str) -> str | None:
        value = m.get(key)
        if isinstance(value, list) and value:
            return value[0]
        return value if isinstance(value, str) else None

    def date_parts(key: str) -> tuple[int | None, str | None]:
        parts = (m.get(key) or {}).get("date-parts") or []
        if not parts or not parts[0]:
            return None, None
        numbers = parts[0]
        year = numbers[0]
        date = "-".join(f"{n:02d}" if i else str(n) for i, n in enumerate(numbers))
        return year, date

    record: dict = {}
    record["title"] = first("title") or ""
    authors = []
    for author in m.get("author") or []:
        family = (author.get("family") or "").strip()
        given = (author.get("given") or "").strip()
        name = f"{family}, {given}".strip(", ") if family else given
        if not name:
            continue
        authors.append(
            {
                "name": name,
                "orcid": (author.get("ORCID") or "").replace("https://orcid.org/", "") or None,
                "affiliation": (author.get("affiliation") or [{}])[0].get("name") or None,
                "corresponding": False,
            }
        )
    record["authors"] = authors

    record["publication_type"] = _CROSSREF_TYPE_MAP.get(
        (m.get("type") or "").lower(), "other"
    )
    record["journal"] = first("container-title") if record["publication_type"] != "preprint" else None
    if record["publication_type"] == "preprint":
        record["conference"] = None
    if record["publication_type"] == "book_chapter" and first("container-title"):
        record["conference"] = first("container-title")
    record["publisher"] = m.get("publisher")
    record["doi"] = m.get("DOI")

    year, date = date_parts("published-print")
    if year is None:
        year, date = date_parts("published-online")
    if year is None:
        year, date = date_parts("issued")
    record["year"] = year
    record["date"] = date

    record["volume"] = m.get("volume")
    record["issue"] = m.get("issue")
    record["pages"] = m.get("page")
    issn = (m.get("ISSN") or [None])[0]
    isbn = (m.get("ISBN") or [None])[0]
    if issn:
        record["issn"] = issn
    if isbn:
        record["isbn"] = isbn
    record["publisher_url"] = m.get("URL")
    record["language"] = m.get("language")
    if m.get("abstract"):
        record["abstract"] = str(m["abstract"]).replace("<jats:p>", "").replace("</jats:p>", "")
    record["citation_count"] = m.get("is-referenced-by-count")
    subjects = [s for s in (m.get("subject") or []) if s]
    if subjects:
        record["keywords"] = subjects[:8]
    return record
