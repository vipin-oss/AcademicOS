"""Harness loads deterministically and never calls parse_question."""

from __future__ import annotations

import ast
from pathlib import Path

from app.application.services.capability_eval import load_suite, run_l0_suite


HARNESS = (
    Path(__file__).resolve().parents[3]
    / "application"
    / "services"
    / "capability_eval.py"
)


def test_suite_loads_all_golden_files():
    cases = load_suite()
    assert {case.capability_id for case in cases}


def test_suite_is_deterministic():
    first = [case.case_id for case in load_suite()]
    second = [case.case_id for case in load_suite()]
    assert first == second


def test_l0_run_marks_cases_data_registered():
    results = run_l0_suite()
    assert results
    assert all(result.status == "data_registered" for result in results)
    assert [r.case_id for r in results] == [c.case_id for c in load_suite()]


def test_harness_ast_has_no_parse_question():
    tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name)
            if node.asname:
                names.add(node.asname)
    assert "parse_question" not in names
    assert "ParsedQuestion" not in names
    assert "RuleBasedAssistantProvider" not in names
    assert "retrieval_plan" not in names


def test_eval_cli_module_imports():
    import importlib.util

    script = Path(__file__).resolve().parents[4] / "scripts" / "eval_capabilities.py"
    spec = importlib.util.spec_from_file_location("eval_capabilities_cli", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0
