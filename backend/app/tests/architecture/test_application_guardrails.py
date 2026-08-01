"""Architecture guardrails for the Application layer.

Mirrors the Domain guardrails: these tests fail CI the moment the Application
layer breaks its contract:

  1. Application imports only the standard library, ``app.domain.*``, and its own
     ``app.application.*`` submodules.
  2. No framework dependency (SQLAlchemy, FastAPI, JWT, Qdrant, Pydantic, ...).
  3. No infrastructure / other app-layer imports (app.core, app.infrastructure,
     app.api, app.main, app.tests).

The Application layer is NOT modified by this file; it adds tests only.
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app" / "application"

FORBIDDEN_FRAMEWORKS = {
    "sqlalchemy", "alembic", "fastapi", "starlette", "uvicorn", "jwt", "pyjwt",
    "qdrant", "qdrant_client", "pydantic", "pydantic_settings", "httpx",
    "requests", "psycopg2", "psycopg", "boto3", "botocore", "redis", "motor",
    "passlib", "bcrypt", "msal", "google", "azure", "minio", "pytest",
}

FORBIDDEN_APP_LAYERS = {
    "app.core", "app.infrastructure", "app.api", "app.main", "app.tests",
}


def _stdlib_set() -> set[str]:
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
    parts = current.split(".")
    if level > 0:
        base = parts[: max(len(parts) - level, 1)]
        if module:
            return ".".join(base + module.split("."))
        return ".".join(base)
    return module or ""


def iter_app_modules():
    for path in sorted(APP_ROOT.rglob("*.py")):
        yield _module_name_from_path(path), path


def _collect_imports(path: Path) -> list[tuple[int, str | None]]:
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
    violations: list[str] = []
    for mod_name, path in iter_app_modules():
        for level, module in _collect_imports(path):
            if level == 0 and module is None:
                continue
            resolved = _resolve_module(mod_name, level, module)
            top = resolved.split(".")[0]
            if top == "app":
                if (
                    resolved == "app.application"
                    or resolved.startswith("app.application.")
                    or resolved == "app.domain"
                    or resolved.startswith("app.domain.")
                ):
                    continue
                violations.append(
                    f"{mod_name}: imports '{resolved}' (only app.domain / app.application allowed)"
                )
                continue
            if top in FORBIDDEN_FRAMEWORKS:
                violations.append(f"{mod_name}: forbidden framework import '{resolved}'")
                continue
            if top not in STDLIB:
                violations.append(
                    f"{mod_name}: non-stdlib, non-domain import '{resolved}'"
                )
    return violations


def test_application_depends_only_on_domain_and_stdlib():
    violations = find_violations()
    assert not violations, "Application architecture violation:\n" + "\n".join(violations)


def test_application_modules_import_cleanly():
    errors: list[str] = []
    for mod_name, _ in iter_app_modules():
        try:
            importlib.import_module(mod_name)
        except Exception as exc:  # noqa: BLE001 - surface any import failure
            errors.append(f"{mod_name}: {exc!r}")
    assert not errors, "Application modules failed to import:\n" + "\n".join(errors)
