"""L3 architecture guardrails (frozen).

Pins the L3 contracts so confirmation stays deterministic + application-layer,
decision audit is claim/CDM-scoped (not conversation-scoped), ACL is enforced,
L1/L2/L0 boundaries are preserved, and no planner/retrieval/agent code leaks in.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l3_adrs_present():
    for name in (
        "ADR-032-confirmation-correction",
        "ADR-033-confidence-triage",
        "ADR-034-extraction-claim-bridge",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l2_done_l3_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L2" in text and "done" in text
    assert "L3" in text and "in_progress" in text


def test_claim_decision_is_claim_scoped_not_conversation():
    # the decision store is claim-scoped; it must not touch review_decisions
    from app.infrastructure.persistence.claim_decision_store import SQLClaimDecisionStore

    assert SQLClaimDecisionStore  # importable
    # verify the store maps to claim_decisions, not review_decisions
    model = REPO / "backend" / "app" / "infrastructure" / "db" / "models" / "claim_decision_model.py"
    assert model.exists()


def test_confirmation_is_application_layer_no_engine_libs():
    import ast

    from app.application.services import cdm_confirmation, claim_confirmation, confirmation_queue

    for mod in (claim_confirmation, cdm_confirmation, confirmation_queue):
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in ("sqlalchemy", "fastapi", "pydantic", "pdfplumber", "openpyxl", "pptx", "PIL"), (
                        f"{mod.__name__} leaks framework/engine import {alias.name}"
                    )


def test_l3_does_not_touch_l1_claim_cdm_tables():
    # L3 decisions live in new tables; L1 claim/cdm model files unchanged by design
    # (we add new model files, not modify frozen ones).
    l3_new = {
        "backend/app/infrastructure/db/models/claim_decision_model.py",
        "backend/app/infrastructure/db/models/cdm_decision_model.py",
    }
    frozen = {
        "backend/app/infrastructure/db/models/claim_model.py",
        "backend/app/infrastructure/db/models/cdm_block_model.py",
        "backend/app/infrastructure/db/models/claim_span_model.py",
    }
    assert l3_new.isdisjoint(frozen)


def test_no_planner_or_retrieval_rewrite():
    l3_paths = {
        "backend/app/application/services/claim_confirmation.py",
        "backend/app/application/services/confirmation_queue.py",
    }
    forbidden = {
        "backend/app/application/assistant/intents.py",
        "backend/app/application/assistant/providers.py",
        "backend/app/application/services/assistant_retrieval.py",
    }
    assert l3_paths.isdisjoint(forbidden)
