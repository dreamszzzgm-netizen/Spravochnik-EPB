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
from app.modules.identity.authorization import (
    AuthorizationContext,
    can_access_building,
    can_access_opo,
    can_reference_organizations,
)
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.opo.repository import get_opo

router = APIRouter(prefix="/api/buildings", tags=["buildings"])
service = BuildingService()

_dep_view = Depends(require_scoped_permission("buildings.view"))  # noqa: B008
_dep_create = Depends(require_scoped_permission("buildings.create"))  # noqa: B008
_dep_edit = Depends(require_scoped_permission("buildings.edit"))  # noqa: B008
_dep_delete = Depends(require_scoped_permission("buildings.delete"))  # noqa: B008
_dep_restore = Depends(require_scoped_permission("buildings.restore"))  # noqa: B008


def _building_or_404(
    db: Session,
    building_id: uuid.UUID,
    authorization: AuthorizationContext | None = None,
    *,
    include_deleted: bool = False,
):
    building = get_building(db, building_id, include_deleted=include_deleted)
    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Building not found"
        )
    if (
        authorization is not None
        and not can_access_building(authorization, building)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Building not found"
        )
    return building


@router.get("", response_model=BuildingPaginatedResponse)
def read_buildings(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
):
    items, total = list_buildings_paginated(
        db, q=q, page=page, page_size=page_size,
        organization_id=organization_id, opo_id=opo_id,
        authorization=authorization,
    )
    return BuildingPaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=BuildingResponse, status_code=status.HTTP_201_CREATED)
def create_building(
    payload: BuildingCreate,
    authorization: AuthorizationContext = _dep_create,
    db: Session = Depends(get_db),
):
    if not can_reference_organizations(authorization, payload.organization_id):
        raise HTTPException(status_code=404, detail="Organization not found")

    if payload.opo_id is not None:
        opo = get_opo(db, payload.opo_id)
        if opo is None or opo.deleted_at is not None:
            raise HTTPException(status_code=404, detail="OPO not found")
        if not can_access_opo(authorization, opo):
            raise HTTPException(status_code=404, detail="OPO not found")

    try:
        return service.create_building(
            db,
            actor_id=authorization.user_id,
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
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
):
    return _building_or_404(db, building_id, authorization)


@router.patch("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: uuid.UUID,
    payload: BuildingUpdate,
    authorization: AuthorizationContext = _dep_edit,
    db: Session = Depends(get_db),
):
    building = _building_or_404(db, building_id, authorization)

    if "organization_id" in payload.model_fields_set and payload.organization_id is None:
        raise HTTPException(status_code=422, detail="organization_id cannot be null")

    if (
        "organization_id" in payload.model_fields_set
        and payload.organization_id is not None
        and not can_reference_organizations(authorization, payload.organization_id)
    ):
        raise HTTPException(status_code=404, detail="Organization not found")

    if (
        "opo_id" in payload.model_fields_set
        and payload.opo_id is not None
    ):
        opo = get_opo(db, payload.opo_id)
        if opo is None or opo.deleted_at is not None:
            raise HTTPException(status_code=404, detail="OPO not found")
        if not can_access_opo(authorization, opo):
            raise HTTPException(status_code=404, detail="OPO not found")

    try:
        return service.update_building(
            db,
            actor_id=authorization.user_id,
            building=building,
            name=payload.name,
            building_type=payload.building_type,
            opo_id=payload.opo_id,
            opo_id_provided="opo_id" in payload.model_fields_set,
            organization_id=payload.organization_id,
            organization_id_provided="organization_id" in payload.model_fields_set,
        )
    except BuildingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_building(
    building_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_delete,
    db: Session = Depends(get_db),
):
    building = _building_or_404(db, building_id, authorization)
    service.delete_building(db, actor_id=authorization.user_id, building=building)
    return None


@router.post("/{building_id}/restore", response_model=BuildingResponse)
def restore_building(
    building_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_restore,
    db: Session = Depends(get_db),
):
    building = _building_or_404(db, building_id, authorization, include_deleted=True)
    if building.deleted_at is None:
        raise HTTPException(status_code=400, detail="Building is not deleted")
    service.restore_building(db, actor_id=authorization.user_id, building=building)
    return building
