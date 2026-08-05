"""Extraction Engine (v2 — Intake M2 Part 1) — application services.

Deterministic, format-driven extraction that turns M1-staged bytes into
honest text + metadata:

- ``text_parsing`` — the stdlib text-family parser (TXT/Markdown/CSV/JSON);
- ``service.ExtractionService`` — the runner-facing step: reads the staged
  blob, re-verifies its SHA-256, dispatches to the injected ``DocumentParser``
  registry (infrastructure adapters for PDF/DOCX live behind the port),
  persists the extracted text blob under ``intake-extracted/`` and the
  descriptor as item metadata — always separate stores — and records
  ``UNSUPPORTED``, never a failure, for every other format.

Still deliberately absent: OCR (M10), classification (M5), matching (M7),
proposals (M8), commit (M9). Nothing here creates or mutates anything outside
Intake.
"""
from app.application.intake.extraction.service import ExtractionService
from app.application.intake.extraction.text_parsing import (
    TextFamilyParser,
    decode_text,
    extract_text_family,
)

__all__ = ["ExtractionService", "TextFamilyParser", "decode_text", "extract_text_family"]
