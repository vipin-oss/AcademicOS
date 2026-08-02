"""Command (CQRS intent) for importing assignment marks from a CSV."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ImportMarksCsvCommand:
    """Intent to grade submissions of one Assignment from CSV text.

    This is the Google-Forms loop (PART G): the Assignment lives in
    AcademicOS first, responses are exported as CSV elsewhere, then the CSV
    (Roll No, Marks, optional Feedback) is re-imported here.
    """

    assignment_id: ObjectId
    text: str
    actor: str = "system"
