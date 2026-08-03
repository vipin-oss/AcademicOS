"""Use case: Read the full settings document (all PART 1..8,10 sections)."""
from __future__ import annotations

from app.application.dtos.settings import SettingsDocumentOutput
from app.application.queries.get_settings import GetSettingsQuery
from app.application.use_cases.settings.helpers import (
    document_output,
    get_or_create_settings,
)
from app.domain.repositories.object_repository import ObjectRepository


class GetSettingsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetSettingsQuery) -> SettingsDocumentOutput:
        del query
        return document_output(get_or_create_settings(self._repository))
