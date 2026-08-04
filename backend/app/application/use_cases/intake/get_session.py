"""Use case: Get one intake session (full dashboard payload)."""
from __future__ import annotations

from app.application.dtos.intake import IntakeSessionOutput
from app.application.queries.get_intake_session import GetIntakeSessionQuery
from app.application.use_cases.intake.helpers import (
    get_intake_session_or_404,
    items_of_session,
    session_view,
)
from app.domain.repositories.object_repository import ObjectRepository


class GetIntakeSessionUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetIntakeSessionQuery) -> IntakeSessionOutput:
        obj = get_intake_session_or_404(self._repository, query.session_id)
        return session_view(obj, items_of_session(self._repository, str(obj.id)))
