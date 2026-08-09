import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.identity.dependencies import require_permission
from app.modules.identity.models import User
from app.modules.organizations.repository import (
    get_contact,
    get_identifier,
    get_organization,
    list_contacts,
    list_identifiers,
    list_organizations_paginated,
)
from app.modules.organizations.schemas import (
    OrganizationContactCreate,
    OrganizationContactResponse,
    OrganizationCreateWithIdentifiers,
    OrganizationIdentifierCreate,
    OrganizationIdentifierResponse,
    OrganizationPaginatedResponse,
    OrganizationResponse,
    OrganizationUpdateWithIdentifiers,
)
from app.modules.organizations.service import (
    ContactNotFoundError,
    OrganizationConflictError,
    OrganizationNotFoundError,
    OrganizationService,
)

router = APIRouter(prefix="/api/organizations", tags=["organizations"])
service = OrganizationService()


def _organization_or_404(db: Session, organization_id: uuid.UUID, *, include_deleted: bool = False):
    organization = get_organization(db, organization_id, include_deleted=include_deleted)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.get("", response_model=OrganizationPaginatedResponse)
def read_organizations(
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    _actor: User = Depends(require_permission("organizations.view")),
    db: Session = Depends(get_db),
):
    items, total = list_organizations_paginated(db, q=q, page=page, page_size=page_size)
    return OrganizationPaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreateWithIdentifiers,
    actor: User = Depends(require_permission("organizations.create")),
    db: Session = Depends(get_db),
):
    try:
        return service.create_organization(
            db,
            actor_id=actor.id,
            legal_name=payload.legal_name,
            short_name=payload.short_name,
            organization_type=payload.organization_type,
            parent_id=payload.parent_id,
            legal_address=payload.legal_address,
            actual_address=payload.actual_address,
            director_name=payload.director_name,
            phone=payload.phone,
            email=payload.email,
            comment=payload.comment,
            identifiers=[ident.model_dump() for ident in payload.identifiers] if payload.identifiers else None,
        )
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{organization_id}", response_model=OrganizationResponse)
def read_organization(
    organization_id: uuid.UUID,
    _actor: User = Depends(require_permission("organizations.view")),
    db: Session = Depends(get_db),
):
    return _organization_or_404(db, organization_id)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: uuid.UUID,
    payload: OrganizationUpdateWithIdentifiers,
    actor: User = Depends(require_permission("organizations.update")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    try:
        return service.update_organization(
            db,
            actor_id=actor.id,
            organization=organization,
            legal_name=payload.legal_name,
            short_name=payload.short_name,
            organization_type=payload.organization_type,
            parent_id=payload.parent_id,
            legal_address=payload.legal_address,
            actual_address=payload.actual_address,
            director_name=payload.director_name,
            phone=payload.phone,
            email=payload.email,
            comment=payload.comment,
            identifiers=[ident.model_dump() for ident in payload.identifiers] if payload.identifiers else None,
        )
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    organization_id: uuid.UUID,
    actor: User = Depends(require_permission("organizations.delete")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    service.delete_organization(db, actor_id=actor.id, organization=organization)
    return None


@router.post("/{organization_id}/restore", response_model=OrganizationResponse)
def restore_organization(
    organization_id: uuid.UUID,
    actor: User = Depends(require_permission("organizations.restore")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id, include_deleted=True)
    service.restore_organization(db, actor_id=actor.id, organization=organization)
    return organization


@router.post(
    "/{organization_id}/contacts",
    response_model=OrganizationContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    organization_id: uuid.UUID,
    payload: OrganizationContactCreate,
    actor: User = Depends(require_permission("organizations.manage_contacts")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    return service.add_contact(
        db,
        actor_id=actor.id,
        organization=organization,
        contact_type=payload.contact_type,
        full_name=payload.full_name,
        position=payload.position,
        phone=payload.phone,
        email=payload.email,
        is_primary=payload.is_primary,
    )


@router.get("/{organization_id}/contacts", response_model=list[OrganizationContactResponse])
def read_contacts(
    organization_id: uuid.UUID,
    _actor: User = Depends(require_permission("organizations.view")),
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id)
    return list_contacts(db, organization_id)


@router.post(
    "/{organization_id}/contacts/{contact_id}/primary",
    response_model=OrganizationContactResponse,
)
def set_primary_contact(
    organization_id: uuid.UUID,
    contact_id: uuid.UUID,
    actor: User = Depends(require_permission("organizations.manage_contacts")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    contact = get_contact(db, contact_id)
    if contact is None or contact.organization_id != organization.id:
        raise HTTPException(status_code=404, detail="Contact not found")
    try:
        return service.set_primary_contact(db, actor_id=actor.id, contact=contact)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{organization_id}/contacts/{contact_id}", response_model=OrganizationContactResponse)
def update_contact(
    organization_id: uuid.UUID,
    contact_id: uuid.UUID,
    payload: OrganizationContactCreate,
    actor: User = Depends(require_permission("organizations.manage_contacts")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    contact = get_contact(db, contact_id)
    if contact is None or contact.organization_id != organization.id:
        raise HTTPException(status_code=404, detail="Contact not found")
    if contact.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.contact_type = payload.contact_type
    contact.full_name = payload.full_name
    contact.position = payload.position
    contact.phone = payload.phone
    contact.email = payload.email
    if payload.is_primary and not contact.is_primary:
        for other in list_contacts(db, organization.id):
            if other.is_primary:
                other.is_primary = False
        contact.is_primary = True
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{organization_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    organization_id: uuid.UUID,
    contact_id: uuid.UUID,
    actor: User = Depends(require_permission("organizations.manage_contacts")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    contact = get_contact(db, contact_id)
    if contact is None or contact.organization_id != organization.id or contact.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Contact not found")
    service.remove_contact(db, actor_id=actor.id, contact=contact)
    return None


@router.post(
    "/{organization_id}/identifiers",
    response_model=OrganizationIdentifierResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_identifier(
    organization_id: uuid.UUID,
    payload: OrganizationIdentifierCreate,
    actor: User = Depends(require_permission("organizations.manage_identifiers")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    try:
        return service.add_identifier(
            db,
            actor_id=actor.id,
            organization=organization,
            identifier_type=payload.identifier_type,
            identifier_value=payload.identifier_value,
            is_primary=payload.is_primary,
        )
    except OrganizationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{organization_id}/identifiers", response_model=list[OrganizationIdentifierResponse])
def read_identifiers(
    organization_id: uuid.UUID,
    _actor: User = Depends(require_permission("organizations.view")),
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id)
    return list_identifiers(db, organization_id)


@router.delete(
    "/{organization_id}/identifiers/{identifier_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_identifier(
    organization_id: uuid.UUID,
    identifier_id: uuid.UUID,
    actor: User = Depends(require_permission("organizations.manage_identifiers")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    identifier = get_identifier(db, identifier_id)
    if identifier is None or identifier.organization_id != organization.id:
        raise HTTPException(status_code=404, detail="Identifier not found")
    service.remove_identifier(db, actor_id=actor.id, identifier=identifier)
    return None
