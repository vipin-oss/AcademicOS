"""Architecture guardrail: singular transport ownership (Sprint M11.2 — ADR-001).

Enforces that generative-LLM transport is owned in exactly one place —
``infrastructure/ai/llm/openai.py`` (the real ``LanguageModelGateway``
adapter) — and that the retired transport home (``infrastructure/llm/``) no
longer touches the wire. This is the structural vaccine against the
duplicate-transport regression that ADR-001 exists to resolve: the
assistant's LLM module must remain a thin translator over a
``LanguageModelGateway`` and may never re-acquire its own httpx transport.

A failure here means the codebase is regressing toward two transport owners.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
LLM_ROOT = BACKEND_ROOT / "app" / "infrastructure" / "llm"


def _imports_httpx(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "httpx" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "httpx":
                return True
    return False


def test_assistant_llm_module_owns_no_transport():
    """``infrastructure/llm`` must not import httpx.

    Transport moved to the AI gateway (``infrastructure/ai/llm/openai.py``)
    in M11.2 (ADR-001). ``LlmAssistantProvider`` is a pure translator over a
    ``LanguageModelGateway``; if it re-imports httpx the duplicate-transport
    regression has returned.
    """
    assert LLM_ROOT.exists()
    offenders = [
        p.name
        for p in sorted(LLM_ROOT.glob("*.py"))
        if p.name != "__init__.py" and _imports_httpx(p)
    ]
    assert not offenders, (
        "infrastructure/llm must not own httpx transport (ADR-001). "
        "Transport belongs to infrastructure/ai/llm/openai.py. "
        "Offending module(s): " + ", ".join(offenders)
    )
