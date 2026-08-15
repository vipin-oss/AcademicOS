"""L4 model-driven planner (Freeze Contract §13.5.1, ADR-020).

Turns a normalized user request into a structured plan via
``AiCore.gateway().structured_generate()``. The planner NEVER executes model
output directly — it returns raw structured output which the QueryUnderstanding
orchestrator validates (PlanValidator) before any dispatch.

Planner output is validated against the frozen plan schema; invalid/unsafe/
unsupported plans are rejected (never executed) and routed to clarify/refuse.
"""

from __future__ import annotations

from app.application.ai.core import AiCore
from app.application.ai.errors import AiNotConfiguredError
from app.application.ai.llm.ports import StructuredGenerationPrompt

#: The frozen plan JSON schema sent to the model (and used to validate output).
PLAN_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "operation": {"type": "string"},
        "domains": {"type": "array", "items": {"type": "string"}},
        "entities": {"type": "array", "items": {"type": "string"}},
        "time_range": {"type": ["string", "null"]},
        "filters": {"type": "object"},
        "output_kind": {"type": "string"},
        "evidence_required": {"type": "boolean"},
        "sub_plans": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["operation"],
}

_SYSTEM_PROMPT = (
    "You are the AcademicOS planner. Given a user's question, produce a single "
    "structured plan with an 'operation' chosen from this frozen capability "
    "list: inventory, lookup, list, search, count, filter, summarize, compare, "
    "aggregate, timeline, document_qa, relationship, cross_domain, absence, "
    "temporal, navigate, clarify, refuse. Choose 'clarify' when the request is "
    "ambiguous (which record/range), and 'refuse' when it cannot be answered "
    "within policy. Output only the JSON plan object."
)


class PlannerError(Exception):
    """The planner could not produce a usable plan (gateway failure / not configured)."""


class PlannerService:
    def __init__(self, ai_core: AiCore) -> None:
        self._ai_core = ai_core
    def plan_for(self, question: str, *, context: str = "") -> dict:
        """Produce raw structured plan output (unvalidated).

        Returns the raw ``result.value`` dict. Raises ``PlannerError`` on
        gateway failure, misconfiguration, or non-object output. The caller
        MUST validate this output with ``PlanValidator`` before dispatch.
        """
        user = question if not context else f"{question}\n\nContext:\n{context}"
        try:
            gateway = self._ai_core.gateway()
        except (AiNotConfiguredError, Exception):  # noqa: BLE001
            raise PlannerError("Planner is not configured.") from None
        try:
            prompt = StructuredGenerationPrompt(
                system=_SYSTEM_PROMPT, user=user, schema=PLAN_SCHEMA,
            )
            result = gateway.structured_generate(prompt)
        except Exception as exc:  # noqa: BLE001 — gateway boundary
            raise PlannerError(f"Planner generation failed: {exc}") from exc
        if not isinstance(result.value, dict):
            raise PlannerError("Planner returned a non-object plan.")
        return result.value


class _UnavailablePlanner:
    """Deterministic planner used when no AiCore is available.

    Always raises ``PlannerError`` so the query-understanding orchestrator falls
    through to the offline fast-path / clarify / refuse (ADR-020) — never
    rules-v1, never regex intent parsing.

    ``offline_only = True`` signals to the query-understanding provider that the
    whole question should be answered by the deterministic offline answer seam
    (the fast-path executor), not routed through the model-driven clarify/refuse.
    """

    offline_only = True

    def plan_for(self, question: str, *, context: str = "") -> dict:
        raise PlannerError("Planner is not available (no AI Core configured).")


__all__ = ["PLAN_SCHEMA", "PlannerError", "PlannerService", "_UnavailablePlanner"]
