"""L2 format detector tests (ADR-031)."""

from __future__ import annotations

from app.infrastructure.extraction.nir_format_detector import detect


def test_pdf_magic_matches_extension():
    probe = detect(b"%PDF-1.4 x", "pdf")
    assert probe.family == "pdf"
    assert probe.magic_match is True
    assert probe.mismatch_warning is None


def test_mismatch_recorded_not_rerouted():
    probe = detect(b"%PDF-1.4 x", "docx")
    assert probe.family == "docx"
    assert probe.magic_match is False
    assert probe.mismatch_warning is not None
    assert "not re-routed" in probe.mismatch_warning


def test_png_magic():
    probe = detect(b"\x89PNG\r\n\x1a\n" + b"rest", "png")
    assert probe.media_kind.value == "raster_image"
    assert probe.magic_match is True


def test_unknown_extension_maps_to_unsupported_family():
    probe = detect(b"whatever", "weird")
    assert probe.family is None
    assert probe.media_kind.value == "unknown"
