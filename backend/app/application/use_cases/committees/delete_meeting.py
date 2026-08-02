"""Use case: Delete a Meeting (its action items cascade — milestone doctrine)."""
from __future__ import annotations

from app.application.commands.delete_meeting import DeleteMeetingCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.use_cases.committees.helpers import actions_of_meeting
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteMeetingUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteMeetingCommand) -> None:
        obj = self._repository.get_by_id(command.meeting_id)
        if obj is None or obj.object_type is not ObjectType.MEETING:
            raise ObjectNotFoundError(f"Meeting {command.meeting_id} not found.")
        for action in actions_of_meeting(self._repository, str(obj.id)):
            self._repository.delete(action.id)
        self._repository.delete(command.meeting_id)
