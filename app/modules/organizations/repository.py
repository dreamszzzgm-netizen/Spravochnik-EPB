import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

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


def list_contacts(db: Session, organization_id: uuid.UUID) -> list[OrganizationContact]:
    stmt = (
        select(OrganizationContact)
        .where(OrganizationContact.organization_id == organization_id)
        .order_by(
            OrganizationContact.is_primary.desc(),
            OrganizationContact.full_name,
        )
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
