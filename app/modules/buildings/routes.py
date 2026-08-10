import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.buildings.repository import get_building, list_buildings_paginated
from app.modules.buildings.schemas import (
    BuildingCreate,
    BuildingPaginatedResponse,
    BuildingResponse,
    BuildingUpdate,
)
from app.modules.buildings.service import BuildingNotFoundError, BuildingService
from app.modules.identity.dependencies import require_permission
from app.modules.identity.models import User

router = APIRouter(prefix="/api/buildings", tags=["buildings"])
service = BuildingService()


def _building_or_404(db: Session, building_id: uuid.UUID, *, include_deleted: bool = False):
    building = get_building(db, building_id, include_deleted=include_deleted)
    if building is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    return building


@router.get("", response_model=BuildingPaginatedResponse)
def read_buildings(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
    _actor: User = Depends(require_permission("buildings.view")),
    db: Session = Depends(get_db),
):
    items, total = list_buildings_paginated(
        db, q=q, page=page, page_size=page_size,
        organization_id=organization_id, opo_id=opo_id,
    )
    return BuildingPaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=BuildingResponse, status_code=status.HTTP_201_CREATED)
def create_building(
    payload: BuildingCreate,
    actor: User = Depends(require_permission("buildings.create")),
    db: Session = Depends(get_db),
):
    try:
        return service.create_building(
            db,
            actor_id=actor.id,
            name=payload.name,
            building_type=payload.building_type,
            organization_id=payload.organization_id,
            opo_id=payload.opo_id,
        )
    except BuildingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{building_id}", response_model=BuildingResponse)
def read_building(
    building_id: uuid.UUID,
    _actor: User = Depends(require_permission("buildings.view")),
    db: Session = Depends(get_db),
):
    return _building_or_404(db, building_id)


@router.patch("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: uuid.UUID,
    payload: BuildingUpdate,
    actor: User = Depends(require_permission("buildings.edit")),
    db: Session = Depends(get_db),
):
    building = _building_or_404(db, building_id)
    try:
        return service.update_building(
            db,
            actor_id=actor.id,
            building=building,
            name=payload.name,
            building_type=payload.building_type,
            opo_id=payload.opo_id,
            organization_id=payload.organization_id,
        )
    except BuildingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_building(
    building_id: uuid.UUID,
    actor: User = Depends(require_permission("buildings.delete")),
    db: Session = Depends(get_db),
):
    building = _building_or_404(db, building_id)
    service.delete_building(db, actor_id=actor.id, building=building)
    return None


@router.post("/{building_id}/restore", response_model=BuildingResponse)
def restore_building(
    building_id: uuid.UUID,
    actor: User = Depends(require_permission("buildings.restore")),
    db: Session = Depends(get_db),
):
    building = _building_or_404(db, building_id, include_deleted=True)
    if building.deleted_at is None:
        raise HTTPException(status_code=400, detail="Building is not deleted")
    service.restore_building(db, actor_id=actor.id, building=building)
    return building
