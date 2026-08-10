import os

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType as BldgType
from app.modules.buildings.service import BuildingService
from app.modules.custom_fields.service import CustomFieldConflictError, CustomFieldService
from app.modules.identity.models import Employee, User
from app.modules.identity.security import hash_password
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import (
    ActivityType,
    HazardSign,
    OPOActivityType,
    OPOHazardSign,
)
from app.modules.opo.service import OPOService
from app.modules.organizations.models import Organization, OrganizationType
from app.modules.organizations.service import OrganizationService
from app.modules.technical_devices.enums import TechnicalDeviceType as TechDeviceType
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
def org_service() -> OrganizationService:
    return OrganizationService()


@pytest.fixture()
def opo_service() -> OPOService:
    return OPOService()


@pytest.fixture()
def td_service() -> TechnicalDeviceService:
    return TechnicalDeviceService()


@pytest.fixture()
def building_service() -> BuildingService:
    return BuildingService()


@pytest.fixture()
def cf_service() -> CustomFieldService:
    return CustomFieldService()


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


def _create_org(db: Session, svc: OrganizationService, actor: User, name: str) -> Organization:
    return svc.create_organization(
        db,
        actor_id=actor.id,
        legal_name=name,
        short_name=name,
        organization_type=OrganizationType.LEGAL_ENTITY,
        parent_id=None,
    )


# ---------------------------------------------------------------------------
# Invariant 1 – OPO can have different owner/operator organizations
# ---------------------------------------------------------------------------
def test_opo_different_owner_and_operator(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    actor: User,
) -> None:
    owner = _create_org(db, org_service, actor, "OOO Owner")
    operator = _create_org(db, org_service, actor, "AO Operator")
    assert owner.id != operator.id

    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="Test OPO",
        registration_number="A01-12345",
        hazard_class=HazardClass.HAZARD_CLASS_2,
        address="ул. Тестовая, 1",
        owner_organization_id=owner.id,
        operating_organization_id=operator.id,
        registration_date="2024-01-15",
    )
    assert opo.owner_organization_id == owner.id
    assert opo.operating_organization_id == operator.id


# ---------------------------------------------------------------------------
# Invariant 2 – OPO can have same organization as owner and operator
# ---------------------------------------------------------------------------
def test_opo_same_owner_and_operator(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Universal")

    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="OPO Same",
        registration_number="B02-67890",
        hazard_class=HazardClass.HAZARD_CLASS_3,
        address="ул. Общая, 5",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        registration_date="2024-01-15",
    )
    assert opo.owner_organization_id == org.id
    assert opo.operating_organization_id == org.id


# ---------------------------------------------------------------------------
# Invariant 3 – Technical Device can exist without OPO
# ---------------------------------------------------------------------------
def test_technical_device_without_opo(
    db: Session,
    org_service: OrganizationService,
    td_service: TechnicalDeviceService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Test Devices")
    device = td_service.create_technical_device(
        db,
        actor_id=actor.id,
        name="Компрессор К-500",
        device_type=TechDeviceType.PRESSURE_VESSEL,
        opo_id=None,
        organization_id=org.id,
    )
    assert device.id is not None
    assert device.opo_id is None


# ---------------------------------------------------------------------------
# Invariant 4 – Building can exist without OPO
# ---------------------------------------------------------------------------
def test_building_without_opo(
    db: Session,
    org_service: OrganizationService,
    building_service: BuildingService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Test Buildings")
    building = building_service.create_building(
        db,
        actor_id=actor.id,
        name="Корпус А",
        building_type=BldgType.INDUSTRIAL,
        opo_id=None,
        organization_id=org.id,
    )
    assert building.id is not None
    assert building.opo_id is None


# ---------------------------------------------------------------------------
# Invariant 5 – Deleting OPO does NOT cascade delete Technical Devices
# ---------------------------------------------------------------------------
def test_delete_opo_preserves_technical_device(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    td_service: TechnicalDeviceService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Test")
    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="OPO with device",
        registration_number="C03-11111",
        hazard_class=HazardClass.HAZARD_CLASS_1,
        address="ул. Промышленная, 10",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        registration_date="2024-01-15",
    )
    device = td_service.create_technical_device(
        db,
        actor_id=actor.id,
        name="Резервуар Р-100",
        device_type=TechDeviceType.PRESSURE_VESSEL,
        opo_id=opo.id,
        organization_id=org.id,
    )
    assert device.opo_id == opo.id

    opo_service.delete_opo(db, actor_id=actor.id, opo=opo)
    db.refresh(device)
    assert device.opo_id is None


# ---------------------------------------------------------------------------
# Invariant 6 – Deleting OPO does NOT cascade delete Buildings
# ---------------------------------------------------------------------------
def test_delete_opo_preserves_building(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    building_service: BuildingService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Test")
    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="OPO with building",
        registration_number="D04-22222",
        hazard_class=HazardClass.HAZARD_CLASS_2,
        address="ул. Заводская, 3",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        registration_date="2024-01-15",
    )
    building = building_service.create_building(
        db,
        actor_id=actor.id,
        name="Цех №1",
        building_type=BldgType.INDUSTRIAL,
        opo_id=opo.id,
        organization_id=org.id,
    )
    assert building.opo_id == opo.id

    opo_service.delete_opo(db, actor_id=actor.id, opo=opo)
    db.refresh(building)
    assert building.opo_id is None


# ---------------------------------------------------------------------------
# Invariant 7 – OPO ↔ hazard signs N:M
# ---------------------------------------------------------------------------
def test_opo_hazard_signs_nm(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Hazard")
    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="OPO Hazards",
        registration_number="E05-33333",
        hazard_class=HazardClass.HAZARD_CLASS_1,
        address="ул. Опасная, 7",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        registration_date="2024-01-15",
    )

    sign1 = db.execute(select(HazardSign).where(HazardSign.code == "explosive")).scalar_one()
    sign2 = db.execute(select(HazardSign).where(HazardSign.code == "toxic")).scalar_one()

    db.add(OPOHazardSign(opo_id=opo.id, hazard_sign_id=sign1.id))
    db.add(OPOHazardSign(opo_id=opo.id, hazard_sign_id=sign2.id))
    db.commit()

    assigned = set(
        db.scalars(select(OPOHazardSign.hazard_sign_id).where(OPOHazardSign.opo_id == opo.id)).all()
    )
    assert assigned == {sign1.id, sign2.id}


# ---------------------------------------------------------------------------
# Invariant 8 – OPO ↔ activity types N:M
# ---------------------------------------------------------------------------
def test_opo_activity_types_nm(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Activity")
    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="OPO Activities",
        registration_number="F06-44444",
        hazard_class=HazardClass.HAZARD_CLASS_3,
        address="ул. Деятельная, 2",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        registration_date="2024-01-15",
    )

    at1 = db.execute(select(ActivityType).where(ActivityType.code == "production")).scalar_one()
    at2 = db.execute(select(ActivityType).where(ActivityType.code == "storage")).scalar_one()

    db.add(OPOActivityType(opo_id=opo.id, activity_type_id=at1.id))
    db.add(OPOActivityType(opo_id=opo.id, activity_type_id=at2.id))
    db.commit()

    assigned = set(
        db.scalars(
            select(OPOActivityType.activity_type_id).where(OPOActivityType.opo_id == opo.id)
        ).all()
    )
    assert assigned == {at1.id, at2.id}


# ---------------------------------------------------------------------------
# Invariant 9 – Technical Device Type works correctly
# ---------------------------------------------------------------------------
def test_technical_device_type_persisted(
    db: Session,
    org_service: OrganizationService,
    td_service: TechnicalDeviceService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Test Device Types")
    device = td_service.create_technical_device(
        db,
        actor_id=actor.id,
        name="Котёл К-100",
        device_type=TechDeviceType.PRESSURE_VESSEL,
        opo_id=None,
        organization_id=org.id,
    )
    raw = db.execute(
        text("select device_type::text from technical_devices where id = :id"),
        {"id": device.id},
    ).scalar_one()
    assert raw == "pressure_vessel"


# ---------------------------------------------------------------------------
# Invariant 10 – Building Type works correctly
# ---------------------------------------------------------------------------
def test_building_type_persisted(
    db: Session,
    org_service: OrganizationService,
    building_service: BuildingService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "OOO Test Building Types")
    building = building_service.create_building(
        db,
        actor_id=actor.id,
        name="Склад С-1",
        building_type=BldgType.WAREHOUSE,
        opo_id=None,
        organization_id=org.id,
    )
    raw = db.execute(
        text("select building_type::text from buildings where id = :id"),
        {"id": building.id},
    ).scalar_one()
    assert raw == "warehouse"


# ---------------------------------------------------------------------------
# Invariant 11 – Custom Field definitions and values work
# ---------------------------------------------------------------------------
def test_custom_field_definition_and_value(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    cf_service: CustomFieldService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "CF Test Org")
    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="CfOpo",
        registration_number="CF-001",
        hazard_class=HazardClass.HAZARD_CLASS_2,
        address="Test",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        registration_date="2024-01-15",
    )
    definition = cf_service.create_definition(
        db,
        actor_id=actor.id,
        code="field_comment",
        name="Комментарий",
        entity_type="opo",
        field_type="text",
    )
    assert definition.id is not None
    assert definition.code == "field_comment"

    value = cf_service.set_value(
        db,
        actor_id=actor.id,
        field_definition_id=definition.id,
        entity_type="opo",
        entity_id=opo.id,
        value="Тестовый комментарий",
    )
    assert value.id is not None
    assert value.value_text == "Тестовый комментарий"


# ---------------------------------------------------------------------------
# Invariant 12 – Custom field value uniqueness
# ---------------------------------------------------------------------------
def test_custom_field_value_unique_constraint(
    db: Session,
    org_service: OrganizationService,
    opo_service: OPOService,
    cf_service: CustomFieldService,
    actor: User,
) -> None:
    org = _create_org(db, org_service, actor, "CF Test Org 2")
    opo = opo_service.create_opo(
        db,
        actor_id=actor.id,
        name="CfOpo2",
        registration_number="CF-002",
        hazard_class=HazardClass.HAZARD_CLASS_2,
        address="Test",
        owner_organization_id=org.id,
        operating_organization_id=org.id,
        registration_date="2024-01-15",
    )
    definition = cf_service.create_definition(
        db,
        actor_id=actor.id,
        code="field_priority",
        name="Приоритет",
        entity_type="opo",
        field_type="text",
    )
    entity_id = opo.id

    cf_service.set_value(
        db,
        actor_id=actor.id,
        field_definition_id=definition.id,
        entity_type="opo",
        entity_id=entity_id,
        value="Высокий",
    )

    with pytest.raises(CustomFieldConflictError):
        cf_service.set_value(
            db,
            actor_id=actor.id,
            field_definition_id=definition.id,
            entity_type="opo",
            entity_id=entity_id,
            value="Низкий",
        )
