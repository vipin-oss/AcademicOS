"""V3 M18 architecture guardrails (ADR-065).

Pins the accreditation authority boundary:

- frameworks are data (additive registry), never code;
- AI suggestion is store-free and cannot approve evidence or lock a period;
- approval and period-lock REQUIRE a human identity (reviewer / locked_by);
- a period can only be locked after approval.
"""

from __future__ import annotations

import inspect


def test_frameworks_are_data() -> None:
    import app.application.knowledge.accreditation_frameworks as mod

    src = inspect.getsource(mod)
    assert isinstance(mod.FRAMEWORKS, tuple)
    assert "get_framework" in src


def test_ai_suggestion_is_store_free() -> None:
    import app.application.services.accreditation as mod

    src = inspect.getsource(mod.AccreditationWorkflow.suggest_evidence)
    assert "self._store" not in src
    assert "self" not in src  # staticmethod


def test_approval_requires_human_reviewer() -> None:
    import app.application.services.accreditation as mod

    sig = inspect.signature(mod.AccreditationWorkflow.approve)
    assert "reviewer" in sig.parameters


def test_period_lock_requires_human_and_approval() -> None:
    import app.application.services.accreditation as mod

    src = inspect.getsource(mod.AccreditationWorkflow.lock_period)
    assert "locked_by" in src
    assert "STATUS_APPROVED" in src  # gate: only approved can lock
