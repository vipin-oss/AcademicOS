"""Claim Support Verifier — the single evidence-support boundary (P0).

The permanent Evidence-Grounded Answer Contract for every AcademicOS
domain (General / Research / Teaching / Publication / Administration):

    QUESTION → INTENT/DOC REFERENCE → EVIDENCE SET → CLAIM → SUPPORT CHECK → ANSWER

The system must NEVER treat "a source exists / is cited" as equivalent to
"the source supports the generated claim". This module is the boundary
that enforces support programmatically (deterministic where possible),
independent of the LLM's own self-reported citations.

Modes
-----
``extraction`` — the user asks for source-grounded exactness (a specific
document is named, or the question demands a quote/verbatim phrase). The
answer MUST be an exact quote from the referenced document's source text;
otherwise the answer is refused. Deterministic, no model required.

``general`` — ordinary factual questions. The verifier computes a
deterministic claim-support score (content-token coverage of the cited
sources) and records it on the result (``claim_supported``) for the UI /
audit trail. A semantic LLM-judge for claim-level support is the P1
extension; the deterministic flag is always available.

Guards
------
- ``acronym_expansion_violation``: when the user explicitly forbids
  expanding an acronym ("do not use or expand the acronym CBLU"), any
  answer that expands an acronym (``CBLU (Chaudhary ...)``) is refused —
  generic across all acronyms, no per-acronym rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Extraction-mode detection
# ---------------------------------------------------------------------------

#: Word-boundary triggers that demand a verbatim quote (in addition to an
#: explicit document reference). "exact" alone is NOT a trigger — it also
#: appears in benign count/entity questions ("the exact number of ...").
_QUOTE_TRIGGERS = ("quote", "verbatim")

#: Count-style phrases that must never enter extraction mode.
_COUNT_PHRASES = ("how many", "total number of", "number of", "count of")


def _norm_lower(question: str) -> str:
    return re.sub(r"\s+", " ", (question or "").lower()).strip()


def evidence_mode(question: str, retrieval_result=None) -> str:
    """``"extraction"`` when the answer must be a verbatim source quote,
    else ``"general"``.

    Extraction mode applies when the user names a specific document
    (``document_reference`` set by the retrieval plan) or explicitly asks
    for a quote/verbatim phrase — and never for count questions.
    """
    norm = _norm_lower(question)
    if any(p in norm for p in _COUNT_PHRASES):
        return "general"
    ref = getattr(retrieval_result, "document_reference", None) if retrieval_result else None
    if ref:
        return "extraction"
    for trigger in _QUOTE_TRIGGERS:
        if re.search(rf"\b{re.escape(trigger)}\b", norm):
            return "extraction"
    return "general"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize for verbatim containment: strip citation markers and
    punctuation, collapse whitespace, lowercase."""
    if not text:
        return ""
    text = re.sub(r"\[\d+\]", " ", text)            # citation markers [1]
    text = re.sub(r"[^A-Za-z0-9\s'’\-]", " ", text)  # punctuation -> space
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def content_tokens(text: str) -> set[str]:
    """Content-bearing tokens (stopword-filtered) for coverage scoring."""
    stop = {
        "the", "a", "an", "of", "to", "in", "on", "for", "with", "and", "or",
        "is", "are", "was", "were", "be", "been", "it", "its", "this", "that",
        "these", "those", "at", "by", "from", "as", "per", "i", "you", "we",
        "they", "he", "she", "my", "your", "our", "their", "do", "does", "did",
        "have", "has", "had", "not", "no", "but", "so", "if", "then", "than",
        "what", "which", "who", "when", "where", "how", "why", "would",
        "should", "could", "can", "will", "about", "into", "over", "under",
        "between", "out", "up", "down", "off", "again", "once", "here",
        "there", "all", "any", "both", "each", "few", "more", "most", "other",
        "some", "such", "only", "own", "same", "too", "very", "also", "just",
    }
    return {t for t in re.findall(r"[a-z0-9’'\-]{2,}", text.lower()) if t not in stop}


# ---------------------------------------------------------------------------
# Acronym-expansion guard (generic)
# ---------------------------------------------------------------------------

_EXPAND_NEGATION_RE = re.compile(
    r"\b(?:do not|don'?t|never|without|avoid)\b.{0,24}\bexpand(?:ing|s)?\b",
    re.IGNORECASE,
)
_ACRONYM_EXPANSION_RE = re.compile(r"\b[A-Z]{2,}\s*\([^)]{2,}\)")


def acronym_expansion_violation(question: str, answer: str) -> bool:
    """True when the user forbids expanding an acronym and the answer
    contains an acronym expansion (``CBLU (Chaudhary Bansi Lal University)``).

    Generic across every acronym — no per-acronym vocabulary.
    """
    if not question or not answer:
        return False
    if _EXPAND_NEGATION_RE.search(question) is None:
        return False
    return _ACRONYM_EXPANSION_RE.search(answer) is not None


# ---------------------------------------------------------------------------
# Verdict + verifier
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaimSupportVerdict:
    """The deterministic result of the claim-support check."""

    supported: bool
    mode: str  # "extraction" | "general"
    reason: str = ""
    coverage: float | None = None  # general mode: content-token coverage


#: General-mode coverage threshold — below this the claim is flagged as
#: unsupported (advisory flag; refusal is P1 via the semantic judge).
_GENERAL_COVERAGE_THRESHOLD = 0.35


class ClaimSupportVerifier:
    """The single support-verification boundary.

    Usage (in grounded QA after generation):

        verdict = verifier.verify(
            question=question,
            answer=result.text,
            referenced_id=retrieval_result.resolved_document_id,
            source_texts={object_id: text, ...},  # authoritative texts
        )
        if not verdict.supported and verdict.mode == "extraction":
            -> honest refusal (never answer from unsupported claims)
        else:
            -> answer + verdict.coverage / claim_supported flag
    """

    def verify(
        self,
        *,
        question: str,
        answer: str,
        referenced_id: str | None = None,
        source_texts: dict[str, str] | None = None,
        mode: str | None = None,
    ) -> ClaimSupportVerdict:
        mode = mode or evidence_mode(question)
        source_texts = source_texts or {}

        if mode == "extraction":
            return self._verify_extraction(question, answer, referenced_id, source_texts)
        return self._verify_general(answer, source_texts)

    # ------------------------------------------------------------ extraction
    def _verify_extraction(
        self, question: str, answer: str, referenced_id: str | None, source_texts: dict[str, str]
    ) -> ClaimSupportVerdict:
        if acronym_expansion_violation(question, answer):
            return ClaimSupportVerdict(
                supported=False,
                mode="extraction",
                reason="answer expands an acronym the user forbade expanding",
            )
        if not answer or not answer.strip():
            return ClaimSupportVerdict(
                supported=False, mode="extraction", reason="empty answer"
            )
        if referenced_id is None or referenced_id not in source_texts:
            return ClaimSupportVerdict(
                supported=False,
                mode="extraction",
                reason="referenced document's source text is unavailable",
            )
        source = source_texts[referenced_id]
        if not source or not source.strip():
            return ClaimSupportVerdict(
                supported=False,
                mode="extraction",
                reason="referenced document has no extractable text",
            )
        norm_answer = normalize_text(answer)
        norm_source = normalize_text(source)
        if not norm_answer:
            return ClaimSupportVerdict(
                supported=False, mode="extraction", reason="answer normalizes to empty"
            )
        if norm_answer in norm_source:
            return ClaimSupportVerdict(
                supported=True,
                mode="extraction",
                reason="answer is a verbatim quote from the referenced document",
            )
        return ClaimSupportVerdict(
            supported=False,
            mode="extraction",
            reason="answer is NOT a verbatim quote from the referenced document "
                   "(it may come from the filename, world knowledge, or "
                   "conversation history)",
        )

    # --------------------------------------------------------------- general
    def _verify_general(self, answer: str, source_texts: dict[str, str]) -> ClaimSupportVerdict:
        answer_tokens = content_tokens(answer)
        if not answer_tokens or not source_texts:
            return ClaimSupportVerdict(
                supported=False, mode="general", reason="no evidence to score"
            )
        source_tokens: set[str] = set()
        for text in source_texts.values():
            source_tokens |= content_tokens(text)
        if not source_tokens:
            return ClaimSupportVerdict(
                supported=False, mode="general", reason="no source text available"
            )
        coverage = len(answer_tokens & source_tokens) / len(answer_tokens)
        return ClaimSupportVerdict(
            supported=coverage >= _GENERAL_COVERAGE_THRESHOLD,
            mode="general",
            coverage=round(coverage, 4),
            reason="content-token coverage of cited sources",
        )


__all__ = [
    "ClaimSupportVerifier",
    "ClaimSupportVerdict",
    "acronym_expansion_violation",
    "content_tokens",
    "evidence_mode",
    "normalize_text",
]
