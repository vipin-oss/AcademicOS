"""Report exporters (PART 11) — CSV / XLSX / PDF from ONE ``ReportView``.

Stdlib only (the backend's frozen dependency set carries no reportlab /
openpyxl, and a read-only reporting module must not grow it):

- CSV  — ``csv`` + ``utf-8-sig`` BOM (Excel opens it with correct encoding);
  one section per table, KPIs first
- XLSX — minimal Office Open XML package written with ``zipfile`` (inline
  strings, one worksheet per table + a Summary sheet) — opens in Excel,
  LibreOffice and Google Sheets
- PDF  — minimal PDF 1.4 writer (Helvetica-Bold titles + Courier tables,
  fixed-width column layout with truncation, multi-page pagination); the
  rupee sign becomes ``Rs`` (WinAnsi has no ₹ — documented here)

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
# PDF (minimal PDF 1.4 writer)
# ---------------------------------------------------------------------------
_PAGE_WIDTH = 612.0   # Letter
_PAGE_HEIGHT = 792.0
_MARGIN = 40.0
_TITLE_SIZE = 13.0
_HEAD_SIZE = 9.0
_BODY_SIZE = 8.0
_LINE_H = 10.5
_CHAR_W = _BODY_SIZE * 0.6  # Courier advance = 0.6 × size
_MAX_COLS_CHARS = int((_PAGE_WIDTH - 2 * _MARGIN) / _CHAR_W)


def _pdf_text(raw: str) -> str:
    """WinAnsi-safe text: ₹ → Rs, everything else cp1252-replaced, escaped."""
    text = str(raw).replace("₹", "Rs ")
    text = text.encode("cp1252", errors="replace").decode("cp1252")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _truncate(raw: str, width: int) -> str:
    text = str(raw)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _table_lines(view: ReportView) -> list[tuple[str, str]]:
    """(style, text) logical lines for the whole report:
    style in {title, head, rule, row, blank, section}."""
    lines: list[tuple[str, str]] = []
    lines.append(("title", view.title))
    for extra in _filter_lines(view) + [f"Generated: {view.generated_at}"]:
        lines.append(("section", extra))
    lines.append(("blank", ""))
    if view.kpis:
        lines.append(("section", "Key Figures"))
        for kpi in view.kpis:
            lines.append(("row", f"{kpi.label}: {kpi.value}"))
        lines.append(("blank", ""))
    for table in view.tables:
        lines.append(("section", table.title))
        columns = list(table.columns)
        if not columns:
            lines.append(("blank", ""))
            continue
        width = max(8, _MAX_COLS_CHARS // len(columns))
        header = " ".join(_truncate(col, width).ljust(width) for col in columns).rstrip()
        lines.append(("head", header))
        lines.append(("rule", "-" * min(len(header), _MAX_COLS_CHARS)))
        for row in table.rows:
            line = " ".join(
                _truncate(cell, width).ljust(width)
                for cell, _ in zip(row, columns, strict=False)
            ).rstrip()
            lines.append(("row", line))
        lines.append(("blank", ""))
    return lines


def _paginate(lines: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    usable = _PAGE_HEIGHT - 2 * _MARGIN
    per_page = int(usable / _LINE_H)
    pages: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for line in lines:
        current.append(line)
        if len(current) >= per_page:
            pages.append(current)
            current = []
    if current:
        pages.append(current)
    return pages or [[("blank", "")]]


def _content_stream(page: list[tuple[str, str]], page_no: int, total_pages: int) -> bytes:
    parts: list[str] = []
    y = _PAGE_HEIGHT - _MARGIN
    for style, text in page:
        if style == "blank":
            y -= _LINE_H * 0.6
            continue
        if style == "title":
            parts.append(f"BT /F1 {_TITLE_SIZE} Tf {_MARGIN} {y:.2f} Td ({_pdf_text(text)}) Tj ET")
        elif style == "section":
            parts.append(f"BT /F1 {_HEAD_SIZE} Tf {_MARGIN} {y:.2f} Td ({_pdf_text(text)}) Tj ET")
        else:
            parts.append(f"BT /F2 {_BODY_SIZE} Tf {_MARGIN} {y:.2f} Td ({_pdf_text(text)}) Tj ET")
        y -= _LINE_H
    footer = f"Page {page_no} of {total_pages}"
    parts.append(f"BT /F2 {_BODY_SIZE} Tf {_PAGE_WIDTH / 2 - 24:.2f} {_MARGIN / 2:.2f} Td ({footer}) Tj ET")
    return ("\n".join(parts)).encode("cp1252", errors="replace")


def report_pdf_bytes(view: ReportView) -> bytes:
    pages = _paginate(_table_lines(view))
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # 1-based object number

    add(b"<< /Type /Catalog /Pages 2 0 R >>")  # object 1
    pages_kids = " ".join(f"{3 + i} 0 R" for i in range(len(pages)))
    add(f"<< /Type /Pages /Kids [{pages_kids}] /Count {len(pages)} >>".encode())  # object 2

    font_base = 3 + len(pages) * 2
    for index, _page in enumerate(pages):
        page_body = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_WIDTH:.0f} {_PAGE_HEIGHT:.0f}] "
            f"/Resources << /Font << /F1 {font_base} 0 R /F2 {font_base + 1} 0 R >> >> "
            f"/Contents {3 + len(pages) + index} 0 R >>"
        ).encode()
        add(page_body)
    for index, page in enumerate(pages):
        content = _content_stream(page, index + 1, len(pages))
        add(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")

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
