"""API models for the Intake Foundations slice (pydantic boundary).

Mirrors ``committee_mapper`` conventions: request models are ``extra=forbid``
(nothing silently absorbed), response models mirror the frozen DTO outputs
field-for-field, and ``to_create_input`` is the single translation point from
wire form to the boundary DTO.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.application.dtos.intake import (
    CreateIntakeSessionInput,
    IntakeItemOutput,
    IntakeProgressOutput,
    IntakeSessionOutput,
    IntakeSourceKind,
)


class IntakeSessionCreateRequest(BaseModel):
    """POST /intake/sessions body."""

    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["folder", "files"]
    path: str | None = None
    paths: list[str] | None = None
    actor: str | None = None
    title: str | None = None


def to_create_input(payload: IntakeSessionCreateRequest) -> CreateIntakeSessionInput:
    return CreateIntakeSessionInput(
        source_kind=IntakeSourceKind(payload.source_kind),
        path=payload.path,
        paths=tuple(payload.paths or ()),
        actor=(payload.actor or "intake").strip() or "intake",
        title=payload.title,
    )


class IntakeSessionResponseModel(BaseModel):
    id: str
    title: str
    source: dict[str, Any]
    status: str
    current_stage: str
    progress: dict[str, Any]
    statistics: dict[str, Any]
    summary: str | None
    error: dict[str, Any] | None
    created_at: str | None
    updated_at: str | None
    version: int


class IntakeProgressResponseModel(BaseModel):
    session_id: str
    status: str
    current_stage: str
    total_items: int
    processed_items: int
    percent: float
    counts: dict[str, int]
    updated_at: str | None
    # M2.3 additive queue/live fields (None until honestly measurable)
    current_item: str | None = None
    remaining_items: int = 0
    avg_seconds_per_item: float | None = None
    items_per_minute: float | None = None
    eta_seconds: int | None = None


class IntakeItemResponseModel(BaseModel):
    id: str
    session_id: str
    title: str
    original_path: str
    relative_path: str
    extension: str
    size_bytes: int
    mime_type: str | None
    sha256: str | None
    staged_key: str | None
    status: str
    stage: str
    attempts: int
    stage_history: list[dict[str, Any]]
    error: dict[str, Any] | None
    extraction: dict[str, Any] | None = None  # M2 descriptor (pre-EXTRACT: null)
    created_at: str | None
    updated_at: str | None


class ListIntakeSessionsResponseModel(BaseModel):
    items: list[IntakeSessionResponseModel]
    total_count: int
    page: int
    page_size: int


class ListIntakeItemsResponseModel(BaseModel):
    items: list[IntakeItemResponseModel]
    total_count: int
    page: int
    page_size: int


def session_response(out: IntakeSessionOutput) -> IntakeSessionResponseModel:
    return IntakeSessionResponseModel(**out.__dict__)


def progress_response(out: IntakeProgressOutput) -> IntakeProgressResponseModel:
    return IntakeProgressResponseModel(**out.__dict__)


def item_response(out: IntakeItemOutput) -> IntakeItemResponseModel:
    return IntakeItemResponseModel(**out.__dict__)

class CommitItemResponseModel(BaseModel):
    """Response for the commit endpoints (Sprint-3 M1.3).

    ``document_id`` is empty on a preview (nothing was created); it is
    always set on a successful commit.
    """

    item_id: str
    document_id: str = ""
    document_title: str = ""


def commit_item_response(out) -> CommitItemResponseModel:
    return CommitItemResponseModel(
        item_id=out.item_id,
        document_id=out.document_id,
        document_title=out.document_title,
    )

class ProposalResponseModel(BaseModel):
    """Response for the proposal endpoints (Sprint-3 M2 integration).

    ``document_type`` is validated against the same DOCUMENT_TYPES
    vocabulary the commit path uses.
    """

    item_id: str
    title: str
    document_type: str
    description: str
    confidence: float


class ProposalUpdateRequest(BaseModel):
    """Body for PUT /items/{id}/proposal — the reviewed proposal."""

    title: str
    document_type: str
    description: str = ""


def proposal_response(item_id: str, proposal) -> ProposalResponseModel:
    return ProposalResponseModel(
        item_id=item_id,
        title=proposal.title,
        document_type=proposal.document_type,
        description=proposal.description,
        confidence=proposal.confidence,
    )
