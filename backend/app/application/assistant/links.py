"""Object-type -> frontend route patterns — the single shared link table.

Both the assistant provider's cards and the citation builder's evidence
cards need the same href templates; the table lives here so it is never
duplicated. (Extracted from the assistant providers module, S6 M3.)
"""
from __future__ import annotations

# object_type -> frontend detail route pattern (the CalendarItem.href doctrine)
TYPE_HREFS: dict[str, str] = {
    "publication": "/publications/{id}",
    "research_project": "/research/projects/{id}",
    "grant": "/research/grants/{id}",
    "funding_agency": "/research/agencies",
    "faculty": "/faculty/{id}",
    "student": "/students/{id}",
    "course": "/teaching/classes/{id}",
    "assignment": "/teaching/assignments/{id}",
    "submission": "/teaching/assignments/{id}",
    "vendor": "/finance/vendors",
    "purchase": "/finance/{id}",
    "event": "/events/{id}",
    "committee": "/committees/{id}",
    "meeting": "/committees/meetings/{id}",
    "document": "/documents/{id}",
    "task": "/productivity",
    "notification": "/productivity",
}


def href_for(object_type: str, object_id: str) -> str:
    """The frontend route for an object of the given type and id."""
    pattern = TYPE_HREFS.get(object_type, "/objects/{id}")
    return pattern.format(id=object_id)
