import uuid
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus, ContractStatus
from app.modules.contracts.models import ContractAddendum, ContractItem, ContractResponsible
from app.modules.contracts.service import ContractService, ContractValidationError
from app.modules.identity.models import AuditEvent, Employee
from app.modules.organizations.models import Organization, OrganizationType
from app.modules.technical_devices.models import TechnicalDevice, TechnicalDeviceType

pytestmark = pytest.mark.integration

TECHNICAL_DEVICE_EXPERTISE_TYPE_ID = uuid.UUID(
    "c79c5348-2ee9-53a6-9417-224e63de5a74"
)


def _actor_id(test_user: dict[str, object]) -> uuid.UUID:
    return uuid.UUID(str(test_user["id"]))


def _organization(db: Session, name: str = "ООО Заказчик") -> Organization:
    organization = Organization(
        legal_name=name,
        short_name=name[:30],
        organization_type=OrganizationType.LEGAL_ENTITY,
    )
    db.add(organization)
    db.flush()
    return organization


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


def _device(db: Session, organization: Organization) -> TechnicalDevice:
    device = TechnicalDevice(
        name="Сосуд №1",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=organization.id,
    )
    db.add(device)
    db.flush()
    return device


def _employee(db: Session, name: str = "Ответственный") -> Employee:
    employee = Employee(full_name=name)
    db.add(employee)
    db.flush()
    return employee


def _item(
    db: Session,
    test_user: dict[str, object],
    contract,
    device: TechnicalDevice,
) -> ContractItem:
    return ContractService().create_item(
        db,
        actor_id=_actor_id(test_user),
        contract=contract,
        name="ЭПБ сосуда",
        expertise_type_id=TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
        price=Decimal("100.00"),
        technical_device_ids=[device.id],
        building_ids=[],
        comment=None,
    )


def _audit_count(db: Session, action: str) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(AuditEvent).where(AuditEvent.action == action)
        )
        or 0
    )


def test_signed_contract_rejects_item_create_update_delete(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer)
    device = _device(db_session, customer)
    item = _item(db_session, test_user, contract, device)
    service = ContractService()

    contract.status = ContractStatus.SIGNED
    db_session.commit()

    before_amount = contract.amount
    before_item_version = item.version
    before_create_audit = _audit_count(db_session, "contract_item.created")
    before_update_audit = _audit_count(db_session, "contract_item.updated")
    before_delete_audit = _audit_count(db_session, "contract_item.deleted")

    with pytest.raises(ContractValidationError):
        service.create_item(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            name="Новый предмет после подписания",
            expertise_type_id=TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
            price=Decimal("50.00"),
            technical_device_ids=[device.id],
            building_ids=[],
            comment=None,
        )

    with pytest.raises(ContractValidationError):
        service.update_item(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            item=item,
            name=item.name,
            expertise_type_id=item.expertise_type_id,
            price=Decimal("200.00"),
            technical_device_ids=[device.id],
            building_ids=[],
            comment=item.comment,
        )

    with pytest.raises(ContractValidationError):
        service.delete_item(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            item=item,
        )

    db_session.refresh(contract)
    db_session.refresh(item)
    assert contract.amount == before_amount
    assert item.price == Decimal("100.00")
    assert item.version == before_item_version
    assert item.deleted_at is None
    assert _audit_count(db_session, "contract_item.created") == before_create_audit
    assert _audit_count(db_session, "contract_item.updated") == before_update_audit
    assert _audit_count(db_session, "contract_item.deleted") == before_delete_audit


def test_signed_contract_rejects_legal_term_changes_but_allows_comment_change(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer)
    service = ContractService()
    contract.status = ContractStatus.SIGNED
    db_session.commit()

    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.updated")

    with pytest.raises(ContractValidationError):
        service.update_contract(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            customer_organization_id=contract.customer_organization_id,
            customer_contact_id=contract.customer_contact_id,
            number="43/2026",
            contract_date=contract.contract_date,
            start_date=contract.start_date,
            end_date=contract.end_date,
            comment=contract.comment,
        )

    db_session.refresh(contract)
    assert contract.number == "42/2026"
    assert contract.version == before_version
    assert _audit_count(db_session, "contract.updated") == before_audit

    updated = service.update_contract(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        customer_organization_id=contract.customer_organization_id,
        customer_contact_id=contract.customer_contact_id,
        number=contract.number,
        contract_date=contract.contract_date,
        start_date=contract.start_date,
        end_date=contract.end_date,
        comment="Разрешённый комментарий",
    )
    assert updated.comment == "Разрешённый комментарий"
    assert updated.version == before_version + 1


def test_contract_delete_allowed_only_draft_or_approval(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    service = ContractService()

    draft = _contract(db_session, test_user, customer)
    service.delete_contract(db_session, actor_id=_actor_id(test_user), contract=draft)
    assert draft.deleted_at is not None

    approval = _contract(db_session, test_user, customer)
    approval.number = "43/2026"
    approval.status = ContractStatus.APPROVAL
    db_session.commit()
    service.delete_contract(db_session, actor_id=_actor_id(test_user), contract=approval)
    assert approval.deleted_at is not None

    signed = _contract(db_session, test_user, customer)
    signed.number = "44/2026"
    signed.status = ContractStatus.SIGNED
    db_session.commit()
    before_version = signed.version
    before_audit = _audit_count(db_session, "contract.deleted")

    with pytest.raises(ContractValidationError):
        service.delete_contract(db_session, actor_id=_actor_id(test_user), contract=signed)

    db_session.refresh(signed)
    assert signed.deleted_at is None
    assert signed.version == before_version
    assert _audit_count(db_session, "contract.deleted") == before_audit


def test_responsibles_frozen_only_in_terminal_statuses(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer)
    employee = _employee(db_session)
    service = ContractService()

    for mutable_status in (
        ContractStatus.DRAFT,
        ContractStatus.APPROVAL,
        ContractStatus.SIGNED,
        ContractStatus.IN_PROGRESS,
        ContractStatus.SUSPENDED,
    ):
        contract.status = mutable_status
        db_session.commit()
        assert service.replace_responsibles(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            employee_ids=[employee.id],
        ) == [employee.id]

    for terminal_status in (
        ContractStatus.COMPLETED,
        ContractStatus.TERMINATED,
        ContractStatus.ARCHIVED,
    ):
        contract.status = terminal_status
        db_session.commit()
        before_audit = _audit_count(db_session, "contract.responsibles_updated")
        before_ids = set(
            db_session.scalars(
                sa.select(ContractResponsible.employee_id).where(
                    ContractResponsible.contract_id == contract.id
                )
            ).all()
        )
        with pytest.raises(ContractValidationError):
            service.replace_responsibles(
                db_session,
                actor_id=_actor_id(test_user),
                contract=contract,
                employee_ids=[],
            )
        assert set(
            db_session.scalars(
                sa.select(ContractResponsible.employee_id).where(
                    ContractResponsible.contract_id == contract.id
                )
            ).all()
        ) == before_ids
        assert _audit_count(db_session, "contract.responsibles_updated") == before_audit


def test_effective_amount_includes_signed_addendum_delta(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    from app.modules.contracts.commercial import calculate_effective_amount

    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer)
    device = _device(db_session, customer)
    _item(db_session, test_user, contract, device)
    actor_id = _actor_id(test_user)

    db_session.add(
        ContractAddendum(
            contract_id=contract.id,
            number="ДС-1",
            addendum_date=date(2026, 8, 20),
            status=ContractAddendumStatus.SIGNED,
            amount_delta=Decimal("25.50"),
            currency="RUB",
            created_by=actor_id,
            updated_by=actor_id,
        )
    )
    db_session.commit()

    assert calculate_effective_amount(db_session, contract.id) == Decimal("125.50")


def test_contract_count_helpers(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    from app.modules.contracts.repository import (
        count_active_contract_items,
        count_contract_responsibles,
    )

    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer)
    device = _device(db_session, customer)
    _item(db_session, test_user, contract, device)
    employee = _employee(db_session)
    ContractService().replace_responsibles(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        employee_ids=[employee.id],
    )

    assert count_active_contract_items(db_session, contract.id) == 1
    assert count_contract_responsibles(db_session, contract.id) == 1
