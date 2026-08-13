import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.organizations.enums import IdentifierType, OrganizationType
from app.modules.organizations.models import (
    Organization,
    OrganizationContact,
    OrganizationIdentifier,
)
from app.modules.organizations.repository import (
    get_organization,
    list_contacts,
    list_identifiers,
)


class OrganizationNotFoundError(Exception):
    pass


class ContactNotFoundError(Exception):
    pass


class IdentifierNotFoundError(Exception):
    pass


class OrganizationConflictError(Exception):
    pass


class OrganizationLegalFormError(ValueError):
    pass


def _has_value(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _identifier_types(
    identifiers: list[dict[str, str | bool]] | None,
) -> set[IdentifierType]:
    result: set[IdentifierType] = set()
    for identifier in identifiers or []:
        raw = identifier.get("identifier_type")
        if isinstance(raw, IdentifierType):
            result.add(raw)
        elif raw is not None:
            result.add(IdentifierType(str(raw)))
    return result


def validate_organization_legal_form(
    organization_type: OrganizationType,
    *,
    legal_address: str | None,
    actual_address: str | None,
    director_name: str | None,
    residence_address: str | None,
    passport_details: str | None,
    identifiers: list[dict[str, str | bool]] | None,
) -> None:
    """Reject fields/identifiers that do not apply to the selected legal form."""
    identifier_types = _identifier_types(identifiers)
    if organization_type is OrganizationType.INDIVIDUAL_ENTREPRENEUR:
        if any(_has_value(value) for value in (legal_address, actual_address, director_name)):
            raise OrganizationLegalFormError(
                "Для ИП нельзя указывать юридический/фактический адрес или директора"
            )
        forbidden = identifier_types & {IdentifierType.KPP, IdentifierType.OGRN}
        if forbidden:
            raise OrganizationLegalFormError("Для ИП допустимы ИНН и ОГРНИП")
        return

    if _has_value(residence_address) or _has_value(passport_details):
        raise OrganizationLegalFormError(
            "Место жительства и паспортные данные допустимы только для ИП"
        )
    if IdentifierType.OGRNIP in identifier_types:
        raise OrganizationLegalFormError("ОГРНИП допустим только для ИП")


class OrganizationService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _upsert_identifiers_for_organization(
        self,
        db: Session,
        *,
        organization: Organization,
        identifiers: list[dict[str, str | bool]] | None,
        actor_id: uuid.UUID,
    ) -> None:
        if identifiers is None:
            return
        existing = {ident.identifier_type: ident for ident in list_identifiers(db, organization.id)}
        for incoming in identifiers:
            itype = incoming["identifier_type"]
            value = incoming["identifier_value"]
            if itype in existing:
                ident = existing[itype]
                ident.identifier_value = value
                ident.is_primary = incoming.get("is_primary", False)
                del existing[itype]
            else:
                ident = OrganizationIdentifier(
                    organization_id=organization.id,
                    identifier_type=itype,
                    identifier_value=value,
                    is_primary=incoming.get("is_primary", False),
                )
                db.add(ident)
        for ident in existing.values():
            self.remove_identifier(db, actor_id=actor_id, identifier=ident)

    def create_organization(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        legal_name: str,
        short_name: str | None,
        organization_type,
        parent_id: uuid.UUID | None,
        legal_address: str | None = None,
        actual_address: str | None = None,
        residence_address: str | None = None,
        director_name: str | None = None,
        passport_details: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        comment: str | None = None,
        identifiers: list[dict[str, str | bool]] | None = None,
    ) -> Organization:
        validate_organization_legal_form(
            organization_type,
            legal_address=legal_address,
            actual_address=actual_address,
            director_name=director_name,
            residence_address=residence_address,
            passport_details=passport_details,
            identifiers=identifiers,
        )
        if parent_id is not None:
            parent = get_organization(db, parent_id)
            if parent is None:
                raise OrganizationNotFoundError("Parent organization not found")
        organization = Organization(
            legal_name=legal_name,
            short_name=short_name,
            organization_type=organization_type,
            parent_id=parent_id,
            legal_address=legal_address,
            actual_address=actual_address,
            residence_address=residence_address,
            director_name=director_name,
            passport_details=passport_details,
            phone=phone,
            email=email,
            comment=comment,
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
        self._upsert_identifiers_for_organization(
            db, organization=organization, identifiers=identifiers, actor_id=actor_id
        )
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
        legal_address: str | None = None,
        actual_address: str | None = None,
        residence_address: str | None = None,
        director_name: str | None = None,
        passport_details: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        comment: str | None = None,
        identifiers: list[dict[str, str | bool]] | None = None,
    ) -> Organization:
        target_type = organization_type or organization.organization_type
        validate_organization_legal_form(
            target_type,
            legal_address=legal_address,
            actual_address=actual_address,
            director_name=director_name,
            residence_address=residence_address,
            passport_details=passport_details,
            identifiers=identifiers,
        )
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
        if organization_type is not None and organization_type != organization.organization_type:
            organization.organization_type = organization_type
            changed.append("organization_type")
        if parent_id != organization.parent_id:
            organization.parent_id = parent_id
            changed.append("parent_id")

        if target_type is OrganizationType.INDIVIDUAL_ENTREPRENEUR:
            for field in ("legal_address", "actual_address", "director_name"):
                if getattr(organization, field) is not None:
                    setattr(organization, field, None)
                    changed.append(field)
        else:
            for field in ("residence_address", "passport_details"):
                if getattr(organization, field) is not None:
                    setattr(organization, field, None)
                    changed.append(field)

        if legal_address is not None and legal_address != organization.legal_address:
            organization.legal_address = legal_address
            changed.append("legal_address")
        if actual_address is not None and actual_address != organization.actual_address:
            organization.actual_address = actual_address
            changed.append("actual_address")
        if residence_address is not None and residence_address != organization.residence_address:
            organization.residence_address = residence_address
            changed.append("residence_address")
        if director_name is not None and director_name != organization.director_name:
            organization.director_name = director_name
            changed.append("director_name")
        if passport_details is not None and passport_details != organization.passport_details:
            organization.passport_details = passport_details
            changed.append("passport_details")
        if phone is not None and phone != organization.phone:
            organization.phone = phone
            changed.append("phone")
        if email is not None and email != organization.email:
            organization.email = email
            changed.append("email")
        if comment is not None and comment != organization.comment:
            organization.comment = comment
            changed.append("comment")
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
        self._upsert_identifiers_for_organization(
            db, organization=organization, identifiers=identifiers, actor_id=actor_id
        )
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
        contact.deleted_at = self._now()
        write_audit(
            db,
            action="organization.contact_removed",
            summary="Organization contact soft deleted",
            result="success",
            user_id=actor_id,
            entity_type="organization",
            entity_id=contact.organization_id,
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
