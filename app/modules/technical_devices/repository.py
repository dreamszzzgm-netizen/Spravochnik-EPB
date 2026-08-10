import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.technical_devices.models import TechnicalDevice


def get_technical_device(
    db: Session, device_id: uuid.UUID, *, include_deleted: bool = False
) -> TechnicalDevice | None:
    stmt = select(TechnicalDevice).where(TechnicalDevice.id == device_id)
    if not include_deleted:
        stmt = stmt.where(TechnicalDevice.deleted_at.is_(None))
    return db.scalar(stmt)


def list_technical_devices_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
) -> tuple[list[TechnicalDevice], int]:
    from sqlalchemy import or_

    stmt = select(TechnicalDevice).where(TechnicalDevice.deleted_at.is_(None))

    if organization_id:
        stmt = stmt.where(TechnicalDevice.organization_id == organization_id)

    if opo_id is not None:
        stmt = stmt.where(TechnicalDevice.opo_id == opo_id)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                TechnicalDevice.name.ilike(pattern),
                TechnicalDevice.serial_number.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    offset = max(0, page - 1) * page_size
    items = list(
        db.scalars(
            stmt.order_by(TechnicalDevice.name.asc(), TechnicalDevice.id.asc())
            .offset(offset)
            .limit(min(page_size, 100))
        )
    )
    return items, total or 0
