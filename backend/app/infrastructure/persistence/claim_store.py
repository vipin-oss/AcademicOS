"""SQL implementation of the claim store (L1, ADR-002 + ADR-019 + ADR-003).

Mirrors the other store conventions: explicit dialect-agnostic writes, no
commits here — the caller (service / applier) owns the transaction.
``claim_id`` is the idempotency key (upsert). Spans are stored polymorphically
(one ``claim_spans`` row per span).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.ports.claim_store import ClaimStore
from app.domain.value_objects.claim import Claim, ClaimStatus
from app.domain.value_objects.enums import Provenance
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.models.claim_model import ClaimModel
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _typed_columns(value: dict) -> tuple[float | None, str | None, str | None]:
    """V3 M5 (audit A1): the writer-populated typed projections of ``value``.

    ``value_number`` carries the ``amount`` of a money value; ``value_date``
    and ``value_text`` carry the ``value`` string of date/text values. These
    columns make rung-0 fact lookups an indexed scan instead of a JSONB scan.
    Unknown/raw values project to ``(None, None, None)`` — never dropped.
    """

    if not isinstance(value, dict):
        return (None, None, None)
    kind = value.get("kind")
    if kind == "money":
        amount = value.get("amount")
        number = float(amount) if isinstance(amount, int | float) and not isinstance(amount, bool) else None
        return (number, None, None)
    if kind == "number":
        # V3 M6: a plain numeric predicate (e.g. project_duration_months) also
        # projects to value_number so range lookups stay an indexed scan.
        num = value.get("value")
        number = float(num) if isinstance(num, int | float) and not isinstance(num, bool) else None
        return (number, None, None)
    if kind == "date":
        text = value.get("value")
        s = str(text) if text is not None else None
        return (None, s, s)
    if kind == "text":
        text = value.get("value")
        s = str(text) if text is not None else None
        return (None, s, None)
    return (None, None, None)


def _to_model(claim: Claim, now: str) -> ClaimModel:
    value_number, value_text, value_date = _typed_columns(claim.value)
    return ClaimModel(
        claim_id=claim.claim_id,
        predicate_id=claim.predicate_id,
        predicate_version=claim.predicate_version,
        value_schema=claim.value_schema,
        value=claim.value,
        source_document_id=claim.source_document_id,
        source_version=claim.source_version,
        status=claim.status.value,
        provenance=claim.provenance.value,
        fact_confidence=claim.fact_confidence,
        extraction_confidence=claim.extraction_confidence,
        acl_scope=claim.acl_scope,
        supersedes_claim_id=claim.supersedes_claim_id,
        value_number=value_number,
        value_text=value_text,
        value_date=value_date,
        created_at=now,
        updated_at=now,
    )


def _from_model(row: ClaimModel) -> Claim:
    return Claim(
        claim_id=row.claim_id,
        predicate_id=row.predicate_id,
        predicate_version=row.predicate_version,
        value_schema=row.value_schema,
        value=row.value,
        source_document_id=row.source_document_id,
        source_version=row.source_version,
        status=ClaimStatus(row.status),
        provenance=Provenance(row.provenance),
        fact_confidence=row.fact_confidence,
        extraction_confidence=row.extraction_confidence,
        acl_scope=row.acl_scope,
        supersedes_claim_id=row.supersedes_claim_id,
    )


def _to_span_model(span: Span, claim_id: str, span_id: str, now: str) -> ClaimSpanModel:
    bbox = list(span.bbox) if span.bbox is not None else None
    return ClaimSpanModel(
        span_id=span_id,
        claim_id=claim_id,
        span_kind=span.kind.value,
        source_id=span.source_id,
        page=span.page,
        block_id=span.block_id,
        char_start=span.char_start,
        char_end=span.char_end,
        row_idx=span.row_idx,
        col_idx=span.col_idx,
        table_id=span.table_id,
        slide=span.slide,
        bbox=bbox,
        region=span.payload or None,
        created_at=now,
    )


def _from_span_model(row: ClaimSpanModel) -> Span:
    return Span(
        kind=SpanKind(row.span_kind),
        source_id=row.source_id,
        page=row.page,
        block_id=row.block_id,
        char_start=row.char_start,
        char_end=row.char_end,
        row_idx=row.row_idx,
        col_idx=row.col_idx,
        table_id=row.table_id,
        bbox=tuple(row.bbox) if row.bbox else None,
        slide=row.slide,
        payload=row.region or {},
    )


class SQLClaimStore(ClaimStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def put(self, claim: Claim, spans: list[Span]) -> Claim:
        from app.application.services.fact_cache import invalidate_facts

        invalidate_facts()
        now = _utcnow_iso()
        existing = self._session.execute(
            select(ClaimModel).where(ClaimModel.claim_id == claim.claim_id)
        ).scalars().first()
        if existing is not None:
            # idempotent in-place update
            value_number, value_text, value_date = _typed_columns(claim.value)
            existing.predicate_id = claim.predicate_id
            existing.predicate_version = claim.predicate_version
            existing.value_schema = claim.value_schema
            existing.value = claim.value
            existing.source_version = claim.source_version
            existing.status = claim.status.value
            existing.provenance = claim.provenance.value
            existing.fact_confidence = claim.fact_confidence
            existing.extraction_confidence = claim.extraction_confidence
            existing.acl_scope = claim.acl_scope
            existing.supersedes_claim_id = claim.supersedes_claim_id
            existing.value_number = value_number
            existing.value_text = value_text
            existing.value_date = value_date
            existing.updated_at = now
        else:
            self._session.add(_to_model(claim, now))
        # spans: delete + insert (idempotent)
        self._session.execute(
            delete(ClaimSpanModel).where(ClaimSpanModel.claim_id == claim.claim_id)
        )
        for span in spans:
            self._session.add(
                _to_span_model(span, claim.claim_id, str(uuid.uuid4()), now)
            )
        return claim

    def get(self, claim_id: str) -> tuple[Claim, list[Span]] | None:
        row = self._session.execute(
            select(ClaimModel).where(ClaimModel.claim_id == claim_id)
        ).scalars().first()
        if row is None:
            return None
        spans = [
            _from_span_model(s)
            for s in self._session.execute(
                select(ClaimSpanModel).where(ClaimSpanModel.claim_id == claim_id)
            ).scalars().all()
        ]
        return _from_model(row), spans

    def by_source(self, source_document_id: str) -> list[Claim]:
        rows = self._session.execute(
            select(ClaimModel)
            .where(ClaimModel.source_document_id == source_document_id)
            .order_by(ClaimModel.created_at, ClaimModel.claim_id)
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def by_status(self, status: ClaimStatus) -> list[Claim]:
        rows = self._session.execute(
            select(ClaimModel)
            .where(ClaimModel.status == status.value)
            .order_by(ClaimModel.created_at, ClaimModel.claim_id)
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def set_status(
        self,
        claim_id: str,
        status: ClaimStatus,
        *,
        reviewer: str | None = None,
        now: str | None = None,
    ) -> Claim:
        from app.application.services.fact_cache import invalidate_facts

        invalidate_facts()
        row = self._session.execute(
            select(ClaimModel).where(ClaimModel.claim_id == claim_id)
        ).scalars().first()
        if row is None:
            raise KeyError(f"Claim not found: {claim_id}")
        row.status = status.value
        row.updated_at = now or _utcnow_iso()
        return _from_model(row)

    def supersede(
        self, claim_id: str, by_claim_id: str, *, now: str | None = None
    ) -> Claim:
        from app.application.services.fact_cache import invalidate_facts

        invalidate_facts()
        row = self._session.execute(
            select(ClaimModel).where(ClaimModel.claim_id == claim_id)
        ).scalars().first()
        if row is None:
            raise KeyError(f"Claim not found: {claim_id}")
        row.status = ClaimStatus.SUPERSEDED.value
        row.supersedes_claim_id = by_claim_id
        row.updated_at = now or _utcnow_iso()
        return _from_model(row)

    def for_source_version(
        self, source_document_id: str, version: int
    ) -> list[Claim]:
        rows = self._session.execute(
            select(ClaimModel).where(
                ClaimModel.source_document_id == source_document_id,
                ClaimModel.source_version == version,
            )
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def confirmed_by_predicate(
        self, predicate_id: str
    ) -> list[tuple[Claim, list[Span]]]:
        rows = self._session.execute(
            select(ClaimModel)
            .where(
                ClaimModel.predicate_id == predicate_id,
                ClaimModel.status == ClaimStatus.CONFIRMED.value,
            )
            .order_by(ClaimModel.created_at, ClaimModel.claim_id)
        ).scalars().all()
        if not rows:
            return []
        ids = [r.claim_id for r in rows]
        span_rows = self._session.execute(
            select(ClaimSpanModel).where(ClaimSpanModel.claim_id.in_(ids))
        ).scalars().all()
        spans_by_claim: dict[str, list[Span]] = {}
        for s in span_rows:
            spans_by_claim.setdefault(s.claim_id, []).append(_from_span_model(s))
        return [(_from_model(r), spans_by_claim.get(r.claim_id, [])) for r in rows]
