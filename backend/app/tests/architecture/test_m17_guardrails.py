"""V3 M17 architecture guardrails (ADR-064).

Pins the temporal-graph + identity contracts:

- relationships carry validity intervals (valid_from/valid_to, nullable);
- claims/claim_spans evidence uses ON DELETE RESTRICT (never cascade evidence
  away);
- identity resolution is read-only (proposes candidates, never auto-merges);
- transliteration is deterministic (no model/network).
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def test_relationships_carry_validity_interval() -> None:
    src = (
        REPO / "backend" / "app" / "infrastructure" / "db" / "models"
        / "object_relationship_model.py"
    ).read_text(encoding="utf-8")
    assert "valid_from" in src and "valid_to" in src


def test_evidence_fk_is_restrict_not_cascade() -> None:
    src = (
        REPO / "backend" / "alembic" / "versions" / "0024_temporal_graph_identity.py"
    ).read_text(encoding="utf-8")
    assert "ON DELETE RESTRICT" in src
    assert "ON DELETE CASCADE" not in src  # never cascade evidence away


def test_identity_resolution_is_read_only() -> None:
    import app.application.services.identity_resolution as mod

    src = inspect.getsource(mod.IdentityResolutionService.find_candidates)
    # The service only READS (get_by_id / find) — it never mutates the graph.
    for forbidden in (".save(", ".delete(", ".put(", ".remove(", ".add_relationship"):
        assert forbidden not in src


def test_transliteration_is_deterministic() -> None:
    import app.application.services.transliteration as mod

    src = inspect.getsource(mod)
    for forbidden in ("openai", "anthropic", "ollama", "httpx", "requests"):
        assert forbidden not in src.lower()
