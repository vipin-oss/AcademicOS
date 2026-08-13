"""L2 text-family NIR adapter (TXT/Markdown/CSV/JSON).

Wraps the existing stdlib text-family parser into the NIR contract so plain
text, markdown, CSV and JSON flow through the same format-agnostic pipeline.
"""

from __future__ import annotations

from app.application.dtos.nir import NirDocument, NirElement, NirElementType
from app.application.intake.extraction.text_parsing import extract_text_family
from app.application.ports.nir_parser import NirParser
from app.domain.value_objects.source import MediaKind


class TextNirParser(NirParser):
    def __init__(self, format_name: str) -> None:
        self._format_name = format_name

    @property
    def format_name(self) -> str:
        return self._format_name

    def parse(self, data: bytes, *, source_id: str, version: int) -> NirDocument:
        result = extract_text_family(data, self._format_name)
        elements = (
            NirElement(
                element_type=NirElementType.PARAGRAPH,
                order=0, text=result.text, extraction_confidence=1.0,
            ),
        )
        return NirDocument(
            source_id=source_id,
            media_kind=MediaKind.PLAIN_TEXT.value,
            version=version,
            engine=result.engine,
            engine_version=1,
            elements=elements,
            normalized_text=result.text[: 8_000_000],
            needs_ocr=False,
            warnings=result.warnings,
        )
