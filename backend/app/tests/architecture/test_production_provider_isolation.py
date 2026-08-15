"""Architecture guardrail: production cannot reach the bypass constructors
(ADR-001 — Sprint M11.3.1 #5).

``LlmAssistantProvider`` (whose legacy client/model/base_url constructor builds
a gateway outside the catalogue) and ``build_gateway_from_params`` (the raw-
parameter gateway builder) are compatibility/test-only seams. Production
layers (the API and the application layer) must resolve providers through the
AI Core (``AiCore.select_provider`` / ``AiCore.gateway``) and compose through
``build_assistant_provider``; they may never import these constructors, so the
bypass cannot participate in production execution. Tests are exempt.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

BYPASS_NAMES = {"LlmAssistantProvider", "build_gateway_from_params"}
SCOPES = (APP_ROOT / "api", APP_ROOT / "application")


def _rel(path: Path) -> str:
    return str(path.relative_to(BACKEND_ROOT)).replace("\\", "/")


def _is_test(path: Path) -> bool:
    return "tests" in path.parts


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_production_layers_do_not_import_bypass_constructors():
    """The API and application layers never import the compatibility/test-only
    gateway constructors — providers come from the AI Core only."""
    offenders: list[str] = []
    for scope in SCOPES:
        if not scope.exists():
            continue
        for path in sorted(scope.rglob("*.py")):
            if _is_test(path):
                continue
            hit = _imported_names(path) & BYPASS_NAMES
            if hit:
                offenders.append(f"{_rel(path)}: {sorted(hit)}")
    assert not offenders, (
        "Production layers (api/, application/) must not import the bypass "
        "constructors LlmAssistantProvider / build_gateway_from_params "
        "(ADR-001). Offending module(s): " + "; ".join(offenders)
    )
