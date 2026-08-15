"""Durable job value objects (V3 M10, ADR-057).

A ``Job`` is a unit of asynchronous work queued by the API and executed by a
separate worker process. The job is generic (job_type + JSON payload), so
extraction, embedding, dossier rebuild, export, digest and scheduled work all
ride the SAME queue — no per-type subsystem (SCALE_LAW: one queue).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class JobType(str, Enum):
    EXTRACTION = "extraction"
    EMBEDDING = "embedding"
    DOSSIER_REBUILD = "dossier_rebuild"
    EXPORT = "export"
    DIGEST = "digest"
    SCHEDULED = "scheduled"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    # failed but within max_attempts -> re-claimable
    RETRYABLE = "retryable"


@dataclass(frozen=True)
class Job:
    id: str
    job_type: str
    payload: dict = field(default_factory=dict)
    status: str = JobStatus.PENDING.value
    priority: int = 0
    tenant_id: str = "default"
    owner_user_id: str = "default"
    created_at: str = ""
    next_run_at: str | None = None
    cron_expr: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    locked_until: str | None = None
