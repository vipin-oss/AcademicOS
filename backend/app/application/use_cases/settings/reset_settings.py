"""Use case: Reset settings sections to factory defaults (PART 6)."""
from __future__ import annotations

from app.application.commands.reset_settings import ResetSettingsCommand
from app.application.dtos.settings import SECTION_CODES, SettingsDocumentOutput
from app.application.use_cases.settings.helpers import (
    document_output,
    get_or_create_settings,
    write_defaults,
)
from app.application.validators.settings import assert_valid_reset_input
from app.domain.repositories.object_repository import ObjectRepository


class ResetSettingsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: ResetSettingsCommand) -> SettingsDocumentOutput:
        assert_valid_reset_input(command.input)
        obj = get_or_create_settings(self._repository)
        for section in command.input.sections or SECTION_CODES:
            write_defaults(obj, section)
        self._repository.save(obj)
        obj.pop_domain_events()
        return document_output(obj)
