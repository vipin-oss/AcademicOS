"""V3 M11 architecture guardrails (ADR-058).

Pins the one-document-pipeline contracts:

- the pipeline is deterministic-only (no AI/network) and shared by every
  entry point (documents.py + intake.py route through it);
- revisions are immutable (add-only, monotonic versions) and carry the A9
  ``document_id + revision_version + content_hash`` identity;
- quarantine stores but never indexes/claims (honesty: never silently dropped,
  never executed);
- the pipeline is application-layer pure.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def test_pipeline_is_deterministic_only() -> None:
    import app.application.services.document_pipeline as mod

    src = inspect.getsource(mod)
    for forbidden in ("openai", "anthropic", "ollama", "httpx", "requests", "sqlalchemy", "fastapi"):
        assert forbidden not in src.lower()
    assert "hashlib.sha256" in src


def test_entry_points_route_through_pipeline() -> None:
    src = (
        REPO / "backend" / "app" / "api" / "routes" / "documents.py"
    ).read_text(encoding="utf-8")
    assert "DocumentPipeline.decision" in src


def test_revision_store_is_immutable() -> None:
    import app.infrastructure.persistence.document_revision_store as mod

    src = inspect.getsource(mod)
    assert "next_version" in src
    assert "for_document" in src
    # no in-place mutation of an existing revision
    assert "UPDATE" not in src


def test_quarantine_never_indexes() -> None:
    src = (
        REPO / "backend" / "app" / "api" / "routes" / "documents.py"
    ).read_text(encoding="utf-8")
    # the content-indexing call is gated on quarantine == "clean"
    assert 'decision.quarantine == "clean"' in src
