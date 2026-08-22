"""Report exporters (PART 11) — CSV / XLSX / PDF from ONE ``ReportView``.

Stdlib only (the backend's frozen dependency set carries no reportlab /
openpyxl, and a read-only reporting module must not grow it):

- CSV  — ``csv`` + ``utf-8-sig`` BOM (Excel opens it with correct encoding);
  one section per table, KPIs first
- XLSX — minimal Office Open XML package written with ``zipfile`` (inline
  strings, one worksheet per table + a Summary sheet) — opens in Excel,
  LibreOffice and Google Sheets
- PDF  — professional PDF 1.4 writer with:
  * Colored section headers with accent bars
  * Alternating row backgrounds for tables
  * Professional typography with proper spacing
  * KPI cards with colored backgrounds
  * Horizontal rules between sections
  * Page headers and footers
  * The rupee sign becomes ``Rs`` (WinAnsi has no ₹ — documented here)

The exporters know only the uniform contract — zero module logic.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile

from app.application.dtos.reports import ReportView


# ---------------------------------------------------------------------------
# Shared shaping
# ---------------------------------------------------------------------------
def _filter_lines(view: ReportView) -> list[str]:
    if not view.applied_filters:
        return ["Filters: none"]
    applied = ", ".join(f"{k}={v}" for k, v in view.applied_filters.items())
    return [f"Filters: {applied}"]


def _report_header(view: ReportView) -> list[str]:
    return [
        view.title,
        f"Generated: {view.generated_at}",
        *_filter_lines(view),
    ]


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
def report_csv_bytes(view: ReportView) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    for line in _report_header(view):
        writer.writerow([line])
    writer.writerow([])
    if view.kpis:
        writer.writerow(["Key Figures"])
        for kpi in view.kpis:
            writer.writerow([kpi.label, kpi.value])
        writer.writerow([])
    for table in view.tables:
        writer.writerow([table.title])
        writer.writerow(list(table.columns))
        for row in table.rows:
            writer.writerow(list(row))
        writer.writerow([])
    return buffer.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# XLSX (minimal OOXML)
# ---------------------------------------------------------------------------
_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{SHEET_OVERRIDES}
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
{SHEETS}
</sheets>
</workbook>"""

_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{SHEET_RELS}
</Relationships>"""

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
</styleSheet>"""


def _xml_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _column_letter(index: int) -> str:
    letters = ""
    while True:
        index, remainder = divmod(index, 26)
        letters = chr(ord("A") + remainder) + letters
        if index == 0:
            return letters
        index -= 1


def _sheet_xml(rows: list[list[str]], bold_rows: set[int] | None = None) -> str:
    bold_rows = bold_rows or set()
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r_index, row in enumerate(rows, start=1):
        parts.append(f'<row r="{r_index}">')
        style = ' s="1"' if (r_index - 1) in bold_rows else ""
        for c_index, value in enumerate(row):
            ref = f"{_column_letter(c_index)}{r_index}"
            parts.append(
                f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">'
                f"{_xml_escape(value)}</t></is></c>"
            )
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


_ILLEGAL_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def _sheet_name(raw: str, taken: set[str]) -> str:
    name = _ILLEGAL_SHEET_CHARS.sub(" ", raw).strip()[:31] or "Sheet"
    candidate = name
    suffix = 2
    while candidate in taken:
        candidate = f"{name[:28]} {suffix}"
        suffix += 1
    taken.add(candidate)
    return candidate


def report_xlsx_bytes(view: ReportView) -> bytes:
    sheets: list[tuple[str, str]] = []  # (name, xml)
    taken: set[str] = set()

    summary_rows: list[list[str]] = [[line] for line in _report_header(view)]
    summary_rows.append([])
    if view.kpis:
        summary_rows.append(["Key Figures"])
        bold = {len(summary_rows) - 1}
        for kpi in view.kpis:
            summary_rows.append([kpi.label, kpi.value])
    else:
        bold = set()
    sheets.append((_sheet_name("Summary", taken), _sheet_xml(summary_rows, bold)))

    for table in view.tables:
        rows = [[table.title], list(table.columns), *[list(row) for row in table.rows]]
        sheets.append((_sheet_name(table.title, taken), _sheet_xml(rows, {0, 1})))

    overrides = "\n".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    sheet_entries = "\n".join(
        f'<sheet name="{_xml_escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _) in enumerate(sheets, start=1)
    )
    sheet_rels = "\n".join(
        f'<Relationship Id="rId{i}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(sheets) + 1)
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES.replace("{SHEET_OVERRIDES}", overrides))
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _WORKBOOK.replace("{SHEETS}", sheet_entries))
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS.replace("{SHEET_RELS}", sheet_rels))
        archive.writestr("xl/styles.xml", _STYLES)
        for i, (_, xml) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", xml)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# PDF (professional PDF 1.4 writer)
# ---------------------------------------------------------------------------
# Page geometry — A4
_PAGE_WIDTH = 595.28
_PAGE_HEIGHT = 841.89
_MARGIN = 50.0
_CONTENT_WIDTH = _PAGE_WIDTH - 2 * _MARGIN

# Typography
_TITLE_SIZE = 22.0
_SUBTITLE_SIZE = 11.0
_SECTION_SIZE = 14.0
_HEAD_SIZE = 9.0
_BODY_SIZE = 8.5
_SMALL_SIZE = 7.5
_LINE_H = 12.0
_SECTION_GAP = 18.0
_TABLE_GAP = 8.0

# Colors (RGB 0-1)
_ACCENT = (0.18, 0.32, 0.65)
_SECTION_BAR = (0.18, 0.32, 0.65)
_ROW_ALT = (0.96, 0.97, 0.98)
_ROW_WHITE = (1.0, 1.0, 1.0)
_HEADER_BG = (0.18, 0.32, 0.65)
_HEADER_TEXT = (1.0, 1.0, 1.0)
_TEXT_PRIMARY = (0.13, 0.13, 0.13)
_TEXT_SECONDARY = (0.40, 0.40, 0.40)
_TEXT_TERTIARY = (0.55, 0.55, 0.55)
_RULE_COLOR = (0.85, 0.85, 0.85)
_KPI_BG = (0.95, 0.96, 0.98)
_KPI_BORDER = (0.82, 0.85, 0.90)

# Approximate Helvetica character widths (per-unit at size 1)
_HELV_W: dict[str, float] = {}
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _HELV_W[ch] = 0.722
for ch in "abcdefghijklmnopqrstuvwxyz":
    _HELV_W[ch] = 0.556
for ch in "0123456789":
    _HELV_W[ch] = 0.556
_HELV_W.update({
    " ": 0.278, ".": 0.278, ",": 0.278, ":": 0.278, ";": 0.278,
    "-": 0.333, "(": 0.333, ")": 0.333, "/": 0.278, "&": 0.667,
    "@": 0.921, "#": 0.556, "%": 0.889, "+": 0.584, "=": 0.584,
    "<": 0.584, ">": 0.584, "!": 0.278, "?": 0.556, "*": 0.389,
    "_": 0.500, "|": 0.260, "~": 0.584, "'": 0.278, '"': 0.355,
})
_DEFAULT_CHAR_W = 0.556


def _text_width(text: str, size: float) -> float:
    """Estimate text width in points using Helvetica metrics."""
    return sum(_HELV_W.get(ch, _DEFAULT_CHAR_W) for ch in text) * size


def _pdf_color(rgb: tuple[float, float, float]) -> str:
    return f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}"


def _pdf_text(raw: str) -> str:
    """WinAnsi-safe text: ₹ → Rs, everything else cp1252-replaced, escaped."""
    text = str(raw).replace("\u20b9", "Rs ")
    text = text.encode("cp1252", errors="replace").decode("cp1252")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _truncate_to_width(raw: str, max_width: float, size: float) -> str:
    """Truncate text to fit within max_width points."""
    if _text_width(raw, size) <= max_width:
        return raw
    ellipsis_w = _text_width("...", size)
    result: list[str] = []
    current_w = 0.0
    for ch in raw:
        ch_w = _HELV_W.get(ch, _DEFAULT_CHAR_W) * size
        if current_w + ch_w + ellipsis_w > max_width:
            break
        result.append(ch)
        current_w += ch_w
    return "".join(result) + "..."


class _PdfPage:
    """Accumulates drawing commands for a single page."""

    def __init__(self) -> None:
        self.ops: list[str] = []
        self.y: float = _PAGE_HEIGHT - _MARGIN

    @property
    def remaining(self) -> float:
        return self.y - _MARGIN

    def rect(self, x: float, y: float, w: float, h: float,
             fill: tuple[float, float, float], stroke: bool = False) -> None:
        self.ops.append(f"{_pdf_color(fill)} rg")
        if stroke:
            self.ops.append(f"{_pdf_color(fill)} RG")
            self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f S")
        else:
            self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def hrule(self, y: float, color: tuple[float, float, float] = _RULE_COLOR,
              thickness: float = 0.5) -> None:
        self.ops.append(f"{_pdf_color(color)} RG")
        self.ops.append(f"{thickness:.1f} w")
        self.ops.append(
            f"{_MARGIN:.2f} {y:.2f} m {(_PAGE_WIDTH - _MARGIN):.2f} {y:.2f} l S"
        )

    def text(self, x: float, y: float, txt: str, size: float,
             font: str, color: tuple[float, float, float] = _TEXT_PRIMARY) -> None:
        self.ops.append(
            f"BT /{font} {size:.1f} Tf {_pdf_color(color)} rg "
            f"{x:.2f} {y:.2f} Td ({_pdf_text(txt)}) Tj ET"
        )

    def draw_page_header_footer(self, page_no: int, total_pages: int,
                                title: str) -> None:
        # Header line
        self.hrule(_PAGE_HEIGHT - _MARGIN + 15, _ACCENT, 1.0)
        # Footer
        footer = f"Page {page_no} of {total_pages}"
        self.text(
            _PAGE_WIDTH / 2 - _text_width(footer, _SMALL_SIZE) / 2,
            _MARGIN / 2, footer, _SMALL_SIZE, "F2", _TEXT_TERTIARY,
        )
        self.hrule(_MARGIN - 10, _RULE_COLOR, 0.3)

    def to_bytes(self) -> bytes:
        return "\n".join(self.ops).encode("cp1252", errors="replace")


def _draw_title(page: _PdfPage, title: str, subtitle: str | None = None) -> None:
    """Draw the report title with accent bar."""
    bar_h = 4.0
    page.rect(_MARGIN, page.y - bar_h, 60, bar_h, _ACCENT)
    page.y -= bar_h + 8

    page.text(_MARGIN, page.y, title, _TITLE_SIZE, "F1", _ACCENT)
    page.y -= _TITLE_SIZE + 4

    if subtitle:
        page.text(_MARGIN, page.y, subtitle, _SUBTITLE_SIZE, "F2", _TEXT_SECONDARY)
        page.y -= _SUBTITLE_SIZE + 2


def _draw_section_header(page: _PdfPage, title: str) -> None:
    """Draw a section header with accent bar."""
    if page.remaining < 40:
        return
    bar_w = 4.0
    page.rect(_MARGIN, page.y - _SECTION_SIZE + 2, bar_w, _SECTION_SIZE, _SECTION_BAR)
    page.text(_MARGIN + bar_w + 8, page.y, title, _SECTION_SIZE, "F1", _ACCENT)
    page.y -= _SECTION_SIZE + 6
    page.hrule(page.y, _ACCENT, 0.8)
    page.y -= 8


def _draw_kpi_cards(page: _PdfPage, kpis: list) -> None:
    """Draw KPI cards in a grid layout."""
    if not kpis:
        return

    profile_labels = {"Name", "Designation", "Department", "Institution", "Email", "ORCID"}
    profile_kpis = [k for k in kpis if k.label in profile_labels]
    summary_kpis = [k for k in kpis if k.label not in profile_labels]

    if profile_kpis:
        if page.remaining < 60:
            return
        _draw_section_header(page, "Profile")
        for kpi in profile_kpis:
            if page.remaining < 20:
                break
            label_text = f"{kpi.label}:"
            page.text(_MARGIN + 10, page.y, label_text, _BODY_SIZE, "F1", _TEXT_SECONDARY)
            page.text(
                _MARGIN + 10 + _text_width(label_text, _BODY_SIZE) + 6,
                page.y, kpi.value, _BODY_SIZE, "F2", _TEXT_PRIMARY,
            )
            page.y -= _LINE_H
        page.y -= 6

    if summary_kpis:
        if page.remaining < 80:
            return
        _draw_section_header(page, "Summary")

        n = len(summary_kpis)
        cols = min(n, 3)
        card_w = (_CONTENT_WIDTH - (cols - 1) * 10) / cols
        card_h = 42.0

        for i, kpi in enumerate(summary_kpis):
            col = i % cols
            row = i // cols

            if row > 0 and col == 0:
                page.y -= card_h + 8

            if page.remaining < card_h:
                break

            x = _MARGIN + col * (card_w + 10)
            y = page.y - card_h

            page.rect(x, y, card_w, card_h, _KPI_BG)
            page.ops.append(f"{_pdf_color(_KPI_BORDER)} RG")
            page.ops.append("0.5 w")
            page.ops.append(f"{x:.2f} {y:.2f} {card_w:.2f} {card_h:.2f} re S")

            value_w = _text_width(kpi.value, _SECTION_SIZE)
            page.text(
                x + (card_w - value_w) / 2, y + card_h - 18,
                kpi.value, _SECTION_SIZE, "F1", _ACCENT,
            )
            label_w = _text_width(kpi.label, _SMALL_SIZE)
            page.text(
                x + (card_w - label_w) / 2, y + 8,
                kpi.label, _SMALL_SIZE, "F2", _TEXT_SECONDARY,
            )

        rows_needed = (len(summary_kpis) + cols - 1) // cols
        page.y -= rows_needed * (card_h + 8)


def _draw_table_header(page: _PdfPage, columns: list[str],
                       col_widths: list[float], row_h: float) -> None:
    """Draw table header row."""
    page.rect(_MARGIN, page.y - row_h, _CONTENT_WIDTH, row_h, _HEADER_BG)
    x = _MARGIN
    for ci, col in enumerate(columns):
        truncated = _truncate_to_width(col, col_widths[ci] - 8, _HEAD_SIZE)
        page.text(x + 6, page.y - row_h + 4, truncated, _HEAD_SIZE, "F1", _HEADER_TEXT)
        x += col_widths[ci]
    page.y -= row_h


def _draw_table(page: _PdfPage, table: object, pages: list[_PdfPage]) -> None:
    """Draw a table with professional formatting."""
    columns = list(table.columns)  # type: ignore[union-attr]
    if not columns:
        return

    n_cols = len(columns)
    available_w = _CONTENT_WIDTH

    # Calculate column widths based on content
    col_widths: list[float] = []
    for ci, col in enumerate(columns):
        max_w = _text_width(col, _HEAD_SIZE) + 16
        for row in table.rows[:50]:  # type: ignore[union-attr]
            if ci < len(row):
                cell_w = _text_width(str(row[ci]), _BODY_SIZE) + 16
                max_w = max(max_w, cell_w)
        col_widths.append(max_w)

    # Scale to fit
    total_w = sum(col_widths)
    if total_w > available_w:
        scale = available_w / total_w
        col_widths = [w * scale for w in col_widths]

    min_col_w = 40.0
    col_widths = [max(w, min_col_w) for w in col_widths]
    total_w = sum(col_widths)
    if total_w > available_w:
        scale = available_w / total_w
        col_widths = [w * scale for w in col_widths]

    row_h = _LINE_H + 2

    # Section title
    if page.remaining < 50:
        new_page = _PdfPage()
        pages.append(new_page)
        page = new_page

    _draw_section_header(page, table.title)  # type: ignore[union-attr]

    # Table header
    if page.remaining < row_h + 10:
        new_page = _PdfPage()
        pages.append(new_page)
        page = new_page

    _draw_table_header(page, columns, col_widths, row_h)

    # Data rows
    for ri, row in enumerate(table.rows):  # type: ignore[union-attr]
        if page.remaining < row_h:
            new_page = _PdfPage()
            pages.append(new_page)
            page = new_page
            _draw_table_header(page, columns, col_widths, row_h)

        bg = _ROW_ALT if ri % 2 == 0 else _ROW_WHITE
        page.rect(_MARGIN, page.y - row_h, _CONTENT_WIDTH, row_h, bg)

        x = _MARGIN
        for ci in range(min(len(row), n_cols)):
            cell_text = str(row[ci]) if ci < len(row) else ""
            truncated = _truncate_to_width(cell_text, col_widths[ci] - 8, _BODY_SIZE)
            page.text(x + 6, page.y - row_h + 4, truncated, _BODY_SIZE, "F2", _TEXT_PRIMARY)
            x += col_widths[ci]

        page.y -= row_h

    # Bottom border
    page.hrule(page.y, _ACCENT, 0.5)
    page.y -= _TABLE_GAP


def report_pdf_bytes(view: ReportView) -> bytes:
    """Generate a professional PDF report."""
    pages: list[_PdfPage] = [_PdfPage()]
    page = pages[0]

    # Title
    _draw_title(page, view.title, f"Generated: {view.generated_at}")

    # Applied filters
    if view.applied_filters:
        filter_text = "Filters: " + ", ".join(f"{k}={v}" for k, v in view.applied_filters.items())
    else:
        filter_text = "Filters: none"
    page.text(_MARGIN, page.y, filter_text, _SUBTITLE_SIZE, "F2", _TEXT_TERTIARY)
    page.y -= _SUBTITLE_SIZE + 4
    page.y -= 8
    page.hrule(page.y, _RULE_COLOR, 0.5)
    page.y -= 12

    # KPIs
    if view.kpis:
        _draw_kpi_cards(page, view.kpis)
        page.y -= 8

    # Tables
    for table in view.tables:
        if page.remaining < 60:
            new_page = _PdfPage()
            pages.append(new_page)
            page = new_page
        _draw_table(page, table, pages)
        page = pages[-1]

    # Page headers and footers
    for i, p in enumerate(pages):
        p.draw_page_header_footer(i + 1, len(pages), view.title)

    # Build PDF
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + i} 0 R" for i in range(len(pages)))
    add(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())

    font_base = 3 + len(pages) * 2
    for i in range(len(pages)):
        content_ref = 3 + len(pages) + i
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {_PAGE_WIDTH:.2f} {_PAGE_HEIGHT:.2f}] "
            f"/Resources << /Font << /F1 {font_base} 0 R /F2 {font_base + 1} 0 R >> >> "
            f"/Contents {content_ref} 0 R >>"
        )
        add(page_dict.encode())

    for p in pages:
        content = p.to_bytes()
        add(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")

    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{number} 0 obj\n".encode())
        buffer.write(body)
        buffer.write(b"\nendobj\n")

    xref_pos = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode())
    buffer.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return buffer.getvalue()


EXPORTERS = {
    "csv": (report_csv_bytes, "text/csv; charset=utf-8", "csv"),
    "xlsx": (report_xlsx_bytes,
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "pdf": (report_pdf_bytes, "application/pdf", "pdf"),
}
