"""V3 M4 — bilingual golden corpus (evaluation DATA, not routing rules).

Deterministic Hindi/English/Hinglish (query, expected-match) pairs used to
prove the Unicode-first tokenizer makes Devanagari searchable without an
English regression. Each entry states the raw text, the query, and the
assertion that folding makes the query tokens a subset of the document tokens
(or explicitly disjoint, for the negative case).

This is data only — the tokenizer under test is the single source of logic.
"""
from __future__ import annotations

#: (document_text, query, expect_match)
BILINGUAL_GOLDEN: tuple[tuple[str, str, bool], ...] = (
    # pure Hindi document, pure Hindi query
    ("गणित विभाग की वार्षिक रिपोर्ट", "गणित विभाग", True),
    # Hindi query with matras — must fold to the same tokens as the doc
    ("विज्ञान संकाय के शोध प्रस्ताव", "विज्ञान", True),
    # Hinglish document, Hinglish query
    ("HSRF sanction letter राशि स्वीकृत", "HSRF राशि", True),
    # English document, English query — no regression (folding is a no-op)
    ("Quantum dots research proposal for SERB funding", "quantum funding", True),
    # mixed-language query must still match the English portion
    ("Annual report of the mathematics department", "mathematics report", True),
    # negative control: unrelated Hindi terms must NOT match
    ("रसायन विज्ञान प्रयोगशाला", "इतिहास", False),
    # case-insensitivity across Latin (folding + lowercase)
    ("CBLU Conference Proceedings", "cblu conference", True),
)
