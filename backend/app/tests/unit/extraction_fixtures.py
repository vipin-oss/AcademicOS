"""Shared fixture builders for the extraction engine tests (M2).

These build *real* parseable documents with deterministic bytes — the engines
under test do the only parsing; fixtures merely produce honest input:

- :func:`make_pdf_bytes` — a minimal single-page PDF written by hand (valid
  header/xref/trailer, one Helvetica text op, a docinfo record). pypdf reads
  it; no third-party writer library needed in tests.
- :func:`make_docx_bytes` — a real OOXML package via python-docx (the pinned
  reader library doubles as the fixture writer; the engine's *read* path is
  what the assertions cover).

Everything else (txt/md/csv/json) is literal bytes in the test bodies.
"""
from __future__ import annotations

import io


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_pdf_bytes(
    text: str,
    *,
    title: str | None = None,
    author: str | None = None,
    creation: str | None = "D:20240102030405Z",
    modified: str | None = "D:20240304050607Z",
) -> bytes:
    """A one-page PDF whose visible text is exactly `text`."""

    info = ""
    if title is not None:
        info += f"/Title ({_pdf_escape(title)})"
    if author is not None:
        info += f"/Author ({_pdf_escape(author)})"
    if creation is not None:
        info += f"/CreationDate ({creation})"
    if modified is not None:
        info += f"/ModDate ({modified})"

    content = f"BT /F1 12 Tf 72 720 Td ({_pdf_escape(text)}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ("<< " + info + " >>").encode("latin-1"),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF"
    ).encode()
    return bytes(out)


def make_docx_bytes(
    lines: list[str],
    *,
    title: str | None = None,
    author: str | None = None,
    subject: str | None = None,
) -> bytes:
    """A real .docx whose paragraphs are exactly `lines`."""

    import docx

    document = docx.Document()
    if title is not None:
        document.core_properties.title = title
    if author is not None:
        document.core_properties.author = author
    if subject is not None:
        document.core_properties.subject = subject
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
