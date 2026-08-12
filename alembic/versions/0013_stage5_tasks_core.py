"""stage 5 cp5.1: tasks core foundation

Revision ID: 0013_stage5_tasks_core
Revises: 0012_stage4_contract_lifecycle
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0013_stage5_tasks_core"
down_revision: str | Sequence[str] | None = "0012_stage4_contract_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_status = postgresql.ENUM(
    "new",
    "in_progress",
    "completed",
    "cancelled",
    name="task_status",
    create_type=False,
)
task_priority = postgresql.ENUM(
    "low",
    "normal",
    "high",
    "urgent",
    name="task_priority",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "new", "in_progress", "completed", "cancelled", name="task_status"
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "low", "normal", "high", "urgent", name="task_priority"
    ).create(bind, checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "creator_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date()),
        sa.Column("priority", task_priority, nullable=False, server_default="normal"),
        sa.Column("status", task_status, nullable=False, server_default="new"),
        sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_tasks_creator_employee_id", "tasks", ["creator_employee_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])
    op.create_index("ix_tasks_deleted_at", "tasks", ["deleted_at"])

    op.create_table(
        "task_assignees",
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )
    op.create_index("ix_task_assignees_employee_id", "task_assignees", ["employee_id"])

    _create_link_table("task_organizations", "organization_id", "organizations.id")
    _create_link_table("task_contracts", "contract_id", "contracts.id")
    _create_link_table("task_contract_items", "contract_item_id", "contract_items.id")
    _create_link_table(
        "task_technical_devices", "technical_device_id", "technical_devices.id"
    )
    _create_link_table("task_buildings", "building_id", "buildings.id")
    _create_link_table("task_opos", "opo_id", "opo.id")

    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "author_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_comments_author_employee_id", "comments", ["author_employee_id"])

    op.create_table(
        "comment_tasks",
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_comment_tasks_task_id", "comment_tasks", ["task_id"])


def _create_link_table(table_name: str, target_column: str, target: str) -> None:
    op.create_table(
        table_name,
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            target_column,
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(target, ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(f"ix_{table_name}_{target_column}", table_name, [target_column])


def downgrade() -> None:
    op.drop_table("comment_tasks")
    op.drop_table("comments")
    op.drop_table("task_opos")
    op.drop_table("task_buildings")
    op.drop_table("task_technical_devices")
    op.drop_table("task_contract_items")
    op.drop_table("task_contracts")
    op.drop_table("task_organizations")
    op.drop_table("task_assignees")
    op.drop_table("tasks")

    bind = op.get_bind()
    postgresql.ENUM(name="task_priority").drop(bind, checkfirst=True)
    postgresql.ENUM(name="task_status").drop(bind, checkfirst=True)
