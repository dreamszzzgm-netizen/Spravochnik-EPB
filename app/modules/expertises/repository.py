import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.models import Contract
from app.modules.expertises.enums import ExpertiseStatus
from app.modules.expertises.models import (
    Expertise,
    ExpertiseContractItem,
    ExpertiseParticipant,
    ExpertiseStatusHistory,
    ExpertiseSubject,
)
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.models import Employee, ScopeType
from app.modules.tasks.models import Task, TaskExpertise


def _apply_expertise_scope(
    stmt: sa.Select,
    authorization: AuthorizationContext | None,
) -> sa.Select:
    if authorization is None or authorization.has_all_scope:
        return stmt

    predicates: list[sa.ColumnElement[bool]] = []

    if (
        ScopeType.RELATED in authorization.active_scope_types
        and authorization.related_organization_ids
    ):
        predicates.append(
            Contract.customer_organization_id.in_(authorization.related_organization_ids)
        )

    if ScopeType.ASSIGNED in authorization.active_scope_types:
        predicates.append(Expertise.responsible_expert_id == authorization.employee_id)

    if not predicates:
        return stmt.where(sa.false())

    return stmt.where(sa.or_(*predicates))


def _joined_select() -> sa.Select:
    return sa.select(Expertise).join(Contract, Contract.id == Expertise.contract_id)


def get_expertise(
    db: Session,
    expertise_id: uuid.UUID,
    *,
    include_deleted: bool = False,
    authorization: AuthorizationContext | None = None,
) -> Expertise | None:
    stmt = _joined_select().where(Expertise.id == expertise_id)
    if not include_deleted:
        stmt = stmt.where(Expertise.deleted_at.is_(None))
    stmt = _apply_expertise_scope(stmt, authorization)
    return db.scalar(stmt)


def get_expertise_for_update(db: Session, expertise_id: uuid.UUID) -> Expertise | None:
    return db.scalar(
        sa.select(Expertise)
        .where(Expertise.id == expertise_id, Expertise.deleted_at.is_(None))
        .with_for_update()
    )


def list_expertises_paginated(
    db: Session,
    *,
    q: str = "",
    contract_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    status: ExpertiseStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[Expertise], int]:
    stmt = _joined_select().where(Expertise.deleted_at.is_(None))
    stmt = _apply_expertise_scope(stmt, authorization)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            sa.or_(
                Expertise.internal_number.ilike(pattern),
                Expertise.comment.ilike(pattern),
            )
        )
    if contract_id is not None:
        stmt = stmt.where(Expertise.contract_id == contract_id)
    if organization_id is not None:
        stmt = stmt.where(Contract.customer_organization_id == organization_id)
    if status is not None:
        stmt = stmt.where(Expertise.status == status)

    total = db.scalar(sa.select(sa.func.count()).select_from(stmt.subquery())) or 0
    offset = max(0, page - 1) * page_size
    items = list(
        db.scalars(
            stmt.order_by(Expertise.created_at.desc(), Expertise.id.asc())
            .offset(offset)
            .limit(min(page_size, 100))
        ).all()
    )
    return items, total


def get_expertise_subject(db: Session, expertise_id: uuid.UUID) -> ExpertiseSubject | None:
    return db.scalar(
        sa.select(ExpertiseSubject).where(ExpertiseSubject.expertise_id == expertise_id)
    )


def get_expertise_subjects_by_ids(
    db: Session, expertise_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ExpertiseSubject]:
    rows = db.scalars(
        sa.select(ExpertiseSubject).where(ExpertiseSubject.expertise_id.in_(expertise_ids))
    ).all()
    return {row.expertise_id: row for row in rows}


def get_expertise_contract_item_ids(db: Session, expertise_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(
            sa.select(ExpertiseContractItem.contract_item_id)
            .where(ExpertiseContractItem.expertise_id == expertise_id)
            .order_by(ExpertiseContractItem.contract_item_id.asc())
        ).all()
    )


def list_expertise_status_history(
    db: Session, expertise_id: uuid.UUID
) -> list[ExpertiseStatusHistory]:
    return list(
        db.scalars(
            sa.select(ExpertiseStatusHistory)
            .where(ExpertiseStatusHistory.expertise_id == expertise_id)
            .order_by(ExpertiseStatusHistory.changed_at.asc(), ExpertiseStatusHistory.id.asc())
        ).all()
    )


def get_participant(
    db: Session, expertise_id: uuid.UUID, employee_id: uuid.UUID
) -> ExpertiseParticipant | None:
    return db.scalar(
        sa.select(ExpertiseParticipant).where(
            ExpertiseParticipant.expertise_id == expertise_id,
            ExpertiseParticipant.employee_id == employee_id,
        )
    )


def list_participants(db: Session, expertise_id: uuid.UUID) -> list[ExpertiseParticipant]:
    return list(
        db.scalars(
            sa.select(ExpertiseParticipant)
            .where(ExpertiseParticipant.expertise_id == expertise_id)
            .order_by(ExpertiseParticipant.created_at.asc(), ExpertiseParticipant.id.asc())
        ).all()
    )


def list_participants_with_employees(
    db: Session, expertise_id: uuid.UUID
) -> list[tuple[ExpertiseParticipant, Employee | None]]:
    rows = db.execute(
        sa.select(ExpertiseParticipant, Employee)
        .outerjoin(Employee, Employee.id == ExpertiseParticipant.employee_id)
        .where(ExpertiseParticipant.expertise_id == expertise_id)
        .order_by(ExpertiseParticipant.created_at.asc(), ExpertiseParticipant.id.asc())
    ).all()
    return [(participant, employee) for participant, employee in rows]


def list_expertise_task_ids(db: Session, expertise_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(
            sa.select(TaskExpertise.task_id)
            .where(TaskExpertise.expertise_id == expertise_id)
            .order_by(TaskExpertise.task_id.asc())
        ).all()
    )


def list_expertise_tasks(db: Session, expertise_id: uuid.UUID) -> list[Task]:
    return list(
        db.scalars(
            sa.select(Task)
            .join(TaskExpertise, TaskExpertise.task_id == Task.id)
            .where(TaskExpertise.expertise_id == expertise_id, Task.deleted_at.is_(None))
            .order_by(Task.created_at.asc(), Task.id.asc())
        ).all()
    )


def list_active_employees(db: Session) -> list[Employee]:
    return list(
        db.scalars(
            sa.select(Employee)
            .where(Employee.deleted_at.is_(None))
            .order_by(Employee.full_name.asc(), Employee.id.asc())
        ).all()
    )
