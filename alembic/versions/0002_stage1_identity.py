"""stage 1 identity and authorization

Revision ID: 0002_stage1
Revises: 0001_stage0
"""
from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_stage1"
down_revision: str | Sequence[str] | None = "0001_stage0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

employment_type = postgresql.ENUM("staff", "external_expert", name="employment_type", create_type=False)
absence_type = postgresql.ENUM("vacation", "sick_leave", "other", name="absence_type", create_type=False)
scope_type = postgresql.ENUM("ALL", "ASSIGNED", "RELATED", "OWN", name="scope_type", create_type=False)

PERMISSION_CODES = ['ai_settings.manage', 'analytics.financial', 'analytics.management', 'analytics.personal', 'audit.view', 'backup.create', 'backup.manage', 'backup.restore', 'backup.view', 'buildings.create', 'buildings.delete', 'buildings.edit', 'buildings.import', 'buildings.restore', 'buildings.view', 'contracts.change_status', 'contracts.complete', 'contracts.create', 'contracts.delete', 'contracts.edit', 'contracts.manage_addenda', 'contracts.manage_items', 'contracts.manage_responsibles', 'contracts.restore', 'contracts.terminate', 'contracts.view', 'custom_fields.manage', 'directories.manage', 'documents.create_version', 'documents.delete', 'documents.download', 'documents.edit_metadata', 'documents.generate', 'documents.manage_templates', 'documents.restore', 'documents.upload', 'documents.view', 'employees.create', 'employees.delete', 'employees.edit', 'employees.view', 'expertises.assign_experts', 'expertises.change_status', 'expertises.complete', 'expertises.create', 'expertises.delete', 'expertises.edit', 'expertises.manage_calculations', 'expertises.manage_conclusion', 'expertises.manage_inspection', 'expertises.manage_normative_docs', 'expertises.mark_customer_received', 'expertises.register_rtn', 'expertises.restore', 'expertises.view', 'inspection.edit', 'inspection.manage_defects', 'inspection.manage_ndt', 'inspection.manage_photos', 'inspection.manage_reviewed_documents', 'inspection.view', 'npd.check_actuality', 'npd.confirm_actuality_update', 'npd.create', 'npd.delete', 'npd.edit', 'npd.import', 'npd.restore', 'npd.view', 'numbering.manage', 'opo.create', 'opo.delete', 'opo.edit', 'opo.manage_control_dates', 'opo.restore', 'opo.view', 'organizations.create', 'organizations.delete', 'organizations.edit', 'organizations.import', 'organizations.restore', 'organizations.view', 'pmla.create', 'pmla.edit', 'pmla.generate', 'pmla.view', 'production_control.edit', 'production_control.generate_documents', 'production_control.view', 'rtn.correct_historical_attempt', 'rtn.prepare_package', 'rtn.record_result', 'rtn.register_equipment', 'rtn.submit', 'rtn.view', 'settings.manage', 'settings.view', 'storage_settings.manage', 'system_health.view', 'tasks.assign', 'tasks.change_status', 'tasks.comment', 'tasks.complete', 'tasks.create', 'tasks.delete', 'tasks.edit', 'tasks.restore', 'tasks.view', 'tasks.view_all', 'technical_devices.create', 'technical_devices.delete', 'technical_devices.edit', 'technical_devices.import', 'technical_devices.manage_rtn_accounting', 'technical_devices.restore', 'technical_devices.view', 'users.create', 'users.edit', 'users.lock', 'users.manage', 'users.manage_roles', 'users.reset_password', 'users.revoke_sessions', 'users.unlock', 'users.view', 'workflows.manage']


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("staff", "external_expert", name="employment_type").create(bind, checkfirst=True)
    postgresql.ENUM("vacation", "sick_leave", "other", name="absence_type").create(bind, checkfirst=True)
    postgresql.ENUM("ALL", "ASSIGNED", "RELATED", "OWN", name="scope_type").create(bind, checkfirst=True)

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("position", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("email", sa.String(320)),
        sa.Column("employment_type", employment_type, nullable=False, server_default="staff"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_employees_full_name", "employees", ["full_name"])

    op.create_table(
        "employee_function_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "employee_function_role_assignments",
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("function_role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee_function_roles.id", ondelete="RESTRICT"), primary_key=True),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("username", sa.String(120), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("failed_login_count >= 0", name="ck_users_failed_login_nonnegative"),
    )

    op.create_table(
        "employee_absences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("absence_type", absence_type, nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("date_to >= date_from", name="ck_employee_absence_dates"),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(160), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="RESTRICT"), primary_key=True),
    )
    op.create_table(
        "user_role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scope_type", scope_type, nullable=False),
        sa.Column("scope_config", postgresql.JSONB()),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_user_role_assignments_active",
        "user_role_assignments",
        ["user_id", "role_id", "scope_type"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(512)),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "password_reset_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.Text()),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("action", sa.String(160), nullable=False),
        sa.Column("entity_type", sa.String(120)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("result", sa.String(64)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("metadata", postgresql.JSONB()),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])

    permission_rows = [
        {"id": uuid.uuid4(), "code": code, "name": code}
        for code in PERMISSION_CODES
    ]
    permissions_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(permissions_table, permission_rows)

    function_rows = [
        {"id": uuid.uuid4(), "code": code, "name": name, "is_active": True}
        for code, name in [
            ("manager", "Руководитель"),
            ("contract_responsible", "Ответственный по договору"),
            ("expert", "Эксперт"),
            ("specialist", "Специалист"),
            ("accountant", "Бухгалтер"),
        ]
    ]
    functions_table = sa.table(
        "employee_function_roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(functions_table, function_rows)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("password_reset_events")
    op.drop_table("user_sessions")
    op.drop_index("uq_user_role_assignments_active", table_name="user_role_assignments")
    op.drop_table("user_role_assignments")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("employee_absences")
    op.drop_table("users")
    op.drop_table("employee_function_role_assignments")
    op.drop_table("employee_function_roles")
    op.drop_table("employees")

    bind = op.get_bind()
    postgresql.ENUM(name="scope_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="absence_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="employment_type").drop(bind, checkfirst=True)
