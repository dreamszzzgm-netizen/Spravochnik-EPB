import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
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
from app.modules.identity.dependencies import require_permission
from app.modules.identity.models import User

router = APIRouter(prefix="/api/custom-fields", tags=["custom-fields"])
service = CustomFieldService()


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
    _actor: User = Depends(require_permission("custom_fields.manage")),
    db: Session = Depends(get_db),
):
    return service.get_values(db, entity_type=entity_type, entity_id=entity_id)


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
    actor: User = Depends(require_permission("custom_fields.manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.set_value(
            db,
            actor_id=actor.id,
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
    actor: User = Depends(require_permission("custom_fields.manage")),
    db: Session = Depends(get_db),
):
    try:
        service.clear_value(
            db,
            actor_id=actor.id,
            field_definition_id=field_definition_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except CustomFieldNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None
