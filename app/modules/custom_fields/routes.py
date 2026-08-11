import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.buildings.repository import get_building
from app.modules.custom_fields.schemas import (
    CustomFieldDefinitionResponse,
    CustomFieldValueResponse,
    CustomFieldValueSetRequest,
)
from app.modules.custom_fields.service import (
    CustomFieldConflictError,
    CustomFieldNotFoundError,
    CustomFieldService,
    CustomFieldValidationError,
)
from app.modules.identity.authorization import (
    AuthorizationContext,
    can_access_building,
    can_access_opo,
    can_access_technical_device,
)
from app.modules.identity.dependencies import require_permission, require_scoped_permission
from app.modules.identity.models import User
from app.modules.opo.repository import get_opo
from app.modules.technical_devices.repository import get_technical_device

router = APIRouter(prefix="/api/custom-fields", tags=["custom-fields"])
service = CustomFieldService()

_SUPPORTED_CF_ENTITY_TYPES = {"opo", "technical_device", "building"}


def _parent_or_404(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    authorization: AuthorizationContext,
) -> object:
    if entity_type not in _SUPPORTED_CF_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Unsupported entity type '{entity_type}'. "
                f"Supported: building, opo, technical_device."
            ),
        )

    if entity_type == "opo":
        parent = get_opo(db, entity_id)
        if parent is None or not can_access_opo(authorization, parent):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return parent

    if entity_type == "technical_device":
        parent = get_technical_device(db, entity_id)
        if parent is None or not can_access_technical_device(authorization, parent):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return parent

    # building
    parent = get_building(db, entity_id)
    if parent is None or not can_access_building(authorization, parent):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return parent


@router.get("/definitions", response_model=list[CustomFieldDefinitionResponse])
def read_definitions(
    entity_type: str | None = Query(None),
    _actor: User = Depends(require_permission("custom_fields.manage")),
    db: Session = Depends(get_db),
):
    return service.list_definitions(db, entity_type=entity_type)


@router.get(
    "/values/{entity_type}/{entity_id}", response_model=list[CustomFieldValueResponse]
)
def read_values(
    entity_type: str,
    entity_id: uuid.UUID,
    authorization: AuthorizationContext = Depends(
        require_scoped_permission("custom_fields.manage")
    ),
    db: Session = Depends(get_db),
):
    _parent_or_404(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        authorization=authorization,
    )
    try:
        return service.get_values(db, entity_type=entity_type, entity_id=entity_id)
    except CustomFieldNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/values/{entity_type}/{entity_id}/{field_definition_id}",
    response_model=CustomFieldValueResponse,
    status_code=status.HTTP_200_OK,
)
def set_value(
    entity_type: str,
    entity_id: uuid.UUID,
    field_definition_id: uuid.UUID,
    payload: CustomFieldValueSetRequest,
    authorization: AuthorizationContext = Depends(
        require_scoped_permission("custom_fields.manage")
    ),
    db: Session = Depends(get_db),
):
    _parent_or_404(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        authorization=authorization,
    )
    try:
        return service.set_value(
            db,
            actor_id=authorization.user_id,
            field_definition_id=field_definition_id,
            entity_type=entity_type,
            entity_id=entity_id,
            value=payload.value,
        )
    except CustomFieldNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CustomFieldValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CustomFieldConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/values/{entity_type}/{entity_id}/{field_definition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def clear_value(
    entity_type: str,
    entity_id: uuid.UUID,
    field_definition_id: uuid.UUID,
    authorization: AuthorizationContext = Depends(
        require_scoped_permission("custom_fields.manage")
    ),
    db: Session = Depends(get_db),
):
    _parent_or_404(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        authorization=authorization,
    )
    try:
        service.clear_value(
            db,
            actor_id=authorization.user_id,
            field_definition_id=field_definition_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except CustomFieldNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None
