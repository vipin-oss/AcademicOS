"""Application port: OCR engine (L2, ADR-030).

OCR is port-isolated and optional (feature-flagged OFF by default). The
application layer depends only on this abstraction; infrastructure provides the
adapter. OCR confidence is kept separate from any fact confidence (ADR-025);
the claim service caps OCR-derived fact confidence at ``MEDIUM_CONFIDENCE_CAP``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OcrResult:
    """OCR output for one image blob.

    ``text`` is the recognized text; ``confidence`` is the OCR (recognition)
    confidence in [0,1], never to be conflated with a fact's confidence.
    ``regions`` optionally carry per-region text + confidence + bbox.
    """

    text: str
    confidence: float | None = None
    regions: tuple[dict, ...] = field(default_factory=tuple)


class OcrEngine(abc.ABC):
    @abc.abstractmethod
    def available(self) -> bool:
        """Whether the OCR backend is installed/usable (feature flag)."""

    @abc.abstractmethod
    def ocr_image(self, data: bytes) -> OcrResult:
        """Recognize text in one image blob; raises on unreadable input."""
