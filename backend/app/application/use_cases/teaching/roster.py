"""Use case: Read the roster of a Class (PART C).

The roster is a pure edge query: students whose Object carries an
ENROLLED_IN edge to the class, projected as denormalised rows sorted by
roll number (then name) — the register order faculty expect.
"""
from __future__ import annotations

from app.application.dtos.teaching import RosterEntry
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_roster import GetRosterQuery
from app.application.use_cases.teaching.helpers import enrolled_students, to_roster_entry
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetRosterUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetRosterQuery) -> list[RosterEntry]:
        cls = self._repository.get_by_id(query.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {query.class_id} not found.")

        entries = [
            to_roster_entry(student)
            for student in enrolled_students(self._repository, str(cls.id))
        ]
        entries.sort(key=lambda e: ((e.roll_number or "￿").casefold(), e.name.casefold()))
        return entries
