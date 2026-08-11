import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.custom_fields.models import (
    CustomFieldDefinition,
    CustomFieldType,
    CustomFieldValue,
)
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
    perm = db.scalar(
        text("SELECT * FROM permissions WHERE code = :code"),
        {"code": code},
    )
    assert perm is not None, f"seeded permission {code!r} must exist"
    return perm


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


def _cf_definition(
    db: Session,
    *,
    code: str,
    entity_type: str,
    field_type: str = "text",
) -> CustomFieldDefinition:
    defn = CustomFieldDefinition(
        code=code,
        name=f"Field {code}",
        entity_type=entity_type,
        field_type=CustomFieldType(field_type),
    )
    db.add(defn)
    db.flush()
    return defn


def _cf_value(
    db: Session,
    *,
    field_definition_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    value_text: str = "test-val",
) -> CustomFieldValue:
    fv = CustomFieldValue(
        field_definition_id=field_definition_id,
        entity_type=entity_type,
        entity_id=entity_id,
        value_text=value_text,
    )
    db.add(fv)
    db.flush()
    return fv


def _count_cf_values(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
) -> int:
    return db.scalar(
        text(
            "SELECT count(*) FROM custom_field_values"
            " WHERE entity_type = :et AND entity_id = :eid"
        ),
        {"et": entity_type, "eid": entity_id},
    )


def _count_cf_values_by_field(
    db: Session,
    *,
    field_definition_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> int:
    return db.scalar(
        text(
            "SELECT count(*) FROM custom_field_values"
            " WHERE field_definition_id = :fid"
            " AND entity_id = :eid"
        ),
        {"fid": field_definition_id, "eid": entity_id},
    )


# ===========================================================================
# 401 / 403
# ===========================================================================

def test_get_values_no_auth_returns_401(
    db_session: Session, client,
) -> None:
    resp = client.get(
        f"/api/custom-fields/values/opo/{uuid.uuid4()}"
    )
    assert resp.status_code == 401


def test_get_values_no_permission_returns_403(
    db_session: Session, client,
) -> None:
    user = _create_user(db_session, username="cf-no-perm")
    db_session.commit()
    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_put_value_no_permission_returns_403(
    db_session: Session, client,
) -> None:
    user = _create_user(db_session, username="cf-put-no-perm")
    db_session.commit()
    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/opo/{uuid.uuid4()}"
        f"/{uuid.uuid4()}",
        json={"value": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ===========================================================================
# Unknown entity_type -> 422
# ===========================================================================

def test_get_values_unknown_entity_type_returns_422(
    db_session: Session, client,
) -> None:
    user = _create_user(db_session, username="cf-unknown-get")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-unknown-get",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()
    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/unknown/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_put_value_unknown_entity_type_returns_422(
    db_session: Session, client,
) -> None:
    user = _create_user(db_session, username="cf-unknown-put")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-unknown-put",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()
    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/unknown"
        f"/{uuid.uuid4()}/{uuid.uuid4()}",
        json={"value": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_delete_value_unknown_entity_type_returns_422(
    db_session: Session, client,
) -> None:
    user = _create_user(db_session, username="cf-unknown-del")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-unknown-del",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()
    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/custom-fields/values/unknown"
        f"/{uuid.uuid4()}/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ===========================================================================
# Definitions regression: non-ALL scope still returns 200
# ===========================================================================

def test_definitions_non_all_scope_returns_200(
    db_session: Session, client,
) -> None:
    org = _organization(db_session, legal_name="CF Def Org")
    _cf_definition(db_session, code="def_test", entity_type="opo")

    user = _create_user(db_session, username="cf-def-scoped")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-def",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org.id)]},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        "/api/custom-fields/definitions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ===========================================================================
# OPO — GET values
# ===========================================================================

def test_opo_get_values_allowed_owner_org(
    db_session: Session, client,
) -> None:
    owner_org = _organization(
        db_session, legal_name="CF OPO Owner Org",
    )
    operator_org = _organization(
        db_session, legal_name="CF OPO Operator Org",
    )
    opo = _opo(
        db_session, name="Allowed OPO",
        owner_id=owner_org.id, operator_id=operator_org.id,
    )

    defn = _cf_definition(
        db_session, code="opo_field", entity_type="opo",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="opo",
        entity_id=opo.id,
        value_text="hello",
    )

    user = _create_user(db_session, username="cf-opo-owner")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-owner",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(owner_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_opo_get_values_allowed_operator_org(
    db_session: Session, client,
) -> None:
    owner_org = _organization(
        db_session, legal_name="CF OPO Owner2 Org",
    )
    operator_org = _organization(
        db_session, legal_name="CF OPO Operator2 Org",
    )
    opo = _opo(
        db_session, name="Allowed OPO 2",
        owner_id=owner_org.id, operator_id=operator_org.id,
    )

    defn = _cf_definition(
        db_session, code="opo_field2", entity_type="opo",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="opo",
        entity_id=opo.id,
        value_text="world",
    )

    user = _create_user(db_session, username="cf-opo-operator")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-op",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(operator_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_opo_get_values_foreign_returns_404(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF OPO Allow3 Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF OPO Foreign Org",
    )
    opo = _opo(
        db_session, name="Foreign OPO",
        owner_id=foreign_org.id,
        operator_id=foreign_org.id,
    )

    user = _create_user(db_session, username="cf-opo-foreign")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-foreign",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_opo_get_values_all_scope_success(
    db_session: Session, client,
) -> None:
    foreign_org = _organization(
        db_session, legal_name="CF OPO AllScope Org",
    )
    opo = _opo(
        db_session, name="AllScope OPO",
        owner_id=foreign_org.id,
        operator_id=foreign_org.id,
    )

    user = _create_user(db_session, username="cf-opo-all")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-all",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_opo_get_values_empty_related_returns_404(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF OPO EmptyRel Org",
    )
    opo = _opo(
        db_session, name="EmptyRel OPO",
        owner_id=org.id, operator_id=org.id,
    )

    user = _create_user(
        db_session, username="cf-opo-emptyrel",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-emptyrel",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": []},
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# OPO — PUT value (foreign -> 404, value NOT inserted)
# ===========================================================================

def test_opo_put_value_foreign_returns_404_no_value_created(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF OPO Put Allow Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF OPO Put Foreign Org",
    )
    opo = _opo(
        db_session, name="Foreign Put OPO",
        owner_id=foreign_org.id,
        operator_id=foreign_org.id,
    )

    defn = _cf_definition(
        db_session, code="opo_put_field", entity_type="opo",
    )

    user = _create_user(
        db_session, username="cf-opo-put-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-put-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
        json={"value": "should-not-exist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    count = _count_cf_values(
        db_session, entity_type="opo", entity_id=opo.id,
    )
    assert count == 0


def test_opo_put_value_allowed_success(
    db_session: Session, client,
) -> None:
    owner_org = _organization(
        db_session, legal_name="CF OPO PutOK Org",
    )
    opo = _opo(
        db_session, name="PutOK OPO",
        owner_id=owner_org.id, operator_id=owner_org.id,
    )

    defn = _cf_definition(
        db_session, code="opo_put_ok", entity_type="opo",
    )

    user = _create_user(
        db_session, username="cf-opo-put-ok",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-put-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(owner_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
        json={"value": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["value_text"] == "yes"


# ===========================================================================
# OPO — DELETE value (foreign -> 404, value remains)
# ===========================================================================

def test_opo_delete_value_foreign_returns_404_value_remains(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF OPO Del Allow Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF OPO Del Foreign Org",
    )
    opo = _opo(
        db_session, name="Foreign Del OPO",
        owner_id=foreign_org.id,
        operator_id=foreign_org.id,
    )

    defn = _cf_definition(
        db_session, code="opo_del_field", entity_type="opo",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="opo",
        entity_id=opo.id,
        value_text="keep-me",
    )

    user = _create_user(
        db_session, username="cf-opo-del-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-del-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    count = _count_cf_values_by_field(
        db_session,
        field_definition_id=defn.id,
        entity_id=opo.id,
    )
    assert count == 1


def test_opo_delete_value_allowed_success(
    db_session: Session, client,
) -> None:
    owner_org = _organization(
        db_session, legal_name="CF OPO DelOK Org",
    )
    opo = _opo(
        db_session, name="DelOK OPO",
        owner_id=owner_org.id, operator_id=owner_org.id,
    )

    defn = _cf_definition(
        db_session, code="opo_del_ok", entity_type="opo",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="opo",
        entity_id=opo.id,
        value_text="delete-me",
    )

    user = _create_user(
        db_session, username="cf-opo-del-ok",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-del-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(owner_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    count = _count_cf_values_by_field(
        db_session,
        field_definition_id=defn.id,
        entity_id=opo.id,
    )
    assert count == 0


# ===========================================================================
# Deleted OPO parent -> 404
# ===========================================================================

def test_opo_get_values_deleted_parent_returns_404(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF OPO Del Org",
    )
    opo = _opo(
        db_session, name="Deleted OPO",
        owner_id=org.id, operator_id=org.id,
    )
    opo.deleted_at = datetime.now(UTC)

    user = _create_user(
        db_session, username="cf-opo-del-parent",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-del-p",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_opo_put_value_deleted_parent_returns_404(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF OPO PutDel Org",
    )
    opo = _opo(
        db_session, name="PutDel OPO",
        owner_id=org.id, operator_id=org.id,
    )
    opo.deleted_at = datetime.now(UTC)

    defn = _cf_definition(
        db_session, code="opo_putfld_del", entity_type="opo",
    )

    user = _create_user(
        db_session, username="cf-opo-put-del-parent",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-opo-putdel",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
        json={"value": "no"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    count = _count_cf_values(
        db_session, entity_type="opo", entity_id=opo.id,
    )
    assert count == 0


# ===========================================================================
# Technical Device — GET values
# ===========================================================================

def test_td_get_values_allowed_org(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF TD Allow Org",
    )
    device = _device(
        db_session, name="Allowed TD",
        organization_id=org.id,
    )

    defn = _cf_definition(
        db_session,
        code="td_field",
        entity_type="technical_device",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="technical_device",
        entity_id=device.id,
        value_text="td-val",
    )

    user = _create_user(
        db_session, username="cf-td-allowed",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_td_get_values_foreign_returns_404(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF TD Allow2 Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF TD Foreign Org",
    )
    device = _device(
        db_session, name="Foreign TD",
        organization_id=foreign_org.id,
    )

    user = _create_user(
        db_session, username="cf-td-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Technical Device — PUT value
# ===========================================================================

def test_td_put_value_foreign_returns_404_no_value_created(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF TD Put Allow Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF TD Put Foreign Org",
    )
    device = _device(
        db_session, name="Foreign Put TD",
        organization_id=foreign_org.id,
    )

    defn = _cf_definition(
        db_session,
        code="td_put_field",
        entity_type="technical_device",
    )

    user = _create_user(
        db_session, username="cf-td-put-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-put-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}/{defn.id}",
        json={"value": "should-not-exist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    count = _count_cf_values(
        db_session,
        entity_type="technical_device",
        entity_id=device.id,
    )
    assert count == 0


def test_td_put_value_allowed_success(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF TD PutOK Org",
    )
    device = _device(
        db_session, name="PutOK TD",
        organization_id=org.id,
    )

    defn = _cf_definition(
        db_session,
        code="td_put_ok",
        entity_type="technical_device",
    )

    user = _create_user(
        db_session, username="cf-td-put-ok",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-put-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}/{defn.id}",
        json={"value": "td-ok"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["value_text"] == "td-ok"


# ===========================================================================
# Technical Device — DELETE value
# ===========================================================================

def test_td_delete_value_foreign_returns_404_value_remains(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF TD Del Allow Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF TD Del Foreign Org",
    )
    device = _device(
        db_session, name="Foreign Del TD",
        organization_id=foreign_org.id,
    )

    defn = _cf_definition(
        db_session,
        code="td_del_field",
        entity_type="technical_device",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="technical_device",
        entity_id=device.id,
        value_text="keep-td",
    )

    user = _create_user(
        db_session, username="cf-td-del-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-del-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}/{defn.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    count = _count_cf_values_by_field(
        db_session,
        field_definition_id=defn.id,
        entity_id=device.id,
    )
    assert count == 1


def test_td_delete_value_allowed_success(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF TD DelOK Org",
    )
    device = _device(
        db_session, name="DelOK TD",
        organization_id=org.id,
    )

    defn = _cf_definition(
        db_session,
        code="td_del_ok",
        entity_type="technical_device",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="technical_device",
        entity_id=device.id,
        value_text="delete-td",
    )

    user = _create_user(
        db_session, username="cf-td-del-ok",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-del-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}/{defn.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    count = _count_cf_values_by_field(
        db_session,
        field_definition_id=defn.id,
        entity_id=device.id,
    )
    assert count == 0


# ===========================================================================
# TD — OPO does NOT widen scope
# ===========================================================================

def test_td_foreign_device_accessible_opo_still_404(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF TD OPO Widen Allow",
    )
    foreign_org = _organization(
        db_session, legal_name="CF TD OPO Widen Foreign",
    )
    opo = _opo(
        db_session, name="TD Widen OPO",
        owner_id=allowed_org.id,
        operator_id=foreign_org.id,
    )
    device = _device(
        db_session, name="Foreign OPO TD",
        organization_id=foreign_org.id,
        opo_id=opo.id,
    )

    defn = _cf_definition(
        db_session,
        code="td_opo_widen",
        entity_type="technical_device",
    )

    user = _create_user(
        db_session, username="cf-td-opo-widen",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-opo-w",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    resp_put = client.put(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}/{defn.id}",
        json={"value": "nope"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_put.status_code == 404


# ===========================================================================
# Deleted Technical Device -> 404
# ===========================================================================

def test_td_get_values_deleted_parent_returns_404(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF TD Del Org",
    )
    device = _device(
        db_session, name="Deleted TD",
        organization_id=org.id,
    )
    device.deleted_at = datetime.now(UTC)

    user = _create_user(
        db_session, username="cf-td-del-parent",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-td-del-p",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/technical_device"
        f"/{device.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Building — GET values
# ===========================================================================

def test_building_get_values_allowed_org(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF Bld Allow Org",
    )
    bld = _building(
        db_session, name="Allowed Bld",
        organization_id=org.id,
    )

    defn = _cf_definition(
        db_session,
        code="bld_field",
        entity_type="building",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="building",
        entity_id=bld.id,
        value_text="bld-val",
    )

    user = _create_user(
        db_session, username="cf-bld-allowed",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/building/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_building_get_values_foreign_returns_404(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF Bld Allow2 Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF Bld Foreign Org",
    )
    bld = _building(
        db_session, name="Foreign Bld",
        organization_id=foreign_org.id,
    )

    user = _create_user(
        db_session, username="cf-bld-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/building/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Building — PUT value
# ===========================================================================

def test_building_put_value_foreign_no_value_created(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF Bld Put Allow Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF Bld Put Foreign Org",
    )
    bld = _building(
        db_session, name="Foreign Put Bld",
        organization_id=foreign_org.id,
    )

    defn = _cf_definition(
        db_session,
        code="bld_put_field",
        entity_type="building",
    )

    user = _create_user(
        db_session, username="cf-bld-put-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-put-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/building"
        f"/{bld.id}/{defn.id}",
        json={"value": "should-not-exist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    count = _count_cf_values(
        db_session,
        entity_type="building",
        entity_id=bld.id,
    )
    assert count == 0


def test_building_put_value_allowed_success(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF Bld PutOK Org",
    )
    bld = _building(
        db_session, name="PutOK Bld",
        organization_id=org.id,
    )

    defn = _cf_definition(
        db_session,
        code="bld_put_ok",
        entity_type="building",
    )

    user = _create_user(
        db_session, username="cf-bld-put-ok",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-put-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/building"
        f"/{bld.id}/{defn.id}",
        json={"value": "bld-ok"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["value_text"] == "bld-ok"


# ===========================================================================
# Building — DELETE value
# ===========================================================================

def test_building_delete_value_foreign_404_value_remains(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF Bld Del Allow Org",
    )
    foreign_org = _organization(
        db_session, legal_name="CF Bld Del Foreign Org",
    )
    bld = _building(
        db_session, name="Foreign Del Bld",
        organization_id=foreign_org.id,
    )

    defn = _cf_definition(
        db_session,
        code="bld_del_field",
        entity_type="building",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="building",
        entity_id=bld.id,
        value_text="keep-bld",
    )

    user = _create_user(
        db_session, username="cf-bld-del-foreign",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-del-f",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/custom-fields/values/building"
        f"/{bld.id}/{defn.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    count = _count_cf_values_by_field(
        db_session,
        field_definition_id=defn.id,
        entity_id=bld.id,
    )
    assert count == 1


def test_building_delete_value_allowed_success(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF Bld DelOK Org",
    )
    bld = _building(
        db_session, name="DelOK Bld",
        organization_id=org.id,
    )

    defn = _cf_definition(
        db_session,
        code="bld_del_ok",
        entity_type="building",
    )
    _cf_value(
        db_session,
        field_definition_id=defn.id,
        entity_type="building",
        entity_id=bld.id,
        value_text="delete-bld",
    )

    user = _create_user(
        db_session, username="cf-bld-del-ok",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-del-ok",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.delete(
        f"/api/custom-fields/values/building"
        f"/{bld.id}/{defn.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    count = _count_cf_values_by_field(
        db_session,
        field_definition_id=defn.id,
        entity_id=bld.id,
    )
    assert count == 0


# ===========================================================================
# Building — OPO does NOT widen scope
# ===========================================================================

def test_building_foreign_bld_opo_still_404(
    db_session: Session, client,
) -> None:
    allowed_org = _organization(
        db_session, legal_name="CF Bld OPO Widen Allow",
    )
    foreign_org = _organization(
        db_session, legal_name="CF Bld OPO Widen Foreign",
    )
    opo = _opo(
        db_session, name="Bld Widen OPO",
        owner_id=allowed_org.id,
        operator_id=foreign_org.id,
    )
    bld = _building(
        db_session, name="Foreign OPO Bld",
        organization_id=foreign_org.id,
        opo_id=opo.id,
    )

    defn = _cf_definition(
        db_session,
        code="bld_opo_widen",
        entity_type="building",
    )

    user = _create_user(
        db_session, username="cf-bld-opo-widen",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-opo-w",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(allowed_org.id)],
        },
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/building/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

    resp_put = client.put(
        f"/api/custom-fields/values/building"
        f"/{bld.id}/{defn.id}",
        json={"value": "nope"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_put.status_code == 404


# ===========================================================================
# Deleted Building -> 404
# ===========================================================================

def test_building_get_values_deleted_parent_returns_404(
    db_session: Session, client,
) -> None:
    org = _organization(
        db_session, legal_name="CF Bld Del Org",
    )
    bld = _building(
        db_session, name="Deleted Bld",
        organization_id=org.id,
    )
    bld.deleted_at = datetime.now(UTC)

    user = _create_user(
        db_session, username="cf-bld-del-parent",
    )
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code="cf-mgr-bld-del-p",
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/building/{bld.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Superuser — always succeeds
# ===========================================================================

def test_superuser_get_values_foreign_opo_success(
    db_session: Session, client,
) -> None:
    foreign_org = _organization(
        db_session, legal_name="CF Super Foreign Org",
    )
    opo = _opo(
        db_session, name="Super Foreign OPO",
        owner_id=foreign_org.id,
        operator_id=foreign_org.id,
    )

    user = _create_user(
        db_session, username="cf-superuser",
        is_superuser=True,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.get(
        f"/api/custom-fields/values/opo/{opo.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_superuser_put_value_foreign_opo_success(
    db_session: Session, client,
) -> None:
    foreign_org = _organization(
        db_session, legal_name="CF Super Put Foreign Org",
    )
    opo = _opo(
        db_session, name="Super Put OPO",
        owner_id=foreign_org.id,
        operator_id=foreign_org.id,
    )

    defn = _cf_definition(
        db_session,
        code="super_put_opo",
        entity_type="opo",
    )

    user = _create_user(
        db_session, username="cf-super-put",
        is_superuser=True,
    )
    db_session.commit()

    token = _make_session_token(db_session, user)
    resp = client.put(
        f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
        json={"value": "super-val"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["value_text"] == "super-val"
