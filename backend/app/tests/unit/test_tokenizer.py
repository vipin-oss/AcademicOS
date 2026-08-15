"""V3 M4 — tokenizer unit tests (blueprint A2/A3, ADR-052).

Proves the canonical tokenizer is Unicode-first and symmetric:

- the old ``[a-z0-9]+`` made Devanagari invisible and a naive ``\\w+``
  shattered it (A2) — both are pinned as regressions;
- ``mark_tokens`` keeps combining marks (full fidelity);
- ``fts_tokens`` folds diacritics so query tokens == index tokens (A3);
- folding is a no-op for ASCII (no English regression).
"""
from __future__ import annotations

import re

from app.infrastructure.search.tokenizer import (
    fold_diacritics,
    fts_tokens,
    mark_tokens,
    normalize_nfc,
)


def test_old_ascii_regex_makes_devanagari_invisible() -> None:
    # The A2 defect: [a-z0-9]+ drops every Hindi word.
    assert re.findall(r"[a-z0-9]+", "गणित विभाग Samarth 2024".lower()) == [
        "samarth",
        "2024",
    ]


def test_naive_word_class_shatters_devanagari() -> None:
    # The A2 trap: \w+ splits at every matra (combining mark).
    assert re.findall(r"\w+", "गणित") == ["गण", "त"]


def test_mark_tokens_keeps_marks() -> None:
    assert mark_tokens("गणित विभाग Samarth 2024") == [
        "गणित",
        "विभाग",
        "Samarth",
        "2024",
    ]


def test_fts_tokens_folds_diacritics() -> None:
    # Folded: गणित -> गणत, विभाग -> वभग; Latin case-folded.
    assert fts_tokens("गणित विभाग Samarth 2024") == [
        "गणत",
        "वभग",
        "samarth",
        "2024",
    ]


def test_folding_is_noop_for_ascii() -> None:
    assert fold_diacritics("Quantum dots 2024") == "Quantum dots 2024"


def test_folding_strips_latin_diacritics() -> None:
    assert fold_diacritics("café résumé") == "cafe resume"


def test_nfc_normalizes_composed_forms() -> None:
    composed = normalize_nfc("गणित")
    assert composed == "गणित"
    # NFC composition makes canonically-equivalent text identical.
    assert normalize_nfc("e\u0301") == "é"


def test_empty_and_none_are_safe() -> None:
    assert fts_tokens("") == []
    assert fts_tokens(None) == []
    assert mark_tokens(None) == []
    assert fold_diacritics(None) == ""


def test_query_tokens_equal_folded_index_tokens() -> None:
    # A3 gate, at the Python level: the query tokens of a document and its
    # folded form must be identical, so the DB index (which stores folded text
    # under a Mark-splitting tokenizer) matches the query.
    doc = "गणित विभाग Samarth 2024"
    assert fts_tokens(doc) == fts_tokens(fold_diacritics(doc))
