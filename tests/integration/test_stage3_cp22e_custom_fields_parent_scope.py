import uuid

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
    owner_org: Organization,
    operating_org: Organization,
) -> OPO:
    opo = OPO(
        name=name,
        registration_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        hazard_class=HazardClass.HAZARD_CLASS_1,
        address="Test Address",
        registration_date="2024-01-01",
        owner_organization_id=owner_org.id,
        operating_organization_id=operating_org.id,
    )
    db.add(opo)
    db.flush()
    return opo


def _technical_device(
    db: Session,
    *,
    name: str,
    organization: Organization | None = None,
    opo: OPO | None = None,
) -> TechnicalDevice:
    device = TechnicalDevice(
        name=name,
        device_type=TechnicalDeviceType.OTHER,
        organization_id=organization.id if organization else None,
        opo_id=opo.id if opo else None,
    )
    db.add(device)
    db.flush()
    return device


def _building(
    db: Session,
    *,
    name: str,
    organization: Organization | None = None,
    opo: OPO | None = None,
) -> Building:
    building = Building(
        name=name,
        building_type=BuildingType.OTHER,
        organization_id=organization.id if organization else None,
        opo_id=opo.id if opo else None,
    )
    db.add(building)
    db.flush()
    return building


def _create_field_definition(
    db: Session,
    *,
    code: str,
    entity_type: str,
    field_type: str = "text",
) -> CustomFieldDefinition:
    definition = CustomFieldDefinition(
        code=code,
        name=f"Test Field {code}",
        entity_type=entity_type,
        field_type=CustomFieldType(field_type),
    )
    db.add(definition)
    db.flush()
    return definition


def _create_field_value(
    db: Session,
    *,
    definition: CustomFieldDefinition,
    entity_type: str,
    entity_id: uuid.UUID,
    value: str = "test-value",
) -> CustomFieldValue:
    fv = CustomFieldValue(
        field_definition_id=definition.id,
        entity_type=entity_type,
        entity_id=entity_id,
        value_text=value,
    )
    db.add(fv)
    db.flush()
    return fv


# ---------------------------------------------------------------------------
# OPO Parent Scope Tests
# ---------------------------------------------------------------------------

class TestOPOParentScope:
    def test_owner_organization_allowed_get(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with owner org can GET values on OPO."""
        user = _create_user(db_session, username="owner-user")
        org = _organization(db_session, legal_name="Owner Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-owner",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(org.id)]},
        )
        token = _make_session_token(db_session, user)

        opo = _opo(db_session, name="Test OPO", owner_org=org, operating_org=org)
        defn = _create_field_definition(db_session, code="opo_field", entity_type="opo")
        _create_field_value(db_session, definition=defn, entity_type="opo", entity_id=opo.id)

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_operating_organization_allowed_get(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with operating org can GET values on OPO."""
        user = _create_user(db_session, username="operator-user")
        owner_org = _organization(db_session, legal_name="Owner Org")
        operating_org = _organization(db_session, legal_name="Operating Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-operator",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(operating_org.id)]},
        )
        token = _make_session_token(db_session, user)

        opo = _opo(db_session, name="Test OPO", owner_org=owner_org, operating_org=operating_org)
        defn = _create_field_definition(db_session, code="opo_field_op", entity_type="opo")
        _create_field_value(db_session, definition=defn, entity_type="opo", entity_id=opo.id)

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_foreign_opo_get_404(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with unrelated org gets 404 on foreign OPO."""
        user = _create_user(db_session, username="foreign-user")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-unrelated",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        owner_org = _organization(db_session, legal_name="Owner Org")
        operating_org = _organization(db_session, legal_name="Operating Org")
        opo = _opo(db_session, name="Foreign OPO", owner_org=owner_org, operating_org=operating_org)

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_foreign_opo_put_404_no_value_inserted(
        self, db_session: Session, client
    ) -> None:
        """Foreign OPO PUT returns 404 and does not insert value."""
        user = _create_user(db_session, username="foreign-put-user")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-unrelated-put",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        owner_org = _organization(db_session, legal_name="Owner Org")
        operating_org = _organization(
            db_session, legal_name="Operating Org"
        )
        opo = _opo(
            db_session,
            name="Foreign OPO PUT",
            owner_org=owner_org,
            operating_org=operating_org,
        )
        defn = _create_field_definition(
            db_session, code="opo_put_field", entity_type="opo"
        )

        resp = client.put(
            f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "test"},
        )
        assert resp.status_code == 404

        fv = db_session.scalar(
            text(
                "SELECT 1 FROM custom_field_values"
                " WHERE entity_type = 'opo'"
                " AND entity_id = :eid"
            ),
            {"eid": opo.id},
        )
        assert fv is None

    def test_foreign_opo_delete_404_value_remains(
        self, db_session: Session, client
    ) -> None:
        """Foreign OPO DELETE returns 404 and existing value remains."""
        user = _create_user(db_session, username="foreign-del-user")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-unrelated-del",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        owner_org = _organization(db_session, legal_name="Owner Org")
        operating_org = _organization(
            db_session, legal_name="Operating Org"
        )
        opo = _opo(
            db_session,
            name="Foreign OPO DEL",
            owner_org=owner_org,
            operating_org=operating_org,
        )
        defn = _create_field_definition(
            db_session, code="opo_del_field", entity_type="opo"
        )
        _create_field_value(
            db_session,
            definition=defn,
            entity_type="opo",
            entity_id=opo.id,
        )

        resp = client.delete(
            f"/api/custom-fields/values/opo/{opo.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

        fv = db_session.scalar(
            text(
                "SELECT 1 FROM custom_field_values"
                " WHERE entity_type = 'opo'"
                " AND entity_id = :eid"
            ),
            {"eid": opo.id},
        )
        assert fv is not None


# ---------------------------------------------------------------------------
# Technical Device Parent Scope Tests
# ---------------------------------------------------------------------------

class TestTechnicalDeviceParentScope:
    def test_own_organization_get_put_delete(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with device's org can GET/PUT/DELETE."""
        user = _create_user(db_session, username="td-owner-user")
        org = _organization(db_session, legal_name="TD Owner Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-td-owner",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(org.id)]},
        )
        token = _make_session_token(db_session, user)

        device = _technical_device(db_session, name="Own TD", organization=org)
        defn = _create_field_definition(db_session, code="td_field", entity_type="technical_device")

        resp_get = client.get(
            f"/api/custom-fields/values/technical_device/{device.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_get.status_code == 200

        resp_put = client.put(
            f"/api/custom-fields/values/technical_device/{device.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "td-value"},
        )
        assert resp_put.status_code == 200

        resp_del = client.delete(
            f"/api/custom-fields/values/technical_device/{device.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_del.status_code == 204

    def test_foreign_organization_get_404(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with unrelated org gets 404 on foreign TD."""
        user = _create_user(db_session, username="td-foreign-user")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-td-unrelated",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        device = _technical_device(db_session, name="Foreign TD", organization=foreign_org)

        resp = client.get(
            f"/api/custom-fields/values/technical_device/{device.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_foreign_td_with_linked_opo_still_404(
        self, db_session: Session, client
    ) -> None:
        """TD with foreign org but linked OPO accessible still returns 404."""
        user = _create_user(db_session, username="td-opo-user")
        accessible_org = _organization(db_session, legal_name="Accessible Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-td-opo",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(accessible_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        opo = _opo(
            db_session,
            name="Accessible OPO",
            owner_org=accessible_org,
            operating_org=accessible_org,
        )
        device = _technical_device(
            db_session,
            name="TD with OPO",
            organization=foreign_org,
            opo=opo,
        )

        resp = client.get(
            f"/api/custom-fields/values/technical_device/{device.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_foreign_td_put_no_value_inserted(
        self, db_session: Session, client
    ) -> None:
        """Foreign TD PUT returns 404 and does not insert value."""
        user = _create_user(db_session, username="td-foreign-put")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-td-foreign-put",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        device = _technical_device(
            db_session, name="Foreign TD PUT", organization=foreign_org
        )
        defn = _create_field_definition(
            db_session,
            code="td_put_field",
            entity_type="technical_device",
        )

        resp = client.put(
            f"/api/custom-fields/values/technical_device/{device.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "test"},
        )
        assert resp.status_code == 404

        fv = db_session.scalar(
            text(
                "SELECT 1 FROM custom_field_values"
                " WHERE entity_type = 'technical_device'"
                " AND entity_id = :eid"
            ),
            {"eid": device.id},
        )
        assert fv is None

    def test_foreign_td_delete_value_remains(
        self, db_session: Session, client
    ) -> None:
        """Foreign TD DELETE returns 404 and existing value remains."""
        user = _create_user(db_session, username="td-foreign-del")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-td-foreign-del",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        device = _technical_device(
            db_session, name="Foreign TD DEL", organization=foreign_org
        )
        defn = _create_field_definition(
            db_session,
            code="td_del_field",
            entity_type="technical_device",
        )
        _create_field_value(
            db_session,
            definition=defn,
            entity_type="technical_device",
            entity_id=device.id,
        )

        resp = client.delete(
            f"/api/custom-fields/values/technical_device/{device.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

        fv = db_session.scalar(
            text(
                "SELECT 1 FROM custom_field_values"
                " WHERE entity_type = 'technical_device'"
                " AND entity_id = :eid"
            ),
            {"eid": device.id},
        )
        assert fv is not None


# ---------------------------------------------------------------------------
# Building Parent Scope Tests
# ---------------------------------------------------------------------------

class TestBuildingParentScope:
    def test_own_organization_get_put_delete(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with building's org can GET/PUT/DELETE."""
        user = _create_user(db_session, username="bld-owner-user")
        org = _organization(db_session, legal_name="Bld Owner Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-bld-owner",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(org.id)]},
        )
        token = _make_session_token(db_session, user)

        bld = _building(db_session, name="Own Building", organization=org)
        defn = _create_field_definition(db_session, code="bld_field", entity_type="building")

        resp_get = client.get(
            f"/api/custom-fields/values/building/{bld.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_get.status_code == 200

        resp_put = client.put(
            f"/api/custom-fields/values/building/{bld.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "bld-value"},
        )
        assert resp_put.status_code == 200

        resp_del = client.delete(
            f"/api/custom-fields/values/building/{bld.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_del.status_code == 204

    def test_foreign_organization_get_404(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with unrelated org gets 404 on foreign building."""
        user = _create_user(db_session, username="bld-foreign-user")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-bld-unrelated",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        bld = _building(db_session, name="Foreign Building", organization=foreign_org)

        resp = client.get(
            f"/api/custom-fields/values/building/{bld.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_foreign_building_with_linked_opo_still_404(
        self, db_session: Session, client
    ) -> None:
        """Building with foreign org but linked OPO accessible still returns 404."""
        user = _create_user(db_session, username="bld-opo-user")
        accessible_org = _organization(db_session, legal_name="Accessible Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-bld-opo",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(accessible_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        opo = _opo(
            db_session,
            name="Accessible OPO for Bld",
            owner_org=accessible_org,
            operating_org=accessible_org,
        )
        bld = _building(db_session, name="Building with OPO", organization=foreign_org, opo=opo)

        resp = client.get(
            f"/api/custom-fields/values/building/{bld.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_foreign_building_put_no_value_inserted(
        self, db_session: Session, client
    ) -> None:
        """Foreign building PUT returns 404 and does not insert value."""
        user = _create_user(db_session, username="bld-foreign-put")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-bld-foreign-put",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        bld = _building(db_session, name="Foreign Bld PUT", organization=foreign_org)
        defn = _create_field_definition(db_session, code="bld_put_field", entity_type="building")

        resp = client.put(
            f"/api/custom-fields/values/building/{bld.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "test"},
        )
        assert resp.status_code == 404

        fv = db_session.scalar(
            text(
                "SELECT 1 FROM custom_field_values"
                " WHERE entity_type = 'building'"
                " AND entity_id = :eid"
            ),
            {"eid": bld.id},
        )
        assert fv is None

    def test_foreign_building_delete_value_remains(
        self, db_session: Session, client
    ) -> None:
        """Foreign building DELETE returns 404 and existing value remains."""
        user = _create_user(db_session, username="bld-foreign-del")
        unrelated_org = _organization(db_session, legal_name="Unrelated Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-bld-foreign-del",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(unrelated_org.id)]},
        )
        token = _make_session_token(db_session, user)

        foreign_org = _organization(db_session, legal_name="Foreign Org")
        bld = _building(db_session, name="Foreign Bld DEL", organization=foreign_org)
        defn = _create_field_definition(db_session, code="bld_del_field", entity_type="building")
        _create_field_value(db_session, definition=defn, entity_type="building", entity_id=bld.id)

        resp = client.delete(
            f"/api/custom-fields/values/building/{bld.id}/{defn.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

        fv = db_session.scalar(
            text(
                "SELECT 1 FROM custom_field_values"
                " WHERE entity_type = 'building'"
                " AND entity_id = :eid"
            ),
            {"eid": bld.id},
        )
        assert fv is not None


# ---------------------------------------------------------------------------
# Boundary Tests
# ---------------------------------------------------------------------------

class TestBoundary:
    def test_related_empty_organization_ids_get_404(
        self, db_session: Session, client
    ) -> None:
        """RELATED user with empty organization_ids gets 404 on known parent."""
        user = _create_user(db_session, username="empty-related")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-empty",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": []},
        )
        token = _make_session_token(db_session, user)

        org = _organization(db_session, legal_name="Some Org")
        opo = _opo(db_session, name="Some OPO", owner_org=org, operating_org=org)

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_all_scope_accesses_known_parents(
        self, db_session: Session, client
    ) -> None:
        """ALL scope user can access any known parent."""
        user = _create_user(db_session, username="all-scope-user")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-all",
            scope_type=ScopeType.ALL,
            scope_config=None,
        )
        token = _make_session_token(db_session, user)

        org = _organization(db_session, legal_name="All Org")
        opo = _opo(db_session, name="All OPO", owner_org=org, operating_org=org)

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_superuser_accesses_known_parents(
        self, db_session: Session, client
    ) -> None:
        """Superuser can access any known parent."""
        user = _create_user(db_session, username="superuser", is_superuser=True)
        token = _make_session_token(db_session, user)

        org = _organization(db_session, legal_name="SU Org")
        opo = _opo(db_session, name="SU OPO", owner_org=org, operating_org=org)

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_deleted_opo_get_404(
        self, db_session: Session, client
    ) -> None:
        """Soft-deleted OPO returns 404."""
        user = _create_user(db_session, username="del-opo-user")
        org = _organization(db_session, legal_name="Del Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-del-opo",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(org.id)]},
        )
        token = _make_session_token(db_session, user)

        from datetime import UTC, datetime
        opo = _opo(db_session, name="Deleted OPO", owner_org=org, operating_org=org)
        opo.deleted_at = datetime.now(UTC)
        db_session.flush()

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_deleted_td_get_404(
        self, db_session: Session, client
    ) -> None:
        """Soft-deleted TD returns 404."""
        user = _create_user(db_session, username="del-td-user")
        org = _organization(db_session, legal_name="Del TD Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-del-td",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(org.id)]},
        )
        token = _make_session_token(db_session, user)

        from datetime import UTC, datetime
        device = _technical_device(db_session, name="Deleted TD", organization=org)
        device.deleted_at = datetime.now(UTC)
        db_session.flush()

        resp = client.get(
            f"/api/custom-fields/values/technical_device/{device.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_deleted_building_get_404(
        self, db_session: Session, client
    ) -> None:
        """Soft-deleted Building returns 404."""
        user = _create_user(db_session, username="del-bld-user")
        org = _organization(db_session, legal_name="Del Bld Org")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-del-bld",
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(org.id)]},
        )
        token = _make_session_token(db_session, user)

        from datetime import UTC, datetime
        bld = _building(db_session, name="Deleted Building", organization=org)
        bld.deleted_at = datetime.now(UTC)
        db_session.flush()

        resp = client.get(
            f"/api/custom-fields/values/building/{bld.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_unknown_entity_type_get_422(
        self, db_session: Session, client
    ) -> None:
        """Unknown entity_type returns 422 on GET."""
        user = _create_user(db_session, username="unknown-get")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-unknown-get",
            scope_type=ScopeType.ALL,
            scope_config=None,
        )
        token = _make_session_token(db_session, user)

        resp = client.get(
            "/api/custom-fields/values/unknown_type/some-id",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_unknown_entity_type_put_422(
        self, db_session: Session, client
    ) -> None:
        """Unknown entity_type returns 422 on PUT."""
        user = _create_user(db_session, username="unknown-put")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-unknown-put",
            scope_type=ScopeType.ALL,
            scope_config=None,
        )
        token = _make_session_token(db_session, user)

        fake_id = str(uuid.uuid4())
        resp = client.put(
            f"/api/custom-fields/values/unknown_type/{fake_id}/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "test"},
        )
        assert resp.status_code == 422

    def test_unknown_entity_type_delete_422(
        self, db_session: Session, client
    ) -> None:
        """Unknown entity_type returns 422 on DELETE."""
        user = _create_user(db_session, username="unknown-del")
        _grant(
            db_session,
            user=user,
            permission_code="custom_fields.manage",
            role_code="cf-unknown-del",
            scope_type=ScopeType.ALL,
            scope_config=None,
        )
        token = _make_session_token(db_session, user)

        fake_id = str(uuid.uuid4())
        resp = client.delete(
            f"/api/custom-fields/values/unknown_type/{fake_id}/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_no_permission_get_403(
        self, db_session: Session, client
    ) -> None:
        """User without custom_fields.manage gets 403."""
        user = _create_user(db_session, username="no-perm-user")
        token = _make_session_token(db_session, user)

        org = _organization(db_session, legal_name="Perm Org")
        opo = _opo(db_session, name="Perm OPO", owner_org=org, operating_org=org)

        resp = client.get(
            f"/api/custom-fields/values/opo/{opo.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_no_auth_get_401(
        self, db_session: Session, client
    ) -> None:
        """Unauthenticated request returns 401."""
        org = _organization(db_session, legal_name="Auth Org")
        opo = _opo(db_session, name="Auth OPO", owner_org=org, operating_org=org)

        resp = client.get(f"/api/custom-fields/values/opo/{opo.id}")
        assert resp.status_code == 401
