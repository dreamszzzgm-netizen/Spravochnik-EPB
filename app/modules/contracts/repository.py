import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.models import (
    Contract,
    ContractItem,
    ContractResponsible,
    ExpertiseType,
)


def get_contract(
    db: Session,
    contract_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Contract | None:
    stmt = sa.select(Contract).where(Contract.id == contract_id)
    if not include_deleted:
        stmt = stmt.where(Contract.deleted_at.is_(None))
    return db.scalar(stmt)


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
