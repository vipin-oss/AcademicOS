"""Capability evaluation harness (L0).

Loads golden JSON, validates schema, and records ``data_registered``.
Does not import intents, does not call ``parse_question``, does not
route questions. Optional observation is out of band and must not
change pass/fail.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.application.capabilities.eval_schema import (
    ALLOWED_GATE_LEVELS,
    ALLOWED_LANGUAGES,
    FORBIDDEN_CASE_KEYS,
    CapabilityCase,
    CapabilityCaseResult,
    CapabilityCheck,
)
from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS, is_frozen_capability


DEFAULT_GOLDEN_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "eval" / "capabilities" / "golden"
)


class CapabilityEvalError(ValueError):
    """Golden-set or case-schema violation."""


def load_golden_file(path: Path) -> list[CapabilityCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CapabilityEvalError(f"{path.name}: root must be an object")
    capability_id = data.get("capability_id")
    if capability_id != path.stem:
        raise CapabilityEvalError(
            f"{path.name}: capability_id {capability_id!r} must match filename stem"
        )
    if not is_frozen_capability(str(capability_id)):
        raise CapabilityEvalError(f"{path.name}: unknown capability_id {capability_id!r}")
    cases_raw = data.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise CapabilityEvalError(f"{path.name}: cases must be a non-empty list")
    cases: list[CapabilityCase] = []
    for raw in cases_raw:
        cases.append(_parse_case(path.name, str(capability_id), raw))
    return cases


def load_suite(golden_dir: Path | None = None) -> list[CapabilityCase]:
    directory = golden_dir or DEFAULT_GOLDEN_DIR
    files = sorted(directory.glob("*.json"))
    expected = {f"{cid}.json" for cid in FROZEN_CAPABILITY_IDS}
    present = {path.name for path in files}
    missing = expected - present
    if missing:
        raise CapabilityEvalError(f"missing golden files: {sorted(missing)}")
    extra = present - expected
    if extra:
        raise CapabilityEvalError(f"unexpected golden files: {sorted(extra)}")
    cases: list[CapabilityCase] = []
    for path in files:
        cases.extend(load_golden_file(path))
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise CapabilityEvalError("case_id values must be globally unique")
    return cases


def validate_suite_coverage(cases: list[CapabilityCase]) -> None:
    by_cap: dict[str, list[CapabilityCase]] = {}
    for case in cases:
        by_cap.setdefault(case.capability_id, []).append(case)
    for capability_id in FROZEN_CAPABILITY_IDS:
        group = by_cap.get(capability_id, [])
        if len(group) < 5:
            raise CapabilityEvalError(
                f"{capability_id}: need ≥5 phrasings, found {len(group)}"
            )
        languages = {case.language for case in group}
        if "en" not in languages or "hi-en" not in languages:
            raise CapabilityEvalError(
                f"{capability_id}: need ≥1 en and ≥1 hi-en, found {sorted(languages)}"
            )


def run_l0_suite(golden_dir: Path | None = None) -> list[CapabilityCaseResult]:
    """L0 run: schema + coverage. Every valid case is ``data_registered``."""

    cases = load_suite(golden_dir)
    validate_suite_coverage(cases)
    return [
        CapabilityCaseResult(
            case_id=case.case_id,
            capability_id=case.capability_id,
            status="data_registered",
        )
        for case in cases
    ]


def _parse_case(filename: str, capability_id: str, raw: object) -> CapabilityCase:
    if not isinstance(raw, dict):
        raise CapabilityEvalError(f"{filename}: each case must be an object")
    forbidden = FORBIDDEN_CASE_KEYS & set(raw)
    if forbidden:
        raise CapabilityEvalError(
            f"{filename}: forbidden routing keys {sorted(forbidden)} — "
            "phrasings are evaluation data, not intents"
        )
    case_id = raw.get("case_id")
    language = raw.get("language")
    question = raw.get("question")
    gate_level = raw.get("gate_level", "l0_data")
    if not case_id or not isinstance(case_id, str):
        raise CapabilityEvalError(f"{filename}: case_id required")
    if language not in ALLOWED_LANGUAGES:
        raise CapabilityEvalError(f"{filename}: language must be en|hi-en")
    if not question or not isinstance(question, str):
        raise CapabilityEvalError(f"{filename}: question required")
    if gate_level not in ALLOWED_GATE_LEVELS:
        raise CapabilityEvalError(f"{filename}: invalid gate_level {gate_level!r}")
    checks_raw = raw.get("checks") or {}
    if not isinstance(checks_raw, dict):
        raise CapabilityEvalError(f"{filename}: checks must be an object")
    return CapabilityCase(
        capability_id=capability_id,
        case_id=case_id,
        language=language,
        question=question,
        checks=CapabilityCheck.from_mapping(checks_raw),
        fixture=raw.get("fixture"),
        gate_level=gate_level,
    )
