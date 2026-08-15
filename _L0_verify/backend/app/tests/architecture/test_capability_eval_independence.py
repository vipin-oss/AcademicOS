"""Capability catalog / eval must not couple to the legacy router."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

FORBIDDEN_FROM_CAPABILITIES = (
    "app.application.assistant.intents",
    "app.application.assistant.providers",
    "parse_question",
    "ParsedQuestion",
    "RuleBasedAssistantProvider",
    "retrieval_plan",
    "formulate_query",
    "INTENT_",
)

CAPABILITY_ROOTS = [
    APP_ROOT / "application" / "capabilities",
    APP_ROOT / "application" / "services" / "capability_eval.py",
    APP_ROOT / "tests" / "eval" / "capabilities",
]

LEGACY_FILES = [
    APP_ROOT / "application" / "assistant" / "intents.py",
    APP_ROOT / "application" / "assistant" / "providers.py",
]


def _iter_py(root: Path):
    if root.is_file():
        yield root
        return
    yield from sorted(root.rglob("*.py"))


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
            out.extend(alias.name for alias in node.names)
    return out


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_capability_package_does_not_import_intents_or_providers():
    for path in _iter_py(APP_ROOT / "application" / "capabilities"):
        imported = _imported_modules(path)
        for item in imported:
            assert "assistant.intents" not in item
            assert "assistant.providers" not in item
            assert not item.startswith("INTENT_")


def test_capability_eval_service_does_not_import_intents():
    imported = _imported_modules(APP_ROOT / "application" / "services" / "capability_eval.py")
    joined = " ".join(imported)
    assert "intents" not in joined
    assert "parse_question" not in joined
    assert "retrieval_plan" not in joined


def test_capability_tests_do_not_import_intents():
    root = APP_ROOT / "tests" / "eval" / "capabilities"
    for path in _iter_py(root):
        imported = _imported_modules(path)
        for item in imported:
            assert "assistant.intents" not in item
            assert item != "parse_question"


def test_intents_and_providers_do_not_import_capabilities():
    for path in LEGACY_FILES:
        imported = _imported_modules(path)
        for item in imported:
            assert "application.capabilities" not in item
            assert "capability_eval" not in item


def test_capability_eval_ast_has_no_parse_question():
    production = [
        APP_ROOT / "application" / "capabilities",
        APP_ROOT / "application" / "services" / "capability_eval.py",
    ]
    for root in production:
        for path in _iter_py(root):
            src = _source(path)
            assert "parse_question(" not in src
            assert "from app.application.assistant.intents" not in src
