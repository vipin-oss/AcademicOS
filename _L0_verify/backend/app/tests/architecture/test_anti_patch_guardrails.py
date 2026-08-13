"""L0 anti-patch ceilings: grow fails, shrink passes.

Legacy rules-v1 / intents / retrieval_plan may not grow. Deletion later
(L4) must remain legal.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"
REPO_ROOT = BACKEND_ROOT.parent

INTENTS = APP_ROOT / "application" / "assistant" / "intents.py"
PROVIDERS = APP_ROOT / "application" / "assistant" / "providers.py"
DTO = APP_ROOT / "application" / "dtos" / "assistant.py"
RETRIEVAL = APP_ROOT / "application" / "services" / "assistant_retrieval.py"
ROUTING_TEST = APP_ROOT / "tests" / "unit" / "test_assistant_intents.py"

CEILING_INTENT_REGEX = 108
CEILING_RULES = 34
CEILING_INTENT_CODES = 34
CEILING_SUGGESTED = 32
CEILING_ANSWER_BUILDERS = 34
CEILING_ROUTING_CASES = 75
CEILING_PRECEDENCE_CASES = 10
CEILING_RETRIEVAL_REGEX = 3
CEILING_DOMAIN_NOUNS = 15
CEILING_STOPWORDS = 96
CEILING_TOPIC_MARKERS = 5
CEILING_TYPE_COUNT = 5
CEILING_CAPITALIZED = 44
CEILING_PARSE_QUESTION_CALLERS = 1

PHRASE_TABLE_ALLOWLIST = {
    "tests/unit/test_assistant_intents.py",
}

INVENTORY_DOC = REPO_ROOT / "docs" / "architecture" / "L0_PATCH_FARM_INVENTORY.md"


def _count_re_compile(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("re.compile")


def _assign_list_len(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                value = node.value
        if value is not None and isinstance(value, ast.List | ast.Tuple):
            return len(value.elts)
    raise AssertionError(f"{name} not found in {path}")


def _intent_code_count() -> int:
    return len(re.findall(r'^INTENT_[A-Z_]+ = "', DTO.read_text(encoding="utf-8"), re.M))


def _rules_entry_count() -> int:
    tree = ast.parse(INTENTS.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "RULES" and isinstance(node.value, ast.Tuple):
                return len(node.value.elts)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "RULES":
                    assert isinstance(node.value, ast.Tuple)
                    return len(node.value.elts)
    raise AssertionError("RULES not found")


def _answer_builder_count() -> int:
    tree = ast.parse(PROVIDERS.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RuleBasedAssistantProvider"
    )
    return sum(
        1
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_answer_")
    )


def _frozenset_or_tuple_size(path: Path, name: str) -> int:
    src = path.read_text(encoding="utf-8")
    # Evaluate the literal after the assignment via AST.
    tree = ast.parse(src)
    for node in tree.body:
        targets: list[ast.expr] = []
        value = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets):
            continue
        assert value is not None
        # frozenset({...}) or tuple (...) or dict {...}
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id == "frozenset" and value.args:
                arg = value.args[0]
                if isinstance(arg, ast.Set | ast.List | ast.Tuple):
                    return len(arg.elts)
        if isinstance(value, ast.Tuple | ast.Set | ast.Dict):
            return len(value.elts) if not isinstance(value, ast.Dict) else len(value.keys)
    raise AssertionError(f"{name} not found in {path}")


def _production_parse_question_callers() -> list[str]:
    callers: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        if path.resolve() == INTENTS.resolve():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "parse_question":
                    rel = path.relative_to(APP_ROOT).as_posix()
                    callers.append(rel)
                    break
    return sorted(callers)


def test_intent_regex_count_has_not_grown():
    assert _count_re_compile(INTENTS) <= CEILING_INTENT_REGEX


def test_intent_rule_count_has_not_grown():
    assert _rules_entry_count() <= CEILING_RULES


def test_intent_code_count_has_not_grown():
    assert _intent_code_count() <= CEILING_INTENT_CODES


def test_suggested_questions_have_not_grown():
    assert _assign_list_len(DTO, "SUGGESTED_QUESTIONS") <= CEILING_SUGGESTED


def test_answer_builder_count_has_not_grown():
    assert _answer_builder_count() <= CEILING_ANSWER_BUILDERS


def test_routing_case_tables_have_not_grown():
    assert _assign_list_len(ROUTING_TEST, "ROUTING_CASES") <= CEILING_ROUTING_CASES
    assert _assign_list_len(ROUTING_TEST, "PRECEDENCE_CASES") <= CEILING_PRECEDENCE_CASES


def test_retrieval_plan_tables_have_not_grown():
    assert _count_re_compile(RETRIEVAL) <= CEILING_RETRIEVAL_REGEX
    assert _frozenset_or_tuple_size(RETRIEVAL, "_DOMAIN_NOUN_TO_TYPE") <= CEILING_DOMAIN_NOUNS
    assert _frozenset_or_tuple_size(RETRIEVAL, "_QUERY_STOPWORDS") <= CEILING_STOPWORDS
    assert _frozenset_or_tuple_size(RETRIEVAL, "_TOPIC_MARKERS") <= CEILING_TOPIC_MARKERS
    assert _frozenset_or_tuple_size(RETRIEVAL, "_TYPE_COUNT_MARKERS") <= CEILING_TYPE_COUNT
    assert _frozenset_or_tuple_size(RETRIEVAL, "_CAPITALIZED_COMMON_WORDS") <= CEILING_CAPITALIZED


def test_parse_question_production_callers_unchanged():
    callers = _production_parse_question_callers()
    assert callers == ["application/assistant/providers.py"]
    assert len(callers) <= CEILING_PARSE_QUESTION_CALLERS


def test_no_new_intent_modules():
    allowed = {APP_ROOT / "application" / "assistant" / "intents.py"}
    offenders = [
        path
        for path in APP_ROOT.rglob("*intent*.py")
        if "tests" not in path.parts and path.resolve() not in {p.resolve() for p in allowed}
    ]
    assert offenders == []


def test_no_new_phrase_to_intent_tables():
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel in PHRASE_TABLE_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.List | ast.Tuple):
                continue
            if len(node.elts) < 3:
                continue
            if _looks_like_phrase_intent_table(node):
                offenders.append(rel)
                break
    assert offenders == []


def _looks_like_phrase_intent_table(node: ast.List | ast.Tuple) -> bool:
    hits = 0
    for elt in node.elts:
        if not isinstance(elt, ast.Tuple) or len(elt.elts) < 2:
            continue
        first, second = elt.elts[0], elt.elts[1]
        is_str = isinstance(first, ast.Constant) and isinstance(first.value, str)
        is_intent = isinstance(second, ast.Attribute) and second.attr.startswith("INTENT_")
        is_intent_name = isinstance(second, ast.Name) and second.id.startswith("INTENT_")
        if is_str and (is_intent or is_intent_name):
            hits += 1
    return hits >= 3


def test_ceiling_constants_match_inventory_doc():
    text = INVENTORY_DOC.read_text(encoding="utf-8")
    assert "108" in text
    assert "34" in text
    assert "75" in text
    assert "96" in text
