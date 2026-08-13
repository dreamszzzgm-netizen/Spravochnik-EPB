"""stage 5 cp5.2: workflow engine

Revision ID: 0014_stage5_workflow_engine
Revises: 0013_stage5_tasks_core
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0014_stage5_workflow_engine"
down_revision: str | Sequence[str] | None = "0013_stage5_tasks_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_priority = postgresql.ENUM(
    "low",
    "normal",
    "high",
    "urgent",
    name="task_priority",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "workflow_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("version > 0", name="ck_workflow_templates_version_positive"),
        sa.UniqueConstraint("code", name="uq_workflow_templates_code"),
    )
    op.create_index("ix_workflow_templates_deleted_at", "workflow_templates", ["deleted_at"])

    op.create_table(
        "workflow_template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "version_number > 0", name="ck_workflow_template_versions_number_positive"
        ),
        sa.UniqueConstraint(
            "workflow_template_id",
            "version_number",
            name="uq_workflow_template_versions_number",
        ),
    )
    op.create_index(
        "ix_workflow_template_versions_template_id",
        "workflow_template_versions",
        ["workflow_template_id"],
    )
    op.create_index(
        "ix_workflow_template_versions_published_at",
        "workflow_template_versions",
        ["published_at"],
    )

    op.create_table(
        "workflow_task_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_template_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_template_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "assignee_function_role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employee_function_roles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("relative_due_days", sa.Integer(), nullable=False),
        sa.Column("priority", task_priority, nullable=False, server_default="normal"),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "relative_due_days >= 0", name="ck_workflow_task_templates_due_days_nonnegative"
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name="ck_workflow_task_templates_sort_order_nonnegative"
        ),
        sa.UniqueConstraint(
            "workflow_template_version_id",
            "sort_order",
            name="uq_workflow_task_templates_sort_order",
        ),
        sa.UniqueConstraint(
            "id",
            "workflow_template_version_id",
            name="uq_workflow_task_templates_id_version",
        ),
    )
    op.create_index(
        "ix_workflow_task_templates_version_id",
        "workflow_task_templates",
        ["workflow_template_version_id"],
    )
    op.create_index(
        "ix_workflow_task_templates_function_role_id",
        "workflow_task_templates",
        ["assignee_function_role_id"],
    )

    op.add_column(
        "tasks",
        sa.Column("source_workflow_template_version_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "tasks",
        sa.Column("source_workflow_task_template_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_index(
        "ix_tasks_source_workflow_template_version_id",
        "tasks",
        ["source_workflow_template_version_id"],
    )
    op.create_index(
        "ix_tasks_source_workflow_task_template_id",
        "tasks",
        ["source_workflow_task_template_id"],
    )
    op.create_check_constraint(
        "ck_tasks_workflow_source_pair",
        "tasks",
        "(source_workflow_template_version_id IS NULL AND source_workflow_task_template_id IS NULL) "
        "OR (source_workflow_template_version_id IS NOT NULL "
        "AND source_workflow_task_template_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_tasks_workflow_source",
        "tasks",
        "workflow_task_templates",
        ["source_workflow_task_template_id", "source_workflow_template_version_id"],
        ["id", "workflow_template_version_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_workflow_source", "tasks", type_="foreignkey")
    op.drop_constraint("ck_tasks_workflow_source_pair", "tasks", type_="check")
    op.drop_index("ix_tasks_source_workflow_task_template_id", table_name="tasks")
    op.drop_index("ix_tasks_source_workflow_template_version_id", table_name="tasks")
    op.drop_column("tasks", "source_workflow_task_template_id")
    op.drop_column("tasks", "source_workflow_template_version_id")

    op.drop_index(
        "ix_workflow_task_templates_function_role_id", table_name="workflow_task_templates"
    )
    op.drop_index("ix_workflow_task_templates_version_id", table_name="workflow_task_templates")
    op.drop_table("workflow_task_templates")

    op.drop_index(
        "ix_workflow_template_versions_published_at", table_name="workflow_template_versions"
    )
    op.drop_index(
        "ix_workflow_template_versions_template_id", table_name="workflow_template_versions"
    )
    op.drop_table("workflow_template_versions")

    op.drop_index("ix_workflow_templates_deleted_at", table_name="workflow_templates")
    op.drop_table("workflow_templates")
