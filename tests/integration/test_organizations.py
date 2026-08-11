import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.identity.models import AuditEvent, Employee, User
from app.modules.identity.security import hash_password
from app.modules.organizations.models import (
    ContactType,
    IdentifierType,
    Organization,
    OrganizationIdentifier,
    OrganizationType,
)
from app.modules.organizations.service import (
    OrganizationConflictError,
    OrganizationNotFoundError,
    OrganizationService,
)

pytestmark = pytest.mark.integration

_ORG_PERMISSIONS = {
    "organizations.view",
    "organizations.create",
    "organizations.update",
    "organizations.delete",
    "organizations.restore",
    "organizations.manage_contacts",
    "organizations.manage_identifiers",
}


@pytest.fixture()
def db() -> Session:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text("""
            TRUNCATE TABLE
                audit_events,
                organization_identifiers, organization_contacts, organizations,
                role_permissions, user_role_assignments,
                user_sessions, password_reset_events, users, employees
            RESTART IDENTITY CASCADE
        """)
        )
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def service() -> OrganizationService:
    return OrganizationService()


@pytest.fixture()
def actor(db: Session) -> User:
    employee = Employee(full_name="Admin")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username="admin-test",
        password_hash=hash_password("Strong-password-123!"),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    return user


def create_organization(db: Session, service: OrganizationService, actor: User) -> Organization:
    return service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Primer",
        short_name="Primer",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )


def test_organization_permissions_seeded(db: Session) -> None:
    from app.modules.identity.models import Permission

    codes = set(db.scalars(select(Permission.code)).all())
    assert codes >= _ORG_PERMISSIONS


def test_create_organization_and_enum_value_persisted(
    db: Session, service: OrganizationService, actor: User
) -> None:
    organization = create_organization(db, service, actor)
    raw = db.execute(
        text("select organization_type::text from organizations where id = :id"),
        {"id": organization.id},
    ).scalar_one()
    assert raw == "legal_entity"

    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.created"))
    assert event is not None
    assert event.entity_id == organization.id
    assert event.user_id == actor.id


def test_organization_family_chain(db: Session, service: OrganizationService, actor: User) -> None:
    parent = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Holding",
        short_name="Holding",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    child = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="AO Primer",
        short_name="Primer",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=parent.id,
    )
    assert child.parent_id == parent.id


def test_create_organization_rejects_missing_parent(
    db: Session, service: OrganizationService, actor: User
) -> None:
    with pytest.raises(OrganizationNotFoundError):
        service.create_organization(
            db,
            actor_id=actor.id,
            legal_name="OOO Ghost",
            short_name=None,
            organization_type=OrganizationType.LEGAL_ENTITY,
            parent_id=uuid.uuid4(),
        )


def test_update_organization_writes_audit(
    db: Session, service: OrganizationService, actor: User
) -> None:
    organization = create_organization(db, service, actor)
    updated = service.update_organization(
        db,
        actor_id=actor.id,
        organization=organization,
        legal_name="OOO Primer Plus",
        short_name="Primer+",
        organization_type=None,
        parent_id=None,
    )
    assert updated.legal_name == "OOO Primer Plus"
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.updated"))
    assert event is not None
    assert "legal_name" in (event.metadata_json or {}).get("changed_fields", [])


def test_soft_delete_and_restore(db: Session, service: OrganizationService, actor: User) -> None:
    organization = create_organization(db, service, actor)
    service.delete_organization(db, actor_id=actor.id, organization=organization)
    db.refresh(organization)
    assert organization.deleted_at is not None
    assert (
        db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.deleted")) is not None
    )

    service.restore_organization(db, actor_id=actor.id, organization=organization)
    db.refresh(organization)
    assert organization.deleted_at is None
    assert (
        db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.restored"))
        is not None
    )


def test_add_contact_and_set_primary(
    db: Session, service: OrganizationService, actor: User
) -> None:
    organization = create_organization(db, service, actor)
    first = service.add_contact(
        db,
        actor_id=actor.id,
        organization=organization,
        contact_type=ContactType.DIRECTOR,
        full_name="Ivanov Ivan",
        position="Director",
        phone="+70000000000",
        email="ivan@example.com",
        is_primary=True,
    )
    second = service.add_contact(
        db,
        actor_id=actor.id,
        organization=organization,
        contact_type=ContactType.ACCOUNTANT,
        full_name="Petrova Anna",
        position=None,
        phone=None,
        email=None,
        is_primary=False,
    )
    db.refresh(first)
    db.refresh(second)
    assert first.is_primary
    assert not second.is_primary

    service.set_primary_contact(db, actor_id=actor.id, contact=second)
    db.refresh(first)
    db.refresh(second)
    assert not first.is_primary
    assert second.is_primary

    assert (
        db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.contact_added"))
        is not None
    )
    assert (
        db.scalar(
            select(AuditEvent).where(AuditEvent.action == "organization.primary_contact_changed")
        )
        is not None
    )


def test_remove_contact(db: Session, service: OrganizationService, actor: User) -> None:
    organization = create_organization(db, service, actor)
    contact = service.add_contact(
        db,
        actor_id=actor.id,
        organization=organization,
        contact_type=ContactType.OTHER,
        full_name="Temp",
        position=None,
        phone=None,
        email=None,
        is_primary=False,
    )
    service.remove_contact(db, actor_id=actor.id, contact=contact)
    db.refresh(contact)
    assert contact.deleted_at is not None
    assert (
        db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.contact_removed"))
        is not None
    )


def test_add_and_remove_identifier(db: Session, service: OrganizationService, actor: User) -> None:
    organization = create_organization(db, service, actor)
    identifier = service.add_identifier(
        db,
        actor_id=actor.id,
        organization=organization,
        identifier_type=IdentifierType.INN,
        identifier_value="7701234567",
        is_primary=True,
    )
    raw = db.execute(
        text("select identifier_type::text from organization_identifiers where id = :id"),
        {"id": identifier.id},
    ).scalar_one()
    assert raw == "inn"

    assert (
        db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.identifier_added"))
        is not None
    )

    service.remove_identifier(db, actor_id=actor.id, identifier=identifier)
    assert db.get(OrganizationIdentifier, identifier.id) is None
    assert (
        db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.identifier_removed"))
        is not None
    )


def test_duplicate_identifier_type_conflicts(
    db: Session, service: OrganizationService, actor: User
) -> None:
    organization = create_organization(db, service, actor)
    service.add_identifier(
        db,
        actor_id=actor.id,
        organization=organization,
        identifier_type=IdentifierType.INN,
        identifier_value="7701234567",
        is_primary=True,
    )
    with pytest.raises(OrganizationConflictError):
        service.add_identifier(
            db,
            actor_id=actor.id,
            organization=organization,
            identifier_type=IdentifierType.INN,
            identifier_value="7701234567",
            is_primary=False,
        )


def test_single_primary_identifier_per_organization(
    db: Session, service: OrganizationService, actor: User
) -> None:
    organization = create_organization(db, service, actor)
    service.add_identifier(
        db,
        actor_id=actor.id,
        organization=organization,
        identifier_type=IdentifierType.INN,
        identifier_value="7701234567",
        is_primary=True,
    )
    with pytest.raises(OrganizationConflictError):
        service.add_identifier(
            db,
            actor_id=actor.id,
            organization=organization,
            identifier_type=IdentifierType.OGRN,
            identifier_value="1234567890123",
            is_primary=True,
        )
