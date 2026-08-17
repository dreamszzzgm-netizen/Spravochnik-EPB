"""CP-N1 Acceptance Regression Tests.

Covers:
- Branch-as-parent: branch CAN have another branch as parent
- Parent type validation: non-branch types cannot have parent_id
- Self-parenting rejection
- Deleted parent rejection
- Search endpoint accessibility
- Completeness endpoint correctness
- bank_details field persistence
- Audit events on create/update/delete
- Transaction atomicity: create/update with conflicting identifiers
- Identifier set replacement atomicity
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.models import AuditEvent, Employee, User
from app.modules.identity.security import hash_password
from app.modules.organizations.models import (
    IdentifierType,
    Organization,
    OrganizationIdentifier,
    OrganizationType,
)
from app.modules.organizations.service import (
    OrganizationService,
    OrganizationValidationError,
)

pytestmark = pytest.mark.integration


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
        username="admin-cp1n",
        password_hash=hash_password("Strong-password-123!"),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def client(db: Session) -> TestClient:
    from app.database.session import get_db
    from app.main import app

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# --- Branch-as-parent tests ---

def test_branch_can_have_branch_as_parent(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Branch CAN have another branch as parent (no type restriction on parent)."""
    # Create a legal entity root (branches need a root ancestor)
    legal = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Legal Root",
        short_name="LR",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    branch = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Branch Org",
        short_name="BO",
        organization_type=OrganizationType.BRANCH,
        parent_id=legal.id,
    )
    # Now make the branch a parent of another branch
    child_branch = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Child Branch",
        short_name="CB",
        organization_type=OrganizationType.BRANCH,
        parent_id=branch.id,
    )
    assert child_branch.parent_id == branch.id


def test_branch_must_have_parent(db: Session, service: OrganizationService, actor: User) -> None:
    """Branch without parent_id is rejected."""
    with pytest.raises(OrganizationValidationError, match="обязательно указание головной"):
        service.create_organization(
            db,
            actor_id=actor.id,
            legal_name="Orphan Branch",
            short_name=None,
            organization_type=OrganizationType.BRANCH,
            parent_id=None,
        )


def test_self_parenting_rejected(db: Session, service: OrganizationService, actor: User) -> None:
    """Organization cannot be parent of itself via update."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Self Parent",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    # Change type to branch and try to set itself as parent
    with pytest.raises(OrganizationValidationError, match="филиалом самой себя"):
        service.update_organization(
            db,
            actor_id=actor.id,
            organization=org,
            legal_name=None,
            short_name=None,
            organization_type=OrganizationType.BRANCH,
            parent_id=org.id,
        )


def test_deleted_parent_rejected(db: Session, service: OrganizationService, actor: User) -> None:
    """Cannot assign deleted organization as parent."""
    parent = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Deleted Parent",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    service.delete_organization(db, actor_id=actor.id, organization=parent)
    db.refresh(parent)
    assert parent.deleted_at is not None

    with pytest.raises(OrganizationValidationError, match="удалённую головную"):
        service.create_organization(
            db,
            actor_id=actor.id,
            legal_name="Child of Deleted",
            short_name=None,
            organization_type=OrganizationType.BRANCH,
            parent_id=parent.id,
        )


def test_non_branch_cannot_have_parent(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """LEGAL_ENTITY and IP cannot have parent_id."""
    parent = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Some Parent",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    with pytest.raises(
        OrganizationValidationError,
        match="указание головной организации запрещено",
    ):
        service.create_organization(
            db,
            actor_id=actor.id,
            legal_name="Bad Child",
            short_name=None,
            organization_type=OrganizationType.LEGAL_ENTITY,
            parent_id=parent.id,
        )


# --- bank_details persistence tests ---

def test_bank_details_persisted_on_create(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """bank_details field is saved on create."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Bank Details",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
        bank_details="р/с 40702810400000000001\nБанк: ПАО Сбербанк",
    )
    db.refresh(org)
    assert org.bank_details == "р/с 40702810400000000001\nБанк: ПАО Сбербанк"


def test_bank_details_persisted_on_update(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """bank_details field is saved on update."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Update Bank",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    assert org.bank_details is None

    updated = service.update_organization(
        db,
        actor_id=actor.id,
        organization=org,
        legal_name=None,
        short_name=None,
        organization_type=None,
        parent_id=None,
        bank_details="New bank details",
    )
    db.refresh(updated)
    assert updated.bank_details == "New bank details"


# --- Completeness tests ---

def test_completeness_legal_entity_missing_required(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Legal entity with no identifiers shows missing fields."""
    from app.modules.organizations.service import assess_organization_completeness

    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Minimal",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    result = assess_organization_completeness(org)
    codes = [f["code"] for f in result["required_fields"]]
    assert "inn" in codes
    assert "kpp" in codes
    assert "ogrn" in codes
    # legal_name is filled, so it should not be in missing
    missing = [f for f in result["required_fields"] if not f["filled"]]
    missing_codes = [f["code"] for f in missing]
    assert "inn" in missing_codes
    assert "legal_name" not in missing_codes


def test_completeness_branch_requires_parent(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Branch completeness includes parent_id field."""
    from app.modules.organizations.service import assess_organization_completeness

    legal = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Legal Root",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    branch = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Branch Org",
        short_name=None,
        organization_type=OrganizationType.BRANCH,
        parent_id=legal.id,
    )
    result = assess_organization_completeness(branch)
    codes = [f["code"] for f in result["required_fields"]]
    assert "parent_id" in codes
    parent_field = [f for f in result["required_fields"] if f["code"] == "parent_id"][0]
    assert parent_field["filled"] is True


def test_completeness_ip_fields(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """IP completeness checks inn, ogrnip, residence_address, passport_details."""
    from app.modules.organizations.service import assess_organization_completeness

    ip = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="ИП Иванов",
        short_name=None,
        organization_type=OrganizationType.INDIVIDUAL_ENTREPRENEUR,
        parent_id=None,
    )
    result = assess_organization_completeness(ip)
    codes = [f["code"] for f in result["required_fields"]]
    assert "inn" in codes
    assert "ogrnip" in codes
    assert "residence_address" in codes
    assert "passport_details" in codes


# --- Search endpoint tests ---

def test_search_endpoint_returns_only_active(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Search endpoint returns only non-deleted organizations."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Searchable Org",
        short_name="SO",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    deleted_org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Deleted Org",
        short_name="DO",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    service.delete_organization(db, actor_id=actor.id, organization=deleted_org)

    from app.database.session import get_db
    from app.main import app
    from app.modules.identity.dependencies import get_current_user

    def _override_db():
        yield db

    def _override_user():
        return actor

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/api/organizations/search?q=Org")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(org.id) in ids
    assert str(deleted_org.id) not in ids


def test_search_endpoint_not_shadowed_by_dynamic_route(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """GET /api/organizations/search is reachable, not caught by /{organization_id}."""
    from app.database.session import get_db
    from app.main import app
    from app.modules.identity.dependencies import get_current_user

    def _override_db():
        yield db

    def _override_user():
        return actor

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/api/organizations/search?q=test")
    app.dependency_overrides.clear()
    # Should return 200 (not 422 which would indicate route shadowing)
    assert response.status_code == 200


# --- Identifier persistence tests ---

def test_identifiers_persisted_on_create(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Identifiers passed on create are saved."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Identifiers",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
        identifiers=[
            {
                "identifier_type": IdentifierType.INN,
                "identifier_value": "7701234567",
                "is_primary": True,
            },
            {
                "identifier_type": IdentifierType.KPP,
                "identifier_value": "770101001",
                "is_primary": False,
            },
        ],
    )
    from app.modules.organizations.repository import list_identifiers

    idents = list_identifiers(db, org.id)
    types = {i.identifier_type for i in idents}
    assert IdentifierType.INN in types
    assert IdentifierType.KPP in types


# --- Audit event tests ---

def test_create_writes_audit_event(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Creating organization writes organization.created audit event."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Audit",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "organization.created",
            AuditEvent.entity_id == org.id,
        )
    )
    assert event is not None
    assert event.user_id == actor.id


def test_update_writes_audit_event(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Updating organization writes organization.updated audit event with changed_fields."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Audit Update",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    service.update_organization(
        db,
        actor_id=actor.id,
        organization=org,
        legal_name="OOO Audit Updated",
        short_name=None,
        organization_type=None,
        parent_id=None,
    )
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "organization.updated")
    )
    assert event is not None
    assert "legal_name" in (event.metadata_json or {}).get("changed_fields", [])


# --- Transaction atomicity tests ---


def _inn(value: str = "7701234567", primary: bool = True) -> dict:
    return {
        "identifier_type": IdentifierType.INN,
        "identifier_value": value,
        "is_primary": primary,
    }


def _kpp(value: str = "770101001", primary: bool = False) -> dict:
    return {
        "identifier_type": IdentifierType.KPP,
        "identifier_value": value,
        "is_primary": primary,
    }


def _ogrn(value: str = "1027700123456", primary: bool = False) -> dict:
    return {
        "identifier_type": IdentifierType.OGRN,
        "identifier_value": value,
        "is_primary": primary,
    }


def test_create_identifier_conflict_rolls_back(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """A: create with conflicting OGRN → error → new org does not exist."""
    org1 = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Org With OGRN",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
        identifiers=[_ogrn()],
    )
    # org1 committed; start a fresh session scope for the conflict test
    db.expire_all()

    with pytest.raises(IntegrityError):
        service.create_organization(
            db,
            actor_id=actor.id,
            legal_name="Conflicting Org",
            short_name=None,
            organization_type=OrganizationType.LEGAL_ENTITY,
            parent_id=None,
            identifiers=[_ogrn()],
        )
    db.rollback()

    # New org must not exist
    conflict = select(Organization).where(
        Organization.legal_name == "Conflicting Org"
    )
    assert db.scalar(conflict) is None
    # org1's identifier must still exist
    ident = db.scalar(
        select(OrganizationIdentifier).where(
            OrganizationIdentifier.organization_id == org1.id,
            OrganizationIdentifier.identifier_type == IdentifierType.OGRN,
        )
    )
    assert ident is not None
    assert ident.identifier_value == "1027700123456"


def test_update_identifier_conflict_rolls_back(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """B: update with conflicting OGRN → error → original fields/identifiers unchanged."""
    service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Org1 OGRN",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
        identifiers=[_ogrn()],
    )
    org2 = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Org2 OGRN",
        short_name="Org2",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
        identifiers=[_ogrn("1029999999999"), _kpp()],
    )
    db.expire_all()

    # Try to change org2's OGRN to org1's OGRN — must fail
    with pytest.raises(IntegrityError):
        service.update_organization(
            db,
            actor_id=actor.id,
            organization=org2,
            legal_name="Org2 Renamed",
            short_name=None,
            organization_type=None,
            parent_id=None,
            identifiers=[_ogrn(), _kpp()],
        )
    db.rollback()

    # Reload from DB: org2 must be completely unchanged
    from app.modules.organizations.repository import list_identifiers

    db.refresh(org2)
    assert org2.legal_name == "Org2 OGRN"
    assert org2.short_name == "Org2"
    idents = list_identifiers(db, org2.id)
    ogrn = [i for i in idents if i.identifier_type == IdentifierType.OGRN]
    assert len(ogrn) == 1
    assert ogrn[0].identifier_value == "1029999999999"
    kpp = [i for i in idents if i.identifier_type == IdentifierType.KPP]
    assert len(kpp) == 1
    assert kpp[0].identifier_value == "770101001"


def test_identifier_replacement_is_atomic(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """C: replacing identifier set in update is atomic — old identifiers removed,
    new identifiers added, no partial state visible."""
    org = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="OOO Replace",
        short_name=None,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
        identifiers=[_inn("7700000001"), _kpp()],
    )
    from app.modules.organizations.repository import list_identifiers

    # Replace KPP with OGRN in a single update call
    updated = service.update_organization(
        db,
        actor_id=actor.id,
        organization=org,
        legal_name=None,
        short_name=None,
        organization_type=None,
        parent_id=None,
        identifiers=[_inn("7700000001"), _ogrn()],
    )
    db.refresh(updated)

    idents = list_identifiers(db, org.id)
    types = {i.identifier_type for i in idents}
    assert IdentifierType.INN in types
    assert IdentifierType.OGRN in types
    assert IdentifierType.KPP not in types
    assert len(idents) == 2


# --- Parent search scope and type tests ---


def test_branch_appears_in_parent_search(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Branch organizations are returned in parent search results."""
    legal = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Legal Root",
        short_name="LR",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    branch = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Branch Parent",
        short_name="BP",
        organization_type=OrganizationType.BRANCH,
        parent_id=legal.id,
    )

    from app.database.session import get_db
    from app.main import app
    from app.modules.identity.dependencies import get_current_user

    def _override_db():
        yield db

    def _override_user():
        return actor

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/api/organizations/search?q=Branch")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(branch.id) in ids


def test_search_respects_related_scope(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Scoped user sees only organizations in their related_organization_ids."""
    from app.modules.identity.authorization import AuthorizationContext
    from app.modules.organizations.repository import list_organizations_paginated

    visible = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Visible Org",
        short_name="VO",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    hidden = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Hidden Org",
        short_name="HO",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )

    scoped_ctx = AuthorizationContext(
        user_id=actor.id,
        employee_id=actor.employee_id,
        permission_code="organizations.view",
        is_superuser=False,
        has_all_scope=False,
        related_organization_ids=frozenset({visible.id}),
        active_scope_types=frozenset(),
    )

    from app.database.session import get_db
    from app.main import app
    from app.modules.identity.dependencies import get_current_user

    def _override_db():
        yield db

    def _override_user():
        return actor

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    items, _total = list_organizations_paginated(
        db, q="Org", authorization=scoped_ctx
    )

    app.dependency_overrides.clear()

    ids = [str(item.id) for item in items]
    assert str(visible.id) in ids
    assert str(hidden.id) not in ids


def test_search_excludes_deleted_organizations(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Soft-deleted organizations never appear in parent search."""
    deleted = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="About to Die",
        short_name="AD",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    service.delete_organization(db, actor_id=actor.id, organization=deleted)

    from app.database.session import get_db
    from app.main import app
    from app.modules.identity.dependencies import get_current_user

    def _override_db():
        yield db

    def _override_user():
        return actor

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/api/organizations/search?q=About")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(deleted.id) not in ids


def test_full_scope_user_sees_all_parent_types(
    db: Session, service: OrganizationService, actor: User
) -> None:
    """Superuser sees all organization types in parent search."""
    legal = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Full LE",
        short_name="FLE",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )
    branch = service.create_organization(
        db,
        actor_id=actor.id,
        legal_name="Full Branch",
        short_name="FB",
        organization_type=OrganizationType.BRANCH,
        parent_id=legal.id,
    )

    from app.database.session import get_db
    from app.main import app
    from app.modules.identity.dependencies import get_current_user

    def _override_db():
        yield db

    def _override_user():
        return actor

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/api/organizations/search?q=Full")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(legal.id) in ids
    assert str(branch.id) in ids
