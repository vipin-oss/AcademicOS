"""Architecture guardrails: M28 SMART_LINK proposal boundary.

The M28 principle is "AI proposes, human approves, AcademicOS records".
The proposal engine is AI code; it may ONLY create SMART_LINK edges with
INFERRED provenance. Human approval (the review flow) is what upgrades
provenance to ASSERTED. This guardrail pins that boundary in source.
"""
from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
PROPOSE_LINKS = BACKEND_ROOT / "app" / "application" / "use_cases" / "ai" / "propose_links.py"


def test_propose_engine_never_creates_asserted_provenance():
    """The AI propose() path must not reference ASSERTED provenance — the
    human review step (approve/_record_decision) is the only place
    provenance becomes asserted."""
    import ast

    tree = ast.parse(PROPOSE_LINKS.read_text(encoding="utf-8"))
    propose_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "propose"
    )
    segment = ast.get_source_segment(PROPOSE_LINKS.read_text(encoding="utf-8"), propose_fn)
    assert "Provenance.ASSERTED" not in segment, (
        "the AI propose() path must never create asserted provenance"
    )


def test_propose_engine_creates_smart_link_with_inferred_provenance():
    """The engine materialises proposals as SMART_LINK / INFERRED edges."""
    source = PROPOSE_LINKS.read_text(encoding="utf-8")
    assert "RelationshipKind.SMART_LINK" in source
    assert "Provenance.INFERRED" in source


def test_propose_engine_is_application_pure():
    """The proposal engine lives in the AI use-case layer: no framework,
    no infrastructure, no API imports."""
    import ast

    tree = ast.parse(PROPOSE_LINKS.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append(node.module)
    forbidden = {
        "fastapi", "starlette", "sqlalchemy", "pydantic", "pydantic_settings",
        "httpx", "qdrant_client", "app.infrastructure", "app.api",
    }
    for resolved in imports:
        top = resolved.split(".")[0]
        assert top not in forbidden, f"forbidden import in propose_links.py: {resolved}"
        assert not resolved.startswith("app.infrastructure.")
        assert not resolved.startswith("app.api.")
