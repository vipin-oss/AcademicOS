"""Architecture guardrails for the AI Core layers (Sprint M11.1).

Automated enforcement of the M11 blueprint's composition rules:

  1. ``application/ai`` + ``application/use_cases/ai`` are pure: no
     infrastructure, no API, no framework, and no other AI-feature
     modules (assistant/intake) imports — future capabilities compose
     through ports only.
  2. ``infrastructure/ai`` adapters never import each other (each adapter
     is independently replaceable) and never import the API layer.
  3. The composition seam is unique: only the DI layer
     (``api/dependencies/ai.py``) and the factory
     (``infrastructure/ai/provider_factory.py``) may import both sides.
  4. Every AI module imports cleanly (no runtime cycles).

These guardrails are additive — the Domain guardrails (7/7) are untouched.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
AI_APPLICATION_ROOT = BACKEND_ROOT / "app" / "application" / "ai"
AI_USE_CASES_ROOT = BACKEND_ROOT / "app" / "application" / "use_cases" / "ai"
AI_INFRASTRUCTURE_ROOT = BACKEND_ROOT / "app" / "infrastructure" / "ai"

FORBIDDEN_FRAMEWORKS = {
    "fastapi",
    "starlette",
    "sqlalchemy",
    "pydantic",
    "pydantic_settings",
    "httpx",
    "requests",
    "qdrant_client",
    "openai",
    "anthropic",
    "google",
    "ollama",
}

#: Application packages the AI core must not reach into (composition via
#: ports only; future capabilities stay independent).
FORBIDDEN_AI_SIBLINGS = {
    "app.application.assistant",
    "app.application.intake",
}


def _module_name_from_path(path: Path) -> str:
    rel = path.relative_to(BACKEND_ROOT)
    return ".".join(rel.with_suffix("").parts)


def _collect_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                out.append(node.module)
    return out


def _iter_py(root: Path):
    for path in sorted(root.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        yield _module_name_from_path(path), path


def find_application_violations() -> list[str]:
    """Pure-application violations in the AI application layer."""
    violations: list[str] = []
    roots = (AI_APPLICATION_ROOT, AI_USE_CASES_ROOT)
    for root in roots:
        if not root.exists():
            continue
        for mod_name, path in _iter_py(root):
            for resolved in _collect_imports(path):
                top = resolved.split(".")[0]
                if top in FORBIDDEN_FRAMEWORKS:
                    violations.append(
                        f"{mod_name}: forbidden framework import '{resolved}'"
                    )
                if resolved == "app.infrastructure" or resolved.startswith(
                    "app.infrastructure."
                ):
                    violations.append(
                        f"{mod_name}: application imports infrastructure '{resolved}'"
                    )
                if resolved == "app.api" or resolved.startswith("app.api."):
                    violations.append(
                        f"{mod_name}: application imports api '{resolved}'"
                    )
                for sibling in FORBIDDEN_AI_SIBLINGS:
                    if resolved == sibling or resolved.startswith(sibling + "."):
                        violations.append(
                            f"{mod_name}: imports AI sibling '{resolved}'"
                        )
    return violations


def find_infrastructure_violations() -> list[str]:
    """Cross-adapter / API violations in the AI infrastructure layer."""
    violations: list[str] = []
    if not AI_INFRASTRUCTURE_ROOT.exists():
        return violations
    for mod_name, path in _iter_py(AI_INFRASTRUCTURE_ROOT):
        for resolved in _collect_imports(path):
            if resolved == "app.infrastructure" or resolved.startswith(
                "app.infrastructure."
            ):
                if resolved.startswith("app.infrastructure.ai"):
                    # The composition root (provider_factory) is the ONE
                    # allowed cross-adapter importer by design.
                    if mod_name == "app.infrastructure.ai.provider_factory":
                        continue
                    violations.append(
                        f"{mod_name}: adapter imports another AI adapter "
                        f"'{resolved}' (adapters must be independent)"
                    )
                else:
                    # The composition root (provider_factory) MAY import
                    # non-AI infrastructure (e.g. the HashingEmbedder fallback).
                    if mod_name == "app.infrastructure.ai.provider_factory":
                        continue
                    violations.append(
                        f"{mod_name}: imports infrastructure '{resolved}' "
                        f"(AI adapters compose through the factory only)"
                    )
            if resolved == "app.api" or resolved.startswith("app.api."):
                violations.append(f"{mod_name}: adapter imports api '{resolved}'")
    return violations


# ----------------------------------------------------------------- tests


def test_ai_application_layer_is_pure():
    violations = find_application_violations()
    assert not violations, "AI application layer purity violated:\n" + "\n".join(
        violations
    )


def test_ai_infrastructure_adapters_are_independent():
    violations = find_infrastructure_violations()
    assert not violations, (
        "AI infrastructure adapter independence violated:\n" + "\n".join(violations)
    )


def test_ai_composition_seams_are_the_only_crossings():
    """Only api/dependencies/ai.py and infrastructure/ai/provider_factory.py
    compose application + infrastructure for the AI core."""
    seams = {
        "app.api.dependencies.ai",
        "app.infrastructure.ai.provider_factory",
    }
    for root in (AI_APPLICATION_ROOT, AI_USE_CASES_ROOT):
        for mod_name, path in _iter_py(root):
            for resolved in _collect_imports(path):
                if resolved.startswith("app.infrastructure"):
                    assert mod_name in seams, (
                        f"{mod_name} imports infrastructure — composition must "
                        f"happen only in {sorted(seams)}"
                    )


def test_ai_modules_import_cleanly():
    import_errors: list[str] = []
    for root in (AI_APPLICATION_ROOT, AI_USE_CASES_ROOT, AI_INFRASTRUCTURE_ROOT):
        if not root.exists():
            continue
        for mod_name, _path in _iter_py(root):
            try:
                importlib.import_module(mod_name)
            except Exception as exc:  # noqa: BLE001 - surface any import failure
                import_errors.append(f"{mod_name}: {exc!r}")
    assert not import_errors, "AI modules failed to import:\n" + "\n".join(
        import_errors
    )
