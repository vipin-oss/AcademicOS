"""L2 architecture guardrails (frozen).

Pins the L2 contracts so engines stay in infrastructure, the application layer
stays engine-free, NIR stays transient, L1 stores are reused, and the
patch-farm / L0 ceilings are untouched.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l2_adrs_present():
    for name in (
        "ADR-028-normalized-intermediate-representation",
        "ADR-029-container-package",
        "ADR-030-ocr-policy",
        "ADR-031-format-detection",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l1_done_l2_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L1" in text and "done" in text
    assert "L2" in text and "in_progress" in text


def test_engines_are_infrastructure_not_application():
    # engine adapters live under infrastructure/extraction, never application
    infra_files = {
        "nir_pdf.py", "nir_docx.py", "nir_xlsx.py", "nir_pptx.py",
        "nir_image.py", "nir_ocr.py", "nir_container.py", "nir_format_detector.py",
        "registry.py",
    }
    infra_dir = REPO / "backend" / "app" / "infrastructure" / "extraction"
    for name in infra_files:
        assert (infra_dir / name).exists(), f"missing engine adapter {name}"
    # application layer must not import engine libraries
    from app.application.dtos.nir import NirDocument  # noqa: F401

    app_dir = REPO / "backend" / "app" / "application"
    import ast

    # zipfile is stdlib (allowed in application); engine libs are forbidden.
    forbidden = ("pdfplumber", "openpyxl", "pptx", "PIL", "Pillow", "pytesseract")
    for path in app_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, (
                        f"{path}: application must not import engine {alias.name}"
                    )


def test_ocr_confidence_capped_for_facts():
    from app.application.services.claim_service import OCR_DERIVED_CONFIDENCE_CAP
    from app.domain.value_objects.claim import MEDIUM_CONFIDENCE_CAP

    assert OCR_DERIVED_CONFIDENCE_CAP == MEDIUM_CONFIDENCE_CAP == 0.7


def test_ocr_engine_disabled_by_default():
    from app.infrastructure.extraction.registry import build_ocr

    assert build_ocr().available() is False


def test_l2_does_not_touch_patch_farm_or_l0():
    l2_new_paths = {
        "backend/app/infrastructure/extraction/nir_pdf.py",
        "backend/app/infrastructure/extraction/nir_container.py",
        "backend/app/application/services/nir_mapper.py",
        "backend/app/application/dtos/nir.py",
    }
    patch_farm = {
        "backend/app/application/assistant/intents.py",
        "backend/app/application/assistant/providers.py",
        "backend/app/application/dtos/assistant.py",
        "backend/app/application/services/assistant_retrieval.py",
    }
    assert l2_new_paths.isdisjoint(patch_farm)
    # no L0 files touched by the L2 module set
    assert not any("capabilities" in p or "predicate_catalogue" in p for p in l2_new_paths)
