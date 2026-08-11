import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.identity.authorization import (
    AuthorizationContext,
    can_access_opo,
    can_reference_organizations,
)
from app.modules.identity.dependencies import require_scoped_permission
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

_dep_view = Depends(require_scoped_permission("opo.view"))  # noqa: B008
_dep_create = Depends(require_scoped_permission("opo.create"))  # noqa: B008
_dep_edit = Depends(require_scoped_permission("opo.edit"))  # noqa: B008
_dep_delete = Depends(require_scoped_permission("opo.delete"))  # noqa: B008
_dep_restore = Depends(require_scoped_permission("opo.restore"))  # noqa: B008


def _opo_or_404(
    db: Session,
    opo_id: uuid.UUID,
    authorization: AuthorizationContext | None = None,
    *,
    include_deleted: bool = False,
):
    opo = get_opo(db, opo_id, include_deleted=include_deleted)
    if opo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OPO not found",
        )
    if (
        authorization is not None
        and not can_access_opo(authorization, opo)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OPO not found",
        )
    return opo


@router.get("", response_model=OPOPaginatedResponse)
def read_opo_list(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: uuid.UUID | None = None,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
):
    items, total = list_opo_paginated(
        db, q=q, page=page, page_size=page_size,
        organization_id=organization_id,
        authorization=authorization,
    )
    return OPOPaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
    )


@router.post(
    "",
    response_model=OPODetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_opo(
    payload: OPOCreate,
    authorization: AuthorizationContext = _dep_create,
    db: Session = Depends(get_db),
):
    if not can_reference_organizations(
        authorization,
        payload.owner_organization_id,
        payload.operating_organization_id,
    ):
        raise HTTPException(
            status_code=404, detail="Organization not found",
        )

    try:
        opo = service.create_opo(
            db,
            actor_id=authorization.user_id,
            name=payload.name,
            registration_number=payload.registration_number,
            hazard_class=payload.hazard_class,
            address=payload.address,
            registration_date=payload.registration_date,
            owner_organization_id=payload.owner_organization_id,
            operating_organization_id=payload.operating_organization_id,
            hazard_sign_ids=payload.hazard_sign_ids,
            activity_type_ids=payload.activity_type_ids,
            comment=payload.comment,
        )
        return service.get_opo_detail(db, opo.id)
    except OPONotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=str(exc),
        ) from exc
    except OPOConflictError as exc:
        raise HTTPException(
            status_code=409, detail=str(exc),
        ) from exc


@router.get("/{opo_id}", response_model=OPODetailResponse)
def read_opo(
    opo_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(db, opo_id, authorization)
    return service.get_opo_detail(db, opo.id)


@router.patch("/{opo_id}", response_model=OPODetailResponse)
def update_opo(
    opo_id: uuid.UUID,
    payload: OPOUpdate,
    authorization: AuthorizationContext = _dep_edit,
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(db, opo_id, authorization)

    if (
        payload.owner_organization_id is not None
        and not can_reference_organizations(
            authorization, payload.owner_organization_id,
        )
    ):
        raise HTTPException(
            status_code=404, detail="Organization not found",
        )

    if (
        payload.operating_organization_id is not None
        and not can_reference_organizations(
            authorization, payload.operating_organization_id,
        )
    ):
        raise HTTPException(
            status_code=404, detail="Organization not found",
        )

    try:
        opo = service.update_opo(
            db,
            actor_id=authorization.user_id,
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
            comment=payload.comment,
            comment_provided=(
                "comment" in payload.model_fields_set
            ),
        )
        return service.get_opo_detail(db, opo.id)
    except OPONotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=str(exc),
        ) from exc
    except OPOConflictError as exc:
        raise HTTPException(
            status_code=409, detail=str(exc),
        ) from exc


@router.delete(
    "/{opo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_opo(
    opo_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_delete,
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(db, opo_id, authorization)
    service.delete_opo(
        db, actor_id=authorization.user_id, opo=opo,
    )
    return None


@router.post(
    "/{opo_id}/restore",
    response_model=OPODetailResponse,
)
def restore_opo(
    opo_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_restore,
    db: Session = Depends(get_db),
):
    opo = _opo_or_404(
        db, opo_id, authorization, include_deleted=True,
    )
    if opo.deleted_at is None:
        raise HTTPException(
            status_code=400, detail="OPO is not deleted",
        )
    service.restore_opo(
        db, actor_id=authorization.user_id, opo=opo,
    )
    return service.get_opo_detail(db, opo.id)
