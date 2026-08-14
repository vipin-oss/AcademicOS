"""L2 OCR adapter (ADR-030).

Port-isolated, optional, feature-flagged OFF by default. The default adapter
is Tesseract (``pytesseract``), used only when explicitly enabled and when the
binary is available. OCR confidence is returned separately and the claim
service caps OCR-derived fact confidence at ``MEDIUM_CONFIDENCE_CAP``.
"""

from __future__ import annotations

import io

from app.application.ports.ocr_engine import OcrEngine, OcrResult


class TesseractOcrEngine(OcrEngine):
    """pytesseract adapter. Optional; absent -> ``available()`` False.

    V3 M4 (Q2, ADR-052): the OCR engine decision is Tesseract with the
    ``eng+hin`` language pack — the only option that reads Devanagari without a
    proprietary/paid service. The language set is configurable at construction;
    the default is ``eng+hin``. If the ``hin`` traineddata is not installed on
    the host, Tesseract degrades to English only (best-effort), which the
    blueprint accepts ("English-first, Hindi best-effort with visible
    confidence").
    """

    def __init__(self, *, enabled: bool = False, lang: str = "eng+hin") -> None:
        self._enabled = enabled
        self._lang = lang
        self._available_cache: bool | None = None

    @property
    def lang(self) -> str:
        return self._lang

    def available(self) -> bool:
        if not self._enabled:
            return False
        if self._available_cache is not None:
            return self._available_cache
        try:
            import pytesseract  # noqa: F401

            self._available_cache = True
        except Exception:  # noqa: BLE001
            self._available_cache = False
        return self._available_cache

    def ocr_image(self, data: bytes) -> OcrResult:
        if not self.available():
            raise RuntimeError("OCR engine is not enabled/available.")
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(data))
            text = pytesseract.image_to_string(image, lang=self._lang)
            data_conf = pytesseract.image_to_data(
                image, lang=self._lang, output_type=pytesseract.Output.DICT
            )
            confs = [int(c) for c in data_conf.get("conf", []) if isinstance(c, int | str)]
            confs = [c for c in confs if c >= 0]
            mean = sum(confs) / len(confs) / 100.0 if confs else None
            return OcrResult(text=text.strip(), confidence=mean)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"OCR failed ({type(exc).__name__}: {exc}).") from exc
