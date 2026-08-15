"""Application port: accreditation submission store (V3 M18, ADR-065)."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class Submission:
    id: str
    framework_id: str
    criterion_id: str
    indicator_id: str
    status: str = "draft"
    evidence: str = "[]"
    narrative: str = ""
    approved_by: str | None = None
    period: str = ""
    period_locked: bool = False
    locked_by: str | None = None
    created_at: str = ""


class AccreditationStore(abc.ABC):
    @abc.abstractmethod
    def add(self, submission: Submission) -> Submission:
        """Record a submission (idempotent by id)."""

    @abc.abstractmethod
    def get(self, submission_id: str) -> Submission | None:
        """Fetch a submission, or None."""

    @abc.abstractmethod
    def set_status(self, submission_id: str, status: str, *, approved_by: str | None = None) -> Submission:
        """Transition a submission's status (approve/reject)."""

    @abc.abstractmethod
    def lock_period(self, submission_id: str, *, locked_by: str) -> Submission:
        """Irreversibly lock a period (human attestation)."""

    @abc.abstractmethod
    def for_framework(self, framework_id: str) -> list[Submission]:
        """All submissions toward one framework."""
