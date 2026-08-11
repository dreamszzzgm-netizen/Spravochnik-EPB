import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
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
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.models import TechnicalDevice

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


def _td(
    db: Session,
    *,
    name: str,
    organization_id: uuid.UUID,
    opo_id: uuid.UUID | None = None,
) -> TechnicalDevice:
    device = TechnicalDevice(
        name=name,
        device_type=TechnicalDeviceType.OTHER,
        organization_id=organization_id,
        opo_id=opo_id,
    )
    db.add(device)
    db.flush()
    return device


def _building(
    db: Session,
    *,
    name: str,
    organization_id: uuid.UUID,
    opo_id: uuid.UUID | None = None,
) -> Building:
    building = Building(
        name=name,
        building_type=BuildingType.OTHER,
        organization_id=organization_id,
        opo_id=opo_id,
    )
    db.add(building)
    db.flush()
    return building


# ===================================================================
# TECHNICAL DEVICES — LIST
# ===================================================================

def test_td_related_list_scoped_and_total_scoped(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Allowed Org")
    foreign_org = _organization(db_session, legal_name="TD Foreign Org")

    _td(db_session, name="Allowed Device", organization_id=allowed_org.id)
    _td(db_session, name="Foreign Device", organization_id=foreign_org.id)

    user = _create_user(db_session, username="td-list-user")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code="td-viewer-list",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/technical-devices?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Allowed Device"


def test_td_related_list_excludes_foreign_via_opo(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Allowed Org OPO")
    foreign_org = _organization(db_session, legal_name="TD Foreign Org OPO")
    foreign_b = _organization(db_session, legal_name="TD Foreign B Org OPO")

    opo = _opo(
        db_session,
        name="Allowed OPO for TD",
        owner_id=allowed_org.id,
        operator_id=foreign_org.id,
    )
    _td(
        db_session,
        name="Foreign Device via OPO",
        organization_id=foreign_b.id,
        opo_id=opo.id,
    )

    user = _create_user(db_session, username="td-list-foreign-opo")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code="td-viewer-foreign-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/technical-devices?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ===================================================================
# TECHNICAL DEVICES — DETAIL
# ===================================================================

def test_td_detail_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Detail Allowed")
    foreign_org = _organization(db_session, legal_name="TD Detail Foreign")

    device = _td(db_session, name="Foreign TD Detail", organization_id=foreign_org.id)

    user = _create_user(db_session, username="td-detail-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code="td-viewer-detail-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/technical-devices/{device.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===================================================================
# TECHNICAL DEVICES — DELETE / RESTORE
# ===================================================================

def test_td_delete_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Delete Allowed")
    foreign_org = _organization(db_session, legal_name="TD Delete Foreign")

    device = _td(db_session, name="Foreign TD Delete", organization_id=foreign_org.id)

    user = _create_user(db_session, username="td-delete-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.delete",
        role_code="td-deleter-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/technical-devices/{device.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_td_restore_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Restore Allowed")
    foreign_org = _organization(db_session, legal_name="TD Restore Foreign")

    device = _td(db_session, name="Foreign TD Restore", organization_id=foreign_org.id)
    device.deleted_at = datetime.now(UTC)

    user = _create_user(db_session, username="td-restore-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.restore",
        role_code="td-restorer-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        f"/api/technical-devices/{device.id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===================================================================
# TECHNICAL DEVICES — CREATE
# ===================================================================

def test_td_create_foreign_organization_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Create Allowed")
    foreign_org = _organization(db_session, legal_name="TD Create Foreign")

    user = _create_user(db_session, username="td-create-foreign-org")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.create",
        role_code="td-creator-foreign-org",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/technical-devices",
        json={
            "name": "Foreign Org Device",
            "device_type": "other",
            "organization_id": str(foreign_org.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_td_create_foreign_opo_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Create Allowed OPO")
    foreign_org = _organization(db_session, legal_name="TD Create Foreign OPO")
    foreign_op = _organization(db_session, legal_name="TD Create Foreign OP")

    opo = _opo(
        db_session,
        name="Foreign OPO for TD Create",
        owner_id=foreign_org.id,
        operator_id=foreign_op.id,
    )

    user = _create_user(db_session, username="td-create-foreign-opo")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.create",
        role_code="td-creator-foreign-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/technical-devices",
        json={
            "name": "Foreign OPO Device",
            "device_type": "other",
            "organization_id": str(allowed_org.id),
            "opo_id": str(opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_td_create_allowed_org_matching_opo(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Create Both Allowed")
    foreign_org = _organization(db_session, legal_name="TD Create Both Foreign")

    opo = _opo(
        db_session,
        name="Matching OPO for TD",
        owner_id=allowed_org.id,
        operator_id=foreign_org.id,
    )

    user = _create_user(db_session, username="td-create-both")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.create",
        role_code="td-creator-both",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/technical-devices",
        json={
            "name": "Matching OPO Device",
            "device_type": "other",
            "organization_id": str(allowed_org.id),
            "opo_id": str(opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Matching OPO Device"


# ===================================================================
# TECHNICAL DEVICES — UPDATE (PATCH)
# ===================================================================

def test_td_patch_explicit_null_organization_returns_422(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="TD Patch Null Org")
    device = _td(db_session, name="TD Patch Null Org Device", organization_id=org.id)

    user = _create_user(db_session, username="td-patch-null-org")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-null-org",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"organization_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_td_patch_foreign_organization_returns_404_unchanged(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch Allowed Org")
    foreign_org = _organization(db_session, legal_name="TD Patch Foreign Org")

    device = _td(
        db_session,
        name="TD Patch Foreign Org Device",
        organization_id=allowed_org.id,
    )

    user = _create_user(db_session, username="td-patch-foreign-org")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-foreign-org",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"organization_id": str(foreign_org.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(device)
    assert device.organization_id == allowed_org.id


def test_td_patch_foreign_opo_returns_404_unchanged(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch Allowed OPO")
    foreign_org = _organization(db_session, legal_name="TD Patch Foreign OPO")
    foreign_op = _organization(db_session, legal_name="TD Patch Foreign OP")

    foreign_opo = _opo(
        db_session,
        name="Foreign OPO for TD Patch",
        owner_id=foreign_org.id,
        operator_id=foreign_op.id,
    )

    device = _td(
        db_session,
        name="TD Patch Foreign OPO Device",
        organization_id=allowed_org.id,
    )

    user = _create_user(db_session, username="td-patch-foreign-opo")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-foreign-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"opo_id": str(foreign_opo.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(device)
    assert device.opo_id is None


def test_td_patch_invalid_relation_combo_returns_404_unchanged(
    db_session: Session,
    client,
) -> None:
    org_a = _organization(db_session, legal_name="TD Patch Combo Org A")
    org_b = _organization(db_session, legal_name="TD Patch Combo Org B")

    opo = _opo(
        db_session,
        name="Combo OPO for TD",
        owner_id=org_b.id,
        operator_id=org_b.id,
    )

    device = _td(
        db_session,
        name="TD Combo Device",
        organization_id=org_a.id,
    )

    user = _create_user(db_session, username="td-patch-combo")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-combo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org_a.id), str(org_b.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={
            "organization_id": str(org_a.id),
            "opo_id": str(opo.id),
            "name": "Should Not Change",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(device)
    assert device.name == "TD Combo Device"
    assert device.organization_id == org_a.id
    assert device.opo_id is None


def test_td_patch_scalar_only_no_reauthorize_unchanged_relation(
    db_session: Session,
    client,
) -> None:
    org_a = _organization(db_session, legal_name="TD Scalar Org A")
    org_b = _organization(db_session, legal_name="TD Scalar Org B")

    opo = _opo(
        db_session,
        name="Scalar OPO for TD",
        owner_id=org_b.id,
        operator_id=org_b.id,
    )

    device = _td(
        db_session,
        name="TD Scalar Device",
        organization_id=org_a.id,
        opo_id=opo.id,
    )

    user = _create_user(db_session, username="td-patch-scalar")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-scalar",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org_a.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"name": "Renamed Device"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Device"

    db_session.refresh(device)
    assert device.name == "Renamed Device"
    assert device.opo_id == opo.id
    assert device.organization_id == org_a.id


# ===================================================================
# BUILDINGS — LIST
# ===================================================================

def test_building_related_list_scoped_and_total_scoped(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Allowed Org")
    foreign_org = _organization(db_session, legal_name="Building Foreign Org")

    _building(db_session, name="Allowed Building", organization_id=allowed_org.id)
    _building(db_session, name="Foreign Building", organization_id=foreign_org.id)

    user = _create_user(db_session, username="building-list-user")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="building-viewer-list",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/buildings?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Allowed Building"


def test_building_related_list_excludes_foreign_via_opo(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Allowed Org OPO")
    foreign_org = _organization(db_session, legal_name="Building Foreign Org OPO")
    foreign_b = _organization(db_session, legal_name="Building Foreign B Org OPO")

    opo = _opo(
        db_session,
        name="Allowed OPO for Building",
        owner_id=allowed_org.id,
        operator_id=foreign_org.id,
    )
    _building(
        db_session,
        name="Foreign Building via OPO",
        organization_id=foreign_b.id,
        opo_id=opo.id,
    )

    user = _create_user(db_session, username="building-list-foreign-opo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="building-viewer-foreign-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/buildings?page=1&page_size=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ===================================================================
# BUILDINGS — DETAIL
# ===================================================================

def test_building_detail_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Detail Allowed")
    foreign_org = _organization(db_session, legal_name="Building Detail Foreign")

    building = _building(db_session, name="Foreign Building Detail", organization_id=foreign_org.id)

    user = _create_user(db_session, username="building-detail-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="building-viewer-detail-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/buildings/{building.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===================================================================
# BUILDINGS — DELETE / RESTORE
# ===================================================================

def test_building_delete_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Delete Allowed")
    foreign_org = _organization(db_session, legal_name="Building Delete Foreign")

    building = _building(db_session, name="Foreign Building Delete", organization_id=foreign_org.id)

    user = _create_user(db_session, username="building-delete-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.delete",
        role_code="building-deleter-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/buildings/{building.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_building_restore_foreign_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Restore Allowed")
    foreign_org = _organization(db_session, legal_name="Building Restore Foreign")

    building = _building(
        db_session,
        name="Foreign Building Restore",
        organization_id=foreign_org.id,
    )
    building.deleted_at = datetime.now(UTC)

    user = _create_user(db_session, username="building-restore-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.restore",
        role_code="building-restorer-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        f"/api/buildings/{building.id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===================================================================
# BUILDINGS — CREATE
# ===================================================================

def test_building_create_foreign_organization_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Create Allowed")
    foreign_org = _organization(db_session, legal_name="Building Create Foreign")

    user = _create_user(db_session, username="building-create-foreign-org")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.create",
        role_code="building-creator-foreign-org",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/buildings",
        json={
            "name": "Foreign Org Building",
            "building_type": "other",
            "organization_id": str(foreign_org.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_building_create_foreign_opo_returns_404(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Create Allowed OPO")
    foreign_org = _organization(db_session, legal_name="Building Create Foreign OPO")
    foreign_op = _organization(db_session, legal_name="Building Create Foreign OP")

    opo = _opo(
        db_session,
        name="Foreign OPO for Building Create",
        owner_id=foreign_org.id,
        operator_id=foreign_op.id,
    )

    user = _create_user(db_session, username="building-create-foreign-opo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.create",
        role_code="building-creator-foreign-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/buildings",
        json={
            "name": "Foreign OPO Building",
            "building_type": "other",
            "organization_id": str(allowed_org.id),
            "opo_id": str(opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_building_create_allowed_org_matching_opo(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Create Both Allowed")
    foreign_org = _organization(db_session, legal_name="Building Create Both Foreign")

    opo = _opo(
        db_session,
        name="Matching OPO for Building",
        owner_id=allowed_org.id,
        operator_id=foreign_org.id,
    )

    user = _create_user(db_session, username="building-create-both")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.create",
        role_code="building-creator-both",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/buildings",
        json={
            "name": "Matching OPO Building",
            "building_type": "other",
            "organization_id": str(allowed_org.id),
            "opo_id": str(opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Matching OPO Building"


# ===================================================================
# BUILDINGS — UPDATE (PATCH)
# ===================================================================

def test_building_patch_explicit_null_organization_returns_422(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, legal_name="Building Patch Null Org")
    building = _building(db_session, name="Building Patch Null Org Bld", organization_id=org.id)

    user = _create_user(db_session, username="building-patch-null-org")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="building-editor-null-org",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{building.id}",
        json={"organization_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_building_patch_foreign_organization_returns_404_unchanged(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Patch Allowed Org")
    foreign_org = _organization(db_session, legal_name="Building Patch Foreign Org")

    building = _building(
        db_session,
        name="Building Patch Foreign Org Bld",
        organization_id=allowed_org.id,
    )

    user = _create_user(db_session, username="building-patch-foreign-org")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="building-editor-foreign-org",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{building.id}",
        json={"organization_id": str(foreign_org.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(building)
    assert building.organization_id == allowed_org.id


def test_building_patch_foreign_opo_returns_404_unchanged(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Building Patch Allowed OPO")
    foreign_org = _organization(db_session, legal_name="Building Patch Foreign OPO")
    foreign_op = _organization(db_session, legal_name="Building Patch Foreign OP")

    foreign_opo = _opo(
        db_session,
        name="Foreign OPO for Building Patch",
        owner_id=foreign_org.id,
        operator_id=foreign_op.id,
    )

    building = _building(
        db_session,
        name="Building Patch Foreign OPO Bld",
        organization_id=allowed_org.id,
    )

    user = _create_user(db_session, username="building-patch-foreign-opo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="building-editor-foreign-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{building.id}",
        json={"opo_id": str(foreign_opo.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(building)
    assert building.opo_id is None


def test_building_patch_invalid_relation_combo_returns_404_unchanged(
    db_session: Session,
    client,
) -> None:
    org_a = _organization(db_session, legal_name="Building Patch Combo Org A")
    org_b = _organization(db_session, legal_name="Building Patch Combo Org B")

    opo = _opo(
        db_session,
        name="Combo OPO for Building",
        owner_id=org_b.id,
        operator_id=org_b.id,
    )

    building = _building(
        db_session,
        name="Building Combo Bld",
        organization_id=org_a.id,
    )

    user = _create_user(db_session, username="building-patch-combo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="building-editor-combo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org_a.id), str(org_b.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{building.id}",
        json={
            "organization_id": str(org_a.id),
            "opo_id": str(opo.id),
            "name": "Should Not Change",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(building)
    assert building.name == "Building Combo Bld"
    assert building.organization_id == org_a.id
    assert building.opo_id is None


def test_building_patch_scalar_only_no_reauthorize_unchanged_relation(
    db_session: Session,
    client,
) -> None:
    org_a = _organization(db_session, legal_name="Building Scalar Org A")
    org_b = _organization(db_session, legal_name="Building Scalar Org B")

    opo = _opo(
        db_session,
        name="Scalar OPO for Building",
        owner_id=org_b.id,
        operator_id=org_b.id,
    )

    building = _building(
        db_session,
        name="Building Scalar Bld",
        organization_id=org_a.id,
        opo_id=opo.id,
    )

    user = _create_user(db_session, username="building-patch-scalar")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="building-editor-scalar",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org_a.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{building.id}",
        json={"name": "Renamed Building"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Building"

    db_session.refresh(building)
    assert building.name == "Renamed Building"
    assert building.opo_id == opo.id
    assert building.organization_id == org_a.id
