"""Provider factory — the single construction site for assistant providers
(Sprint-7 M1, revised Sprint M11.2 — ADR-001).

ADR-001 change: the assistant no longer builds an httpx transport. It
constructs the AI Core's :class:`LanguageModelGateway` (the real
:class:`OpenAIProvider` adapter — the single transport owner) from the model
spec, then wraps it in the thin :class:`LlmAssistantProvider` translator and
the deterministic-rules fallback chain. The rules kind returns the rules
provider directly. Lives in the infrastructure layer because it composes
infrastructure adapters (the AI gateway, the rules provider, the permission
evaluator) — the application layer stays framework-free.

The optional ``ai_core`` lets the assistant consume the AI Core's configured
generation defaults (max_tokens / temperature / streaming) for the gateway —
the explicit ``consume AiCore`` seam from M11.2 goal 3. It is optional so
the unit-tested ``(spec, repository)`` construction path stays unchanged.
"""
from __future__ import annotations

from app.application.assistant.providers import (
    FallbackAssistantProvider,
    RuleBasedAssistantProvider,
)
from app.application.dtos.ai import ProviderConfig
from app.application.ports.assistant_provider import AssistantProvider
from app.application.services.model_registry import ModelSpec
from app.domain.repositories.object_repository import ObjectRepository
from app.infrastructure.ai.llm.openai import OpenAIProvider
from app.infrastructure.llm.llm_provider import LlmAssistantProvider
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator


def build_provider(
    spec: ModelSpec,
    repository: ObjectRepository,
    *,
    ai_core=None,
    fallback: AssistantProvider | None = None,
) -> AssistantProvider:
    """The single provider factory.

    No route or use case ever builds a provider itself — provider
    construction is centralized here and driven by the model registry. The
    LLM transport is the AI Core's gateway adapter (M11.2); it is always
    wrapped in the deterministic-rules fallback chain (the S6 M2 degradation
    doctrine, unchanged). The rules kind returns the rules provider directly.
    """
    rules = fallback or RuleBasedAssistantProvider(
        repository, permission_evaluator=ObjectPermissionEvaluator()
    )
    if not spec.is_llm:
        return rules
    ai_cfg = ai_core.config if ai_core is not None else None
    config = ProviderConfig(
        provider_id="openai",
        kind="openai",
        model=spec.model,
        base_url=spec.base_url or "",
        api_key=spec.api_key or "",
        timeout_seconds=spec.timeout_seconds,
        max_tokens=ai_cfg.max_tokens if ai_cfg is not None else 2048,
        temperature=ai_cfg.temperature if ai_cfg is not None else 0.0,
        streaming_enabled=ai_cfg.streaming_enabled if ai_cfg is not None else True,
    )
    gateway = OpenAIProvider(config)  # the single transport owner (ADR-001)
    primary = LlmAssistantProvider(gateway)  # thin translator, no transport
    return FallbackAssistantProvider(primary, rules)
