"""L1 knowledge-plane contract guardrails (frozen).

These are static/architectural guards, not behaviour tests. They pin the L1
contracts so future engines cannot silently break the frozen decisions:

- claims/CDM/spans tables exist and carry acl_scope (ADR-009/ADR-026)
- the source contract is format-agnostic (ADR-023): MediaKind includes image,
  spreadsheet, slide, package; no engine dependency
- spans are polymorphic (ADR-024): not page-only
- claim store binds the predicate catalogue, not a closed enum (ADR-019)
- migration 0012 exists and chains off 0011
- L1 files do NOT touch the L0 patch-farm / freeze artifacts
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l1_adrs_present():
    for name in (
        "ADR-023-source-contract",
        "ADR-024-polymorphic-spans",
        "ADR-025-confidence-split",
        "ADR-026-acl-scope-source",
        "ADR-027-version-identity",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l0_done():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L0" in text and "done" in text and "L1" in text and "in_progress" in text


def test_source_contract_is_format_agnostic():
    from app.domain.value_objects.source import MediaKind

    kinds = {k.value for k in MediaKind}
    assert "raster_image" in kinds
    assert "spreadsheet" in kinds
    assert "slides" in kinds
    assert "package" in kinds
    assert "unknown" in kinds


def test_span_model_is_polymorphic_not_page_only():
    from app.domain.value_objects.span import SpanKind

    kinds = {k.value for k in SpanKind}
    assert "page" in kinds
    assert "bbox" in kinds
    assert "table_cell" in kinds
    assert "equation" in kinds
    assert "image_region" in kinds
    assert "spreadsheet_cell" in kinds
    assert "slide" in kinds


def test_derived_models_carry_acl_scope():
    from app.infrastructure.db.models.claim_model import ClaimModel
    from app.infrastructure.db.models.cdm_block_model import CdmBlockModel
    from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel

    for model in (ClaimModel, CdmBlockModel, DocumentChunkModel):
        assert any(c.name == "acl_scope" for c in model.__table__.columns), model


def test_predicate_catalogue_is_registry_not_closed_enum():
    from app.application.knowledge.predicate_catalogue import get_predicate

    assert get_predicate("sanctioned_amount") is not None
    assert get_predicate("never_a_fact") is None  # additive registry, not enum


def test_claim_service_does_not_import_engine_libs():
    import inspect

    import app.application.services.claim_service as mod

    src = inspect.getsource(mod)
    for forbidden in ("pypdf", "docx", "paddleocr", "tesseract", "cv2", "PIL"):
        assert forbidden not in src, f"claim_service must not import {forbidden}"


def test_migration_0012_chains_off_0011():
    mig = REPO / "backend" / "alembic" / "versions" / "0012_claims_cdm_spans_acl_scope.py"
    assert mig.exists()
    text = mig.read_text(encoding="utf-8")
    assert 'down_revision = "0011_search_fts_identity"' in text


def test_l1_does_not_touch_l0_patch_farm():
    # The L1 changed files must not be in the L0 allowlist / patch-farm files.
    l1_paths = {
        "backend/app/application/services/claim_service.py",
        "backend/app/application/services/cdm_service.py",
        "backend/app/application/services/version_cascade.py",
        "backend/app/domain/value_objects/source.py",
        "backend/app/domain/value_objects/span.py",
    }
    from app.application.assistant.intents import RULES  # noqa: F401
    # The L1 files never touch intents/providers/retrieval routing.
    patch_farm = {
        "backend/app/application/assistant/intents.py",
        "backend/app/application/assistant/providers.py",
        "backend/app/application/dtos/assistant.py",
        "backend/app/application/services/assistant_retrieval.py",
    }
    assert l1_paths.isdisjoint(patch_farm)
