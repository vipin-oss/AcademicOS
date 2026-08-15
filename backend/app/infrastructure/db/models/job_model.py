"""SQLAlchemy models: ``jobs`` + ``job_attempts`` (V3 M10, ADR-057)."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class JobModel(TenantStampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    next_run_at: Mapped[str | None] = mapped_column(String, nullable=True)
    cron_expr: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    locked_until: Mapped[str | None] = mapped_column(String, nullable=True)


class JobAttemptModel(TenantStampMixin, Base):
    __tablename__ = "job_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    worker_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
