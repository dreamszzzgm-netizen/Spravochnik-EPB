import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.documents.models import DocumentRequirement
from app.modules.documents.repository import get_requirement, list_requirements
from app.modules.documents.schemas import (
    DocumentRequirementCreate,
    DocumentRequirementResponse,
    DocumentRequirementUpdate,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/api/document-requirements", tags=["document-requirements"])


def _require_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


@router.get("", response_model=list[DocumentRequirementResponse])
def read_requirements(
    _user: User = Depends(_require_superuser), db: Session = Depends(get_db)
):
    return list_requirements(db)


@router.post(
    "", response_model=DocumentRequirementResponse, status_code=status.HTTP_201_CREATED
)
def create_requirement(
    payload: DocumentRequirementCreate,
    _user: User = Depends(_require_superuser),
    db: Session = Depends(get_db),
):
    requirement = DocumentRequirement(**payload.model_dump())
    db.add(requirement)
    try:
        db.commit()
        db.refresh(requirement)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Requirement already exists") from exc
    return requirement


@router.patch("/{requirement_id}", response_model=DocumentRequirementResponse)
def update_requirement(
    requirement_id: uuid.UUID,
    payload: DocumentRequirementUpdate,
    _user: User = Depends(_require_superuser),
    db: Session = Depends(get_db),
):
    requirement = get_requirement(db, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(requirement, field, value)
    try:
        db.commit()
        db.refresh(requirement)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Requirement already exists") from exc
    return requirement


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def disable_requirement(
    requirement_id: uuid.UUID,
    _user: User = Depends(_require_superuser),
    db: Session = Depends(get_db),
):
    requirement = get_requirement(db, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    requirement.active = False
    db.commit()
