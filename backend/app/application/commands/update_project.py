"""Command (CQRS intent) for updating a Research Project."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import UpdateProjectInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateProjectCommand:
    """Intent to update an existing project (partial; merge semantics).

    Carries lifecycle transitions (``lifecycle_status``), field edits, link
    group replacements and team group replacements.
    """

    object_id: ObjectId
    input: UpdateProjectInput
