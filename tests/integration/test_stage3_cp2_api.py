import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.service import BuildingService
from app.modules.custom_fields.service import CustomFieldService
from app.modules.identity.models import Employee, User
from app.modules.identity.security import hash_password
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import ActivityType, HazardSign
from app.modules.opo.repository import list_activity_types, list_hazard_signs
from app.modules.opo.service import OPOConflictError, OPONotFoundError, OPOService
from app.modules.organizations.models import Organization, OrganizationType
from app.modules.organizations.service import OrganizationService
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.service import TechnicalDeviceService

pytestmark = pytest.mark.integration


@pytest.fixture()
def db() -> Session:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text("""
            TRUNCATE TABLE
                audit_events,
                custom_field_values, custom_field_definitions,
                opo_hazard_signs, opo_activity_types, opo,
                technical_devices,
                buildings,
                organization_identifiers, organization_contacts, organizations,
                role_permissions, user_role_assignments,
                user_sessions, password_reset_events, users,
                employee_function_role_assignments,
                employees
            RESTART IDENTITY CASCADE
        """)
        )
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def actor(db: Session) -> User:
    employee = Employee(full_name="CP2 Admin")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username="cp2admin",
        password_hash=hash_password("Strong-password-123!"),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def org(db: Session, actor: User) -> Organization:
    return OrganizationService().create_organization(
        db,
        actor_id=actor.id,
        legal_name="CP2 Test Org",
        short_name="CP2",
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )


@pytest.fixture()
def opo_svc() -> OPOService:
    return OPOService()


@pytest.fixture()
def td_svc() -> TechnicalDeviceService:
    return TechnicalDeviceService()


@pytest.fixture()
def bld_svc() -> BuildingService:
    return BuildingService()


@pytest.fixture()
def cf_svc() -> CustomFieldService:
    return CustomFieldService()


def _create_opo(db, svc, actor, org, reg_num, **kw):
    defaults = {
        "name": f"OPO {reg_num}",
        "registration_number": reg_num,
        "hazard_class": HazardClass.HAZARD_CLASS_2,
        "address": "Test Address",
        "owner_organization_id": org.id,
        "operating_organization_id": org.id,
    }
    defaults.update(kw)
    return svc.create_opo(db, actor_id=actor.id, **defaults)


# ---------------------------------------------------------------------------
# OPO CRUD
# ---------------------------------------------------------------------------
def test_opo_create(db, actor, org, opo_svc):
    opo = _create_opo(db, opo_svc, actor, org, "CRUD-001")
    assert opo.name == "OPO CRUD-001"
    assert opo.hazard_class == HazardClass.HAZARD_CLASS_2


def test_opo_different_owner_operator(db, actor, org, opo_svc):
    org2 = OrganizationService().create_organization(
        db, actor_id=actor.id, legal_name="Org2", short_name="O2",
        organization_type=OrganizationType.LEGAL_ENTITY, parent_id=None,
    )
    opo = opo_svc.create_opo(
        db, actor_id=actor.id,
        name="Multi", registration_number="MULTI-001",
        hazard_class=HazardClass.HAZARD_CLASS_1, address="Addr",
        owner_organization_id=org.id,
        operating_organization_id=org2.id,
    )
    assert opo.owner_organization_id == org.id
    assert opo.operating_organization_id == org2.id


def test_opo_invalid_owner(db, actor, org, opo_svc):
    with pytest.raises(OPONotFoundError):
        opo_svc.create_opo(
            db, actor_id=actor.id, name="Bad", registration_number="BAD-001",
            hazard_class=HazardClass.HAZARD_CLASS_1, address="Addr",
            owner_organization_id=uuid.uuid4(),
            operating_organization_id=org.id,
        )


def test_opo_duplicate_reg_number(db, actor, org, opo_svc):
    _create_opo(db, opo_svc, actor, org, "DUP-001")
    with pytest.raises(OPOConflictError):
        _create_opo(db, opo_svc, actor, org, "DUP-001")


def test_opo_update(db, actor, org, opo_svc):
    opo = _create_opo(db, opo_svc, actor, org, "UPD-001")
    updated = opo_svc.update_opo(db, actor_id=actor.id, opo=opo, name="Updated Name")
    assert updated.name == "Updated Name"


def test_opo_soft_delete_and_restore(db, actor, org, opo_svc):
    opo = _create_opo(db, opo_svc, actor, org, "DEL-001")
    opo_svc.delete_opo(db, actor_id=actor.id, opo=opo)
    db.refresh(opo)
    assert opo.deleted_at is not None
    opo_svc.restore_opo(db, actor_id=actor.id, opo=opo)
    db.refresh(opo)
    assert opo.deleted_at is None


# ---------------------------------------------------------------------------
# OPO N:M relationships
# ---------------------------------------------------------------------------
def test_opo_create_with_hazard_signs(db, actor, org, opo_svc):
    signs = db.execute(select(HazardSign).limit(2)).scalars().all()
    opo = opo_svc.create_opo(
        db, actor_id=actor.id,
        name="HS OPO", registration_number="HS-001",
        hazard_class=HazardClass.HAZARD_CLASS_1, address="Addr",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        hazard_sign_ids=[s.id for s in signs],
    )
    opo_detail = opo_svc.get_opo_detail(db, opo.id)
    assert len(opo_detail.hazard_signs) == 2


def test_opo_update_hazard_signs(db, actor, org, opo_svc):
    signs = db.execute(select(HazardSign).limit(3)).scalars().all()
    opo = _create_opo(db, opo_svc, actor, org, "HS-UPD-001",
                      hazard_sign_ids=[signs[0].id])
    opo = opo_svc.update_opo(db, actor_id=actor.id, opo=opo,
                             hazard_sign_ids=[signs[1].id, signs[2].id])
    opo_detail = opo_svc.get_opo_detail(db, opo.id)
    assert len(opo_detail.hazard_signs) == 2


def test_opo_update_activity_types(db, actor, org, opo_svc):
    types = db.execute(select(ActivityType).limit(2)).scalars().all()
    opo = _create_opo(db, opo_svc, actor, org, "AT-UPD-001",
                      activity_type_ids=[types[0].id])
    opo = opo_svc.update_opo(db, actor_id=actor.id, opo=opo,
                             activity_type_ids=[types[0].id, types[1].id])
    opo_detail = opo_svc.get_opo_detail(db, opo.id)
    assert len(opo_detail.activity_types) == 2


# ---------------------------------------------------------------------------
# OPO delete preserves children
# ---------------------------------------------------------------------------
def test_opo_delete_preserves_td_building(db, actor, org, opo_svc, td_svc, bld_svc):
    opo = _create_opo(db, opo_svc, actor, org, "PRES-001")
    device = td_svc.create_technical_device(
        db, actor_id=actor.id, name="TD", device_type=TechnicalDeviceType.OTHER,
        opo_id=opo.id,
    )
    building = bld_svc.create_building(
        db, actor_id=actor.id, name="BLD", building_type=BuildingType.OTHER,
        opo_id=opo.id,
    )
    opo_svc.delete_opo(db, actor_id=actor.id, opo=opo)
    db.refresh(device)
    db.refresh(building)
    assert device.opo_id is None
    assert building.opo_id is None


# ---------------------------------------------------------------------------
# Technical Devices
# ---------------------------------------------------------------------------
def test_td_create_without_opo(db, actor, td_svc):
    device = td_svc.create_technical_device(
        db, actor_id=actor.id, name="Standalone",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
    )
    assert device.id is not None
    assert device.opo_id is None


def test_td_create_with_opo(db, actor, org, opo_svc, td_svc):
    opo = _create_opo(db, opo_svc, actor, org, "TD-OPO-001")
    device = td_svc.create_technical_device(
        db, actor_id=actor.id, name="Linked",
        device_type=TechnicalDeviceType.PIPELINE, opo_id=opo.id,
    )
    assert device.opo_id == opo.id


def test_td_update(db, actor, td_svc):
    device = td_svc.create_technical_device(
        db, actor_id=actor.id, name="Upd", device_type=TechnicalDeviceType.OTHER,
    )
    td_svc.update_technical_device(db, actor_id=actor.id, device=device, name="Updated")
    db.refresh(device)
    assert device.name == "Updated"


def test_td_soft_delete_and_restore(db, actor, td_svc):
    device = td_svc.create_technical_device(
        db, actor_id=actor.id, name="Del", device_type=TechnicalDeviceType.OTHER,
    )
    td_svc.delete_technical_device(db, actor_id=actor.id, device=device)
    db.refresh(device)
    assert device.deleted_at is not None
    td_svc.restore_technical_device(db, actor_id=actor.id, device=device)
    db.refresh(device)
    assert device.deleted_at is None


# ---------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------
def test_bld_create_without_opo(db, actor, bld_svc):
    building = bld_svc.create_building(
        db, actor_id=actor.id, name="Standalone",
        building_type=BuildingType.INDUSTRIAL,
    )
    assert building.id is not None
    assert building.opo_id is None


def test_bld_create_with_opo(db, actor, org, opo_svc, bld_svc):
    opo = _create_opo(db, opo_svc, actor, org, "BLD-OPO-001")
    building = bld_svc.create_building(
        db, actor_id=actor.id, name="Linked",
        building_type=BuildingType.WAREHOUSE, opo_id=opo.id,
    )
    assert building.opo_id == opo.id


def test_bld_update(db, actor, bld_svc):
    building = bld_svc.create_building(
        db, actor_id=actor.id, name="Upd", building_type=BuildingType.OTHER,
    )
    bld_svc.update_building(db, actor_id=actor.id, building=building, name="Updated")
    db.refresh(building)
    assert building.name == "Updated"


def test_bld_soft_delete_and_restore(db, actor, bld_svc):
    building = bld_svc.create_building(
        db, actor_id=actor.id, name="Del", building_type=BuildingType.OTHER,
    )
    bld_svc.delete_building(db, actor_id=actor.id, building=building)
    db.refresh(building)
    assert building.deleted_at is not None
    bld_svc.restore_building(db, actor_id=actor.id, building=building)
    db.refresh(building)
    assert building.deleted_at is None


# ---------------------------------------------------------------------------
# Reference dictionaries
# ---------------------------------------------------------------------------
def test_list_hazard_signs(db):
    signs = list_hazard_signs(db)
    assert len(signs) == 7


def test_list_activity_types(db):
    types = list_activity_types(db)
    assert len(types) == 5


def test_deterministic_uuids(db):
    s1 = db.execute(select(HazardSign).where(HazardSign.code == "explosive")).scalar_one()
    s2 = db.execute(select(HazardSign).where(HazardSign.code == "toxic")).scalar_one()
    assert s1.id != s2.id


# ---------------------------------------------------------------------------
# Custom fields typed dispatch
# ---------------------------------------------------------------------------
def test_custom_field_text_accepted(db, actor, cf_svc):
    definition = cf_svc.create_definition(
        db, actor_id=actor.id, code="cf_text", name="Text Field",
        entity_type="opo", field_type="text",
    )
    value = cf_svc.set_value(
        db, actor_id=actor.id, field_definition_id=definition.id,
        entity_type="opo", entity_id=uuid.uuid4(), value="hello",
    )
    assert value.value_text == "hello"


def test_custom_field_number_accepted(db, actor, cf_svc):
    definition = cf_svc.create_definition(
        db, actor_id=actor.id, code="cf_num", name="Num Field",
        entity_type="opo", field_type="number",
    )
    value = cf_svc.set_value(
        db, actor_id=actor.id, field_definition_id=definition.id,
        entity_type="opo", entity_id=uuid.uuid4(), value="42.5",
    )
    assert value.value_number is not None
    assert str(value.value_number) == "42.5"


def test_custom_field_number_rejected(db, actor, cf_svc):
    definition = cf_svc.create_definition(
        db, actor_id=actor.id, code="cf_num2", name="Num Field 2",
        entity_type="opo", field_type="number",
    )
    from app.modules.custom_fields.service import CustomFieldValidationError

    with pytest.raises(CustomFieldValidationError):
        cf_svc.set_value(
            db, actor_id=actor.id, field_definition_id=definition.id,
            entity_type="opo", entity_id=uuid.uuid4(), value="not-a-number",
        )


def test_custom_field_date_accepted(db, actor, cf_svc):
    definition = cf_svc.create_definition(
        db, actor_id=actor.id, code="cf_date", name="Date Field",
        entity_type="opo", field_type="date",
    )
    value = cf_svc.set_value(
        db, actor_id=actor.id, field_definition_id=definition.id,
        entity_type="opo", entity_id=uuid.uuid4(), value="2024-01-15",
    )
    assert value.value_date is not None


def test_custom_field_boolean_accepted(db, actor, cf_svc):
    definition = cf_svc.create_definition(
        db, actor_id=actor.id, code="cf_bool", name="Bool Field",
        entity_type="opo", field_type="boolean",
    )
    value = cf_svc.set_value(
        db, actor_id=actor.id, field_definition_id=definition.id,
        entity_type="opo", entity_id=uuid.uuid4(), value="true",
    )
    assert value.value_boolean is True


def test_custom_field_wrong_entity_type(db, actor, cf_svc):
    definition = cf_svc.create_definition(
        db, actor_id=actor.id, code="cf_only_opo", name="Only OPO",
        entity_type="opo", field_type="text",
    )
    from app.modules.custom_fields.service import CustomFieldValidationError

    with pytest.raises(CustomFieldValidationError):
        cf_svc.set_value(
            db, actor_id=actor.id, field_definition_id=definition.id,
            entity_type="building", entity_id=uuid.uuid4(), value="nope",
        )


def test_custom_field_clear(db, actor, cf_svc):
    definition = cf_svc.create_definition(
        db, actor_id=actor.id, code="cf_clear", name="Clearable",
        entity_type="opo", field_type="text",
    )
    eid = uuid.uuid4()
    cf_svc.set_value(
        db, actor_id=actor.id, field_definition_id=definition.id,
        entity_type="opo", entity_id=eid, value="temp",
    )
    cf_svc.clear_value(
        db, actor_id=actor.id, field_definition_id=definition.id,
        entity_type="opo", entity_id=eid,
    )
    values = cf_svc.get_values(db, entity_type="opo", entity_id=eid)
    assert len(values) == 0
