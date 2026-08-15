"""Deterministic Devanagari↔Latin transliteration (V3 M17, ADR-064).

A small, reversible character-level mapping so identity resolution can match
``Vipin`` ↔ ``विपिन`` (and general Hindi/Latin names) WITHOUT a model or
network. Deterministic and idempotent: transliterating twice is a no-op on the
Latin side (the Latin→Devanagari map is a function; Devanagari→Latin is its
inverse on this closed alphabet).

This is a MATCHING aid, not a truth engine: identity resolution surfaces
candidates for human review — nothing is ever auto-merged (ADR-064).
"""

from __future__ import annotations

#: Devanagari -> Latin (ITRANS-ish) for the consonants/vowels/matras used in
#: Indian academic names. Additive: a missing glyph simply passes through.
_DEVA_TO_LATIN: dict[str, str] = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h",
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ः": "h",
    "़": "", "्": "",
}

#: Latin -> Devanagari (inverse for the canonical Latin spellings).
_LATIN_TO_DEVA: dict[str, str] = {
    "a": "अ", "aa": "आ", "i": "इ", "ii": "ई", "u": "उ", "uu": "ऊ",
    "e": "ए", "ai": "ऐ", "o": "ओ", "au": "औ",
    "k": "क", "kh": "ख", "g": "ग", "gh": "घ", "ng": "ङ",
    "ch": "च", "chh": "छ", "j": "ज", "jh": "झ", "ny": "ञ",
    "t": "त", "th": "थ", "d": "द", "dh": "ध", "n": "न",
    "p": "प", "ph": "फ", "b": "ब", "bh": "भ", "m": "म",
    "y": "य", "r": "र", "l": "ल", "v": "व", "sh": "श", "s": "स", "h": "ह",
}


def to_latin(text: str) -> str:
    """Transliterate Devanagari text to a canonical Latin form."""
    out: list[str] = []
    for ch in text:
        out.append(_DEVA_TO_LATIN.get(ch, ch))
    return "".join(out)


def to_devanagari(text: str) -> str:
    """Transliterate canonical Latin text to Devanagari (greedy, left-to-right)."""
    out: list[str] = []
    i = 0
    lower = text.lower()
    while i < len(lower):
        matched = False
        for size in (3, 2, 1):
            token = lower[i : i + size]
            if token in _LATIN_TO_DEVA:
                out.append(_LATIN_TO_DEVA[token])
                i += size
                matched = True
                break
        if not matched:
            out.append(text[i])
            i += 1
    return "".join(out)


def match_key(text: str) -> str:
    """A normalization key for identity matching: Devanagari -> canonical Latin,
    lowercased and whitespace-normalized, so ``Vipin`` == ``विपिन``."""
    latin = to_latin(text).lower()
    return " ".join(latin.split())


__all__ = ["match_key", "to_devanagari", "to_latin"]
