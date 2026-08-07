"""Use case: provider catalogue (Sprint M11.1).

One record per catalogue provider (status, configured models, detail) —
the data behind the AI settings surface. Deterministic order.
"""
from __future__ import annotations

from app.application.ai.core import AiCore
from app.application.dtos.ai import ProviderRecord


class ListAiProvidersUseCase:
    def __init__(self, core: AiCore) -> None:
        self._core = core

    def execute(self) -> tuple[ProviderRecord, ...]:
        return self._core.provider_records()


__all__ = ["ListAiProvidersUseCase"]
