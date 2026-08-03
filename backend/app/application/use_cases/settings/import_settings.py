"""Use case: Import an exported settings document (PART 6).

Unknown sections/fields are rejected by validation (422) so a typo in a
hand-edited file can never silently corrupt the document; provided values
replace the current ones, omitted sections stay untouched.
"""
from __future__ import annotations

from app.application.commands.import_settings import ImportSettingsCommand
from app.application.dtos.settings import SettingsDocumentOutput
from app.application.use_cases.settings.helpers import (
    document_output,
    get_or_create_settings,
    write_fields,
)
from app.application.validators.settings import assert_valid_section_patch
from app.domain.repositories.object_repository import ObjectRepository


class ImportSettingsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: ImportSettingsCommand) -> SettingsDocumentOutput:
        obj = get_or_create_settings(self._repository)
        for section, values in command.input.sections.items():
            cleaned = assert_valid_section_patch(section, dict(values))
            write_fields(obj, section, cleaned)
        self._repository.save(obj)
        obj.pop_domain_events()
        return document_output(obj)
