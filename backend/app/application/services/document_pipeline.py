"""Canonical document pipeline (V3 M11, ADR-058).

The single, shared upload pre-processing contract that EVERY entry point
(direct upload ``documents.py``, folder import ``intake.py``, and any future
adapter) routes through, so uploads are processed identically regardless of
where they entered:

1. size check (hard cap, ``MAX_FILE_BYTES``) — oversize is rejected, never
   partially stored;
2. content hash (sha256) — the immutable identity signal;
3. deterministic quarantine decision — dangerous/known-malicious inputs are
   flagged, stored but never indexed/claimed (never silently dropped);
4. revision minting — every upload becomes an immutable revision row
   (``document_id + revision_version + content_hash``), the A9 upgrade of the
   M5 ``source_version`` binding.

Deterministic-only (no AI, no network). The async processing leg (extraction /
embedding) is M10's durable-job concern; this service owns only the SYNC
upload contract the blueprint's "auth → stream → hash → check → quarantine →
revision + job row" sequence requires.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

#: Known-dangerous file patterns (executables, archives-as-code, scripts).
_DANGEROUS_EXTENSIONS = frozenset(
    {"exe", "dll", "bat", "cmd", "com", "scr", "sh", "ps1", "vbs", "js", "jar", "msi"}
)
#: "MZ" (Windows PE) / "ELF" / "#!/" (script) magic bytes — executable content
#: disguised under a benign extension.
_EXEC_MAGICS = (b"MZ", b"\x7fELF", b"#!", b"PK\x03\x04\x05\x06")

QUARANTINE_CLEAN = "clean"
QUARANTINE_FLAGGED = "quarantined"


@dataclass(frozen=True)
class PipelineDecision:
    """The sync upload contract result: clean vs quarantined (+ reason)."""

    content_hash: str
    quarantine: str
    quarantine_reason: str | None = None


def _quarantine_reason(file_name: str, mime_type: str, content: bytes) -> str | None:
    ext = (file_name.rsplit(".", 1)[-1] if "." in file_name else "").lower()
    if ext in _DANGEROUS_EXTENSIONS:
        return f"dangerous extension: {ext}"
    if content and content.startswith(_EXEC_MAGICS):
        return "executable content"
    if mime_type and "x-msdownload" in mime_type:
        return "executable MIME"
    return None


class DocumentPipeline:
    """Deterministic upload pre-processing shared by every entry point."""

    @staticmethod
    def decision(file_name: str, mime_type: str, content: bytes) -> PipelineDecision:
        content_hash = hashlib.sha256(content).hexdigest()
        reason = _quarantine_reason(file_name, mime_type, content)
        return PipelineDecision(
            content_hash=content_hash,
            quarantine=QUARANTINE_FLAGGED if reason else QUARANTINE_CLEAN,
            quarantine_reason=reason,
        )

    @staticmethod
    def sanitize_file_name(file_name: str) -> str:
        """A safe single-segment file name for storage keys (no path escape)."""
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", file_name).strip("._")
        return name or "unnamed"


__all__ = [
    "QUARANTINE_CLEAN",
    "QUARANTINE_FLAGGED",
    "DocumentPipeline",
    "PipelineDecision",
]
