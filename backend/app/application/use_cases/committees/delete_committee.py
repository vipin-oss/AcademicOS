"""Use case: Delete a Committee.

Mirrors ``DeleteProjectUseCase``: linked projects/grants/publications and
member person records are institutional records on OTHER Objects and survive
by design (their RELATED_TO/MEMBER_OF edges simply dangle and are skipped on
denormalisation — the frozen tolerance). Meeting children and their action
items exist only as this committee's record and are deleted with it
(the milestone cascade precedent), so the dashboard never leaks orphans.
"""
from __future__ import annotations

from app.application.commands.delete_committee import DeleteCommitteeCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.use_cases.committees.helpers import (
    actions_of_meeting,
    meetings_of_committee,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteCommitteeUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteCommitteeCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.COMMITTEE:
            raise ObjectNotFoundError(f"Committee {command.object_id} not found.")
        committee_id = str(obj.id)
        for meeting in meetings_of_committee(self._repository, committee_id):
            for action in actions_of_meeting(self._repository, str(meeting.id)):
                self._repository.delete(action.id)
            self._repository.delete(meeting.id)
        self._repository.delete(command.object_id)
