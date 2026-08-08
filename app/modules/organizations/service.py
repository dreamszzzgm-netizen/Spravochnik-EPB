import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.organizations.models import (
    Organization,
    OrganizationContact,
    OrganizationIdentifier,
)
from app.modules.organizations.repository import (
    get_organization,
    list_contacts,
)


class OrganizationNotFoundError(Exception):
    pass


class ContactNotFoundError(Exception):
    pass


class IdentifierNotFoundError(Exception):
    pass


class OrganizationConflictError(Exception):
    pass


class OrganizationService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def create_organization(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        legal_name: str,
        short_name: str | None,
        organization_type,
        parent_id: uuid.UUID | None,
    ) -> Organization:
        if parent_id is not None:
            parent = get_organization(db, parent_id)
            if parent is None:
                raise OrganizationNotFoundError("Parent organization not found")
        organization = Organization(
            legal_name=legal_name,
            short_name=short_name,
            organization_type=organization_type,
            parent_id=parent_id,
        )
        db.add(organization)
        db.flush()
        write_audit(
            db,
            action="organization.created",
            summary="Organization created",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization.id,
        )
        db.commit()
        db.refresh(organization)
        return organization

    def update_organization(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        organization: Organization,
        legal_name: str | None,
        short_name: str | None,
        organization_type,
        parent_id: uuid.UUID | None,
    ) -> Organization:
        if parent_id is not None and parent_id != organization.id:
            parent = get_organization(db, parent_id)
            if parent is None:
                raise OrganizationNotFoundError("Parent organization not found")
        changed: list[str] = []
        if legal_name is not None and legal_name != organization.legal_name:
            organization.legal_name = legal_name
            changed.append("legal_name")
        if short_name is not None and short_name != organization.short_name:
            organization.short_name = short_name
            changed.append("short_name")
        if organization_type is not None:
            organization.organization_type = organization_type
            changed.append("organization_type")
        if parent_id != organization.parent_id:
            organization.parent_id = parent_id
            changed.append("parent_id")
        write_audit(
            db,
            action="organization.updated",
            summary="Organization updated",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization.id,
            metadata={"changed_fields": changed},
        )
        db.commit()
        db.refresh(organization)
        return organization

    def delete_organization(
        self, db: Session, *, actor_id: uuid.UUID, organization: Organization
    ) -> None:
        organization.deleted_at = self._now()
        write_audit(
            db,
            action="organization.deleted",
            summary="Organization soft deleted",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization.id,
        )
        db.commit()

    def restore_organization(
        self, db: Session, *, actor_id: uuid.UUID, organization: Organization
    ) -> None:
        organization.deleted_at = None
        write_audit(
            db,
            action="organization.restored",
            summary="Organization restored",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization.id,
        )
        db.commit()

    def add_contact(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        organization: Organization,
        contact_type,
        full_name: str,
        position: str | None,
        phone: str | None,
        email: str | None,
        is_primary: bool,
    ) -> OrganizationContact:
        if is_primary:
            for contact in list_contacts(db, organization.id):
                if contact.is_primary:
                    contact.is_primary = False
            db.flush()
        contact = OrganizationContact(
            organization_id=organization.id,
            contact_type=contact_type,
            full_name=full_name,
            position=position,
            phone=phone,
            email=email,
            is_primary=is_primary,
        )
        db.add(contact)
        db.flush()
        write_audit(
            db,
            action="organization.contact_added",
            summary="Organization contact added",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization.id,
            metadata={"contact_id": str(contact.id), "is_primary": is_primary},
        )
        db.commit()
        db.refresh(contact)
        return contact

    def set_primary_contact(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contact: OrganizationContact,
    ) -> OrganizationContact:
        if not contact.is_primary:
            for other in list_contacts(db, contact.organization_id):
                if other.is_primary:
                    other.is_primary = False
            db.flush()
            contact.is_primary = True
            write_audit(
                db,
                action="organization.primary_contact_changed",
                summary="Primary organization contact changed",
                result="success",
                user_id=actor_id,
                entity_type="organization",
                entity_id=contact.organization_id,
                metadata={"contact_id": str(contact.id)},
            )
            db.commit()
        db.refresh(contact)
        return contact

    def remove_contact(
        self, db: Session, *, actor_id: uuid.UUID, contact: OrganizationContact
    ) -> None:
        organization_id = contact.organization_id
        db.delete(contact)
        write_audit(
            db,
            action="organization.contact_removed",
            summary="Organization contact removed",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization_id,
            metadata={"contact_id": str(contact.id)},
        )
        db.commit()

    def add_identifier(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        organization: Organization,
        identifier_type,
        identifier_value: str,
        is_primary: bool,
    ) -> OrganizationIdentifier:
        identifier = OrganizationIdentifier(
            organization_id=organization.id,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            is_primary=is_primary,
        )
        db.add(identifier)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise OrganizationConflictError("Identifier type or value already in use") from exc
        write_audit(
            db,
            action="organization.identifier_added",
            summary="Organization identifier added",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization.id,
            metadata={
                "identifier_id": str(identifier.id),
                "identifier_type": identifier_type.value,
            },
        )
        db.commit()
        db.refresh(identifier)
        return identifier

    def remove_identifier(
        self, db: Session, *, actor_id: uuid.UUID, identifier: OrganizationIdentifier
    ) -> None:
        organization_id = identifier.organization_id
        db.delete(identifier)
        write_audit(
            db,
            action="organization.identifier_removed",
            summary="Organization identifier removed",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=organization_id,
            metadata={
                "identifier_id": str(identifier.id),
                "identifier_type": identifier.identifier_type.value,
            },
        )
        db.commit()
