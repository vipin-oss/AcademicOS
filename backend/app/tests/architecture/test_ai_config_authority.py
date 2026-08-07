"""Architecture guardrail: AI Core is the sole configuration authority
(ADR-001 — Sprint M11.3).

A feature (the assistant, the API layer, the application layer outside the AI
Core) must NEVER construct a ``ProviderConfig``. Provider/model/credential/
base-url/generation-policy configuration is owned by the AI Core
(``application/ai`` + ``infrastructure/ai``); features obtain configured
gateways through ``AiCore.gateway`` / ``AiCore.select_provider``.

This is the ownership invariant that makes "AI Core is the single production
authority for provider, model, credentials and runtime execution"
machine-enforced. Tests are exempt.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

#: Modules permitted to CONSTRUCT ProviderConfig: the AI Core only.
ALLOWED_CONFIG_OWNERS = {
    "app/application/ai",
    "app/infrastructure/ai",
}


def _rel(path: Path) -> str:
    return str(path.relative_to(BACKEND_ROOT)).replace("\\", "/")


def _is_test(path: Path) -> bool:
    return "tests" in path.parts


def _constructs_provider_config(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = ""
            if isinstance(f, ast.Name):
                name = f.id
            elif isinstance(f, ast.Attribute):
                name = f.attr
            if name == "ProviderConfig":
                return True
    return False


def test_only_ai_core_constructs_provider_config():
    """``ProviderConfig(...)`` appears ONLY inside the AI Core. No feature
    (assistant, api, application/* outside ai) builds a provider config —
    AI Core owns configuration (ADR-001)."""
    offenders: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if _is_test(path):
            continue
        rel = _rel(path)
        if any(rel.startswith(prefix) for prefix in ALLOWED_CONFIG_OWNERS):
            continue
        if _constructs_provider_config(path):
            offenders.append(rel)
    assert not offenders, (
        "Only the AI Core (application/ai, infrastructure/ai) may construct "
        "ProviderConfig (ADR-001). Offending module(s): " + ", ".join(offenders)
    )
