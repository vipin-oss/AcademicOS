"""V3 M6 document classifier tests (ADR-053): deterministic stage priority."""

from __future__ import annotations

from app.application.services.document_classifier import DocumentClassifier


def test_filename_stage_classifies_grant() -> None:
    result = DocumentClassifier().classify("irrelevant body text", "sanction_letter.pdf")
    assert result.document_type_id == "grant_sanction_letter"
    assert result.method == "filename"


def test_filename_stage_classifies_office_order() -> None:
    result = DocumentClassifier().classify("", "office_order_2.txt")
    assert result.document_type_id == "office_order"
    assert result.method == "filename"


def test_heading_stage_when_filename_neutral() -> None:
    text = "OFFICE ORDER\n\nOrder Number: 1\n"
    result = DocumentClassifier().classify(text, "doc1.txt")
    assert result.document_type_id == "office_order"
    assert result.method == "heading"


def test_issuer_stage_when_heading_neutral() -> None:
    # Issuer-only keywords (principal investigator / funding agency) must
    # classify when neither filename nor heading keywords are present.
    text = "\n".join([
        "We are pleased to inform you that the proposal has been approved.",
        "The principal investigator is Dr. X and the funding agency is SERB.",
    ])
    result = DocumentClassifier().classify(text, "letter_9.txt")
    assert result.document_type_id == "grant_sanction_letter"
    assert result.method == "issuer"


def test_unknown_when_nothing_matches() -> None:
    result = DocumentClassifier().classify("completely unrelated text", "notes.txt")
    assert result.document_type_id is None
    assert result.method == "unknown"
    assert result.confidence == 0.0


def test_never_uses_a_strong_model() -> None:
    # The classifier is deterministic only — assert on imports (call graph),
    # never on prose. No AI infra, no network, no framework imports.
    import ast
    import inspect

    import app.application.services.document_classifier as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    for forbidden in ("app.infrastructure.ai", "app.api", "httpx", "requests",
                      "sqlalchemy", "openai", "anthropic", "fastapi"):
        assert not any(forbidden in name for name in imported), imported
