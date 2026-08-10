import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.identity.dependencies import require_permission
from app.modules.identity.models import User
from app.modules.opo.repository import (
    get_opo,
    list_opo_paginated,
)
from app.modules.opo.schemas import (
    OPOCreate,
    OPODetailResponse,
    OPOPaginatedResponse,
    OPOUpdate,
)
from app.modules.opo.service import (
    OPOConflictError,
    OPONotFoundError,
    OPOService,
)

router = APIRouter(prefix="/api/opo", tags=["opo"])
service = OPOService()


def _opo_or_404(db: Session, opo_id: uuid.UUID, *, include_deleted: bool = False):
    opo = get_opo(db, opo_id, include_deleted=include_deleted)
    if opo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OPO not found")
    return opo


@router.get("", response_model=OPOPaginatedResponse)
def read_opo_list(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: uuid.UUID | None = None,
    _actor: User = Depends(require_permission("opo.view")),
    db: Session = Depends(get_db),
):
    items, total = list_opo_paginated(
        db, q=q, page=page, page_size=page_size, organization_id=organization_id
    )
    return OPOPaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=OPODetailResponse, status_code=status.HTTP_201_CREATED)
def create_opo(
    payload: OPOCreate,
    actor: User = Depends(require_permission("opo.create")),
    db: Session = Depends(get_db),
):
    try:
        opo = service.create_opo(
            db,
            actor_id=actor.id,
            name=payload.name,
            registration_number=payload.registration_number,
            hazard_class=payload.hazard_class,
            address=payload.address,
            registration_date=payload.registration_date,
            owner_organization_id=payload.owner_organization_id,
            operating_organization_id=payload.operating_organization_id,
            hazard_sign_ids=payload.hazard_sign_ids,
            activity_type_ids=payload.activity_type_ids,
        )
        return service.get_opo_detail(db, opo.id)
    except OPONotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OPOConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{opo_id}", response_model=OPODetailResponse)
def read_opo(
    opo_id: uuid.UUID,
    _actor: User = Depends(require_permission("opo.view")),
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(db, opo_id)
    return service.get_opo_detail(db, opo.id)


@router.patch("/{opo_id}", response_model=OPODetailResponse)
def update_opo(
    opo_id: uuid.UUID,
    payload: OPOUpdate,
    actor: User = Depends(require_permission("opo.edit")),
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(db, opo_id)
    try:
        opo = service.update_opo(
            db,
            actor_id=actor.id,
            opo=opo,
            name=payload.name,
            registration_number=payload.registration_number,
            hazard_class=payload.hazard_class,
            address=payload.address,
            registration_date=payload.registration_date,
            owner_organization_id=payload.owner_organization_id,
            operating_organization_id=payload.operating_organization_id,
            hazard_sign_ids=payload.hazard_sign_ids,
            activity_type_ids=payload.activity_type_ids,
        )
        return service.get_opo_detail(db, opo.id)
    except OPONotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OPOConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{opo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opo(
    opo_id: uuid.UUID,
    actor: User = Depends(require_permission("opo.delete")),
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(db, opo_id)
    service.delete_opo(db, actor_id=actor.id, opo=opo)
    return None


@router.post("/{opo_id}/restore", response_model=OPODetailResponse)
def restore_opo(
    opo_id: uuid.UUID,
    actor: User = Depends(require_permission("opo.restore")),
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(db, opo_id, include_deleted=True)
    if opo.deleted_at is None:
        raise HTTPException(status_code=400, detail="OPO is not deleted")
    service.restore_opo(db, actor_id=actor.id, opo=opo)
    return service.get_opo_detail(db, opo.id)
