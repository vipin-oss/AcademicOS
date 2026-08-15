"""Deterministic document classifier (V3 M6, ADR-053).

The M6 "CLASSIFY TYPE" stage: given extracted text and a filename, decide the
document's *semantic* type (grant/sanction letter, office order, …) using
deterministic rules only, in priority order:

1. filename patterns  (strongest signal — filenames are rarely ambiguous)
2. heading keywords   (the first lines of the document)
3. issuer keywords    (distinctive vocabulary in the body)

If exactly one type matches at a stage it wins; if zero or several match, the
classifier falls through to the next stage. On final ambiguity it returns
``unknown`` — the ``FAST_LOCAL`` tie-break is deliberately deferred and a
strong model is never consulted (blueprint: "FAST_LOCAL only as tiebreak;
never strong model"). Honesty over guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.knowledge.document_types import DOCUMENT_TYPES, DocumentTypeSpec

#: How many leading lines count as the "heading" region.
_HEADING_LINES = 12

#: Deterministic confidence per rule family (filename > heading > issuer).
_CONFIDENCE = {"filename": 0.95, "heading": 0.9, "issuer": 0.8}


@dataclass(frozen=True)
class ClassificationResult:
    document_type_id: str | None
    confidence: float
    method: str  # "filename" | "heading" | "issuer" | "unknown"
    evidence: tuple[str, ...] = ()


def _matches(spec: DocumentTypeSpec, text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(p.casefold() in lowered for p in patterns)


class DocumentClassifier:
    """Classify a document's semantic type from text + filename (deterministic)."""

    def classify(self, text: str, filename: str = "") -> ClassificationResult:
        body = text or ""
        heading = "\n".join(body.splitlines()[: _HEADING_LINES])

        for method, haystack, getter in (
            ("filename", filename, lambda s: s.filename_patterns),
            ("heading", heading, lambda s: s.heading_keywords),
            ("issuer", body, lambda s: s.issuer_keywords),
        ):
            hits = [
                spec
                for spec in DOCUMENT_TYPES
                if _matches(spec, haystack, getter(spec))
            ]
            if len(hits) == 1:
                spec = hits[0]
                return ClassificationResult(
                    document_type_id=spec.type_id,
                    confidence=_CONFIDENCE[method],
                    method=method,
                    evidence=(f"{method}:{spec.type_id}",),
                )
            if len(hits) > 1:
                # ambiguous at this stage — fall through to a stronger signal
                continue

        return ClassificationResult(document_type_id=None, confidence=0.0, method="unknown")


__all__ = ["ClassificationResult", "DocumentClassifier"]
