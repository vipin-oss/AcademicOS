"""SQL implementation of the accreditation store (V3 M18, ADR-065)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.accreditation_store import AccreditationStore, Submission
from app.infrastructure.db.models.accreditation_model import AccreditationSubmissionModel


class SQLAccreditationStore(AccreditationStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, submission: Submission) -> Submission:
        existing = self._session.execute(
            select(AccreditationSubmissionModel).where(
                AccreditationSubmissionModel.id == submission.id
            )
        ).scalars().first()
        if existing is not None:
            return submission
        self._session.add(
            AccreditationSubmissionModel(
                id=submission.id,
                framework_id=submission.framework_id,
                criterion_id=submission.criterion_id,
                indicator_id=submission.indicator_id,
                status=submission.status,
                evidence=submission.evidence,
                narrative=submission.narrative,
                approved_by=submission.approved_by,
                period=submission.period,
                period_locked=1 if submission.period_locked else 0,
                locked_by=submission.locked_by,
                created_at=submission.created_at,
            )
        )
        return submission

    def get(self, submission_id: str) -> Submission | None:
        row = self._session.execute(
            select(AccreditationSubmissionModel).where(
                AccreditationSubmissionModel.id == submission_id
            )
        ).scalars().first()
        return _from_model(row) if row else None

    def set_status(self, submission_id: str, status: str, *, approved_by: str | None = None) -> Submission:
        row = self._session.execute(
            select(AccreditationSubmissionModel).where(
                AccreditationSubmissionModel.id == submission_id
            )
        ).scalars().first()
        if row is None:
            raise KeyError(f"Submission not found: {submission_id}")
        row.status = status
        if approved_by is not None:
            row.approved_by = approved_by
        self._session.commit()
        return _from_model(row)

    def lock_period(self, submission_id: str, *, locked_by: str) -> Submission:
        row = self._session.execute(
            select(AccreditationSubmissionModel).where(
                AccreditationSubmissionModel.id == submission_id
            )
        ).scalars().first()
        if row is None:
            raise KeyError(f"Submission not found: {submission_id}")
        row.period_locked = 1
        row.locked_by = locked_by
        self._session.commit()
        return _from_model(row)

    def for_framework(self, framework_id: str) -> list[Submission]:
        rows = self._session.execute(
            select(AccreditationSubmissionModel)
            .where(AccreditationSubmissionModel.framework_id == framework_id)
            .order_by(AccreditationSubmissionModel.created_at)
        ).scalars().all()
        return [_from_model(r) for r in rows]


def _from_model(row: AccreditationSubmissionModel) -> Submission:
    return Submission(
        id=row.id,
        framework_id=row.framework_id,
        criterion_id=row.criterion_id,
        indicator_id=row.indicator_id,
        status=row.status,
        evidence=row.evidence,
        narrative=row.narrative,
        approved_by=row.approved_by,
        period=row.period,
        period_locked=bool(row.period_locked),
        locked_by=row.locked_by,
        created_at=row.created_at,
    )
