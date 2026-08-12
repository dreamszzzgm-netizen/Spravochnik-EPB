import uuid
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus, ContractStatus
from app.modules.contracts.models import ContractAddendum
from app.modules.contracts.service import ContractService, ContractValidationError
from app.modules.identity.models import AuditEvent
from app.modules.organizations.models import Organization, OrganizationType
from app.modules.technical_devices.models import TechnicalDevice, TechnicalDeviceType

pytestmark = pytest.mark.integration

TECHNICAL_DEVICE_EXPERTISE_TYPE_ID = uuid.UUID(
    "c79c5348-2ee9-53a6-9417-224e63de5a74"
)


def _actor_id(test_user: dict[str, object]) -> uuid.UUID:
    return uuid.UUID(str(test_user["id"]))


def _organization(db: Session) -> Organization:
    organization = Organization(
        legal_name="ООО Заказчик",
        short_name="Заказчик",
        organization_type=OrganizationType.LEGAL_ENTITY,
    )
    db.add(organization)
    db.flush()
    return organization


def _contract(
    db: Session,
    test_user: dict[str, object],
    organization: Organization,
    *,
    number: str,
    status: ContractStatus = ContractStatus.SIGNED,
    base_amount: Decimal = Decimal("100000.00"),
):
    contract = ContractService().create_contract(
        db,
        actor_id=_actor_id(test_user),
        customer_organization_id=organization.id,
        customer_contact_id=None,
        number=number,
        contract_date=date(2026, 8, 11),
        start_date=date(2026, 8, 12),
        end_date=date(2026, 9, 30),
        comment=None,
    )
    device = TechnicalDevice(
        name=f"Сосуд {number}",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=organization.id,
    )
    db.add(device)
    db.flush()
    ContractService().create_item(
        db,
        actor_id=_actor_id(test_user),
        contract=contract,
        name="ЭПБ сосуда",
        expertise_type_id=TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
        price=base_amount,
        technical_device_ids=[device.id],
        building_ids=[],
        comment=None,
    )
    contract.status = status
    contract.original_end_date = contract.end_date if status != ContractStatus.DRAFT else None
    db.commit()
    db.refresh(contract)
    return contract


def _service():
    from app.modules.contracts.addenda import ContractAddendumService

    return ContractAddendumService()


def _audit_count(db: Session, action: str) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(AuditEvent).where(AuditEvent.action == action)
        )
        or 0
    )


def _create_addendum(
    db: Session,
    test_user: dict[str, object],
    contract,
    *,
    number: str = "ДС-1",
    amount_delta: Decimal | None = Decimal("25000.00"),
    new_end_date: date | None = None,
    description: str | None = None,
):
    return _service().create_addendum(
        db,
        actor_id=_actor_id(test_user),
        contract=contract,
        number=number,
        addendum_date=date(2026, 8, 20),
        amount_delta=amount_delta,
        new_end_date=new_end_date,
        description=description,
    )


def test_addendum_create_allowed_only_for_signed_active_parent_statuses(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    for index, parent_status in enumerate(
        (ContractStatus.SIGNED, ContractStatus.IN_PROGRESS, ContractStatus.SUSPENDED),
        start=1,
    ):
        contract = _contract(
            db_session,
            test_user,
            customer,
            number=f"ALLOWED-{index}",
            status=parent_status,
        )
        addendum = _create_addendum(
            db_session,
            test_user,
            contract,
            number=f"ДС-{index}",
        )
        assert addendum.status == ContractAddendumStatus.DRAFT
        assert addendum.currency == contract.currency
        assert addendum.created_by == _actor_id(test_user)
        assert addendum.updated_by == _actor_id(test_user)

    draft = _contract(
        db_session,
        test_user,
        customer,
        number="DRAFT-PARENT",
        status=ContractStatus.DRAFT,
    )
    before_audit = _audit_count(db_session, "contract_addendum.created")
    with pytest.raises(ContractValidationError):
        _create_addendum(db_session, test_user, draft, number="ДС-DRAFT")
    assert _audit_count(db_session, "contract_addendum.created") == before_audit


def test_addendum_edit_delete_allowed_only_before_terminal_status(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="EDIT-DELETE")
    service = _service()
    addendum = _create_addendum(db_session, test_user, contract)

    updated = service.update_addendum(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
        addendum=addendum,
        number="ДС-1А",
        addendum_date=date(2026, 8, 21),
        amount_delta=Decimal("30000.00"),
        new_end_date=None,
        description="Уточнение",
    )
    assert updated.number == "ДС-1А"
    assert updated.amount_delta == Decimal("30000.00")

    updated.status = ContractAddendumStatus.SIGNED
    db_session.commit()
    before_version = updated.version
    with pytest.raises(ContractValidationError):
        service.update_addendum(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            addendum=updated,
            number="НЕ МЕНЯТЬ",
            addendum_date=updated.addendum_date,
            amount_delta=updated.amount_delta,
            new_end_date=updated.new_end_date,
            description=updated.description,
        )
    with pytest.raises(ContractValidationError):
        service.delete_addendum(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
            addendum=updated,
        )
    db_session.refresh(updated)
    assert updated.version == before_version
    assert updated.deleted_at is None


def test_addendum_transition_matrix(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    service = _service()
    actor_id = _actor_id(test_user)

    contract = _contract(db_session, test_user, customer, number="TRANSITIONS")
    approved = _create_addendum(db_session, test_user, contract, number="ДС-A")
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=approved,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    assert approved.status == ContractAddendumStatus.APPROVAL
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=approved,
        target_status=ContractAddendumStatus.SIGNED,
    )
    assert approved.status == ContractAddendumStatus.SIGNED
    assert approved.signed_at is not None

    cancelled_draft = _create_addendum(
        db_session, test_user, contract, number="ДС-CANCEL-DRAFT"
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=cancelled_draft,
        target_status=ContractAddendumStatus.CANCELLED,
    )
    assert cancelled_draft.status == ContractAddendumStatus.CANCELLED

    cancelled_approval = _create_addendum(
        db_session, test_user, contract, number="ДС-CANCEL-APPROVAL"
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=cancelled_approval,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=cancelled_approval,
        target_status=ContractAddendumStatus.CANCELLED,
    )
    assert cancelled_approval.status == ContractAddendumStatus.CANCELLED

    with pytest.raises(ContractValidationError):
        service.change_status(
            db_session,
            actor_id=actor_id,
            contract=contract,
            addendum=approved,
            target_status=ContractAddendumStatus.CANCELLED,
        )


def test_signed_addenda_recalculate_amount_and_effective_deadline(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="COMMERCIAL")
    service = _service()
    actor_id = _actor_id(test_user)
    assert contract.amount == Decimal("100000.00")
    assert contract.original_end_date == date(2026, 9, 30)

    first = _create_addendum(
        db_session,
        test_user,
        contract,
        number="ДС-PLUS",
        amount_delta=Decimal("25000.00"),
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=first,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=first,
        target_status=ContractAddendumStatus.SIGNED,
    )
    assert contract.amount == Decimal("125000.00")

    second = _create_addendum(
        db_session,
        test_user,
        contract,
        number="ДС-MINUS-DEADLINE",
        amount_delta=Decimal("-10000.00"),
        new_end_date=date(2026, 12, 31),
        description="Заказчик продлил срок выполнения работ",
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=second,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=second,
        target_status=ContractAddendumStatus.SIGNED,
    )

    assert contract.amount == Decimal("115000.00")
    assert contract.original_end_date == date(2026, 9, 30)
    assert contract.end_date == date(2026, 12, 31)


def test_negative_projected_effective_amount_is_rejected_atomically(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="NEGATIVE")
    service = _service()
    actor_id = _actor_id(test_user)
    addendum = _create_addendum(
        db_session,
        test_user,
        contract,
        amount_delta=Decimal("-100000.01"),
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=addendum,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    before_contract_version = contract.version
    before_addendum_version = addendum.version
    before_audit = _audit_count(db_session, "contract_addendum.signed")

    with pytest.raises(ContractValidationError):
        service.change_status(
            db_session,
            actor_id=actor_id,
            contract=contract,
            addendum=addendum,
            target_status=ContractAddendumStatus.SIGNED,
        )

    db_session.refresh(contract)
    db_session.refresh(addendum)
    assert contract.amount == Decimal("100000.00")
    assert contract.end_date == date(2026, 9, 30)
    assert contract.version == before_contract_version
    assert addendum.status == ContractAddendumStatus.APPROVAL
    assert addendum.signed_at is None
    assert addendum.version == before_addendum_version
    assert _audit_count(db_session, "contract_addendum.signed") == before_audit


def test_deadline_extension_requires_description_reason(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="EXTENSION")
    service = _service()
    actor_id = _actor_id(test_user)
    addendum = _create_addendum(
        db_session,
        test_user,
        contract,
        amount_delta=None,
        new_end_date=date(2026, 10, 31),
        description="   ",
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=addendum,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    with pytest.raises(ContractValidationError):
        service.change_status(
            db_session,
            actor_id=actor_id,
            contract=contract,
            addendum=addendum,
            target_status=ContractAddendumStatus.SIGNED,
        )
    db_session.refresh(contract)
    db_session.refresh(addendum)
    assert contract.end_date == date(2026, 9, 30)
    assert addendum.status == ContractAddendumStatus.APPROVAL


def test_addendum_without_effect_cannot_sign(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="NO-EFFECT")
    service = _service()
    actor_id = _actor_id(test_user)
    addendum = _create_addendum(
        db_session,
        test_user,
        contract,
        amount_delta=Decimal("0.00"),
        new_end_date=None,
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=addendum,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    with pytest.raises(ContractValidationError):
        service.change_status(
            db_session,
            actor_id=actor_id,
            contract=contract,
            addendum=addendum,
            target_status=ContractAddendumStatus.SIGNED,
        )


def test_signing_retry_does_not_double_apply_effect(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="IDEMPOTENT")
    service = _service()
    actor_id = _actor_id(test_user)
    addendum = _create_addendum(
        db_session,
        test_user,
        contract,
        amount_delta=Decimal("25000.00"),
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=addendum,
        target_status=ContractAddendumStatus.APPROVAL,
    )
    service.change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=addendum,
        target_status=ContractAddendumStatus.SIGNED,
    )
    amount_after_sign = contract.amount
    audit_after_sign = _audit_count(db_session, "contract_addendum.signed")

    with pytest.raises(ContractValidationError):
        service.change_status(
            db_session,
            actor_id=actor_id,
            contract=contract,
            addendum=addendum,
            target_status=ContractAddendumStatus.SIGNED,
        )
    db_session.refresh(contract)
    assert contract.amount == amount_after_sign == Decimal("125000.00")
    assert _audit_count(db_session, "contract_addendum.signed") == audit_after_sign


def test_signed_addenda_history_has_deterministic_order(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    from app.modules.contracts.repository import list_signed_contract_addenda

    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="HISTORY")
    actor_id = _actor_id(test_user)
    rows = [
        ContractAddendum(
            contract_id=contract.id,
            number=f"ДС-{index}",
            addendum_date=date(2026, 8, 20 + index),
            status=ContractAddendumStatus.SIGNED,
            amount_delta=Decimal("1.00"),
            currency="RUB",
            signed_at=sa.func.now(),
            created_by=actor_id,
            updated_by=actor_id,
        )
        for index in range(3)
    ]
    db_session.add_all(rows)
    db_session.commit()

    history = list_signed_contract_addenda(db_session, contract.id)
    assert [row.id for row in history] == sorted(
        [row.id for row in rows],
        key=str,
    )
