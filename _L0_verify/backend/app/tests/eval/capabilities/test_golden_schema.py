"""Golden-set schema: bilingual, ≥5 phrasings, no intent keys."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS
from app.application.services.capability_eval import (
    DEFAULT_GOLDEN_DIR,
    load_golden_file,
    load_suite,
    validate_suite_coverage,
)


@pytest.mark.parametrize("capability_id", FROZEN_CAPABILITY_IDS)
def test_each_golden_file_validates(capability_id: str):
    path = DEFAULT_GOLDEN_DIR / f"{capability_id}.json"
    assert path.is_file(), path
    cases = load_golden_file(path)
    assert len(cases) >= 5
    languages = {case.language for case in cases}
    assert "en" in languages
    assert "hi-en" in languages
    assert all(case.capability_id == capability_id for case in cases)
    assert all(case.gate_level in {"l0_data", "l4", "l5", "l9"} for case in cases)


def test_suite_has_unique_case_ids_and_full_coverage():
    cases = load_suite()
    validate_suite_coverage(cases)
    ids = [case.case_id for case in cases]
    assert len(ids) == len(set(ids))


def test_golden_files_contain_no_intent_keys():
    for path in Path(DEFAULT_GOLDEN_DIR).glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert '"intent"' not in text
        assert "INTENT_" not in text
        assert "expected_intent" not in text
