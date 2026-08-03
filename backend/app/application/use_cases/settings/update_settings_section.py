"""Use case: Update one section of the settings document (verbatim merge).

One generic use case parameterized by section code — the 8 section routers
profile/appearance/academic/notifications/dashboard/search/privacy/ai all
exercise it; only provided keys are written (None-filtered at the mapper).
"""
from __future__ import annotations

from app.application.commands.update_settings_section import UpdateSettingsSectionCommand
from app.application.dtos.settings import SettingsSectionOutput
from app.application.use_cases.settings.helpers import (
    get_or_create_settings,
    section_output,
    write_fields,
)
from app.application.validators.settings import assert_valid_section_patch
from app.domain.repositories.object_repository import ObjectRepository


class UpdateSettingsSectionUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: UpdateSettingsSectionCommand) -> SettingsSectionOutput:
        cleaned = assert_valid_section_patch(command.input.section, dict(command.input.values))
        obj = get_or_create_settings(self._repository)
        write_fields(obj, command.input.section, cleaned)
        self._repository.save(obj)
        obj.pop_domain_events()
        return section_output(obj, command.input.section)
