"""Assistant provider composition (Sprint M11.3 — ADR-001).

The assistant owns NO transport and creates NO ``ProviderConfig``. It composes
the thin :class:`LlmAssistantProvider` translator over a gateway OBTAINED FROM
THE AI CORE (``AiCore.gateway``) with the deterministic rules fallback. AI Core
is the single authority for provider/model/config/credentials/policy.
"""
from __future__ import annotations

from app.application.ai.llm.ports import LanguageModelGateway
from app.application.assistant.providers import (
    FallbackAssistantProvider,
    RuleBasedAssistantProvider,
)
from app.application.ports.assistant_provider import AssistantProvider
from app.domain.repositories.object_repository import ObjectRepository
from app.infrastructure.llm.llm_provider import LlmAssistantProvider
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator


def _rules(repository: ObjectRepository) -> RuleBasedAssistantProvider:
    return RuleBasedAssistantProvider(
        repository, permission_evaluator=ObjectPermissionEvaluator()
    )


def build_assistant_provider(
    gateway: LanguageModelGateway,
    repository: ObjectRepository,
    *,
    fallback: AssistantProvider | None = None,
) -> AssistantProvider:
    """Compose the assistant provider around a gateway from the AI Core.

    The gateway's transport is owned by the AI Core; this function only wraps
    the translator + the deterministic rules fallback (P9 — degrade, never
    disappear). A gateway that is not configured yields the rules provider
    directly (no half-configured transport). The assistant creates no
    ``ProviderConfig`` and constructs no provider.
    """
    rules = fallback or _rules(repository)
    if not _gateway_ready(gateway):
        return rules
    return FallbackAssistantProvider(LlmAssistantProvider(gateway), rules)


def _gateway_ready(gateway: LanguageModelGateway) -> bool:
    """True when the gateway can actually EXECUTE (real adapter + endpoint).

    Readiness is executability, not mere declaration (M11.3.3): a declared
    but non-executable provider (e.g. a placeholder with a config entry, or a
    provider with no base_url) must never become the assistant's primary
    runtime provider — the deterministic rules provider is used instead.
    """
    try:
        return bool(gateway.health().executable)
    except Exception:  # noqa: BLE001 — a broken gateway degrades to rules
        return False
