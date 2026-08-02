"""Query (CQRS intent) for reading a single Funding Agency."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetAgencyQuery:
    """Intent to fetch one Funding Agency by Object id."""

    object_id: ObjectId
