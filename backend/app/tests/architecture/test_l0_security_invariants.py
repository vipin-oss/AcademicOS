"""L0 must not introduce LLM-owned ACL or citation decisions.

Existing owners remain ``AnswerVerifier`` and the grounded-QA evidence
gate. L0 files are documentation, catalogues, and eval data only.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

L0_CODE = [
    APP_ROOT / "application" / "capabilities",
    APP_ROOT / "application" / "knowledge",
    APP_ROOT / "application" / "services" / "capability_eval.py",
]

VERIFIER = APP_ROOT / "application" / "assistant" / "verifier.py"
GROUNDED = APP_ROOT / "application" / "use_cases" / "ai" / "grounded_qa.py"


def _iter_py(root: Path):
    if root.is_file():
        yield root
        return
    yield from root.rglob("*.py")


def test_l0_modules_do_not_decide_acl_or_citations():
    forbidden = {
        "can",
        "PermissionAction",
        "object_acl_scope",
        "verify",
        "CitationBuilder",
        "AnswerVerifier",
    }
    for root in L0_CODE:
        for path in _iter_py(root):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    names.add(node.attr)
                elif isinstance(node, ast.alias):
                    names.add(node.name)
            assert not (names & forbidden), f"{path} touches ACL/citation owners: {names & forbidden}"


def test_existing_citation_owner_unchanged_in_l0():
    text = VERIFIER.read_text(encoding="utf-8")
    assert "class AnswerVerifier" in text
    assert "PermissionEvaluator" in text


def test_existing_evidence_gate_unchanged_in_l0():
    text = GROUNDED.read_text(encoding="utf-8")
    assert "def _evidence_gate" in text
    assert "document_reference" in text
