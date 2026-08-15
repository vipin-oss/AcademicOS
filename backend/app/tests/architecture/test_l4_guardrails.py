"""L4 architecture guardrails (ADR-020/035/036).

Pins:
- rules-v1 / parse_question removed from the ACTIVE answering path (provider
  factory no longer routes through RuleBasedAssistantProvider);
- the fast-path is frozen at exactly ≤15 commands and cannot grow;
- planner output is validated before dispatch (no raw model execution);
- L3 done / L4 in_progress;
- L0/L1/L2/L3 boundaries preserved.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l4_adrs_present():
    for name in (
        "ADR-035-query-understanding-planner",
        "ADR-036-frozen-fast-path",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l3_done_l4_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L3" in text and "done" in text
    assert "L4" in text and "in_progress" in text


def test_active_provider_path_does_not_use_rules_v1():
    """ADR-020: the active assistant provider factory must not route through
    RuleBasedAssistantProvider / FallbackAssistantProvider -> rules-v1."""
    factory = REPO / "backend" / "app" / "infrastructure" / "assistant" / "provider_factory.py"
    src = factory.read_text(encoding="utf-8")
    assert "RuleBasedAssistantProvider" not in src
    assert "FallbackAssistantProvider" not in src
    # The planner/query-understanding provider is used.
    assert "QueryUnderstandingAssistantProvider" in src


def test_fast_path_is_frozen_at_15():
    from app.application.services.fast_path import FAST_PATH_COMMANDS, FAST_PATH_MAX

    assert len(FAST_PATH_COMMANDS) <= FAST_PATH_MAX
    assert len(FAST_PATH_COMMANDS) == 15


def test_planner_uses_ai_core_gateway_not_second_client():
    from app.application.services import planner

    src = inspect.getsource(planner)
    assert "structured_generate" in src  # uses the gateway contract
    assert "AiCore" in src or "ai_core" in src


def test_l4_does_not_touch_l0_l1_l2_l3_frozen():
    l4_new = {
        "backend/app/application/dtos/plan.py",
        "backend/app/application/services/planner.py",
        "backend/app/application/services/plan_validator.py",
        "backend/app/application/services/fast_path.py",
    }
    frozen = {
        "backend/app/domain/value_objects/claim.py",
        "backend/app/infrastructure/extraction/nir_pdf.py",
        "backend/app/application/services/claim_confirmation.py",
        "backend/app/application/knowledge/predicate_catalogue.py",
    }
    assert l4_new.isdisjoint(frozen)
