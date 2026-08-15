"""L4 plan validator — deterministic (Freeze Contract §13.5.4, ADR-020).

Validates raw model/planner output against the frozen plan schema BEFORE any
dispatch. Model output is untrusted: a plan that fails validation is rejected
and routed to clarify/refuse — never executed, never substring-matched.

Rules:
- ``operation`` must be a frozen capability id.
- ``domains``/``entities`` must be lists of strings (bounded).
- ``filters`` must be a dict (bounded).
- ``sub_plans`` are validated recursively (bounded depth).
- Unknown/malformed fields → invalid plan (rejected).
"""

from __future__ import annotations

from app.application.capabilities.registry import is_frozen_capability
from app.application.dtos.plan import Plan

#: Bounds to keep a single plan small and cheap to validate.
_MAX_ENTITIES = 32
_MAX_DOMAINS = 16
_MAX_FILTER_KEYS = 32
_MAX_SUBPLAN_DEPTH = 3

#: output kinds accepted by the frozen contract.
_VALID_OUTPUT_KINDS = {"answer", "list", "count", "timeline", "card", "clarification", "summary"}


class PlanValidationError(Exception):
    """A plan failed deterministic validation."""


class PlanValidator:
    def validate(self, raw: object, *, depth: int = 0) -> Plan:
        """Validate raw (dict from structured_generate) → Plan.

        Raises ``PlanValidationError`` for any invalid/unsafe/unsupported plan.
        """
        if depth > _MAX_SUBPLAN_DEPTH:
            raise PlanValidationError("Plan nesting exceeds max depth.")
        if not isinstance(raw, dict):
            raise PlanValidationError("Plan must be a JSON object.")
        operation = raw.get("operation")
        if not isinstance(operation, str) or not is_frozen_capability(operation):
            raise PlanValidationError(f"Operation {operation!r} is not a frozen capability.")

        domains = self._str_list(raw.get("domains"), "domains", _MAX_DOMAINS)
        entities = self._str_list(raw.get("entities"), "entities", _MAX_ENTITIES)

        time_range = raw.get("time_range")
        if time_range is not None and not isinstance(time_range, str):
            raise PlanValidationError("time_range must be a string or null.")

        filters = raw.get("filters") or {}
        if not isinstance(filters, dict) or len(filters) > _MAX_FILTER_KEYS:
            raise PlanValidationError("filters must be a bounded object.")
        if not all(isinstance(k, str) for k in filters):
            raise PlanValidationError("filters keys must be strings.")

        output_kind = raw.get("output_kind") or "answer"
        if output_kind not in _VALID_OUTPUT_KINDS:
            raise PlanValidationError(f"output_kind {output_kind!r} not supported.")

        evidence_required = bool(raw.get("evidence_required", False))
        if not isinstance(raw.get("evidence_required", False), bool):
            raise PlanValidationError("evidence_required must be a boolean.")

        sub_raw = raw.get("sub_plans") or []
        if not isinstance(sub_raw, list) or len(sub_raw) > 4:
            raise PlanValidationError("sub_plans must be a small list.")
        sub_plans = tuple(
            self.validate(sub, depth=depth + 1) for sub in sub_raw
        )

        return Plan(
            operation=operation,
            domains=domains,
            entities=entities,
            time_range=time_range,
            filters=filters,
            output_kind=output_kind,
            evidence_required=evidence_required,
            sub_plans=sub_plans,
        )

    @staticmethod
    def _str_list(value: object, name: str, limit: int) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or len(value) > limit:
            raise PlanValidationError(f"{name} must be a bounded list of strings.")
        if not all(isinstance(v, str) for v in value):
            raise PlanValidationError(f"{name} entries must be strings.")
        return tuple(value)


__all__ = ["PlanValidationError", "PlanValidator"]
