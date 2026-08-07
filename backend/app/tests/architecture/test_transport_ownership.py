"""Architecture guardrail: singular transport ownership (ADR-001).

Enforces that generative-LLM transport (httpx) is owned in exactly one place
— ``infrastructure/ai/llm/openai.py`` — and that NO feature module (the AI
Core catalogue modules, the assistant, the application layer, or the API
layer) imports httpx. This is the structural vaccine against the duplicate-
transport regression ADR-001 exists to resolve.

A failure here means the codebase is regressing toward two transport owners.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

#: The one module permitted to import httpx (the single transport owner).
TRANSPORT_OWNER = Path("app/infrastructure/ai/llm/openai.py")

#: Feature layers that must NEVER own transport. (Other infrastructure modules
#: such as ``infrastructure/external`` may use httpx for non-AI purposes and
#: are intentionally out of scope.)
FEATURE_SCOPES = (
    APP_ROOT / "infrastructure" / "ai",
    APP_ROOT / "infrastructure" / "llm",
    APP_ROOT / "infrastructure" / "assistant",
    APP_ROOT / "application",
    APP_ROOT / "api",
)


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


def _rel(path: Path) -> str:
    return str(path.relative_to(BACKEND_ROOT)).replace("\\", "/")


def test_no_feature_module_owns_transport():
    """No feature module imports httpx — transport belongs to the AI gateway
    (``infrastructure/ai/llm/openai.py``) alone (ADR-001)."""
    offenders: list[str] = []
    for scope in FEATURE_SCOPES:
        if not scope.exists():
            continue
        for path in sorted(scope.rglob("*.py")):
            if _rel(path) == TRANSPORT_OWNER.as_posix():
                continue
            if _imports_httpx(path):
                offenders.append(_rel(path))
    assert not offenders, (
        "Feature modules must not import httpx (ADR-001) — transport is owned "
        "only by infrastructure/ai/llm/openai.py. Offending module(s): "
        + ", ".join(offenders)
    )
