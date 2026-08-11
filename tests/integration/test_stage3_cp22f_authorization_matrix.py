import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.custom_fields.models import CustomFieldDefinition, CustomFieldType
from app.modules.identity.models import (
    Employee,
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


REFERENCE_CASES = [
    ("/api/reference/hazard-signs", "opo.view", "opo.create"),
    ("/api/reference/activity-types", "opo.view", "opo.create"),
    (
        "/api/reference/technical-device-types",
        "technical_devices.view",
        "technical_devices.create",
    ),
    ("/api/reference/building-types", "buildings.view", "buildings.create"),
]

MALFORMED_RELATED_CONFIGS = [
    {"organization_ids": ["not-a-uuid"]},
    {"organization_ids": [str(uuid.uuid4())], "extra": True},
    {"organization_ids": "not-a-list"},
    {"org_ids": [str(uuid.uuid4())]},
]

PROTECTED_ENDPOINTS = [
    "/api/organizations",
    "/api/opo",
    "/api/technical-devices",
    "/api/buildings",
    "/api/custom-fields/definitions",
    f"/api/custom-fields/values/opo/{uuid.uuid4()}",
    "/api/reference/hazard-signs",
    "/api/reference/technical-device-types",
    "/api/reference/building-types",
]


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
    assert perm_id is not None, f"seeded permission {permission_code!r} must exist"
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


def _role(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _token(db: Session, user: User) -> str:
    from app.core.config import get_settings
    from app.modules.identity.service import AuthService

    return AuthService(get_settings()).login(
        db,
        username=user.username,
        password="test-password-123!",
        ip_address="127.0.0.1",
        user_agent="cp22f-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _related(*organization_ids: uuid.UUID) -> dict[str, list[str]]:
    return {"organization_ids": [str(value) for value in organization_ids]}


def _organization(db: Session, name: str) -> Organization:
    org = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name=name,
        short_name=name,
    )
    db.add(org)
    db.flush()
    return org


def _opo(
    db: Session,
    *,
    owner: Organization,
    operator: Organization,
    name: str,
) -> OPO:
    opo = OPO(
        name=name,
        registration_number=f"REG-{uuid.uuid4()}",
        hazard_class=HazardClass.HAZARD_CLASS_3,
        address=f"{name} address",
        registration_date=date(2026, 1, 1),
        owner_organization_id=owner.id,
        operating_organization_id=operator.id,
    )
    db.add(opo)
    db.flush()
    return opo


def _device(
    db: Session,
    *,
    organization: Organization,
    name: str,
    opo: OPO | None = None,
) -> TechnicalDevice:
    device = TechnicalDevice(
        name=name,
        device_type=TechnicalDeviceType.OTHER,
        organization_id=organization.id,
        opo_id=opo.id if opo else None,
    )
    db.add(device)
    db.flush()
    return device


def _building(
    db: Session,
    *,
    organization: Organization,
    name: str,
    opo: OPO | None = None,
) -> Building:
    building = Building(
        name=name,
        building_type=BuildingType.OTHER,
        organization_id=organization.id,
        opo_id=opo.id if opo else None,
    )
    db.add(building)
    db.flush()
    return building


def _cf_definition(db: Session, *, code: str) -> CustomFieldDefinition:
    definition = CustomFieldDefinition(
        code=code,
        name=f"Field {code}",
        entity_type="opo",
        field_type=CustomFieldType.TEXT,
    )
    db.add(definition)
    db.flush()
    return definition


def _cf_value_count(
    db: Session,
    *,
    definition_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> int:
    return int(
        db.scalar(
            text(
                "SELECT count(*) FROM custom_field_values "
                "WHERE field_definition_id = :definition_id "
                "AND entity_id = :entity_id"
            ),
            {"definition_id": definition_id, "entity_id": entity_id},
        )
        or 0
    )


def _commit_and_token(db: Session, user: User) -> str:
    db.commit()
    return _token(db, user)


def _item_ids(response) -> set[str]:
    return {item["id"] for item in response.json()["items"]}


@pytest.mark.parametrize("path,matching_permission,wrong_permission", REFERENCE_CASES)
def test_reference_unauthenticated_returns_401(
    client,
    path: str,
    matching_permission: str,
    wrong_permission: str,
) -> None:
    del matching_permission, wrong_permission
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path,matching_permission,wrong_permission", REFERENCE_CASES)
def test_reference_wrong_permission_returns_403(
    db_session: Session,
    client,
    path: str,
    matching_permission: str,
    wrong_permission: str,
) -> None:
    del matching_permission
    user = _create_user(db_session, username=f"ref-wrong-{uuid.uuid4().hex[:8]}")
    _grant(
        db_session,
        user=user,
        permission_code=wrong_permission,
        role_code=_role("ref-wrong"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)
    assert client.get(path, headers=_auth(token)).status_code == 403


@pytest.mark.parametrize("path,matching_permission,wrong_permission", REFERENCE_CASES)
@pytest.mark.parametrize(
    ("scope_type", "scope_config"),
    [
        (ScopeType.ALL, None),
        (ScopeType.RELATED, {"organization_ids": []}),
        (ScopeType.ASSIGNED, None),
        (ScopeType.OWN, None),
    ],
)
def test_reference_matching_permission_is_global_across_scope_types(
    db_session: Session,
    client,
    path: str,
    matching_permission: str,
    wrong_permission: str,
    scope_type: ScopeType,
    scope_config: dict | None,
) -> None:
    del wrong_permission
    user = _create_user(db_session, username=f"ref-ok-{uuid.uuid4().hex[:8]}")
    _grant(
        db_session,
        user=user,
        permission_code=matching_permission,
        role_code=_role("ref-ok"),
        scope_type=scope_type,
        scope_config=scope_config,
    )
    token = _commit_and_token(db_session, user)
    assert client.get(path, headers=_auth(token)).status_code == 200


@pytest.mark.parametrize("path,matching_permission,wrong_permission", REFERENCE_CASES)
def test_reference_superuser_returns_200(
    db_session: Session,
    client,
    path: str,
    matching_permission: str,
    wrong_permission: str,
) -> None:
    del matching_permission, wrong_permission
    user = _create_user(
        db_session,
        username=f"ref-super-{uuid.uuid4().hex[:8]}",
        is_superuser=True,
    )
    token = _commit_and_token(db_session, user)
    assert client.get(path, headers=_auth(token)).status_code == 200


def test_scope_isolation_view_organizations_does_not_borrow_update_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Org View")
    foreign = _organization(db_session, "Foreign Org View")
    user = _create_user(db_session, username="scope-view-org")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code=_role("org-view-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="organizations.update",
        role_code=_role("org-update-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.get("/api/organizations", headers=_auth(token))
    assert response.status_code == 200
    assert str(allowed.id) in _item_ids(response)
    assert str(foreign.id) not in _item_ids(response)
    assert (
        client.get(
            f"/api/organizations/{foreign.id}", headers=_auth(token)
        ).status_code
        == 404
    )


def test_scope_isolation_view_opo_does_not_borrow_edit_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed OPO Org")
    foreign = _organization(db_session, "Foreign OPO Org")
    allowed_opo = _opo(
        db_session,
        owner=allowed,
        operator=allowed,
        name="Allowed OPO",
    )
    foreign_opo = _opo(
        db_session,
        owner=foreign,
        operator=foreign,
        name="Foreign OPO",
    )
    user = _create_user(db_session, username="scope-view-opo")
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code=_role("opo-view-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="opo.edit",
        role_code=_role("opo-edit-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.get("/api/opo", headers=_auth(token))
    assert response.status_code == 200
    assert str(allowed_opo.id) in _item_ids(response)
    assert str(foreign_opo.id) not in _item_ids(response)
    assert (
        client.get(f"/api/opo/{foreign_opo.id}", headers=_auth(token)).status_code
        == 404
    )


def test_scope_isolation_view_device_does_not_borrow_edit_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Device Org")
    foreign = _organization(db_session, "Foreign Device Org")
    allowed_device = _device(
        db_session, organization=allowed, name="Allowed Device"
    )
    foreign_device = _device(
        db_session, organization=foreign, name="Foreign Device"
    )
    user = _create_user(db_session, username="scope-view-device")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code=_role("device-view-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code=_role("device-edit-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.get("/api/technical-devices", headers=_auth(token))
    assert response.status_code == 200
    assert str(allowed_device.id) in _item_ids(response)
    assert str(foreign_device.id) not in _item_ids(response)
    assert (
        client.get(
            f"/api/technical-devices/{foreign_device.id}",
            headers=_auth(token),
        ).status_code
        == 404
    )


def test_scope_isolation_view_building_does_not_borrow_edit_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Building Org")
    foreign = _organization(db_session, "Foreign Building Org")
    allowed_building = _building(
        db_session, organization=allowed, name="Allowed Building"
    )
    foreign_building = _building(
        db_session, organization=foreign, name="Foreign Building"
    )
    user = _create_user(db_session, username="scope-view-building")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code=_role("building-view-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code=_role("building-edit-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.get("/api/buildings", headers=_auth(token))
    assert response.status_code == 200
    assert str(allowed_building.id) in _item_ids(response)
    assert str(foreign_building.id) not in _item_ids(response)
    assert (
        client.get(
            f"/api/buildings/{foreign_building.id}", headers=_auth(token)
        ).status_code
        == 404
    )


def test_scope_isolation_edit_organization_does_not_borrow_view_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Edit Org")
    foreign = _organization(db_session, "Foreign Edit Org")
    original_name = foreign.legal_name
    user = _create_user(db_session, username="scope-edit-org")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.update",
        role_code=_role("org-update-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code=_role("org-view-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.patch(
        f"/api/organizations/{foreign.id}",
        json={"legal_name": "Mutated Foreign Organization"},
        headers=_auth(token),
    )
    assert response.status_code == 404
    db_session.refresh(foreign)
    assert foreign.legal_name == original_name


def test_scope_isolation_edit_opo_does_not_borrow_view_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Edit OPO Org")
    foreign = _organization(db_session, "Foreign Edit OPO Org")
    foreign_opo = _opo(
        db_session,
        owner=foreign,
        operator=foreign,
        name="Foreign Edit OPO",
    )
    original_name = foreign_opo.name
    user = _create_user(db_session, username="scope-edit-opo")
    _grant(
        db_session,
        user=user,
        permission_code="opo.edit",
        role_code=_role("opo-edit-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code=_role("opo-view-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.patch(
        f"/api/opo/{foreign_opo.id}",
        json={"name": "Mutated Foreign OPO"},
        headers=_auth(token),
    )
    assert response.status_code == 404
    db_session.refresh(foreign_opo)
    assert foreign_opo.name == original_name


def test_scope_isolation_edit_device_does_not_borrow_view_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Edit Device Org")
    foreign = _organization(db_session, "Foreign Edit Device Org")
    foreign_device = _device(
        db_session, organization=foreign, name="Foreign Edit Device"
    )
    original_name = foreign_device.name
    user = _create_user(db_session, username="scope-edit-device")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.edit",
        role_code=_role("device-edit-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code=_role("device-view-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.patch(
        f"/api/technical-devices/{foreign_device.id}",
        json={"name": "Mutated Foreign Device"},
        headers=_auth(token),
    )
    assert response.status_code == 404
    db_session.refresh(foreign_device)
    assert foreign_device.name == original_name


def test_scope_isolation_edit_building_does_not_borrow_view_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Edit Building Org")
    foreign = _organization(db_session, "Foreign Edit Building Org")
    foreign_building = _building(
        db_session, organization=foreign, name="Foreign Edit Building"
    )
    original_name = foreign_building.name
    user = _create_user(db_session, username="scope-edit-building")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.edit",
        role_code=_role("building-edit-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code=_role("building-view-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    response = client.patch(
        f"/api/buildings/{foreign_building.id}",
        json={"name": "Mutated Foreign Building"},
        headers=_auth(token),
    )
    assert response.status_code == 404
    db_session.refresh(foreign_building)
    assert foreign_building.name == original_name


def test_custom_field_scope_isolation_does_not_borrow_opo_view_all(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed CF Org")
    foreign = _organization(db_session, "Foreign CF Org")
    foreign_opo = _opo(
        db_session,
        owner=foreign,
        operator=foreign,
        name="Foreign CF OPO",
    )
    definition = _cf_definition(db_session, code=f"cp22f-{uuid.uuid4().hex[:8]}")
    user = _create_user(db_session, username="scope-cf")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code=_role("cf-related"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code=_role("cf-opo-view-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    get_response = client.get(
        f"/api/custom-fields/values/opo/{foreign_opo.id}",
        headers=_auth(token),
    )
    assert get_response.status_code == 404

    before = _cf_value_count(
        db_session,
        definition_id=definition.id,
        entity_id=foreign_opo.id,
    )
    put_response = client.put(
        f"/api/custom-fields/values/opo/{foreign_opo.id}/{definition.id}",
        json={"value": "blocked"},
        headers=_auth(token),
    )
    assert put_response.status_code == 404
    after = _cf_value_count(
        db_session,
        definition_id=definition.id,
        entity_id=foreign_opo.id,
    )
    assert after == before


@pytest.mark.parametrize("scope_config", MALFORMED_RELATED_CONFIGS)
def test_malformed_related_organizations_list_is_empty_not_forbidden(
    db_session: Session,
    client,
    scope_config: dict,
) -> None:
    _organization(db_session, "Existing Malformed Org")
    user = _create_user(db_session, username=f"mal-list-{uuid.uuid4().hex[:8]}")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code=_role("mal-list"),
        scope_type=ScopeType.RELATED,
        scope_config=scope_config,
    )
    token = _commit_and_token(db_session, user)

    response = client.get("/api/organizations", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.parametrize("scope_config", MALFORMED_RELATED_CONFIGS)
@pytest.mark.parametrize(
    ("case", "permission"),
    [
        ("organization", "organizations.view"),
        ("opo", "opo.view"),
        ("device", "technical_devices.view"),
        ("building", "buildings.view"),
        ("custom_fields", "custom_fields.manage"),
    ],
)
def test_malformed_related_detail_returns_404(
    db_session: Session,
    client,
    scope_config: dict,
    case: str,
    permission: str,
) -> None:
    org = _organization(db_session, f"Malformed {case} Org")
    opo = _opo(
        db_session,
        owner=org,
        operator=org,
        name=f"Malformed {case} OPO",
    )
    device = _device(db_session, organization=org, name=f"Malformed {case} Device")
    building = _building(
        db_session, organization=org, name=f"Malformed {case} Building"
    )
    user = _create_user(db_session, username=f"mal-{case}-{uuid.uuid4().hex[:6]}")
    _grant(
        db_session,
        user=user,
        permission_code=permission,
        role_code=_role(f"mal-{case}"),
        scope_type=ScopeType.RELATED,
        scope_config=scope_config,
    )
    token = _commit_and_token(db_session, user)

    paths = {
        "organization": f"/api/organizations/{org.id}",
        "opo": f"/api/opo/{opo.id}",
        "device": f"/api/technical-devices/{device.id}",
        "building": f"/api/buildings/{building.id}",
        "custom_fields": f"/api/custom-fields/values/opo/{opo.id}",
    }
    assert client.get(paths[case], headers=_auth(token)).status_code == 404


@pytest.mark.parametrize("scope_type", [ScopeType.ASSIGNED, ScopeType.OWN])
@pytest.mark.parametrize(
    ("case", "permission"),
    [
        ("organization", "organizations.view"),
        ("opo", "opo.view"),
        ("device", "technical_devices.view"),
        ("building", "buildings.view"),
    ],
)
def test_deny_by_default_assigned_and_own_return_404(
    db_session: Session,
    client,
    scope_type: ScopeType,
    case: str,
    permission: str,
) -> None:
    org = _organization(db_session, f"Deny {case} Org")
    opo = _opo(db_session, owner=org, operator=org, name=f"Deny {case} OPO")
    device = _device(db_session, organization=org, name=f"Deny {case} Device")
    building = _building(db_session, organization=org, name=f"Deny {case} Building")
    user = _create_user(db_session, username=f"deny-{case}-{scope_type.value.lower()}")
    _grant(
        db_session,
        user=user,
        permission_code=permission,
        role_code=_role(f"deny-{case}"),
        scope_type=scope_type,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)

    paths = {
        "organization": f"/api/organizations/{org.id}",
        "opo": f"/api/opo/{opo.id}",
        "device": f"/api/technical-devices/{device.id}",
        "building": f"/api/buildings/{building.id}",
    }
    assert client.get(paths[case], headers=_auth(token)).status_code == 404


@pytest.mark.parametrize("path", PROTECTED_ENDPOINTS)
def test_unauthenticated_matrix_returns_401(client, path: str) -> None:
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", PROTECTED_ENDPOINTS)
def test_missing_permission_matrix_returns_403(
    db_session: Session,
    client,
    path: str,
) -> None:
    user = _create_user(db_session, username=f"missing-{uuid.uuid4().hex[:8]}")
    _grant(
        db_session,
        user=user,
        permission_code="tasks.view",
        role_code=_role("tasks-view-all"),
        scope_type=ScopeType.ALL,
        scope_config=None,
    )
    token = _commit_and_token(db_session, user)
    assert client.get(path, headers=_auth(token)).status_code == 403


def test_non_enumeration_organization_foreign_and_absent_both_404(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Nonenum Allowed Org")
    foreign = _organization(db_session, "Nonenum Foreign Org")
    user = _create_user(db_session, username="nonenum-org")
    _grant(
        db_session,
        user=user,
        permission_code="organizations.view",
        role_code=_role("nonenum-org"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _commit_and_token(db_session, user)

    foreign_status = client.get(
        f"/api/organizations/{foreign.id}", headers=_auth(token)
    ).status_code
    absent_status = client.get(
        f"/api/organizations/{uuid.uuid4()}", headers=_auth(token)
    ).status_code
    assert foreign_status == absent_status == 404


def test_non_enumeration_opo_foreign_and_absent_both_404(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Nonenum Allowed OPO Org")
    foreign = _organization(db_session, "Nonenum Foreign OPO Org")
    foreign_opo = _opo(
        db_session,
        owner=foreign,
        operator=foreign,
        name="Nonenum Foreign OPO",
    )
    user = _create_user(db_session, username="nonenum-opo")
    _grant(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code=_role("nonenum-opo"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _commit_and_token(db_session, user)

    foreign_status = client.get(
        f"/api/opo/{foreign_opo.id}", headers=_auth(token)
    ).status_code
    absent_status = client.get(
        f"/api/opo/{uuid.uuid4()}", headers=_auth(token)
    ).status_code
    assert foreign_status == absent_status == 404


def test_non_enumeration_device_foreign_and_absent_both_404(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Nonenum Allowed Device Org")
    foreign = _organization(db_session, "Nonenum Foreign Device Org")
    foreign_device = _device(
        db_session, organization=foreign, name="Nonenum Foreign Device"
    )
    user = _create_user(db_session, username="nonenum-device")
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        role_code=_role("nonenum-device"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _commit_and_token(db_session, user)

    foreign_status = client.get(
        f"/api/technical-devices/{foreign_device.id}", headers=_auth(token)
    ).status_code
    absent_status = client.get(
        f"/api/technical-devices/{uuid.uuid4()}", headers=_auth(token)
    ).status_code
    assert foreign_status == absent_status == 404


def test_non_enumeration_building_foreign_and_absent_both_404(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Nonenum Allowed Building Org")
    foreign = _organization(db_session, "Nonenum Foreign Building Org")
    foreign_building = _building(
        db_session, organization=foreign, name="Nonenum Foreign Building"
    )
    user = _create_user(db_session, username="nonenum-building")
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        role_code=_role("nonenum-building"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _commit_and_token(db_session, user)

    foreign_status = client.get(
        f"/api/buildings/{foreign_building.id}", headers=_auth(token)
    ).status_code
    absent_status = client.get(
        f"/api/buildings/{uuid.uuid4()}", headers=_auth(token)
    ).status_code
    assert foreign_status == absent_status == 404


def test_non_enumeration_custom_fields_foreign_and_absent_both_404(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Nonenum Allowed CF Org")
    foreign = _organization(db_session, "Nonenum Foreign CF Org")
    foreign_opo = _opo(
        db_session,
        owner=foreign,
        operator=foreign,
        name="Nonenum Foreign CF OPO",
    )
    user = _create_user(db_session, username="nonenum-cf")
    _grant(
        db_session,
        user=user,
        permission_code="custom_fields.manage",
        role_code=_role("nonenum-cf"),
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _commit_and_token(db_session, user)

    foreign_status = client.get(
        f"/api/custom-fields/values/opo/{foreign_opo.id}",
        headers=_auth(token),
    ).status_code
    absent_status = client.get(
        f"/api/custom-fields/values/opo/{uuid.uuid4()}",
        headers=_auth(token),
    ).status_code
    assert foreign_status == absent_status == 404
