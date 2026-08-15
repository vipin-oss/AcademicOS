"""V3 M7 architecture guardrails (ADR-054).

Pins the review-at-scale contracts:

- bulk confirmation is a human, attributable, non-authoritative shortcut:
  it confirms AUTO_SUGGESTED (never PROPOSED), requires a reviewer id, and
  writes a decision per claim (never a silent status flip);
- extraction health / conflict reporting are READ-ONLY aggregations (no new
  writers, no new schema) over the L3 decision trail + claim store;
- conflict reporting never resolves anything (escalate only);
- the M7 services stay application-layer pure (no engine/framework imports).
"""

from __future__ import annotations

import inspect

from app.application.services.bulk_confirmation import BulkConfirmationService
from app.application.services.extraction_health import ConflictReport, ExtractionHealthService


def test_bulk_confirm_only_touches_auto_suggested() -> None:
    src = inspect.getsource(BulkConfirmationService.confirm_suggested)

    assert "AUTO_SUGGESTED" in src
    assert "PROPOSED" not in src


def test_bulk_confirm_requires_reviewer() -> None:
    sig = inspect.signature(BulkConfirmationService.confirm_suggested)
    assert "reviewer" in sig.parameters


def test_conflict_report_is_read_only() -> None:
    # Conflict reporting must never mutate: it only reads the claim store via
    # by_status / confirmed_by_predicate. Assert on mutating method calls.
    src = inspect.getsource(ConflictReport.conflicts)
    for forbidden in (".set_status(", ".confirm(", ".reject(", ".supersede(", ".put(", ".propose("):
        assert forbidden not in src


def test_m7_services_are_application_pure() -> None:
    for mod in (BulkConfirmationService, ExtractionHealthService, ConflictReport):
        module = inspect.getmodule(mod)
        assert module.__name__.startswith("app.application"), module.__name__
    # no infrastructure imports in the two service modules
    import app.application.services.bulk_confirmation as bm
    import app.application.services.extraction_health as eh

    for m in (bm, eh):
        src = inspect.getsource(m)
        for forbidden in ("app.infrastructure", "app.api", "sqlalchemy", "fastapi"):
            assert forbidden not in src, m.__name__


def test_bulk_confirm_writes_a_decision_per_claim() -> None:
    src = inspect.getsource(BulkConfirmationService.confirm_suggested)
    # it routes through the confirmation service (decision trail), not raw
    # status flips.
    assert "approve" in src
