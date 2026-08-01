"""Architecture guardrails for the Domain layer.

These tests are the automated enforcement of the frozen architecture. They MUST
fail the build (CI) the moment any future code breaks Domain isolation:

  1. Domain imports only the standard library and ``app.domain.*``.
  2. No framework dependency exists in Domain
     (no SQLAlchemy, FastAPI, JWT, Qdrant, Pydantic, etc.).
  3. No infrastructure / other app-layer imports exist in Domain.
  4. Repository interfaces remain abstract (not implemented here).
  5. No circular imports exist within Domain.

The Domain is frozen and is NOT modified by this file. This file adds tests
only. Run with: ``pytest app/tests/architecture`` (or ``python -m pytest``).
"""
from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DOMAIN_ROOT = BACKEND_ROOT / "app" / "domain"

# Explicit framework packages that must never appear in Domain.
FORBIDDEN_FRAMEWORKS = {
    "sqlalchemy",
    "alembic",
    "fastapi",
    "starlette",
    "uvicorn",
    "jwt",
    "pyjwt",
    "qdrant",
    "qdantic" if False else "qdrant_client",
    "pydantic",
    "pydantic_settings",
    "httpx",
    "requests",
    "psycopg2",
    "psycopg",
    "boto3",
    "botocore",
    "redis",
    "motor",
    "passlib",
    "bcrypt",
    "msal",
    "google",
    "azure",
    "minio",
}

# Other app layers that Domain must never reach into.
FORBIDDEN_APP_LAYERS = {
    "app.core",
    "app.infrastructure",
    "app.api",
    "app.main",
    "app.tests",
}


def _stdlib_set() -> set[str]:
    """Best-effort standard-library module set (version tolerant)."""
    names: set[str] = set()
    try:
        names |= set(sys.stdlib_module_names)  # type: ignore[attr-defined]
    except AttributeError:
        pass
    names |= {
        "abc", "argparse", "ast", "asyncio", "base64", "bisect", "collections",
        "concurrent", "configparser", "contextlib", "copy", "csv", "dataclasses",
        "datetime", "decimal", "difflib", "dis", "enum", "functools", "gc",
        "glob", "gzip", "hashlib", "heapq", "html", "http", "importlib", "inspect",
        "io", "itertools", "json", "logging", "math", "mimetypes", "os", "pathlib",
        "pickle", "platform", "pprint", "queue", "random", "re", "secrets", "shlex",
        "shutil", "signal", "socket", "sqlite3", "ssl", "stat", "string", "struct",
        "subprocess", "sys", "tempfile", "textwrap", "threading", "time",
        "traceback", "types", "typing", "unicodedata", "unittest", "urllib", "uuid",
        "warnings", "weakref", "xml", "zipfile", "__future__",
    }
    return names


STDLIB = _stdlib_set()


def _module_name_from_path(path: Path) -> str:
    rel = path.relative_to(BACKEND_ROOT)
    return ".".join(rel.with_suffix("").parts)


def _resolve_module(current: str, level: int, module: str | None) -> str:
    """Resolve an import (possibly relative) to an absolute dotted module."""
    parts = current.split(".")
    if level > 0:
        base = parts[: max(len(parts) - level, 1)]
        if module:
            return ".".join(base + module.split("."))
        return ".".join(base)
    return module or ""


def iter_domain_modules():
    for path in sorted(DOMAIN_ROOT.rglob("*.py")):
        yield _module_name_from_path(path), path


def _collect_imports(path: Path) -> list[tuple[int, str | None]]:
    """Return (level, module) for every import statement in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[int, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((0, alias.name))
        elif isinstance(node, ast.ImportFrom):
            out.append((node.level or 0, node.module))
    return out


def find_violations() -> list[str]:
    """Static analysis: list human-readable architecture violations."""
    violations: list[str] = []
    for mod_name, path in iter_domain_modules():
        for level, module in _collect_imports(path):
            if level == 0 and module is None:
                continue
            resolved = _resolve_module(mod_name, level, module)
            top = resolved.split(".")[0]
            if top == "app":
                if resolved != "app.domain" and not resolved.startswith("app.domain."):
                    violations.append(
                        f"{mod_name}: imports '{resolved}' (only app.domain.* allowed)"
                    )
                continue
            if top in FORBIDDEN_FRAMEWORKS:
                violations.append(f"{mod_name}: forbidden framework import '{resolved}'")
                continue
            if resolved in FORBIDDEN_APP_LAYERS or any(
                resolved == f or resolved.startswith(f + ".") for f in FORBIDDEN_APP_LAYERS
            ):
                violations.append(f"{mod_name}: imports app layer '{resolved}'")
                continue
            if top not in STDLIB:
                violations.append(
                    f"{mod_name}: non-stdlib, non-domain import '{resolved}'"
                )
    return violations


def build_internal_graph() -> dict[str, set[str]]:
    """Directed graph of intra-Domain imports (for cycle detection)."""
    graph: dict[str, set[str]] = {}
    for mod_name, path in iter_domain_modules():
        graph.setdefault(mod_name, set())
        for level, module in _collect_imports(path):
            if level == 0 and module is None:
                continue
            resolved = _resolve_module(mod_name, level, module)
            if resolved == "app.domain" or resolved.startswith("app.domain."):
                graph[mod_name].add(resolved)
    return graph


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GREY
        stack.append(node)
        for nxt in graph.get(node, ()):
            if nxt not in color:
                continue
            if color[nxt] == GREY:
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
            if color[nxt] == WHITE:
                cyc = visit(nxt)
                if cyc:
                    return cyc
        color[node] = BLACK
        stack.pop()
        return None

    for node in graph:
        if color[node] == WHITE:
            cyc = visit(node)
            if cyc:
                return cyc
    return None


# ----------------------------------------------------------------- tests


def test_domain_imports_only_stdlib_and_app_domain():
    violations = find_violations()
    assert not violations, "Architecture violation(s) in Domain:\n" + "\n".join(violations)


def test_no_framework_imports_in_domain():
    frameworks_seen: list[str] = []
    for mod_name, path in iter_domain_modules():
        for level, module in _collect_imports(path):
            if level == 0 and module is None:
                continue
            resolved = _resolve_module(mod_name, level, module)
            top = resolved.split(".")[0]
            if top in FORBIDDEN_FRAMEWORKS:
                frameworks_seen.append(f"{mod_name} -> {resolved}")
    assert not frameworks_seen, (
        "Domain must not import frameworks (SQLAlchemy/FastAPI/JWT/Qdrant/...):\n"
        + "\n".join(frameworks_seen)
    )


def test_no_infrastructure_imports_in_domain():
    seen: list[str] = []
    for mod_name, path in iter_domain_modules():
        for level, module in _collect_imports(path):
            if level == 0 and module is None:
                continue
            resolved = _resolve_module(mod_name, level, module)
            if resolved in FORBIDDEN_APP_LAYERS or any(
                resolved == f or resolved.startswith(f + ".") for f in FORBIDDEN_APP_LAYERS
            ):
                seen.append(f"{mod_name} -> {resolved}")
    assert not seen, "Domain must not import infrastructure/other app layers:\n" + "\n".join(seen)


def test_repository_interfaces_remain_abstract():
    from app.domain.repositories.base import Repository
    from app.domain.repositories.object_repository import ObjectRepository

    assert inspect.isabstract(Repository), "Repository must stay abstract"
    assert inspect.isabstract(ObjectRepository), "ObjectRepository must stay abstract"

    required_base = {"save", "get_by_id", "find_by_ids", "exists", "delete"}
    required_obj = {"find_by_type", "find_by_status", "find_related", "find_by_metadata"}
    assert required_base <= Repository.__abstractmethods__, (
        f"Repository missing abstract methods: {required_base - Repository.__abstractmethods__}"
    )
    assert required_obj <= ObjectRepository.__abstractmethods__, (
        f"ObjectRepository missing abstract methods: "
        f"{required_obj - ObjectRepository.__abstractmethods__}"
    )

    # Cannot be instantiated while still abstract.
    with pytest.raises(TypeError):
        Repository()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        ObjectRepository()  # type: ignore[abstract]


def test_no_circular_imports_within_domain():
    graph = build_internal_graph()
    cycle = find_cycle(graph)
    assert cycle is None, "Circular import detected in Domain: " + " -> ".join(cycle)

    # Bonus: real import of every Domain module must succeed (no runtime cycle).
    import_errors: list[str] = []
    for mod_name, _ in iter_domain_modules():
        try:
            importlib.import_module(mod_name)
        except Exception as exc:  # noqa: BLE001 - surface any import failure
            import_errors.append(f"{mod_name}: {exc!r}")
    assert not import_errors, "Domain modules failed to import:\n" + "\n".join(import_errors)


if __name__ == "__main__":
    test_domain_imports_only_stdlib_and_app_domain()
    test_no_framework_imports_in_domain()
    test_no_infrastructure_imports_in_domain()
    test_repository_interfaces_remain_abstract()
    test_no_circular_imports_within_domain()
    print("ARCHITECTURE_GUARDRAILS_OK")
