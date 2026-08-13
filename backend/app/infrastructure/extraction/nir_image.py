"""L2 image engine adapter (Pillow).

Images are first-class: produces a ``NirDocument`` with image metadata, an
image-region element, and (only when OCR is enabled) OCR text with separate
OCR confidence. Images are never an "OCR side effect" — the image itself is
the source and remains bound as evidence via its blob key.
"""

from __future__ import annotations

import io

from app.application.dtos.nir import NirDocument, NirElement, NirElementType, NirImage
from app.application.ports.nir_parser import NirParseError, NirParser
from app.application.ports.ocr_engine import OcrEngine
from app.application.services.extraction_limits import MAX_IMAGE_DIMENSION
from app.domain.value_objects.source import MediaKind


class ImageNirParser(NirParser):
    format_name = "image"

    def __init__(self, ocr: OcrEngine | None = None) -> None:
        self._ocr = ocr

    def parse(self, data: bytes, *, source_id: str, version: int) -> NirDocument:
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover
            raise NirParseError(f"Image engine unavailable: {exc}.") from exc

        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except Exception as exc:  # noqa: BLE001
            raise NirParseError(f"Image could not be parsed ({type(exc).__name__}: {exc}).") from exc

        width, height = image.size
        if max(width, height) > MAX_IMAGE_DIMENSION:
            raise NirParseError(
                f"Image dimension {width}x{height} exceeds max {MAX_IMAGE_DIMENSION}."
            )

        fmt = (image.format or "").lower()
        bbox = (0.0, 0.0, float(width), float(height))
        image_id = f"img-{source_id}"
        nir_image = NirImage(
            image_id=image_id, bbox=bbox, region={"media_type": fmt},
            media_type=fmt, width=width, height=height,
            extraction_confidence=1.0,
        )

        elements: list[NirElement] = []
        warnings: list[str] = []
        text = ""
        needs_ocr = False
        ocr_conf = None
        if self._ocr is not None and self._ocr.available():
            try:
                result = self._ocr.ocr_image(data)
                text = result.text
                ocr_conf = result.confidence
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"OCR failed: {exc}")
                needs_ocr = True
        else:
            needs_ocr = True
            warnings.append("OCR not enabled; image text unavailable.")

        elements.append(
            NirElement(
                element_type=NirElementType.IMAGE,
                order=0, text=text, value={"image_id": image_id, "ocr_confidence": ocr_conf},
                bbox=bbox, extraction_confidence=ocr_conf if ocr_conf is not None else 1.0,
            )
        )

        return NirDocument(
            source_id=source_id,
            media_kind=MediaKind.RASTER_IMAGE.value,
            version=version,
            engine="Pillow",
            engine_version=_pillow_version(),
            elements=tuple(elements),
            images=(nir_image,),
            normalized_text=text[: 8_000_000],
            needs_ocr=needs_ocr,
            warnings=tuple(warnings),
        )


def _pillow_version() -> int:
    try:
        from PIL import __version__

        return int(__version__.split(".")[0])
    except Exception:  # noqa: BLE001
        return 0
