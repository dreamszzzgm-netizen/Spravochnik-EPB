"""expertise collaboration: participants and task link

Revision ID: 0018_expertise_collaboration
Revises: 0017_expertises
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018_expertise_collaboration"
down_revision: str | Sequence[str] | None = "0017_expertises"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    participation_role = postgresql.ENUM(
        "expert",
        "specialist",
        name="expertise_participation_role",
        create_type=False,
    )
    participation_role.create(bind, checkfirst=True)

    op.create_table(
        "expertise_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "expertise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expertises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("participation_role", participation_role, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "expertise_id",
            "employee_id",
            "participation_role",
            name="uq_expertise_participants_employee_role",
        ),
    )
    op.create_index(
        "ix_expertise_participants_expertise_id",
        "expertise_participants",
        ["expertise_id"],
    )
    op.create_index(
        "ix_expertise_participants_employee_id",
        "expertise_participants",
        ["employee_id"],
    )

    op.create_table(
        "task_expertises",
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "expertise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expertises.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_task_expertises_expertise_id", "task_expertises", ["expertise_id"])


def downgrade() -> None:
    op.drop_index("ix_task_expertises_expertise_id", table_name="task_expertises")
    op.drop_table("task_expertises")

    op.drop_index(
        "ix_expertise_participants_employee_id", table_name="expertise_participants"
    )
    op.drop_index(
        "ix_expertise_participants_expertise_id", table_name="expertise_participants"
    )
    op.drop_table("expertise_participants")

    bind = op.get_bind()
    postgresql.ENUM(name="expertise_participation_role", create_type=False).drop(
        bind, checkfirst=True
    )
