"""Use case: Export the full settings document as portable JSON (PART 6).

Settings only — this is NOT a database backup (per instructions).
"""
from __future__ import annotations

import datetime as dt

from app.application.dtos.settings import EXPORT_VERSION, ExportSettingsOutput
from app.application.queries.get_settings import GetSettingsQuery
from app.application.use_cases.settings.helpers import (
    get_or_create_settings,
    read_document,
)
from app.domain.repositories.object_repository import ObjectRepository


class ExportSettingsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetSettingsQuery) -> ExportSettingsOutput:
        del query
        return ExportSettingsOutput(
            version=EXPORT_VERSION,
            app="AcademicOS",
            exported_at=dt.datetime.now(dt.UTC).isoformat(),
            sections=read_document(get_or_create_settings(self._repository)),
        )
