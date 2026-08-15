"""V3 ADR-068 guardrails: domain routing + prose extraction + conversational guard."""

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


def test_router_reuses_existing_create_use_cases() -> None:
    import app.application.services.domain_record_router as mod

    src = inspect.getsource(mod)
    assert "CreateEventUseCase" in src
    assert "CreatePublicationUseCase" in src
    assert "CreateProjectUseCase" in src
    assert "CreateCommitteeUseCase" in src
    # duplicate detection is delegated to the frozen helpers
    assert "find_event_duplicates" in src
    assert "find_publication_duplicates" in src
    assert "find_project_duplicates" in src
    assert "find_committee_duplicates" in src


def test_router_is_application_pure() -> None:
    import app.application.services.domain_record_router as mod
    import app.application.services.prose_extractor as pe

    for m in (mod, pe):
        imports = _imports(m)
        for forbidden in ("app.infrastructure", "app.api", "sqlalchemy", "fastapi"):
            assert not any(forbidden in name for name in imports), m.__name__


def test_claim_only_for_unmodeled_types() -> None:
    import app.application.services.domain_record_router as mod

    assert "award" not in mod.ROUTABLE
    assert "appointment" not in mod.ROUTABLE
    assert "experience" not in mod.ROUTABLE


def test_prose_extractor_is_deterministic() -> None:
    import app.application.services.prose_extractor as pe

    src = inspect.getsource(pe)
    for forbidden in ("openai", "ollama", "httpx", "gateway", "ai_core"):
        assert forbidden not in src.lower()


def test_conversational_guard_preserves_domain_questions() -> None:
    import app.application.services.assistant_retrieval as ar

    src = inspect.getsource(ar.retrieval_plan)
    assert "_is_conversational" in src
    assert "noun is None" in src
