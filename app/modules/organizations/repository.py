import uuid

from sqlalchemy import Select, false, func, or_, select
from sqlalchemy.orm import Session

from app.modules.identity.authorization import AuthorizationContext
from app.modules.organizations.models import (
    Organization,
    OrganizationContact,
    OrganizationIdentifier,
)


def get_organization(
    db: Session, organization_id: uuid.UUID, *, include_deleted: bool = False
) -> Organization | None:
    stmt: Select[tuple[Organization]] = select(Organization).where(
        Organization.id == organization_id
    )
    if not include_deleted:
        stmt = stmt.where(Organization.deleted_at.is_(None))
    return db.scalar(stmt)


def list_organizations(
    db: Session, *, include_deleted: bool = False, limit: int = 100
) -> list[Organization]:
    stmt = select(Organization).order_by(Organization.legal_name).limit(limit)
    if not include_deleted:
        stmt = stmt.where(Organization.deleted_at.is_(None))
    return list(db.scalars(stmt))


def list_contacts(
    db: Session,
    organization_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> list[OrganizationContact]:
    stmt = (
        select(OrganizationContact)
        .where(OrganizationContact.organization_id == organization_id)
    )
    if not include_deleted:
        stmt = stmt.where(OrganizationContact.deleted_at.is_(None))
    stmt = stmt.order_by(
        OrganizationContact.is_primary.desc(),
        OrganizationContact.full_name,
    )
    return list(db.scalars(stmt))


def get_contact(db: Session, contact_id: uuid.UUID) -> OrganizationContact | None:
    return db.get(OrganizationContact, contact_id)


def list_identifiers(db: Session, organization_id: uuid.UUID) -> list[OrganizationIdentifier]:
    stmt = (
        select(OrganizationIdentifier)
        .where(OrganizationIdentifier.organization_id == organization_id)
        .order_by(OrganizationIdentifier.identifier_type)
    )
    return list(db.scalars(stmt))


def get_identifier(db: Session, identifier_id: uuid.UUID) -> OrganizationIdentifier | None:
    return db.get(OrganizationIdentifier, identifier_id)


def list_organizations_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[Organization], int]:
    stmt = select(Organization).where(Organization.deleted_at.is_(None))

    if (
        authorization is not None
        and not authorization.has_all_scope
    ):
        allowed_ids = authorization.related_organization_ids

        stmt = (
            stmt.where(Organization.id.in_(allowed_ids))
            if allowed_ids
            else stmt.where(false())
        )

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Organization.legal_name.ilike(pattern),
                Organization.short_name.ilike(pattern),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(
            stmt.subquery()
        )
    )

    offset = max(0, page - 1) * page_size

    items = list(
        db.scalars(
            stmt.order_by(
                Organization.legal_name.asc()
            )
            .offset(offset)
            .limit(page_size)
        )
    )

    return items, total or 0
