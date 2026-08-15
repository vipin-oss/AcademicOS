"""V3 M16 architecture guardrails (ADR-063).

Pins the normalization contracts:

- the 5-phase order is frozen (EXPAND→BACKFILL→VALIDATE→SWITCH READS→SWITCH
  WRITES);
- a wave never serves reads after a VALIDATE failure (rollback first);
- projections are derived (the object stays the source of truth) and
  independently reversible;
- the framework is application-layer pure (no infrastructure imports).
"""

from __future__ import annotations

import inspect


def test_phase_order_is_frozen() -> None:
    import app.application.services.normalization as mod

    assert mod.PHASES == (
        "expand", "backfill", "validate", "switch_reads", "switch_writes",
    )


def test_validation_failure_rolls_back_before_reads() -> None:
    import app.application.services.normalization as mod

    src = inspect.getsource(mod.NormalizationRunner.run)
    assert src.index("validate()") < src.index("switch_reads()")
    assert "rollback()" in src


def test_framework_is_application_pure() -> None:
    import app.application.services.normalization as mod

    src = inspect.getsource(mod)
    for forbidden in ("sqlalchemy", "fastapi", "app.infrastructure", "app.api"):
        assert forbidden not in src


def test_wave_is_reversible() -> None:
    import app.application.services.user_state_wave as mod

    src = inspect.getsource(mod.UserStateWave)
    assert "def rollback" in src
