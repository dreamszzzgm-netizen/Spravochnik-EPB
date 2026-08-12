from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts.models import Contract, ContractItem
from app.modules.opo.models import OPO
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
    organization_ids = set(
        db.scalars(
            select(TaskOrganization.organization_id).where(
                TaskOrganization.task_id == task_id
            )
        ).all()
    )

    organization_ids.update(
        db.scalars(
            select(Contract.customer_organization_id)
            .join(TaskContract, TaskContract.contract_id == Contract.id)
            .where(TaskContract.task_id == task_id)
        ).all()
    )
    organization_ids.update(
        db.scalars(
            select(Contract.customer_organization_id)
            .join(ContractItem, ContractItem.contract_id == Contract.id)
            .join(
                TaskContractItem,
                TaskContractItem.contract_item_id == ContractItem.id,
            )
            .where(TaskContractItem.task_id == task_id)
        ).all()
    )

    organization_ids.update(
        organization_id
        for organization_id in db.scalars(
            select(TechnicalDevice.organization_id)
            .join(
                TaskTechnicalDevice,
                TaskTechnicalDevice.technical_device_id == TechnicalDevice.id,
            )
            .where(
                TaskTechnicalDevice.task_id == task_id,
                TechnicalDevice.organization_id.is_not(None),
            )
        ).all()
        if organization_id is not None
    )
    organization_ids.update(
        organization_id
        for organization_id in db.scalars(
            select(Building.organization_id)
            .join(TaskBuilding, TaskBuilding.building_id == Building.id)
            .where(
                TaskBuilding.task_id == task_id,
                Building.organization_id.is_not(None),
            )
        ).all()
        if organization_id is not None
    )

    for owner_id, operator_id in db.execute(
        select(OPO.owner_organization_id, OPO.operating_organization_id)
        .join(TaskOPO, TaskOPO.opo_id == OPO.id)
        .where(TaskOPO.task_id == task_id)
    ):
        organization_ids.add(owner_id)
        organization_ids.add(operator_id)

    return organization_ids
