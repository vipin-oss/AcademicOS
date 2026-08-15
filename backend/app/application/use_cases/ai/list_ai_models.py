"""Use case: model catalogue (Sprint M11.1).

The aggregated model list across all providers plus the configured
defaults — the data behind the "current model" display.
"""
from __future__ import annotations

from app.application.ai.core import AiCore
from app.application.dtos.ai import AiModelsSummary


class ListAiModelsUseCase:
    def __init__(self, core: AiCore) -> None:
        self._core = core

    def execute(self) -> AiModelsSummary:
        return self._core.model_records()


__all__ = ["ListAiModelsUseCase"]
