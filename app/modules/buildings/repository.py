import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building


def get_building(
    db: Session, building_id: uuid.UUID, *, include_deleted: bool = False
) -> Building | None:
    stmt = select(Building).where(Building.id == building_id)
    if not include_deleted:
        stmt = stmt.where(Building.deleted_at.is_(None))
    return db.scalar(stmt)


def list_buildings_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
) -> tuple[list[Building], int]:
    from sqlalchemy import or_

    stmt = select(Building).where(Building.deleted_at.is_(None))

    if organization_id is not None:
        from app.modules.opo.models import OPO

        stmt = stmt.join(OPO, Building.opo_id == OPO.id, isouter=True).where(
            or_(
                OPO.owner_organization_id == organization_id,
                OPO.operating_organization_id == organization_id,
            )
        )

    if opo_id is not None:
        stmt = stmt.where(Building.opo_id == opo_id)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Building.name.ilike(pattern))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    offset = max(0, page - 1) * page_size
    items = list(
        db.scalars(
            stmt.order_by(Building.name.asc(), Building.id.asc())
            .offset(offset)
            .limit(min(page_size, 100))
        )
    )
    return items, total or 0
