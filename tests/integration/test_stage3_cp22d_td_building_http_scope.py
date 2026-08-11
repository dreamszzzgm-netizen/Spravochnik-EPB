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


def _device(
    db: Session,
    *,
    name: str,
    organization_id: uuid.UUID | None = None,
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
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
) -> Building:
    bld = Building(
        name=name,
        building_type=BuildingType.OTHER,
        organization_id=organization_id,
        opo_id=opo_id,
    )
    db.add(bld)
    db.flush()
    return bld


# ===========================================================================
# Technical Devices — LIST
# ===========================================================================

def test_td_related_list_scoped_and_total_scoped(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Allowed Org")
    foreign_org = _organization(db_session, legal_name="TD Foreign Org")

    _device(db_session, name="Allowed TD", organization_id=allowed_org.id)
    _device(db_session, name="Foreign TD", organization_id=foreign_org.id)

    user = _create_user(db_session, username="td-list-scoped")
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
        "/api/technical-devices?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Allowed TD"


def test_td_related_list_q_cannot_broaden_scope(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Allowed Q Org")
    foreign_org = _organization(db_session, legal_name="TD Foreign Q Org")

    _device(db_session, name="Foreign Target TD", organization_id=foreign_org.id)

    user = _create_user(db_session, username="td-list-q")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code="td-viewer-q",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/technical-devices?q=Foreign",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ===========================================================================
# Technical Devices — DETAIL
# ===========================================================================

def test_td_detail_allowed(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Detail Allowed Org")
    device = _device(db_session, name="Allowed Detail TD", organization_id=allowed_org.id)

    user = _create_user(db_session, username="td-detail-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code="td-viewer-detail",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/technical-devices/{device.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(device.id)


def test_td_detail_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Detail Allowed2 Org")
    foreign_org = _organization(db_session, legal_name="TD Detail Foreign Org")

    device = _device(db_session, name="Foreign Detail TD", organization_id=foreign_org.id)

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


# ===========================================================================
# Technical Devices — CREATE
# ===========================================================================

def test_td_create_allowed_org(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Create Allowed Org")

    user = _create_user(db_session, username="td-create-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.create",
        role_code="td-creator-allowed",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/technical-devices",
        json={
            "name": "New TD",
            "device_type": "pipeline",
            "organization_id": str(allowed_org.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "New TD"


def test_td_create_foreign_org_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Create Allowed2 Org")
    foreign_org = _organization(db_session, legal_name="TD Create Foreign Org")

    user = _create_user(db_session, username="td-create-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.create",
        role_code="td-creator-foreign",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/technical-devices",
        json={
            "name": "Foreign Org TD",
            "device_type": "pipeline",
            "organization_id": str(foreign_org.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_td_create_allowed_org_foreign_opo_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Create OPO Allowed Org")
    foreign_org = _organization(db_session, legal_name="TD Create OPO Foreign Org")
    foreign_opo = _opo(
        db_session, name="Foreign OPO",
        owner_id=foreign_org.id, operator_id=foreign_org.id,
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
            "name": "TD with Foreign OPO",
            "device_type": "pipeline",
            "organization_id": str(allowed_org.id),
            "opo_id": str(foreign_opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_td_create_allowed_org_accessible_opo_success(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Create OPO OK Org")
    foreign_org = _organization(db_session, legal_name="TD Create OPO OK Foreign")
    accessible_opo = _opo(
        db_session, name="Accessible OPO",
        owner_id=allowed_org.id, operator_id=foreign_org.id,
    )

    user = _create_user(db_session, username="td-create-ok-opo")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.create",
        role_code="td-creator-ok-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/technical-devices",
        json={
            "name": "TD with OK OPO",
            "device_type": "pipeline",
            "organization_id": str(allowed_org.id),
            "opo_id": str(accessible_opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


# ===========================================================================
# Technical Devices — PATCH
# ===========================================================================

def test_td_patch_allowed(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch Allowed Org")
    device = _device(db_session, name="TD To Patch", organization_id=allowed_org.id)

    user = _create_user(db_session, username="td-patch-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-allowed",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"name": "Patched TD"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Patched TD"


def test_td_patch_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch Allowed2 Org")
    foreign_org = _organization(db_session, legal_name="TD Patch Foreign Org")
    device = _device(db_session, name="Foreign Patch TD", organization_id=foreign_org.id)

    user = _create_user(db_session, username="td-patch-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-foreign",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"name": "Hacked TD"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_td_patch_explicit_null_organization_returns_422(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch Null Org")
    device = _device(db_session, name="TD Null Org", organization_id=allowed_org.id)

    user = _create_user(db_session, username="td-patch-null")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-null",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"organization_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_td_patch_foreign_organization_returns_404_unchanged(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch FO Allowed")
    foreign_new_org = _organization(db_session, legal_name="TD Patch FO Foreign")
    device = _device(db_session, name="TD FO Unchanged", organization_id=allowed_org.id)

    user = _create_user(db_session, username="td-patch-fo")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-fo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"organization_id": str(foreign_new_org.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(device)
    assert device.organization_id == allowed_org.id


def test_td_patch_foreign_opo_returns_404_unchanged(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch FOPO Allowed")
    foreign_org = _organization(db_session, legal_name="TD Patch FOPO Foreign")
    foreign_opo = _opo(
        db_session, name="Foreign OPO Patch",
        owner_id=foreign_org.id, operator_id=foreign_org.id,
    )
    device = _device(db_session, name="TD FOPO Unchanged", organization_id=allowed_org.id)

    user = _create_user(db_session, username="td-patch-fopo")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-fopo",
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


def test_td_patch_invalid_org_opo_relation_returns_404_unchanged(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch InvalidRel Allowed")
    foreign_org = _organization(db_session, legal_name="TD Patch InvalidRel Foreign")
    foreign_opo = _opo(
        db_session, name="Invalid Rel OPO",
        owner_id=foreign_org.id, operator_id=foreign_org.id,
    )
    device = _device(db_session, name="TD InvalidRel Unchanged", organization_id=allowed_org.id)

    user = _create_user(db_session, username="td-patch-invrel")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-invrel",
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
    assert device.organization_id == allowed_org.id
    assert device.opo_id is None


def test_td_patch_scalar_only_succeeds(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Patch Scalar Org")
    device = _device(db_session, name="TD Scalar Old", organization_id=allowed_org.id)

    user = _create_user(db_session, username="td-patch-scalar")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code="td-editor-scalar",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/technical-devices/{device.id}",
        json={"name": "TD Scalar New"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "TD Scalar New"


# ===========================================================================
# Technical Devices — DELETE / RESTORE
# ===========================================================================

def test_td_delete_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Delete Allowed Org")
    foreign_org = _organization(db_session, legal_name="TD Delete Foreign Org")
    device = _device(db_session, name="Foreign Delete TD", organization_id=foreign_org.id)

    user = _create_user(db_session, username="td-delete-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.delete",
        role_code="td-deleter-foreign",
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


def test_td_restore_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD Restore Allowed Org")
    foreign_org = _organization(db_session, legal_name="TD Restore Foreign Org")
    device = _device(db_session, name="Foreign Restore TD", organization_id=foreign_org.id)
    device.deleted_at = datetime.now(UTC)

    user = _create_user(db_session, username="td-restore-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.restore",
        role_code="td-restorer-foreign",
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


# ===========================================================================
# Technical Devices — OPO DOES NOT WIDEN
# ===========================================================================

def test_td_accessible_opo_does_not_widen_foreign_device(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="TD OPO Widen Allowed")
    foreign_org = _organization(db_session, legal_name="TD OPO Widen Foreign")
    opo = _opo(
        db_session, name="Widening OPO",
        owner_id=allowed_org.id, operator_id=foreign_org.id,
    )
    device = _device(
        db_session, name="Foreign OPO TD",
        organization_id=foreign_org.id, opo_id=opo.id,
    )

    user = _create_user(db_session, username="td-opo-widen")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code="td-viewer-widen",
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


# ===========================================================================
# Buildings — LIST
# ===========================================================================

def test_building_related_list_scoped_and_total_scoped(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Allowed Org")
    foreign_org = _organization(db_session, legal_name="Bld Foreign Org")

    _building(db_session, name="Allowed Bld", organization_id=allowed_org.id)
    _building(db_session, name="Foreign Bld", organization_id=foreign_org.id)

    user = _create_user(db_session, username="bld-list-scoped")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="bld-viewer-list",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/buildings?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Allowed Bld"


def test_building_related_list_q_cannot_broaden_scope(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Q Allowed")
    foreign_org = _organization(db_session, legal_name="Bld Q Foreign")

    _building(db_session, name="Foreign Target Bld", organization_id=foreign_org.id)

    user = _create_user(db_session, username="bld-list-q")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="bld-viewer-q",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/buildings?q=Foreign",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ===========================================================================
# Buildings — DETAIL
# ===========================================================================

def test_building_detail_allowed(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Detail Allowed")
    bld = _building(db_session, name="Allowed Detail Bld", organization_id=allowed_org.id)

    user = _create_user(db_session, username="bld-detail-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="bld-viewer-detail",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/buildings/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(bld.id)


def test_building_detail_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Detail Allowed2")
    foreign_org = _organization(db_session, legal_name="Bld Detail Foreign")

    bld = _building(db_session, name="Foreign Detail Bld", organization_id=foreign_org.id)

    user = _create_user(db_session, username="bld-detail-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="bld-viewer-detail-f",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/buildings/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Buildings — CREATE
# ===========================================================================

def test_building_create_allowed_org(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Create Allowed")

    user = _create_user(db_session, username="bld-create-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.create",
        role_code="bld-creator-allowed",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/buildings",
        json={
            "name": "New Bld",
            "building_type": "industrial",
            "organization_id": str(allowed_org.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "New Bld"


def test_building_create_foreign_org_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Create Allowed2")
    foreign_org = _organization(db_session, legal_name="Bld Create Foreign")

    user = _create_user(db_session, username="bld-create-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.create",
        role_code="bld-creator-foreign",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/buildings",
        json={
            "name": "Foreign Org Bld",
            "building_type": "industrial",
            "organization_id": str(foreign_org.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_building_create_allowed_org_foreign_opo_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Create OPO Allowed")
    foreign_org = _organization(db_session, legal_name="Bld Create OPO Foreign")
    foreign_opo = _opo(
        db_session, name="Bld Foreign OPO",
        owner_id=foreign_org.id, operator_id=foreign_org.id,
    )

    user = _create_user(db_session, username="bld-create-foreign-opo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.create",
        role_code="bld-creator-foreign-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/buildings",
        json={
            "name": "Bld with Foreign OPO",
            "building_type": "industrial",
            "organization_id": str(allowed_org.id),
            "opo_id": str(foreign_opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_building_create_allowed_org_accessible_opo_success(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Create OPO OK")
    foreign_org = _organization(db_session, legal_name="Bld Create OPO OK Foreign")
    accessible_opo = _opo(
        db_session, name="Bld Accessible OPO",
        owner_id=allowed_org.id, operator_id=foreign_org.id,
    )

    user = _create_user(db_session, username="bld-create-ok-opo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.create",
        role_code="bld-creator-ok-opo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        "/api/buildings",
        json={
            "name": "Bld with OK OPO",
            "building_type": "industrial",
            "organization_id": str(allowed_org.id),
            "opo_id": str(accessible_opo.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


# ===========================================================================
# Buildings — PATCH
# ===========================================================================

def test_building_patch_allowed(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Patch Allowed")
    bld = _building(db_session, name="Bld To Patch", organization_id=allowed_org.id)

    user = _create_user(db_session, username="bld-patch-allowed")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="bld-editor-allowed",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{bld.id}",
        json={"name": "Patched Bld"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Patched Bld"


def test_building_patch_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Patch Allowed2")
    foreign_org = _organization(db_session, legal_name="Bld Patch Foreign")
    bld = _building(db_session, name="Foreign Patch Bld", organization_id=foreign_org.id)

    user = _create_user(db_session, username="bld-patch-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="bld-editor-foreign",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{bld.id}",
        json={"name": "Hacked Bld"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_building_patch_explicit_null_organization_returns_422(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Patch Null")
    bld = _building(db_session, name="Bld Null Org", organization_id=allowed_org.id)

    user = _create_user(db_session, username="bld-patch-null")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="bld-editor-null",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{bld.id}",
        json={"organization_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_building_patch_foreign_organization_returns_404_unchanged(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Patch FO Allowed")
    foreign_new_org = _organization(db_session, legal_name="Bld Patch FO Foreign")
    bld = _building(db_session, name="Bld FO Unchanged", organization_id=allowed_org.id)

    user = _create_user(db_session, username="bld-patch-fo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="bld-editor-fo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{bld.id}",
        json={"organization_id": str(foreign_new_org.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(bld)
    assert bld.organization_id == allowed_org.id


def test_building_patch_foreign_opo_returns_404_unchanged(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Patch FOPO Allowed")
    foreign_org = _organization(db_session, legal_name="Bld Patch FOPO Foreign")
    foreign_opo = _opo(
        db_session, name="Bld Foreign OPO Patch",
        owner_id=foreign_org.id, operator_id=foreign_org.id,
    )
    bld = _building(db_session, name="Bld FOPO Unchanged", organization_id=allowed_org.id)

    user = _create_user(db_session, username="bld-patch-fopo")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="bld-editor-fopo",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{bld.id}",
        json={"opo_id": str(foreign_opo.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(bld)
    assert bld.opo_id is None


def test_building_patch_invalid_org_opo_relation_returns_404_unchanged(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Patch InvRel Allowed")
    foreign_org = _organization(db_session, legal_name="Bld Patch InvRel Foreign")
    foreign_opo = _opo(
        db_session, name="Bld Invalid Rel OPO",
        owner_id=foreign_org.id, operator_id=foreign_org.id,
    )
    bld = _building(db_session, name="Bld InvRel Unchanged", organization_id=allowed_org.id)

    user = _create_user(db_session, username="bld-patch-invrel")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="bld-editor-invrel",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{bld.id}",
        json={"opo_id": str(foreign_opo.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    db_session.refresh(bld)
    assert bld.organization_id == allowed_org.id
    assert bld.opo_id is None


def test_building_patch_scalar_only_succeeds(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Patch Scalar")
    bld = _building(db_session, name="Bld Scalar Old", organization_id=allowed_org.id)

    user = _create_user(db_session, username="bld-patch-scalar")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code="bld-editor-scalar",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.patch(
        f"/api/buildings/{bld.id}",
        json={"name": "Bld Scalar New"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Bld Scalar New"


# ===========================================================================
# Buildings — DELETE / RESTORE
# ===========================================================================

def test_building_delete_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Delete Allowed")
    foreign_org = _organization(db_session, legal_name="Bld Delete Foreign")
    bld = _building(db_session, name="Foreign Delete Bld", organization_id=foreign_org.id)

    user = _create_user(db_session, username="bld-delete-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.delete",
        role_code="bld-deleter-foreign",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/buildings/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_building_restore_foreign_returns_404(db_session: Session, client) -> None:
    allowed_org = _organization(db_session, legal_name="Bld Restore Allowed")
    foreign_org = _organization(db_session, legal_name="Bld Restore Foreign")
    bld = _building(db_session, name="Foreign Restore Bld", organization_id=foreign_org.id)
    bld.deleted_at = datetime.now(UTC)

    user = _create_user(db_session, username="bld-restore-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.restore",
        role_code="bld-restorer-foreign",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.post(
        f"/api/buildings/{bld.id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Buildings — OPO DOES NOT WIDEN
# ===========================================================================

def test_building_accessible_opo_does_not_widen_foreign_building(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(db_session, legal_name="Bld OPO Widen Allowed")
    foreign_org = _organization(db_session, legal_name="Bld OPO Widen Foreign")
    opo = _opo(
        db_session, name="Bld Widening OPO",
        owner_id=allowed_org.id, operator_id=foreign_org.id,
    )
    bld = _building(
        db_session, name="Foreign OPO Bld",
        organization_id=foreign_org.id, opo_id=opo.id,
    )

    user = _create_user(db_session, username="bld-opo-widen")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code="bld-viewer-widen",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(allowed_org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/buildings/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
