"""durable jobs + job_attempts (V3 M10)

Revision ID: 0018_durable_jobs
Revises: 0017_session_revocations
Create Date: 2026-08-15

V3 Milestone M10 (ADR-057): a durable job queue with a separate worker/relay
process model. ``jobs`` is the work queue (generic job types, priority,
recurrence via ``next_run_at``/``cron_expr``, lease via ``locked_until``);
``job_attempts`` is the per-claim execution audit (at-least-once, idempotent).
The in-process intake worker pool (IntakeJobManager) is retained behind a
config flag as the rollback path.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0018_durable_jobs"
down_revision = "0017_session_revocations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("next_run_at", sa.String(), nullable=True),
        sa.Column("cron_expr", sa.String(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("locked_until", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_next_run", "jobs", ["next_run_at"])
    op.create_index("ix_jobs_tenant", "jobs", ["tenant_id"])
    op.create_index("ix_jobs_owner", "jobs", ["owner_user_id"])

    op.create_table(
        "job_attempts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_attempts_job", "job_attempts", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_attempts_job", table_name="job_attempts")
    op.drop_table("job_attempts")
    op.drop_index("ix_jobs_owner", table_name="jobs")
    op.drop_index("ix_jobs_tenant", table_name="jobs")
    op.drop_index("ix_jobs_next_run", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
