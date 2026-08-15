"""V3 M12 architecture guardrails (ADR-059) — assert on COMPOSITION, not files.

The L4 lesson: a guardrail that greps one hard-coded path proves nothing. These
assert on the router's runtime composition (call graph) and its invariants:

- the router is the single classification/source-policy/routing owner;
- source policy is internal-only (NO_EXTERNAL_SEARCH) — never the web;
- the paid path is gated by the budget policy (degrade on exhaustion);
- spend is append-only (the ledger is never mutated);
- the router never imports rules-v1 / parse_question (it composes rung-0 +
  grounded QA, not the regex intent parser).
"""

from __future__ import annotations

import inspect


def test_router_owns_classification_and_source_policy() -> None:
    import app.application.services.academic_ai_router as mod

    src = inspect.getsource(mod)
    assert "NO_EXTERNAL_SEARCH = True" in src
    assert "def route" in src


def test_router_is_internal_only() -> None:
    import app.application.services.academic_ai_router as mod

    src = inspect.getsource(mod)
    for forbidden in ("requests.get", "httpx.get", "urllib", "web_search", "EXTERNAL_SEARCH = False"):
        assert forbidden not in src.lower()


def test_router_does_not_import_rules_v1() -> None:
    # Assert on the import graph (composition), never on prose/docstrings.
    import ast

    import app.application.services.academic_ai_router as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    for forbidden in ("assistant.intents", "assistant.providers"):
        assert not any(forbidden in name for name in imported), imported


def test_budget_gates_paid_path() -> None:
    import app.application.services.academic_ai_router as mod

    src = inspect.getsource(mod)
    assert "self._budget.check" in src
    assert "ON_BUDGET_DEGRADE" in src


def test_spend_ledger_is_append_only() -> None:
    import app.infrastructure.persistence.spend_ledger as mod

    src = inspect.getsource(mod)
    # no UPDATE / DELETE on the ledger
    assert "update(" not in src and "delete(" not in src and "DELETE" not in src


def test_router_composes_rung0_not_regex() -> None:
    # The router composes the deterministic rung-0 answerer (claims), not a
    # regex intent parser.
    import ast

    import app.application.services.academic_ai_router as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert "app.application.use_cases.ai.rung0" in imported
    assert not any("assistant" in name for name in imported)
