# ruff: noqa: I001
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.tasks.enums import TaskLinkKind
from app.modules.tasks.models import (
    Task,
    TaskAssignee,
    TaskBuilding,
    TaskContract,
    TaskContractItem,
    TaskOPO,
    TaskOrganization,
    TaskTechnicalDevice,
)


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
)


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
        """
    )
    return set(db.execute(statement, {"task_id": task_id}).scalars().all())
