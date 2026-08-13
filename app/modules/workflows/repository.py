"""Persistence helpers for versioned workflow configuration."""

import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.identity.models import (
    Employee,
    EmployeeAbsence,
    EmployeeFunctionRole,
    EmployeeFunctionRoleAssignment,
)
from app.modules.workflows.models import (
    WorkflowTaskTemplate,
    WorkflowTemplate,
    WorkflowTemplateVersion,
)


def get_template(
    db: Session,
    template_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> WorkflowTemplate | None:
    stmt = sa.select(WorkflowTemplate).where(WorkflowTemplate.id == template_id)
    if not include_deleted:
        stmt = stmt.where(WorkflowTemplate.deleted_at.is_(None))
    return db.scalar(stmt)


def get_template_for_update(db: Session, template_id: uuid.UUID) -> WorkflowTemplate | None:
    return db.scalar(
        sa.select(WorkflowTemplate)
        .where(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.deleted_at.is_(None),
        )
        .with_for_update()
    )


def get_template_by_code(db: Session, code: str) -> WorkflowTemplate | None:
    return db.scalar(
        sa.select(WorkflowTemplate).where(
            WorkflowTemplate.code == code,
            WorkflowTemplate.deleted_at.is_(None),
        )
    )


def list_templates(db: Session) -> list[WorkflowTemplate]:
    return list(
        db.scalars(
            sa.select(WorkflowTemplate)
            .where(WorkflowTemplate.deleted_at.is_(None))
            .order_by(WorkflowTemplate.name.asc(), WorkflowTemplate.id.asc())
        ).all()
    )


def next_version_number(db: Session, template_id: uuid.UUID) -> int:
    current = db.scalar(
        sa.select(sa.func.max(WorkflowTemplateVersion.version_number)).where(
            WorkflowTemplateVersion.workflow_template_id == template_id
        )
    )
    return int(current or 0) + 1


def get_version(
    db: Session,
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> WorkflowTemplateVersion | None:
    stmt = sa.select(WorkflowTemplateVersion).where(
        WorkflowTemplateVersion.id == version_id,
        WorkflowTemplateVersion.workflow_template_id == template_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def list_versions(db: Session, template_id: uuid.UUID) -> list[WorkflowTemplateVersion]:
    return list(
        db.scalars(
            sa.select(WorkflowTemplateVersion)
            .where(WorkflowTemplateVersion.workflow_template_id == template_id)
            .order_by(
                WorkflowTemplateVersion.version_number.desc(),
                WorkflowTemplateVersion.id.asc(),
            )
        ).all()
    )


def latest_published_version(
    db: Session, template_id: uuid.UUID
) -> WorkflowTemplateVersion | None:
    return db.scalar(
        sa.select(WorkflowTemplateVersion)
        .where(
            WorkflowTemplateVersion.workflow_template_id == template_id,
            WorkflowTemplateVersion.published_at.is_not(None),
        )
        .order_by(
            WorkflowTemplateVersion.version_number.desc(),
            WorkflowTemplateVersion.id.asc(),
        )
        .limit(1)
    )


def list_task_templates(
    db: Session, version_id: uuid.UUID
) -> list[WorkflowTaskTemplate]:
    return list(
        db.scalars(
            sa.select(WorkflowTaskTemplate)
            .where(WorkflowTaskTemplate.workflow_template_version_id == version_id)
            .order_by(
                WorkflowTaskTemplate.sort_order.asc(),
                WorkflowTaskTemplate.id.asc(),
            )
        ).all()
    )


def active_function_role_ids(
    db: Session, role_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    if not role_ids:
        return set()
    return set(
        db.scalars(
            sa.select(EmployeeFunctionRole.id).where(
                EmployeeFunctionRole.id.in_(role_ids),
                EmployeeFunctionRole.is_active.is_(True),
            )
        ).all()
    )


def eligible_employee_ids_for_function_role(
    db: Session,
    *,
    function_role_id: uuid.UUID,
    anchor_date: date,
) -> list[uuid.UUID]:
    absence_exists = sa.exists(
        sa.select(EmployeeAbsence.employee_id).where(
            EmployeeAbsence.employee_id == Employee.id,
            EmployeeAbsence.date_from <= anchor_date,
            EmployeeAbsence.date_to >= anchor_date,
        )
    )
    stmt = (
        sa.select(Employee.id)
        .join(
            EmployeeFunctionRoleAssignment,
            EmployeeFunctionRoleAssignment.employee_id == Employee.id,
        )
        .where(
            EmployeeFunctionRoleAssignment.function_role_id == function_role_id,
            Employee.deleted_at.is_(None),
            ~absence_exists,
        )
        .order_by(Employee.full_name.asc(), Employee.id.asc())
    )
    return list(db.scalars(stmt).all())
