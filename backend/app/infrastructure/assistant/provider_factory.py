"""Assistant provider composition (L4 — ADR-020 active path).

The assistant owns NO transport and creates NO ``ProviderConfig``. It composes
the L4 query-understanding provider (model-driven planner + deterministic
fast-path + clarify/refuse) over a gateway OBTAINED FROM THE AI CORE
(``AiCore.gateway``). AI Core is the single authority for
provider/model/config/credentials/policy.

ADR-020: the regex ``parse_question`` intent path is NOT used for routing in
the active answering path. The model-driven planner is the primary; a
deterministic offline answer seam (the fast-path executor) answers the common
data queries offline, and clarify/refuse handle the rest — never regex intent
parsing, never a growing phrase→intent table.
"""

from __future__ import annotations

from app.application.ai.core import AiCore
from app.application.ai.llm.ports import LanguageModelGateway
from app.application.ports.assistant_provider import AssistantProvider
from app.application.services.planner import PlannerService
from app.domain.repositories.object_repository import ObjectRepository
from app.infrastructure.llm.llm_provider import LlmAssistantProvider
from app.infrastructure.llm.query_understanding_provider import (
    QueryUnderstandingAssistantProvider,
)


def build_assistant_provider(
    gateway: LanguageModelGateway,
    repository: ObjectRepository,
    *,
    ai_core: AiCore | None = None,
    fallback: AssistantProvider | None = None,
    offline: AssistantProvider | None = None,
) -> AssistantProvider:
    """Compose the L4 assistant provider around a gateway from the AI Core.

    - ``fallback``/``offline`` is the deterministic offline answer seam used as
      the fast-path executor when no usable LLM gateway exists (ADR-020: the
      offline path answers common data queries deterministically; it does not
      regex-route intents).
    - When the gateway is usable, the LLM is the executor behind the planner.
    """
    if not _gateway_ready(gateway):
        # No usable LLM: the deterministic offline answer seam answers
        # (offline_only mode — the whole question goes to the offline executor).
        executor = offline or LlmAssistantProvider(gateway)
        return _wrap_with_planner(executor, ai_core, offline_only=True)
    executor = fallback or LlmAssistantProvider(gateway)
    return _wrap_with_planner(executor, ai_core, offline_only=False)


def _wrap_with_planner(
    executor: AssistantProvider, ai_core: AiCore | None, *, offline_only: bool = False
) -> AssistantProvider:
    """Wrap the answer seam with the L4 query-understanding layer."""
    if offline_only:
        from app.application.services.clarify_refuse import ClarifyRefuse
        from app.application.services.fast_path import FastPathExecutor
        from app.application.services.plan_validator import PlanValidator
        from app.application.services.planner import _UnavailablePlanner

        return QueryUnderstandingAssistantProvider(
            planner=_UnavailablePlanner(),
            executor=executor,
            fast_path=FastPathExecutor(executor),
            clarify_refuse=ClarifyRefuse(),
            validator=PlanValidator(),
            offline_only=True,
        )
    return QueryUnderstandingAssistantProvider(
        planner=PlannerService(ai_core) if ai_core is not None else _unavailable(),
        executor=executor,
    )


def _unavailable():
    from app.application.services.planner import _UnavailablePlanner

    return _UnavailablePlanner()


def _gateway_ready(gateway: LanguageModelGateway) -> bool:
    """True when the gateway can actually EXECUTE (real adapter + endpoint)."""
    try:
        return bool(gateway.health().executable)
    except Exception:  # noqa: BLE001 — a broken gateway degrades to fast-path
        return False
