"""Provider factory — the single construction site for assistant providers (Sprint-7 M1).

Infrastructure composition: maps a registered ``ModelSpec`` onto the
existing provider adapters. The LLM adapter is always wrapped in the
deterministic-rules fallback chain (the S6 M2 degradation doctrine); the
rules kind returns the rules provider directly. Lives in the
infrastructure layer because it composes infrastructure adapters (httpx,
LLM transport, permission evaluator) — the application layer stays
framework-free.
"""
from __future__ import annotations

import httpx

from app.application.assistant.providers import (
    FallbackAssistantProvider,
    RuleBasedAssistantProvider,
)
from app.application.ports.assistant_provider import AssistantProvider
from app.application.services.model_registry import ModelSpec
from app.domain.repositories.object_repository import ObjectRepository
from app.infrastructure.llm.llm_provider import LlmAssistantProvider
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator


def build_provider(
    spec: ModelSpec,
    repository: ObjectRepository,
    *,
    fallback: AssistantProvider | None = None,
) -> AssistantProvider:
    """The single provider factory.

    No route or use case ever builds a provider itself — provider
    construction is centralized here and driven by the model registry.
    """
    rules = fallback or RuleBasedAssistantProvider(
        repository, permission_evaluator=ObjectPermissionEvaluator()
    )
    if not spec.is_llm:
        return rules
    headers = {"Authorization": f"Bearer {spec.api_key}"} if spec.api_key else {}
    client = httpx.Client(timeout=spec.timeout_seconds, headers=headers)
    primary = LlmAssistantProvider(
        client,
        model=spec.model,
        base_url=spec.base_url,  # type: ignore[arg-type]  # is_llm guarantees it
    )
    return FallbackAssistantProvider(primary, rules)
