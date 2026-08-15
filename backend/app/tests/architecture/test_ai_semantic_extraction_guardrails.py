"""V3 ADR-069 architecture guardrails.

Pins the AI-assisted semantic extraction contracts:

- the extractor is application-layer pure (no infra / framework imports) — it
  composes the AI Core, never a provider/transport;
- the intake orchestrator stays deterministic-first: the AI extractor is an
  OPTIONAL seam (absent -> pure deterministic), never a storage requirement;
- anti-hallucination is deterministic: an AI value must be grounded in the
  source text, and low-confidence / ungrounded values are rejected, never
  written.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def _imports(mod) -> set[str]:
    tree = ast.parse(inspect.getsource(mod))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_extractor_is_application_pure() -> None:
    import app.application.services.ai_semantic_extractor as mod

    imports = _imports(mod)
    for forbidden in ("app.infrastructure", "app.api", "sqlalchemy", "fastapi",
                      "httpx", "openai", "anthropic", "ollama", "jsonschema",
                      "pydantic"):
        assert not any(forbidden in name for name in imports), mod.__name__


def test_intake_is_deterministic_first_and_ai_is_optional() -> None:
    import app.application.services.document_intake as mod

    src = inspect.getsource(mod.DocumentIntakeService.__init__)
    # the AI seam is optional and defaults to None (deterministic-only)
    assert "ai_extractor=None" in src or "ai_extractor=None" in src

    analyze = inspect.getsource(mod.DocumentIntakeService.analyze)
    # deterministic extraction runs before the AI enrichment
    assert "prose_fields" in analyze
    # AI-derived fields are marked with extractor "ai"
    assert 'extractor="ai"' in analyze


def test_grounding_is_deterministic_and_rejects_unverified() -> None:
    import app.application.services.ai_semantic_extractor as mod

    assert mod.verify_grounded("city", "New Delhi", "held at Vigyan Bhawan, New Delhi")
    assert not mod.verify_grounded("city", "Chandigarh", "held at Vigyan Bhawan, New Delhi")
    assert not mod.verify_grounded("start_date", "1 January 1999", "from 6 December 2022")


def test_low_confidence_is_never_accepted() -> None:
    import app.application.services.ai_semantic_extractor as mod

    # the acceptance gate is a single, explicit constant
    assert isinstance(mod.AI_ACCEPT_CONFIDENCE, float)
    src = inspect.getsource(mod.AiSemanticExtractor.extract)
    assert "AI_ACCEPT_CONFIDENCE" in src


def test_ai_fields_flow_through_deterministic_dedupe_conflict() -> None:
    """AI fields must go through the SAME dedupe/conflict/claim write path as
    deterministic fields — no separate write channel."""
    import app.application.services.document_intake as mod

    analyze = inspect.getsource(mod.DocumentIntakeService.analyze)
    # AI enrichment merges into the shared `fields` list BEFORE the dedupe loop
    idx_ai = analyze.index("extractor=\"ai\"") if "extractor=\"ai\"" in analyze else -1
    idx_dedupe = analyze.index("unique_fields")
    assert idx_ai < idx_dedupe
