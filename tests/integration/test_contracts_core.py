import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building, BuildingType
from app.modules.contracts.models import (
    ContractItemBuilding,
    ContractItemTechnicalDevice,
    ContractResponsible,
    ContractStatus,
)
from app.modules.contracts.service import ContractService, ContractValidationError
from app.modules.identity.models import AuditEvent, Employee
from app.modules.organizations.models import (
    ContactType,
    Organization,
    OrganizationContact,
    OrganizationType,
)
from app.modules.technical_devices.models import TechnicalDevice, TechnicalDeviceType

pytestmark = pytest.mark.integration

BUILDING_EXPERTISE_TYPE_ID = uuid.UUID("0312543b-b525-530e-ac8d-efa8e8b2391d")
TECHNICAL_DEVICE_EXPERTISE_TYPE_ID = uuid.UUID(
    "c79c5348-2ee9-53a6-9417-224e63de5a74"
)


def _actor_id(test_user: dict[str, object]) -> uuid.UUID:
    return uuid.UUID(str(test_user["id"]))


def _organization(db: Session, name: str) -> Organization:
    organization = Organization(
        legal_name=name,
        short_name=name[:30],
        organization_type=OrganizationType.LEGAL_ENTITY,
    )
    db.add(organization)
    db.flush()
    return organization


def _contact(db: Session, organization: Organization, name: str) -> OrganizationContact:
    contact = OrganizationContact(
        organization_id=organization.id,
        contact_type=ContactType.OTHER,
        full_name=name,
        is_primary=False,
    )
    db.add(contact)
    db.flush()
    return contact


def _employee(db: Session, name: str, *, deleted: bool = False) -> Employee:
    employee = Employee(full_name=name)
    if deleted:
        employee.deleted_at = datetime.now(UTC)
    db.add(employee)
    db.flush()
    return employee


def _contract(
    db: Session,
    test_user: dict[str, object],
    organization: Organization,
):
    return ContractService().create_contract(
        db,
        actor_id=_actor_id(test_user),
        customer_organization_id=organization.id,
        customer_contact_id=None,
        number="42/2026",
        contract_date=date(2026, 8, 11),
        start_date=date(2026, 8, 12),
        end_date=date(2026, 9, 30),
        comment=None,
    )


def _audit_count(db: Session, action: str) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(AuditEvent).where(AuditEvent.action == action)
        )
        or 0
    )


def test_create_contract_sets_server_owned_defaults_and_audit(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    organization = _organization(db_session, "ООО Заказчик")
    contact = _contact(db_session, organization, "Иван Иванов")

    contract = ContractService().create_contract(
        db_session,
        actor_id=_actor_id(test_user),
        customer_organization_id=organization.id,
        customer_contact_id=contact.id,
        number="  42/2026  ",
        contract_date=date(2026, 8, 11),
        start_date=date(2026, 8, 12),
        end_date=date(2026, 9, 30),
        comment="Первичный договор",
    )

    assert contract.number == "42/2026"
    assert contract.customer_organization_id == organization.id
    assert contract.customer_contact_id == contact.id
    assert contract.status == ContractStatus.DRAFT
    assert contract.amount == Decimal("0.00")
    assert contract.currency == "RUB"
    assert contract.created_by == _actor_id(test_user)
    assert _audit_count(db_session, "contract.created") == 1


def test_create_contract_rejects_foreign_contact_without_persisting_audit(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session, "ООО Заказчик")
    foreign = _organization(db_session, "ООО Другая")
    foreign_contact = _contact(db_session, foreign, "Чужой контакт")

    with pytest.raises(ContractValidationError):
        ContractService().create_contract(
            db_session,
            actor_id=_actor_id(test_user),
            customer_organization_id=customer.id,
            customer_contact_id=foreign_contact.id,
            number="43/2026",
            contract_date=date(2026, 8, 11),
            start_date=None,
            end_date=None,
            comment=None,
        )

    assert _audit_count(db_session, "contract.created") == 0


def test_create_contract_rejects_blank_number_and_invalid_dates(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session, "ООО Заказчик")
    service = ContractService()

    with pytest.raises(ContractValidationError):
        service.create_contract(
            db_session,
            actor_id=_actor_id(test_user),
            customer_organization_id=customer.id,
            customer_contact_id=None,
            number="   ",
            contract_date=date(2026, 8, 11),
            start_date=None,
            end_date=None,
            comment=None,
        )

    with pytest.raises(ContractValidationError):
        service.create_contract(
            db_session,
            actor_id=_actor_id(test_user),
            customer_organization_id=customer.id,
            customer_contact_id=None,
            number="44/2026",
            contract_date=date(2026, 8, 11),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 9, 30),
            comment=None,
        )

    assert _audit_count(db_session, "contract.created") == 0


def test_replace_responsibles_is_atomic_and_normalizes_duplicates(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session, "ООО Заказчик")
    contract = _contract(db_session, test_user, customer)
    employee_a = _employee(db_session, "Ответственный А")
    employee_b = _employee(db_session, "Ответственный Б")
    deleted_employee = _employee(db_session, "Удалённый", deleted=True)
    service = ContractService()

    result = service.replace_responsibles(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        employee_ids=[employee_b.id, employee_a.id, employee_a.id],
    )

    assert result == sorted([employee_a.id, employee_b.id], key=str)
    rows = db_session.scalars(
        sa.select(ContractResponsible).where(ContractResponsible.contract_id == contract.id)
    ).all()
    assert {row.employee_id for row in rows} == {employee_a.id, employee_b.id}
    before_audit = _audit_count(db_session, "contract.responsibles_updated")

    with pytest.raises(ContractValidationError):
        service.replace_responsibles(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            employee_ids=[deleted_employee.id],
        )

    rows = db_session.scalars(
        sa.select(ContractResponsible).where(ContractResponsible.contract_id == contract.id)
    ).all()
    assert {row.employee_id for row in rows} == {employee_a.id, employee_b.id}
    assert _audit_count(db_session, "contract.responsibles_updated") == before_audit


def test_contract_items_require_subject_and_recalculate_amount(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session, "ООО Заказчик")
    contract = _contract(db_session, test_user, customer)
    device = TechnicalDevice(
        name="Сосуд №1",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=customer.id,
    )
    building = Building(
        name="Здание цеха",
        building_type=BuildingType.INDUSTRIAL,
        organization_id=customer.id,
    )
    db_session.add_all([device, building])
    db_session.flush()
    service = ContractService()

    with pytest.raises(ContractValidationError):
        service.create_item(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            name="Пустой предмет",
            expertise_type_id=TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
            price=Decimal("1.00"),
            technical_device_ids=[],
            building_ids=[],
            comment=None,
        )

    first = service.create_item(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        name="ЭПБ сосуда",
        expertise_type_id=TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
        price=Decimal("125000.10"),
        technical_device_ids=[device.id],
        building_ids=[],
        comment=None,
    )
    assert contract.amount == Decimal("125000.10")

    second = service.create_item(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        name="ЭПБ здания",
        expertise_type_id=BUILDING_EXPERTISE_TYPE_ID,
        price=Decimal("50000.25"),
        technical_device_ids=[],
        building_ids=[building.id],
        comment=None,
    )
    assert contract.amount == Decimal("175000.35")

    updated = service.update_item(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        item=first,
        name="ЭПБ здания вместо сосуда",
        expertise_type_id=BUILDING_EXPERTISE_TYPE_ID,
        price=Decimal("120000.00"),
        technical_device_ids=[],
        building_ids=[building.id],
        comment="Изменён состав",
    )
    assert updated.price == Decimal("120000.00")
    assert contract.amount == Decimal("170000.25")
    assert db_session.scalar(
        sa.select(sa.func.count()).select_from(ContractItemTechnicalDevice).where(
            ContractItemTechnicalDevice.contract_item_id == first.id
        )
    ) == 0
    assert db_session.scalar(
        sa.select(sa.func.count()).select_from(ContractItemBuilding).where(
            ContractItemBuilding.contract_item_id == first.id
        )
    ) == 1

    service.delete_item(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        item=second,
    )
    assert second.deleted_at is not None
    assert contract.amount == Decimal("120000.00")


def test_rejected_item_update_preserves_item_amount_and_audit(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session, "ООО Заказчик")
    contract = _contract(db_session, test_user, customer)
    device = TechnicalDevice(
        name="Сосуд №2",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=customer.id,
    )
    db_session.add(device)
    db_session.flush()
    service = ContractService()

    item = service.create_item(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        name="ЭПБ сосуда",
        expertise_type_id=TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
        price=Decimal("100.00"),
        technical_device_ids=[device.id],
        building_ids=[],
        comment=None,
    )
    before_audit = _audit_count(db_session, "contract_item.updated")

    with pytest.raises(ContractValidationError):
        service.update_item(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            item=item,
            name="Не должно сохраниться",
            expertise_type_id=TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
            price=Decimal("999.00"),
            technical_device_ids=[],
            building_ids=[],
            comment=None,
        )

    db_session.refresh(item)
    db_session.refresh(contract)
    assert item.name == "ЭПБ сосуда"
    assert item.price == Decimal("100.00")
    assert contract.amount == Decimal("100.00")
    assert _audit_count(db_session, "contract_item.updated") == before_audit


def test_contract_soft_delete_and_restore_are_audited(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session, "ООО Заказчик")
    contract = _contract(db_session, test_user, customer)
    service = ContractService()

    service.delete_contract(db_session, actor_id=_actor_id(test_user), contract=contract)
    assert contract.deleted_at is not None
    assert _audit_count(db_session, "contract.deleted") == 1

    service.restore_contract(db_session, actor_id=_actor_id(test_user), contract=contract)
    assert contract.deleted_at is None
    assert _audit_count(db_session, "contract.restored") == 1
