"""V3 M11 document pipeline unit tests (ADR-058)."""

from __future__ import annotations

from app.application.services.document_pipeline import (
    QUARANTINE_CLEAN,
    QUARANTINE_FLAGGED,
    DocumentPipeline,
)


def test_clean_upload_hashes_and_passes():
    content = b"%PDF-1.4\nreal content"
    decision = DocumentPipeline.decision("paper.pdf", "application/pdf", content)
    assert decision.quarantine == QUARANTINE_CLEAN
    assert decision.quarantine_reason is None
    assert len(decision.content_hash) == 64


def test_dangerous_extension_is_quarantined():
    decision = DocumentPipeline.decision("setup.exe", "application/octet-stream", b"MZ...")
    assert decision.quarantine == QUARANTINE_FLAGGED
    assert "exe" in (decision.quarantine_reason or "")


def test_executable_magic_disguised_as_pdf_is_quarantined():
    decision = DocumentPipeline.decision("paper.pdf", "application/pdf", b"MZ\x90\x00payload")
    assert decision.quarantine == QUARANTINE_FLAGGED
    assert decision.quarantine_reason == "executable content"


def test_script_shebang_is_quarantined():
    decision = DocumentPipeline.decision("notes.txt", "text/plain", b"#!/bin/sh\nrm -rf /")
    assert decision.quarantine == QUARANTINE_FLAGGED


def test_sanitize_file_name_prevents_path_escape():
    assert DocumentPipeline.sanitize_file_name("../../etc/passwd") == "etc_passwd"
    assert DocumentPipeline.sanitize_file_name("") == "unnamed"
