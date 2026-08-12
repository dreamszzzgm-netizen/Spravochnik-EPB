import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.models import (
    Contract,
    ContractItem,
    ContractItemBuilding,
    ContractItemTechnicalDevice,
    ContractResponsible,
    ContractSuspension,
    ExpertiseType,
)
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.models import ScopeType


def _apply_contract_scope(
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
            Contract.customer_organization_id.in_(
                authorization.related_organization_ids
            )
        )

    if ScopeType.OWN in authorization.active_scope_types:
        predicates.append(Contract.created_by == authorization.user_id)

    if ScopeType.ASSIGNED in authorization.active_scope_types:
        predicates.append(
            sa.exists(
                sa.select(1).where(
                    ContractResponsible.contract_id == Contract.id,
                    ContractResponsible.employee_id == authorization.employee_id,
                )
            )
        )

    if not predicates:
        return stmt.where(sa.false())

    return stmt.where(sa.or_(*predicates))


def get_contract(
    db: Session,
    contract_id: uuid.UUID,
    *,
    include_deleted: bool = False,
    authorization: AuthorizationContext | None = None,
) -> Contract | None:
    stmt = sa.select(Contract).where(Contract.id == contract_id)
    if not include_deleted:
        stmt = stmt.where(Contract.deleted_at.is_(None))
    stmt = _apply_contract_scope(stmt, authorization)
    return db.scalar(stmt)


def get_contract_for_update(
    db: Session,
    contract_id: uuid.UUID,
) -> Contract | None:
    return db.scalar(
        sa.select(Contract)
        .where(
            Contract.id == contract_id,
            Contract.deleted_at.is_(None),
        )
        .with_for_update()
    )


def get_open_contract_suspension(
    db: Session,
    contract_id: uuid.UUID,
) -> ContractSuspension | None:
    return db.scalar(
        sa.select(ContractSuspension).where(
            ContractSuspension.contract_id == contract_id,
            ContractSuspension.ended_at.is_(None),
        )
    )


def list_contract_suspensions(
    db: Session,
    contract_id: uuid.UUID,
) -> list[ContractSuspension]:
    return list(
        db.scalars(
            sa.select(ContractSuspension)
            .where(ContractSuspension.contract_id == contract_id)
            .order_by(
                ContractSuspension.started_at.asc(),
                ContractSuspension.id.asc(),
            )
        ).all()
    )


def list_contracts_paginated(
    db: Session,
    *,
    q: str = "",
    customer_organization_id: uuid.UUID | None = None,
    contract_status: ContractStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[Contract], int]:
    stmt = sa.select(Contract).where(Contract.deleted_at.is_(None))
    stmt = _apply_contract_scope(stmt, authorization)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Contract.number.ilike(pattern))
    if customer_organization_id is not None:
        stmt = stmt.where(
            Contract.customer_organization_id == customer_organization_id
        )
    if contract_status is not None:
        stmt = stmt.where(Contract.status == contract_status)

    total = db.scalar(sa.select(sa.func.count()).select_from(stmt.subquery())) or 0
    offset = max(0, page - 1) * page_size
    items = list(
        db.scalars(
            stmt.order_by(
                Contract.contract_date.desc(),
                Contract.number.asc(),
                Contract.id.asc(),
            )
            .offset(offset)
            .limit(min(page_size, 100))
        ).all()
    )
    return items, total


def get_contract_item(
    db: Session,
    contract_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> ContractItem | None:
    stmt = sa.select(ContractItem).where(
        ContractItem.id == item_id,
        ContractItem.contract_id == contract_id,
    )
    if not include_deleted:
        stmt = stmt.where(ContractItem.deleted_at.is_(None))
    return db.scalar(stmt)


def get_contract_responsible_ids(db: Session, contract_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.scalars(
            sa.select(ContractResponsible.employee_id).where(
                ContractResponsible.contract_id == contract_id
            )
        ).all()
    )


def count_contract_responsibles(db: Session, contract_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(ContractResponsible).where(
                ContractResponsible.contract_id == contract_id
            )
        )
        or 0
    )


def count_active_contract_items(db: Session, contract_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(ContractItem).where(
                ContractItem.contract_id == contract_id,
                ContractItem.deleted_at.is_(None),
            )
        )
        or 0
    )


def list_contract_items(
    db: Session,
    contract_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> list[ContractItem]:
    stmt = sa.select(ContractItem).where(ContractItem.contract_id == contract_id)
    if not include_deleted:
        stmt = stmt.where(ContractItem.deleted_at.is_(None))
    stmt = stmt.order_by(ContractItem.created_at.asc(), ContractItem.id.asc())
    return list(db.scalars(stmt).all())


def get_contract_item_subject_ids(
    db: Session,
    item_id: uuid.UUID,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    technical_device_ids = list(
        db.scalars(
            sa.select(ContractItemTechnicalDevice.technical_device_id)
            .where(ContractItemTechnicalDevice.contract_item_id == item_id)
            .order_by(ContractItemTechnicalDevice.technical_device_id.asc())
        ).all()
    )
    building_ids = list(
        db.scalars(
            sa.select(ContractItemBuilding.building_id)
            .where(ContractItemBuilding.contract_item_id == item_id)
            .order_by(ContractItemBuilding.building_id.asc())
        ).all()
    )
    return technical_device_ids, building_ids


def get_active_expertise_type(db: Session, expertise_type_id: uuid.UUID) -> ExpertiseType | None:
    return db.scalar(
        sa.select(ExpertiseType).where(
            ExpertiseType.id == expertise_type_id,
            ExpertiseType.is_active.is_(True),
        )
    )


def list_active_expertise_types(db: Session) -> list[ExpertiseType]:
    return list(
        db.scalars(
            sa.select(ExpertiseType)
            .where(ExpertiseType.is_active.is_(True))
            .order_by(ExpertiseType.name.asc(), ExpertiseType.id.asc())
        ).all()
    )
