import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.identity.models import (
    Employee,
    Permission,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_permission(db: Session, code: str) -> Permission:
    permission = db.scalar(text("SELECT * FROM permissions WHERE code = :code"), {"code": code})
    assert permission is not None, f"seeded permission {code!r} must exist"
    return permission


def _create_user(
    db: Session,
    *,
    username: str,
    is_superuser: bool = False,
) -> User:
    employee = Employee(full_name=f"{username} Employee")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=username,
        password_hash=hash_password("test-password-123!"),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.flush()
    return user


def _grant(
    db: Session,
    *,
    user: User,
    permission_code: str,
    role_code: str,
    scope_type: ScopeType,
    scope_config: dict | None,
) -> None:
    role = Role(code=role_code, name=role_code, is_system=False)
    db.add(role)
    db.flush()

    perm_id = db.scalar(
        text("SELECT id FROM permissions WHERE code = :code"),
        {"code": permission_code},
    )
    if perm_id is not None:
        db.add(RolePermission(role_id=role.id, permission_id=perm_id))

    db.add(
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            scope_type=scope_type,
            scope_config=scope_config,
            assigned_by=user.id,
        )
    )
    db.flush()


def _make_session_token(db: Session, user: User) -> str:
    from app.core.config import get_settings
    from app.modules.identity.service import AuthService
    result = AuthService(get_settings()).login(
        db,
        username=user.username,
        password="test-password-123!",
        ip_address="127.0.0.1",
        user_agent="test",
    )
    return result.token


def _organization(db: Session, *, legal_name: str) -> Organization:
    org = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name=legal_name,
        short_name=legal_name,
    )
    db.add(org)
    db.flush()
    return org


def _opo(
    db: Session,
    *,
    name: str,
    owner_id: uuid.UUID,
    operator_id: uuid.UUID,
) -> OPO:
    opo = OPO(
        name=name,
        registration_number=f"REG-{uuid.uuid4()}",
        hazard_class=HazardClass.HAZARD_CLASS_3,
        address=f"{name} address",
        registration_date=date(2026, 1, 1),
        owner_organization_id=owner_id,
        operating_organization_id=operator_id,
    )
    db.add(opo)
    db.flush()
    return opo


# ---------------------------------------------------------------------------
# Organizations — LIST
# ---------------------------------------------------------------------------

def test_org_related_list_scoped_and_total_scoped(
    db_session: Session,
    client,
) -> None:
    allowed_a = _organization(db_session, legal_name="Alpha Allowed")
    _organization(db_session, legal_name="Bravo Foreign")
    allowed_c = _organization(db_session, legal_name="Charlie Allowed")
    _organization(db_session, legal_name="Delta Foreign")

    user = _create_user(db_session, username="org-list-user")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-viewer-list",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_a.id), str(allowed_c.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/organizations?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {str(allowed_a.id), str(allowed_c.id)}


def test_org_related_list_q_cannot_broaden_scope(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, legal_name="Allowed Org")
    _organization(db_session, legal_name="Foreign Target")

    user = _create_user(db_session, username="org-q-user")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-viewer-q",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/organizations?q=Foreign",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ---------------------------------------------------------------------------
# Organizations — DETAIL
# ---------------------------------------------------------------------------

def test_org_detail_allowed(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="Allowed Detail")

    user = _create_user(db_session, username="org-detail-user")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-viewer-detail",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/organizations/{org.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(org.id)


def test_org_detail_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    foreign = _organization(db_session, legal_name="Foreign Detail")
    other = _organization(db_session, legal_name="Allowed Detail Other")

    user = _create_user(db_session, username="org-detail-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-viewer-detail-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(other.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/organizations/{foreign.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Organizations — CREATE
# ---------------------------------------------------------------------------

def test_org_create_related_returns_403(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="Existing Org")

    user = _create_user(db_session, username="org-create-user")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.create",
        role_code="org-creator-related",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/organizations",
        json={
            "legal_name": "New Organization",
            "short_name": "New Org",
            "organization_type": "legal_entity",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_org_create_all_allowed(
    db_session: Session,
    client,
) -> None:
    user = _create_user(db_session, username="org-create-all")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.create",
        role_code="org-creator-all",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/organizations",
        json={
            "legal_name": "All-Created Org",
            "short_name": "AC Org",
            "organization_type": "legal_entity",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["legal_name"] == "All-Created Org"


# ---------------------------------------------------------------------------
# Organizations — UPDATE (PATCH)
# ---------------------------------------------------------------------------

def test_org_update_allowed(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="Org To Update")

    user = _create_user(db_session, username="org-update-user")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.update",
        role_code="org-updater",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/organizations/{org.id}",
        json={"legal_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["legal_name"] == "Updated Name"


def test_org_update_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    foreign = _organization(db_session, legal_name="Foreign Update Org")
    allowed = _organization(db_session, legal_name="Allowed Update Org")

    user = _create_user(db_session, username="org-update-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.update",
        role_code="org-updater-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/organizations/{foreign.id}",
        json={"legal_name": "Hacked Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_org_update_foreign_parent_returns_404_unchanged(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="Org With Foreign Parent")
    foreign_parent = _organization(db_session, legal_name="Foreign Parent")

    user = _create_user(db_session, username="org-update-parent")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.update",
        role_code="org-updater-parent",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/organizations/{org.id}",
        json={"parent_id": str(foreign_parent.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Organizations — DELETE / RESTORE
# ---------------------------------------------------------------------------

def test_org_delete_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    foreign = _organization(db_session, legal_name="Foreign Delete Org")
    allowed = _organization(db_session, legal_name="Allowed Delete Org")

    user = _create_user(db_session, username="org-delete-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.delete",
        role_code="org-deleter-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/organizations/{foreign.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_org_restore_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    foreign = _organization(db_session, legal_name="Foreign Restore Org")
    foreign.deleted_at = datetime.now(UTC)
    allowed = _organization(db_session, legal_name="Allowed Restore Org")

    user = _create_user(db_session, username="org-restore-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.restore",
        role_code="org-restorer-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        f"/api/organizations/{foreign.id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Organizations — NESTED (contacts / identifiers)
# ---------------------------------------------------------------------------

def test_org_contacts_foreign_parent_returns_404(
    db_session: Session,
    client,
) -> None:
    foreign = _organization(db_session, legal_name="Foreign Contacts Org")
    allowed = _organization(db_session, legal_name="Allowed Contacts Org")

    user = _create_user(db_session, username="org-contacts-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-contacts-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/organizations/{foreign.id}/contacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_org_identifiers_foreign_parent_returns_404(
    db_session: Session,
    client,
) -> None:
    foreign = _organization(db_session, legal_name="Foreign Ident Org")
    allowed = _organization(db_session, legal_name="Allowed Ident Org")

    user = _create_user(db_session, username="org-ident-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-ident-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/organizations/{foreign.id}/identifiers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_org_contacts_allowed_parent(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="Allowed Contacts Org")

    user = _create_user(db_session, username="org-contacts-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-contacts-a",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/organizations/{org.id}/contacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_org_identifiers_allowed_parent(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="Allowed Ident Org")

    user = _create_user(db_session, username="org-ident-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code="org-ident-a",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/organizations/{org.id}/identifiers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# OPO — LIST
# ---------------------------------------------------------------------------

def test_opo_related_list_owner_allowed(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Allowed OPO Org")
    foreign_b = _organization(db_session, legal_name="Foreign B OPO")

    opo_allowed = _opo(
        db_session,
        name="Owner Allowed OPO",
        owner_id=allowed_org.id,
        operator_id=foreign_b.id,
    )

    user = _create_user(db_session, username="opo-list-owner")
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="opo-viewer-owner",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/opo?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(opo_allowed.id)


def test_opo_related_list_operator_allowed(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Allowed OPO Operator Org")
    foreign_a = _organization(db_session, legal_name="Foreign A OPO Op")

    opo_allowed = _opo(
        db_session,
        name="Operator Allowed OPO",
        owner_id=foreign_a.id,
        operator_id=allowed_org.id,
    )

    user = _create_user(db_session, username="opo-list-operator")
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="opo-viewer-operator",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/opo?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(opo_allowed.id)


def test_opo_related_list_excludes_fully_foreign(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Allowed OPO Exc Org")
    foreign_x = _organization(db_session, legal_name="Foreign X")
    foreign_y = _organization(db_session, legal_name="Foreign Y")

    _opo(
        db_session,
        name="Fully Foreign OPO",
        owner_id=foreign_x.id,
        operator_id=foreign_y.id,
    )

    user = _create_user(db_session, username="opo-list-exclude")
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="opo-viewer-exclude",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/opo?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ---------------------------------------------------------------------------
# OPO — DETAIL
# ---------------------------------------------------------------------------

def test_opo_detail_allowed(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Allowed OPO Detail Org")
    foreign = _organization(db_session, legal_name="Foreign Detail Org OPO")

    opo = _opo(
        db_session,
        name="Allowed OPO Detail",
        owner_id=allowed_org.id,
        operator_id=foreign.id,
    )

    user = _create_user(db_session, username="opo-detail-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="opo-viewer-detail",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_opo_detail_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Allowed OPO Detail F Org")
    foreign_a = _organization(db_session, legal_name="Foreign A Detail")
    foreign_b = _organization(db_session, legal_name="Foreign B Detail")

    opo = _opo(
        db_session,
        name="Foreign OPO Detail",
        owner_id=foreign_a.id,
        operator_id=foreign_b.id,
    )

    user = _create_user(db_session, username="opo-detail-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="opo-viewer-detail-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# OPO — CREATE
# ---------------------------------------------------------------------------

def test_opo_create_both_allowed(
    db_session: Session,
    client,
) -> None:
    owner = _organization(db_session, legal_name="OPO Create Owner")
    operator = _organization(db_session, legal_name="OPO Create Operator")

    user = _create_user(db_session, username="opo-create-both")
    _grant(
        db_session,
        user=user,
        permission_code="opo.create",
        role_code="opo-creator-both",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(owner.id), str(operator.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/opo",
        json={
            "name": "New OPO",
            "registration_number": "REG-NEW-001",
            "hazard_class": "hazard_class_3",
            "address": "123 Main St",
            "registration_date": "2026-01-01",
            "owner_organization_id": str(owner.id),
            "operating_organization_id": str(operator.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "New OPO"


def test_opo_create_foreign_owner_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_op = _organization(db_session, legal_name="OPO Create Allowed Op")
    foreign_owner = _organization(db_session, legal_name="Foreign Owner Create")

    user = _create_user(db_session, username="opo-create-fo")
    _grant(
        db_session,
        user=user,
        permission_code="opo.create",
        role_code="opo-creator-fo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_op.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/opo",
        json={
            "name": "Foreign Owner OPO",
            "registration_number": "REG-FO-001",
            "hazard_class": "hazard_class_3",
            "address": "456 Side St",
            "registration_date": "2026-01-01",
            "owner_organization_id": str(foreign_owner.id),
            "operating_organization_id": str(allowed_op.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_opo_create_foreign_operator_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_owner = _organization(db_session, legal_name="OPO Create Allowed Owner")
    foreign_op = _organization(db_session, legal_name="Foreign Operator Create")

    user = _create_user(db_session, username="opo-create-fopt")
    _grant(
        db_session,
        user=user,
        permission_code="opo.create",
        role_code="opo-creator-fopt",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_owner.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/opo",
        json={
            "name": "Foreign Operator OPO",
            "registration_number": "REG-FOPT-001",
            "hazard_class": "hazard_class_3",
            "address": "789 Back St",
            "registration_date": "2026-01-01",
            "owner_organization_id": str(allowed_owner.id),
            "operating_organization_id": str(foreign_op.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# OPO — UPDATE (PATCH)
# ---------------------------------------------------------------------------

def test_opo_update_allowed(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="OPO Update Org")
    opo = _opo(db_session, name="OPO To Update", owner_id=org.id, operator_id=org.id)

    user = _create_user(db_session, username="opo-update-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="opo.edit",
        role_code="opo-editor",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/opo/{opo.id}",
        json={"name": "Updated OPO"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated OPO"


def test_opo_update_newly_foreign_owner_returns_404(
    db_session: Session,
    client,
) -> None:
    owner = _organization(db_session, legal_name="OPO Update Owner Org")
    operator = _organization(db_session, legal_name="OPO Update Operator Org")
    foreign_new_owner = _organization(db_session, legal_name="Foreign New Owner")

    opo = _opo(db_session, name="OPO Update FO", owner_id=owner.id, operator_id=operator.id)

    user = _create_user(db_session, username="opo-update-fo")
    _grant(
        db_session,
        user=user,
        permission_code="opo.edit",
        role_code="opo-editor-fo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(owner.id), str(operator.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/opo/{opo.id}",
        json={"owner_organization_id": str(foreign_new_owner.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_opo_update_newly_foreign_operator_returns_404(
    db_session: Session,
    client,
) -> None:
    owner = _organization(db_session, legal_name="OPO Update Owner2 Org")
    operator = _organization(db_session, legal_name="OPO Update Operator2 Org")
    foreign_new_op = _organization(db_session, legal_name="Foreign New Operator")

    opo = _opo(db_session, name="OPO Update FO2", owner_id=owner.id, operator_id=operator.id)

    user = _create_user(db_session, username="opo-update-fo2")
    _grant(
        db_session,
        user=user,
        permission_code="opo.edit",
        role_code="opo-editor-fo2",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(owner.id), str(operator.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/opo/{opo.id}",
        json={"operating_organization_id": str(foreign_new_op.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# OPO — DELETE / RESTORE
# ---------------------------------------------------------------------------

def test_opo_delete_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, legal_name="OPO Delete Allowed")
    foreign_a = _organization(db_session, legal_name="Foreign Delete A")
    foreign_b = _organization(db_session, legal_name="Foreign Delete B")

    opo = _opo(
        db_session, name="Foreign Delete OPO",
        owner_id=foreign_a.id, operator_id=foreign_b.id,
    )

    user = _create_user(db_session, username="opo-delete-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="opo.delete",
        role_code="opo-deleter-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_opo_restore_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, legal_name="OPO Restore Allowed")
    foreign_a = _organization(db_session, legal_name="Foreign Restore A")
    foreign_b = _organization(db_session, legal_name="Foreign Restore B")

    opo = _opo(
        db_session, name="Foreign Restore OPO",
        owner_id=foreign_a.id, operator_id=foreign_b.id,
    )
    opo.deleted_at = datetime.now(UTC)

    user = _create_user(db_session, username="opo-restore-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="opo.restore",
        role_code="opo-restorer-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        f"/api/opo/{opo.id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# OPO — foreign PATCH leaves DB unchanged
# ---------------------------------------------------------------------------

def test_opo_update_foreign_owner_leaves_db_unchanged(
    db_session: Session,
    client,
) -> None:
    owner = _organization(db_session, legal_name="OPO Unchanged Owner")
    operator = _organization(db_session, legal_name="OPO Unchanged Operator")
    foreign_new = _organization(db_session, legal_name="Foreign Unchanged")

    opo = _opo(
        db_session,
        name="OPO Unchanged Name",
        owner_id=owner.id,
        operator_id=operator.id,
    )

    user = _create_user(db_session, username="opo-unchanged")
    _grant(
        db_session,
        user=user,
        permission_code="opo.edit",
        role_code="opo-editor-unchanged",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(owner.id), str(operator.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/opo/{opo.id}",
        json={"owner_organization_id": str(foreign_new.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(opo)
    assert opo.owner_organization_id == owner.id
    assert opo.operating_organization_id == operator.id
