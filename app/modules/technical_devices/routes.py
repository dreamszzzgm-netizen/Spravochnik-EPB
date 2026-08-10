import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.identity.dependencies import require_permission
from app.modules.identity.models import User
from app.modules.technical_devices.repository import (
    get_technical_device,
    list_technical_devices_paginated,
)
from app.modules.technical_devices.schemas import (
    TechnicalDeviceCreate,
    TechnicalDevicePaginatedResponse,
    TechnicalDeviceResponse,
    TechnicalDeviceUpdate,
)
from app.modules.technical_devices.service import (
    TechnicalDeviceNotFoundError,
    TechnicalDeviceService,
)

router = APIRouter(prefix="/api/technical-devices", tags=["technical-devices"])
service = TechnicalDeviceService()


def _device_or_404(db: Session, device_id: uuid.UUID, *, include_deleted: bool = False):
    device = get_technical_device(db, device_id, include_deleted=include_deleted)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Technical device not found"
        )
    return device


@router.get("", response_model=TechnicalDevicePaginatedResponse)
def read_devices(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
    _actor: User = Depends(require_permission("technical_devices.view")),
    db: Session = Depends(get_db),
):
    items, total = list_technical_devices_paginated(
        db, q=q, page=page, page_size=page_size,
        organization_id=organization_id, opo_id=opo_id,
    )
    return TechnicalDevicePaginatedResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("", response_model=TechnicalDeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: TechnicalDeviceCreate,
    actor: User = Depends(require_permission("technical_devices.create")),
    db: Session = Depends(get_db),
):
    try:
        return service.create_technical_device(
            db,
            actor_id=actor.id,
            name=payload.name,
            device_type=payload.device_type,
            serial_number=payload.serial_number,
            opo_id=payload.opo_id,
            organization_id=payload.organization_id,
        )
    except TechnicalDeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{device_id}", response_model=TechnicalDeviceResponse)
def read_device(
    device_id: uuid.UUID,
    _actor: User = Depends(require_permission("technical_devices.view")),
    db: Session = Depends(get_db),
):
    return _device_or_404(db, device_id)


@router.patch("/{device_id}", response_model=TechnicalDeviceResponse)
def update_device(
    device_id: uuid.UUID,
    payload: TechnicalDeviceUpdate,
    actor: User = Depends(require_permission("technical_devices.edit")),
    db: Session = Depends(get_db),
):
    device = _device_or_404(db, device_id)
    if "organization_id" in payload.model_fields_set and payload.organization_id is None:
        raise HTTPException(status_code=422, detail="organization_id cannot be null")
    try:
        return service.update_technical_device(
            db,
            actor_id=actor.id,
            device=device,
            name=payload.name,
            device_type=payload.device_type,
            serial_number=payload.serial_number,
            serial_number_provided="serial_number" in payload.model_fields_set,
            opo_id=payload.opo_id,
            opo_id_provided="opo_id" in payload.model_fields_set,
            organization_id=payload.organization_id,
            organization_id_provided="organization_id" in payload.model_fields_set,
        )
    except TechnicalDeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: uuid.UUID,
    actor: User = Depends(require_permission("technical_devices.delete")),
    db: Session = Depends(get_db),
):
    device = _device_or_404(db, device_id)
    service.delete_technical_device(db, actor_id=actor.id, device=device)
    return None


@router.post("/{device_id}/restore", response_model=TechnicalDeviceResponse)
def restore_device(
    device_id: uuid.UUID,
    actor: User = Depends(require_permission("technical_devices.restore")),
    db: Session = Depends(get_db),
):
    device = _device_or_404(db, device_id, include_deleted=True)
    if device.deleted_at is None:
        raise HTTPException(status_code=400, detail="Device is not deleted")
    service.restore_technical_device(db, actor_id=actor.id, device=device)
    return device
