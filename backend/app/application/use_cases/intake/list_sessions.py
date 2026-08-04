"""Use case: List intake sessions (newest first, paginated)."""
from __future__ import annotations

from app.application.dtos.intake import ListIntakeSessionsResult, intake_session_output
from app.application.queries.list_intake_sessions import ListIntakeSessionsQuery
from app.application.use_cases.intake.helpers import items_grouped_by_session
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListIntakeSessionsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListIntakeSessionsQuery) -> ListIntakeSessionsResult:
        sessions = self._repository.find(object_type=ObjectType.INTAKE_SESSION)
        sessions.sort(
            key=lambda s: s.audit.created_at if s.audit is not None else s.title,
            reverse=True,
        )
        grouped = items_grouped_by_session(self._repository)
        total = len(sessions)
        start = (query.page - 1) * query.page_size
        window = sessions[start : start + query.page_size]
        return ListIntakeSessionsResult(
            items=[intake_session_output(s, grouped.get(str(s.id), [])) for s in window],
            total_count=total,
            page=query.page,
            page_size=query.page_size,
        )
