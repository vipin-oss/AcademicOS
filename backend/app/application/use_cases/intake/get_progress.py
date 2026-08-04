"""Use case: Session progress (lean polling payload)."""
from __future__ import annotations

from app.application.dtos.intake import IntakeProgressOutput
from app.application.queries.get_intake_progress import GetIntakeProgressQuery
from app.application.use_cases.intake.helpers import (
    get_intake_session_or_404,
    items_of_session,
    progress_view,
)
from app.domain.repositories.object_repository import ObjectRepository


class GetIntakeProgressUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetIntakeProgressQuery) -> IntakeProgressOutput:
        obj = get_intake_session_or_404(self._repository, query.session_id)
        return progress_view(obj, items_of_session(self._repository, str(obj.id)))
