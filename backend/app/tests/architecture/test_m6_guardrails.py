"""V3 M6 architecture guardrails (ADR-053).

Pins the M6 contracts so later milestones cannot silently regress them:

- document types + extraction templates + predicate catalogue are DATA
  (tuples), never code / a closed enum;
- templates reference only known predicates and known document types;
- the classifier is deterministic-only (no LLM / strong model / network);
- suggestion is fail-safe (unmeasured predicate -> never AUTO_SUGGESTED);
- the Wave-1 golden corpus has >= 3 labelled documents per type.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from app.application.knowledge.document_types import DOCUMENT_TYPES
from app.application.knowledge.extraction_templates import EXTRACTION_TEMPLATES
from app.application.knowledge.predicate_catalogue import CATALOGUE
from app.application.services.suggestion_policy import SuggestionPolicy

REPO = Path(__file__).resolve().parents[4]


def test_knowledge_registries_are_data_tuples() -> None:
    assert isinstance(CATALOGUE, tuple)
    assert isinstance(DOCUMENT_TYPES, tuple)
    assert isinstance(EXTRACTION_TEMPLATES, tuple)


def test_template_referential_integrity() -> None:
    predicates = {s.predicate_id for s in CATALOGUE}
    types = {t.type_id for t in DOCUMENT_TYPES}
    for template in EXTRACTION_TEMPLATES:
        assert template.document_type_id in types
        assert set(template.predicate_ids) <= predicates


def _imported_names(mod) -> set[str]:
    import ast

    tree = ast.parse(inspect.getsource(mod))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_classifier_is_deterministic_only() -> None:
    import app.application.services.document_classifier as classifier_mod
    import app.application.services.typed_extraction as typed_mod

    forbidden = ("app.infrastructure.ai", "app.api", "httpx", "requests",
                 "sqlalchemy", "openai", "anthropic", "fastapi")
    for mod in (classifier_mod, typed_mod):
        imports = _imported_names(mod)
        assert not any(f in name for f in forbidden for name in imports), imports


def test_suggestion_is_failsafe_when_unmeasured() -> None:
    from app.application.services.suggestion_policy import SAFE_FIELDS

    policy = SuggestionPolicy()
    for spec in CATALOGUE:
        if spec.predicate_id in SAFE_FIELDS:
            # Safe fields are always allowed (deterministic extraction)
            assert policy.allows_auto_suggest(spec.predicate_id) is True
        else:
            # Non-safe unmeasured fields are blocked (fail-safe)
            assert policy.allows_auto_suggest(spec.predicate_id) is False


def test_golden_corpus_has_three_docs_per_type() -> None:
    from app.tests.eval.m6_golden_documents import GOLDEN_DOCUMENTS

    by_type: dict[str, int] = {}
    for _filename, doc_type, _text, truth in GOLDEN_DOCUMENTS:
        by_type[doc_type] = by_type.get(doc_type, 0) + 1
        assert truth, "every golden document must carry ground truth"
    assert by_type.get("grant_sanction_letter", 0) >= 3
    assert by_type.get("office_order", 0) >= 3


def test_m6_does_not_import_engine_libs() -> None:
    import app.application.services.fact_extraction as fact_mod

    imports = _imported_names(fact_mod)
    for forbidden in ("pypdf", "pdfplumber", "docx", "openpyxl", "pptx", "PIL"):
        assert not any(forbidden in name for name in imports), imports
