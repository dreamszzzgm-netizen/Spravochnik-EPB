"""stage 0 foundation

Revision ID: 0001_stage0
Revises:
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_stage0"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


job_status = postgresql.ENUM(
    "pending", "running", "succeeded", "failed", "cancelled",
    name="job_status", create_type=False
)
outbox_status = postgresql.ENUM(
    "pending", "processing", "processed", "failed",
    name="outbox_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "pending", "running", "succeeded", "failed", "cancelled",
        name="job_status"
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "pending", "processing", "processed", "failed",
        name="outbox_status"
    ).create(bind, checkfirst=True)

    op.create_table(
        "stored_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("size_bytes >= 0", name="ck_stored_files_size_nonnegative"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_stored_files_sha256_length"),
        sa.UniqueConstraint("storage_key", name="uq_stored_files_storage_key"),
    )
    op.create_index("ix_stored_files_sha256", "stored_files", ["sha256"])

    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_key", sa.String(255), nullable=False),
        sa.Column("job_type", sa.String(120), nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("attempt_count >= 0", name="ck_background_jobs_attempt_nonnegative"),
    )
    op.create_index("ix_background_jobs_job_key", "background_jobs", ["job_key"])
    op.create_index("ix_background_jobs_job_type", "background_jobs", ["job_type"])
    op.create_index("ix_background_jobs_correlation_id", "background_jobs", ["correlation_id"])
    op.create_index(
        "uq_background_jobs_active_operation",
        "background_jobs",
        ["job_type", "job_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("aggregate_type", sa.String(120), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True)),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", outbox_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("correlation_id", sa.String(64)),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_attempt_nonnegative"),
    )
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_correlation_id", "outbox_events", ["correlation_id"])
    op.create_index(
        "ix_outbox_pending_created",
        "outbox_events",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("background_jobs")
    op.drop_table("stored_files")

    bind = op.get_bind()
    postgresql.ENUM(name="outbox_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="job_status").drop(bind, checkfirst=True)
