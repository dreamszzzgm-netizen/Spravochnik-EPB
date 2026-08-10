import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.opo.models import (
    OPO,
    ActivityType,
    HazardSign,
    OPOActivityType,
    OPOHazardSign,
)


def get_opo(db: Session, opo_id: uuid.UUID, *, include_deleted: bool = False) -> OPO | None:
    stmt = select(OPO).where(OPO.id == opo_id)
    if not include_deleted:
        stmt = stmt.where(OPO.deleted_at.is_(None))
    return db.scalar(stmt)


def list_opo_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    organization_id: uuid.UUID | None = None,
    include_deleted: bool = False,
) -> tuple[list[OPO], int]:
    from sqlalchemy import or_

    stmt = select(OPO)
    if not include_deleted:
        stmt = stmt.where(OPO.deleted_at.is_(None))

    if organization_id is not None:
        stmt = stmt.where(
            or_(
                OPO.owner_organization_id == organization_id,
                OPO.operating_organization_id == organization_id,
            )
        )

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                OPO.name.ilike(pattern),
                OPO.registration_number.ilike(pattern),
                OPO.address.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    offset = max(0, page - 1) * page_size
    items = list(
        db.scalars(
            stmt.order_by(OPO.name.asc(), OPO.id.asc())
            .offset(offset)
            .limit(min(page_size, 100))
        )
    )
    return items, total or 0


def get_hazard_sign(db: Session, sign_id: uuid.UUID) -> HazardSign | None:
    return db.get(HazardSign, sign_id)


def list_hazard_signs(db: Session) -> list[HazardSign]:
    return list(db.scalars(select(HazardSign).order_by(HazardSign.code)))


def get_activity_type(db: Session, type_id: uuid.UUID) -> ActivityType | None:
    return db.get(ActivityType, type_id)


def list_activity_types(db: Session) -> list[ActivityType]:
    return list(db.scalars(select(ActivityType).order_by(ActivityType.code)))


def list_opo_hazard_signs(db: Session, opo_id: uuid.UUID) -> list[HazardSign]:
    return list(
        db.scalars(
            select(HazardSign)
            .join(OPOHazardSign, OPOHazardSign.hazard_sign_id == HazardSign.id)
            .where(OPOHazardSign.opo_id == opo_id)
            .order_by(HazardSign.code)
        )
    )


def list_opo_activity_types(db: Session, opo_id: uuid.UUID) -> list[ActivityType]:
    return list(
        db.scalars(
            select(ActivityType)
            .join(OPOActivityType, OPOActivityType.activity_type_id == ActivityType.id)
            .where(OPOActivityType.opo_id == opo_id)
            .order_by(ActivityType.code)
        )
    )


def get_registration_number_count(db: Session, registration_number: str) -> int:
    return db.scalar(
        select(func.count()).select_from(
            select(OPO).where(OPO.registration_number == registration_number).subquery()
        )
    ) or 0
