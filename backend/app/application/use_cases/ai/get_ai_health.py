"""Use case: AI health summary (Sprint M11.1).

Thin projection over the composed ``AiCore`` — the route stays
orchestration-free and the summary logic stays testable without HTTP.
"""
from __future__ import annotations

from app.application.ai.core import AiCore
from app.application.dtos.ai import AiHealthSummary


class GetAiHealthUseCase:
    def __init__(self, core: AiCore) -> None:
        self._core = core

    def execute(self) -> AiHealthSummary:
        return self._core.health_summary()


__all__ = ["GetAiHealthUseCase"]
