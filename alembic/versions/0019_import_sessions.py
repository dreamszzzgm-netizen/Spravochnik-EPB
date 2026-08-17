"""create import sessions and candidates

Revision ID: 0019_import_sessions
Revises: 0018_cp_n1_bank_details
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019_import_sessions"
down_revision: str | Sequence[str] | None = "0018_cp_n1_bank_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    import_session_status = postgresql.ENUM(
        "uploaded", "processing", "preview_ready", "confirmed",
        "applying", "completed", "failed", "cancelled",
        name="import_session_status",
        create_type=False,
    )
    candidate_status = postgresql.ENUM(
        "new", "update", "potential_duplicate", "conflict", "error", "skip",
        name="candidate_status",
        create_type=False,
    )
    candidate_action = postgresql.ENUM(
        "create", "update", "skip", "resolve_conflict",
        name="candidate_action",
        create_type=False,
    )

    import_session_status.create(op.get_bind(), checkfirst=True)
    candidate_status.create(op.get_bind(), checkfirst=True)
    candidate_action.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "import_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("source", sa.String(50), nullable=False, server_default="excel"),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("import_type", sa.String(50), nullable=False, server_default="organizations"),
        sa.Column(
            "status",
            import_session_status,
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflict_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "import_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("normalized_data", postgresql.JSONB(), nullable=True),
        sa.Column("validation_errors", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column(
            "candidate_status",
            candidate_status,
            nullable=False,
            server_default="new",
        ),
        sa.Column(
            "proposed_action",
            candidate_action,
            nullable=False,
            server_default="create",
        ),
        sa.Column(
            "matched_organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("conflict_details", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_import_candidates_session_row",
        "import_candidates",
        ["session_id", "row_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_import_candidates_session_row", table_name="import_candidates")
    op.drop_table("import_candidates")
    op.drop_table("import_sessions")

    postgresql.ENUM(name="candidate_action").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="candidate_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="import_session_status").drop(op.get_bind(), checkfirst=True)
