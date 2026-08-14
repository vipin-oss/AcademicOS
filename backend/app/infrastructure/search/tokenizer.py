"""V3 M4 — Unicode-first tokenization (blueprint V3 A2/A3, ADR-052).

The single canonical tokenizer for full-text search and the hashing embedder.
Blueprint audit A2 showed the old ``[a-z0-9]+`` made Hindi (Devanagari)
invisible, and that a naive ``\\w+`` "fix" shatters Devanagari words at every
combining mark (matra) — actively worse than absent.

Two related functions:

- :func:`mark_tokens` — the A2 mark-aware tokenizer: one token per word, with
  combining marks kept (``गणित`` stays ``गणित``). Used by the hashing embedder,
  which has no database index to match, so it keeps full fidelity.
- :func:`fts_tokens` — index/query parity tokens for FTS. A3 requires that the
  query-side and index-side tokenization be *identical*, but the database
  tokenizers (SQLite FTS5 ``unicode61`` and PostgreSQL ``simple``) split at
  combining marks and cannot be reconfigured portably. So :func:`fold_diacritics`
  strips Unicode Mark characters (Mn/Mc/Me) on BOTH sides, after which the
  database tokenizers and the Python tokenizer agree by construction.

``fold_diacritics`` is symmetric and a no-op for ASCII (English is unaffected),
so there is no English regression. The original (unfolded) text remains the
source of truth in ``document_contents``; folding applies only to the derived
FTS projection.
"""
from __future__ import annotations

import re
import unicodedata

#: A2 mark-aware token class: a word character, or a combining mark
#: (general combining diacritics + the Devanagari sign/vowel/virama ranges).
MARK_TOKEN_RE = re.compile(
    r"(?:[^\W_]|[\u0300-\u036F\u0900-\u0903\u093A-\u094F\u0951-\u0957\u0962-\u0963])+",
    re.UNICODE,
)


def normalize_nfc(text: str | None) -> str:
    """NFC-normalize (canonical composition); never returns ``None``."""
    return unicodedata.normalize("NFC", text or "")


def fold_diacritics(text: str | None) -> str:
    """Strip Unicode Mark characters (Mn/Mc/Me) so combining marks do not split
    words under the database tokenizers.

    ``गणित`` (with matra) folds to ``गणत``; ``café`` folds to ``cafe``; ASCII
    text is unchanged. Applied to BOTH the indexed text and the query, which is
    what makes query tokens == index tokens.
    """
    nfc = normalize_nfc(text)
    decomposed = unicodedata.normalize("NFD", nfc)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch)[0] != "M")
    return unicodedata.normalize("NFC", stripped)


def mark_tokens(text: str | None) -> list[str]:
    """Mark-aware tokens over NFC text — combining marks kept (blueprint A2)."""
    return MARK_TOKEN_RE.findall(normalize_nfc(text))


def fts_tokens(text: str | None) -> list[str]:
    """Index/query parity tokens: fold diacritics, then mark-aware tokenize,
    then lowercase (a no-op for Devanagari; case-folds Latin).
    """
    return MARK_TOKEN_RE.findall(fold_diacritics(text).lower())


__all__ = [
    "MARK_TOKEN_RE",
    "fold_diacritics",
    "fts_tokens",
    "mark_tokens",
    "normalize_nfc",
]
