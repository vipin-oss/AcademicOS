"""L2 XLSX engine adapter (openpyxl).

Workbook / worksheet / cell / range / formula / value structural provenance.
Cells are represented as SHEET + SHEET_CELL elements; structural context is
preserved (not flattened).
"""

from __future__ import annotations

import io

from app.application.dtos.nir import NirDocument, NirElement, NirElementType
from app.application.ports.nir_parser import NirParseError, NirParser
from app.application.services.extraction_limits import MAX_CELLS, MAX_SHEETS
from app.domain.value_objects.source import MediaKind


class XlsxNirParser(NirParser):
    format_name = "xlsx"

    def __init__(self) -> None:
        self._engine = "openpyxl"

    def parse(self, data: bytes, *, source_id: str, version: int) -> NirDocument:
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover
            raise NirParseError(f"XLSX engine unavailable: {exc}.") from exc

        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=False, read_only=True)
        except Exception as exc:  # noqa: BLE001
            raise NirParseError(f"XLSX could not be parsed ({type(exc).__name__}: {exc}).") from exc

        elements: list[NirElement] = []
        sheet_names: list[str] = []
        text_parts: list[str] = []
        order = 0
        cell_count = 0
        truncated = False

        for ws in wb.worksheets:
            if len(sheet_names) >= MAX_SHEETS:
                truncated = True
                break
            sheet = ws.title
            sheet_names.append(sheet)
            elements.append(
                NirElement(
                    element_type=NirElementType.SHEET, order=order, text=sheet,
                    value={"sheet": sheet}, extraction_confidence=1.0,
                )
            )
            order += 1
            try:
                rows = list(ws.iter_rows(values_only=False))
            except Exception:  # noqa: BLE001
                continue
            for r, row in enumerate(rows):
                for c, cell in enumerate(row):
                    if cell_count >= MAX_CELLS:
                        truncated = True
                        break
                    cell_count += 1
                    raw = cell.value
                    formula = None
                    if isinstance(cell, openpyxl.cell.cell.Cell) and cell.data_type == "f":
                        formula = cell.value
                        raw = cell.value
                    value_str = _stringify(raw)
                    if value_str:
                        text_parts.append(value_str)
                    col = _col_letter(c)
                    if order < 50_000:
                        elements.append(
                            NirElement(
                                element_type=NirElementType.SHEET_CELL,
                                order=order, text=value_str or "",
                                value={
                                    "sheet": sheet, "row": r, "col": c,
                                    "ref": f"{sheet}!{col}{r + 1}",
                                    "formula": formula,
                                },
                                sheet=sheet,
                                extraction_confidence=1.0,
                            )
                        )
                        order += 1
                if truncated:
                    break

        try:
            wb.close()
        except Exception:  # noqa: BLE001
            pass

        warnings = ("Cell limit reached; output truncated." if truncated else "",)
        warnings = tuple(w for w in warnings if w)
        return NirDocument(
            source_id=source_id,
            media_kind=MediaKind.SPREADSHEET.value,
            version=version,
            engine=self._engine,
            engine_version=_openpyxl_version(),
            elements=tuple(elements),
            sheets=tuple(sheet_names),
            normalized_text="\n".join(text_parts)[: 8_000_000],
            needs_ocr=False,
            warnings=warnings,
        )


def _stringify(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _col_letter(index: int) -> str:
    letters = ""
    n = index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _openpyxl_version() -> int:
    try:
        import openpyxl

        return int(openpyxl.__version__.split(".")[0])
    except Exception:  # noqa: BLE001
        return 0
