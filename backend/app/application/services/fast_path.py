"""L4 frozen deterministic fast-path (Freeze Contract §13.5.2, ADR-020).

A bounded, explicit, deterministic set of ≤15 commands that execute OFFLINE
(no LLM) for the most common operations. The list MUST NOT silently grow —
``FAST_PATH_COMMANDS`` is the frozen contract; a guardrail pins its length.

The fast-path validates that a generated plan's operation is a supported
offline command; it does not answer arbitrary text (the planner/retrieval path
handles those).
"""

from __future__ import annotations

from app.application.dtos.plan import Plan

#: Frozen fast-path command list — EXACTLY these, ≤15, cannot grow.
#: (ADR-020: new commands go through the planner, never here.)
FAST_PATH_COMMANDS: tuple[str, ...] = (
    "inventory",
    "lookup",
    "list",
    "search",
    "count",
    "filter",
    "timeline",
    "navigate",
    "aggregate",
    "summarize",
    "document_qa",
    "relationship",
    "absence",
    "clarify",
    "refuse",
)

FAST_PATH_MAX = 15
assert len(FAST_PATH_COMMANDS) <= FAST_PATH_MAX, "fast-path must stay ≤15 commands"


def is_fast_path_command(operation: str) -> bool:
    return operation in FAST_PATH_COMMANDS


class FastPathExecutor:
    """Deterministic offline dispatcher for the frozen fast-path commands.

    Executes a validated plan whose operation is a fast-path command. The
    actual data work is delegated to the injected retrieval/execution seam so
    this layer stays offline-deterministic and does not duplicate retrieval.
    """

    def __init__(self, executor: object) -> None:
        # ``executor`` is the injection seam (e.g. the assistant/grounded-QA
        # service) that performs the actual data operation for a command.
        self._executor = executor

    def supports(self, plan: Plan) -> bool:
        return is_fast_path_command(plan.operation)

    def execute(self, plan: Plan, *, context: object = None) -> object:
        """Run a validated fast-path plan through the executor seam."""
        if not self.supports(plan):
            raise ValueError(f"Operation {plan.operation!r} is not a fast-path command.")
        dispatch = getattr(self._executor, "execute_fast_path", None)
        if dispatch is None:
            raise RuntimeError("FastPathExecutor requires an executor with execute_fast_path().")
        return dispatch(plan, context=context)


__all__ = [
    "FAST_PATH_COMMANDS",
    "FAST_PATH_MAX",
    "FastPathExecutor",
    "is_fast_path_command",
]
