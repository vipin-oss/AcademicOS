"""V3 ADR-067 architecture guardrails.

Pins the document-intake contracts:

- document types / extraction schemas / predicate catalogue are DATA (tuples /
  dicts), never code, and the classifier + intake are deterministic-only
  (no AI/network/framework imports);
- extraction writes claims (provenance + review), never fabricates and never
  silently overwrites (duplicate -> skip, conflict -> skip + review);
- the intake service is application-layer pure (no infra/framework imports).
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


def test_registries_are_data() -> None:
    import app.application.knowledge.document_types as dt
    import app.application.knowledge.extraction_schemas as es
    import app.application.knowledge.predicate_catalogue as pc

    assert isinstance(dt.DOCUMENT_TYPES, tuple)
    assert isinstance(es.EXTRACTION_SCHEMAS, dict)
    assert isinstance(pc.CATALOGUE, tuple)


def test_intake_is_deterministic_and_application_pure() -> None:
    import app.application.services.document_classifier as dc
    import app.application.services.document_intake as mod
    import app.application.services.value_normalizer as vn

    for m in (mod, vn, dc):
        imports = _imports(m)
        for forbidden in ("app.infrastructure", "app.api", "sqlalchemy", "fastapi",
                          "httpx", "openai", "anthropic", "ollama"):
            assert not any(forbidden in name for name in imports), m.__name__


def test_conflict_never_overwrites() -> None:
    import app.application.services.document_intake as mod

    src = inspect.getsource(mod.DocumentIntakeService.analyze)
    # conflict path records a "skipped" outcome (never a write)
    assert 'reason="conflict"' in src


def test_schemas_reference_known_predicates() -> None:
    import app.application.knowledge.extraction_schemas as es
    import app.application.knowledge.predicate_catalogue as pc

    known = {s.predicate_id for s in pc.CATALOGUE}
    for fields in es.EXTRACTION_SCHEMAS.values():
        for f in fields:
            assert f.predicate_id in known, f.predicate_id
