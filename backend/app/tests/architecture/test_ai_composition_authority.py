"""Architecture guardrail: AI Core is the sole gateway-composition authority
(ADR-001 — M11.2.1).

A "hostile audit" of M11.2 found that the assistant still constructed the
concrete ``OpenAIProvider`` directly (an AI Core bypass) and that the only
guardrail checked httpx imports. These guardrails close that gap
structurally:

1. **No feature constructs a provider.** Concrete provider gateway classes
   (``OpenAIProvider``, the placeholders, ``NotConfiguredGateway``) may be
   imported ONLY by the AI Core composition root
   (``infrastructure/ai/provider_factory.py``) and the modules that define
   them — never by the assistant, the translator, the application layer, or
   the API layer. Features obtain gateways through ``AiCore.build_gateway`` /
   ``build_gateway``.

2. **One gateway constructor.** ``build_gateway`` is defined ONLY in
   ``infrastructure/ai/provider_factory.py`` — there is no second
   composition root that instantiates providers.

Together with ``test_transport_ownership`` (httpx isolation) and
``test_ai_guardrails`` (AI Core purity + adapter independence), these make
ADR-001 machine-enforced.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

#: Concrete provider gateway classes — the things only AI Core may name.
CONCRETE_PROVIDERS = {
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "OllamaProvider",
    "LocalProvider",
    "NotConfiguredGateway",
}

#: Modules permitted to import the concrete provider classes:
#: the composition root + the modules that define them. Tests are exempt.
ALLOWED_PROVIDERS_IMPORTERS = {
    "app/infrastructure/ai/provider_factory.py",
    "app/infrastructure/ai/llm/openai.py",
    "app/infrastructure/ai/llm/placeholders.py",
}

#: The single module permitted to DEFINE the gateway constructor.
COMPOSITION_ROOT = "app/infrastructure/ai/provider_factory.py"


def _rel(path: Path) -> str:
    return str(path.relative_to(BACKEND_ROOT)).replace("\\", "/")


def _is_test(path: Path) -> bool:
    return "tests" in path.parts


def _imported_provider_names(path: Path) -> set[str]:
    """Concrete provider class names brought into scope by this module."""
    found: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in CONCRETE_PROVIDERS:
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in CONCRETE_PROVIDERS:
                    found.add(alias.name)
    return found


def test_no_feature_imports_a_concrete_provider():
    """Concrete provider classes are imported ONLY by the AI Core composition
    root and the modules that define them — never by a feature (assistant,
    translator, application, api). A feature must obtain gateways through
    ``AiCore.build_gateway`` / ``build_gateway`` (ADR-001)."""
    offenders: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if _is_test(path):
            continue
        rel = _rel(path)
        if rel in ALLOWED_PROVIDERS_IMPORTERS:
            continue
        names = _imported_provider_names(path)
        if names:
            offenders.append(f"{rel}: imports {sorted(names)}")
    assert not offenders, (
        "No feature may import a concrete provider class (ADR-001) — gateways "
        "are obtained from the AI Core only. Offending module(s): "
        + "; ".join(offenders)
    )


def test_single_gateway_constructor():
    """``build_gateway`` is defined ONLY in the AI Core composition root —
    there is exactly one transport-composition authority (ADR-001).

    Scoped to MODULE-LEVEL functions: ``AiCore.build_gateway`` is a delegating
    *method* (it calls the registry; it does not instantiate a provider), not
    a second constructor, so it is intentionally not counted here.
    """
    definers: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if _is_test(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        # Top-level (module-scope) function definitions only - not methods.
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "build_gateway":
                definers.append(_rel(path))
    assert definers == [COMPOSITION_ROOT], (
        "The module-level build_gateway must be defined only in "
        f"{COMPOSITION_ROOT} (the single composition root). Defined in: "
        + ", ".join(definers)
    )
