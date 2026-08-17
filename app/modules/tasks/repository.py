# ruff: noqa: I001
from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts.models import Contract, ContractItem
from app.modules.expertises.models import Expertise
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.models import ScopeType
from app.modules.opo.models import OPO
from app.modules.tasks.enums import TaskLinkKind, TaskPriority, TaskStatus
from app.modules.tasks.models import (
    Task,
    TaskAssignee,
    TaskBuilding,
    TaskContract,
    TaskContractItem,
    TaskExpertise,
    TaskOPO,
    TaskOrganization,
    TaskTechnicalDevice,
)
from app.modules.technical_devices.models import TechnicalDevice


_LINK_SPECS = (
    (TaskLinkKind.ORGANIZATION, TaskOrganization, TaskOrganization.organization_id),
    (TaskLinkKind.CONTRACT, TaskContract, TaskContract.contract_id),
    (TaskLinkKind.CONTRACT_ITEM, TaskContractItem, TaskContractItem.contract_item_id),
    (
        TaskLinkKind.TECHNICAL_DEVICE,
        TaskTechnicalDevice,
        TaskTechnicalDevice.technical_device_id,
    ),
    (TaskLinkKind.BUILDING, TaskBuilding, TaskBuilding.building_id),
    (TaskLinkKind.OPO, TaskOPO, TaskOPO.opo_id),
    (TaskLinkKind.EXPERTISE, TaskExpertise, TaskExpertise.expertise_id),
)


def _related_organization_predicate(
    organization_ids: frozenset[uuid.UUID] | set[uuid.UUID],
) -> sa.ColumnElement[bool]:
    if not organization_ids:
        return sa.false()

    ids = tuple(organization_ids)
    return sa.or_(
        sa.exists(
            sa.select(1).where(
                TaskOrganization.task_id == Task.id,
                TaskOrganization.organization_id.in_(ids),
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(TaskContract)
            .join(Contract, Contract.id == TaskContract.contract_id)
            .where(
                TaskContract.task_id == Task.id,
                Contract.customer_organization_id.in_(ids),
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(TaskContractItem)
            .join(ContractItem, ContractItem.id == TaskContractItem.contract_item_id)
            .join(Contract, Contract.id == ContractItem.contract_id)
            .where(
                TaskContractItem.task_id == Task.id,
                Contract.customer_organization_id.in_(ids),
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(TaskTechnicalDevice)
            .join(
                TechnicalDevice,
                TechnicalDevice.id == TaskTechnicalDevice.technical_device_id,
            )
            .where(
                TaskTechnicalDevice.task_id == Task.id,
                TechnicalDevice.organization_id.in_(ids),
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(TaskBuilding)
            .join(Building, Building.id == TaskBuilding.building_id)
            .where(
                TaskBuilding.task_id == Task.id,
                Building.organization_id.in_(ids),
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(TaskOPO)
            .join(OPO, OPO.id == TaskOPO.opo_id)
            .where(
                TaskOPO.task_id == Task.id,
                sa.or_(
                    OPO.owner_organization_id.in_(ids),
                    OPO.operating_organization_id.in_(ids),
                ),
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(TaskExpertise)
            .join(Expertise, Expertise.id == TaskExpertise.expertise_id)
            .join(Contract, Contract.id == Expertise.contract_id)
            .where(
                TaskExpertise.task_id == Task.id,
                Contract.customer_organization_id.in_(ids),
            )
        ),
    )


def _apply_task_scope(
    stmt: sa.Select,
    authorization: AuthorizationContext | None,
) -> sa.Select:
    if authorization is None or authorization.has_all_scope:
        return stmt

    predicates: list[sa.ColumnElement[bool]] = []
    if ScopeType.OWN in authorization.active_scope_types:
        predicates.append(Task.creator_employee_id == authorization.employee_id)
    if ScopeType.ASSIGNED in authorization.active_scope_types:
        predicates.append(
            sa.exists(
                sa.select(1).where(
                    TaskAssignee.task_id == Task.id,
                    TaskAssignee.employee_id == authorization.employee_id,
                )
            )
        )
    if ScopeType.RELATED in authorization.active_scope_types:
        predicates.append(
            _related_organization_predicate(authorization.related_organization_ids)
        )

    if not predicates:
        return stmt.where(sa.false())
    return stmt.where(sa.or_(*predicates))


def get_task(
    db: Session,
    task_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Task | None:
    stmt = select(Task).where(Task.id == task_id)
    if not include_deleted:
        stmt = stmt.where(Task.deleted_at.is_(None))
    return db.scalar(stmt)


def get_task_for_update(
    db: Session,
    task_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Task | None:
    stmt = select(Task).where(Task.id == task_id)
    if not include_deleted:
        stmt = stmt.where(Task.deleted_at.is_(None))
    return db.scalar(stmt.with_for_update())


def get_task_assignee_ids(db: Session, task_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.scalars(
            select(TaskAssignee.employee_id).where(TaskAssignee.task_id == task_id)
        ).all()
    )


def get_task_links(
    db: Session,
    task_id: uuid.UUID,
) -> list[tuple[TaskLinkKind, uuid.UUID, bool]]:
    links: list[tuple[TaskLinkKind, uuid.UUID, bool]] = []
    for kind, model, target_column in _LINK_SPECS:
        rows = db.execute(
            select(target_column, model.is_primary).where(model.task_id == task_id)
        ).all()
        links.extend(
            (kind, entity_id, bool(is_primary))
            for entity_id, is_primary in rows
        )
    return sorted(links, key=lambda item: (item[0].value, str(item[1])))


def get_task_related_organization_ids(
    db: Session,
    task_id: uuid.UUID,
) -> set[uuid.UUID]:
    statement = text(
        """
        SELECT organization_id
        FROM task_organizations
        WHERE task_id = :task_id
        UNION
        SELECT c.customer_organization_id
        FROM task_contracts tc
        JOIN contracts c ON c.id = tc.contract_id
        WHERE tc.task_id = :task_id
        UNION
        SELECT c.customer_organization_id
        FROM task_contract_items tci
        JOIN contract_items ci ON ci.id = tci.contract_item_id
        JOIN contracts c ON c.id = ci.contract_id
        WHERE tci.task_id = :task_id
        UNION
        SELECT td.organization_id
        FROM task_technical_devices ttd
        JOIN technical_devices td ON td.id = ttd.technical_device_id
        WHERE ttd.task_id = :task_id AND td.organization_id IS NOT NULL
        UNION
        SELECT b.organization_id
        FROM task_buildings tb
        JOIN buildings b ON b.id = tb.building_id
        WHERE tb.task_id = :task_id AND b.organization_id IS NOT NULL
        UNION
        SELECT o.owner_organization_id
        FROM task_opos tor
        JOIN opo o ON o.id = tor.opo_id
        WHERE tor.task_id = :task_id
        UNION
        SELECT o.operating_organization_id
        FROM task_opos tor
        JOIN opo o ON o.id = tor.opo_id
        WHERE tor.task_id = :task_id
        UNION
        SELECT c.customer_organization_id
        FROM task_expertises te
        JOIN expertises e ON e.id = te.expertise_id
        JOIN contracts c ON c.id = e.contract_id
        WHERE te.task_id = :task_id
        """
    )
    return set(db.execute(statement, {"task_id": task_id}).scalars().all())


def list_tasks_paginated(
    db: Session,
    *,
    assignee_id: uuid.UUID | None = None,
    creator_employee_id: uuid.UUID | None = None,
    task_status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    contract_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    is_overdue: bool | None = None,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 20,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[Task], int]:
    stmt = sa.select(Task)
    if not include_deleted:
        stmt = stmt.where(Task.deleted_at.is_(None))
    stmt = _apply_task_scope(stmt, authorization)

    if assignee_id is not None:
        stmt = stmt.where(
            sa.exists(
                sa.select(1).where(
                    TaskAssignee.task_id == Task.id,
                    TaskAssignee.employee_id == assignee_id,
                )
            )
        )
    if creator_employee_id is not None:
        stmt = stmt.where(Task.creator_employee_id == creator_employee_id)
    if task_status is not None:
        stmt = stmt.where(Task.status == task_status)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    if due_from is not None:
        stmt = stmt.where(Task.due_date >= due_from)
    if due_to is not None:
        stmt = stmt.where(Task.due_date <= due_to)
    if contract_id is not None:
        stmt = stmt.where(
            sa.or_(
                sa.exists(
                    sa.select(1).where(
                        TaskContract.task_id == Task.id,
                        TaskContract.contract_id == contract_id,
                    )
                ),
                sa.exists(
                    sa.select(1)
                    .select_from(TaskContractItem)
                    .join(
                        ContractItem,
                        ContractItem.id == TaskContractItem.contract_item_id,
                    )
                    .where(
                        TaskContractItem.task_id == Task.id,
                        ContractItem.contract_id == contract_id,
                    )
                ),
            )
        )
    if organization_id is not None:
        stmt = stmt.where(_related_organization_predicate({organization_id}))
    if is_overdue is not None:
        terminal = (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        if is_overdue:
            stmt = stmt.where(
                Task.due_date.is_not(None),
                Task.due_date < date.today(),
                Task.status.not_in(terminal),
            )
        else:
            stmt = stmt.where(
                sa.or_(
                    Task.due_date.is_(None),
                    Task.due_date >= date.today(),
                    Task.status.in_(terminal),
                )
            )

    total = db.scalar(sa.select(sa.func.count()).select_from(stmt.subquery())) or 0
    offset = max(0, page - 1) * page_size
    items = list(
        db.scalars(
            stmt.order_by(
                Task.due_date.asc().nullslast(),
                Task.created_at.desc(),
                Task.id.asc(),
            )
            .offset(offset)
            .limit(min(page_size, 100))
        ).all()
    )
    return items, total
