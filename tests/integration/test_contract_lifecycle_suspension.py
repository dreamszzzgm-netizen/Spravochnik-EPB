import uuid
from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.lifecycle import ContractLifecycleService
from app.modules.contracts.models import ContractSuspension
from app.modules.contracts.service import ContractService, ContractValidationError
from app.modules.identity.models import AuditEvent
from app.modules.organizations.models import Organization, OrganizationType

pytestmark = pytest.mark.integration


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
    *,
    number: str,
):
    return ContractService().create_contract(
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


def _set_status(db: Session, contract, status: ContractStatus) -> None:
    contract.status = status
    db.commit()
    db.refresh(contract)


def _audit_count(db: Session, action: str) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(AuditEvent).where(AuditEvent.action == action)
        )
        or 0
    )


def _suspension_count(db: Session, contract_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count())
            .select_from(ContractSuspension)
            .where(ContractSuspension.contract_id == contract_id)
        )
        or 0
    )


def test_suspend_requires_in_progress_and_reason(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="SUSPEND-VALIDATE")
    lifecycle = ContractLifecycleService()
    actor_id = _actor_id(test_user)

    _set_status(db_session, contract, ContractStatus.SIGNED)
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.suspended")

    with pytest.raises(ContractValidationError):
        lifecycle.suspend(
            db_session,
            actor_id=actor_id,
            contract=contract,
            reason="Техническая пауза",
        )

    db_session.refresh(contract)
    assert contract.status == ContractStatus.SIGNED
    assert contract.version == before_version
    assert _suspension_count(db_session, contract.id) == 0
    assert _audit_count(db_session, "contract.suspended") == before_audit

    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.suspended")

    with pytest.raises(ContractValidationError):
        lifecycle.suspend(
            db_session,
            actor_id=actor_id,
            contract=contract,
            reason="   ",
        )

    db_session.refresh(contract)
    assert contract.status == ContractStatus.IN_PROGRESS
    assert contract.version == before_version
    assert _suspension_count(db_session, contract.id) == 0
    assert _audit_count(db_session, "contract.suspended") == before_audit


def test_suspend_creates_one_open_interval(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="SUSPEND-OPEN")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    lifecycle = ContractLifecycleService()
    actor_id = _actor_id(test_user)
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.suspended")

    suspension = lifecycle.suspend(
        db_session,
        actor_id=actor_id,
        contract=contract,
        reason="  Ожидание заказчика  ",
    )

    assert contract.status == ContractStatus.SUSPENDED
    assert contract.version == before_version + 1
    assert suspension.contract_id == contract.id
    assert suspension.reason == "Ожидание заказчика"
    assert suspension.ended_at is None
    assert suspension.created_by == actor_id
    assert suspension.started_at.tzinfo is not None
    assert _suspension_count(db_session, contract.id) == 1
    assert _audit_count(db_session, "contract.suspended") == before_audit + 1


def test_second_open_suspension_is_rejected_by_service(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="SUSPEND-DUP-SVC")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    lifecycle = ContractLifecycleService()
    actor_id = _actor_id(test_user)

    lifecycle.suspend(
        db_session,
        actor_id=actor_id,
        contract=contract,
        reason="Первая пауза",
    )
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.suspended")

    with pytest.raises(ContractValidationError):
        lifecycle.suspend(
            db_session,
            actor_id=actor_id,
            contract=contract,
            reason="Вторая пауза",
        )

    db_session.refresh(contract)
    assert contract.status == ContractStatus.IN_PROGRESS
    assert contract.version == before_version
    assert _suspension_count(db_session, contract.id) == 1
    assert _audit_count(db_session, "contract.suspended") == before_audit


def test_second_open_suspension_is_rejected_by_database(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="SUSPEND-DUP-DB")
    actor_id = _actor_id(test_user)

    first = ContractSuspension(
        contract_id=contract.id,
        started_at=datetime.now(UTC),
        ended_at=None,
        reason="Первая",
        created_by=actor_id,
    )
    db_session.add(first)
    db_session.flush()
    second = ContractSuspension(
        contract_id=contract.id,
        started_at=datetime.now(UTC),
        ended_at=None,
        reason="Вторая",
        created_by=actor_id,
    )
    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_resume_requires_suspended_and_open_interval(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="RESUME-VALIDATE")
    lifecycle = ContractLifecycleService()
    actor_id = _actor_id(test_user)

    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.resumed")
    with pytest.raises(ContractValidationError):
        lifecycle.resume(db_session, actor_id=actor_id, contract=contract)
    db_session.refresh(contract)
    assert contract.status == ContractStatus.IN_PROGRESS
    assert contract.version == before_version
    assert _audit_count(db_session, "contract.resumed") == before_audit

    _set_status(db_session, contract, ContractStatus.SUSPENDED)
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.resumed")
    with pytest.raises(ContractValidationError):
        lifecycle.resume(db_session, actor_id=actor_id, contract=contract)
    db_session.refresh(contract)
    assert contract.status == ContractStatus.SUSPENDED
    assert contract.version == before_version
    assert _audit_count(db_session, "contract.resumed") == before_audit


def test_resume_closes_interval_and_restores_in_progress(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="RESUME-CLOSE")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    lifecycle = ContractLifecycleService()
    actor_id = _actor_id(test_user)
    suspension = lifecycle.suspend(
        db_session,
        actor_id=actor_id,
        contract=contract,
        reason="Пауза",
    )
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.resumed")

    closed = lifecycle.resume(db_session, actor_id=actor_id, contract=contract)

    assert closed.id == suspension.id
    assert closed.ended_at is not None
    assert closed.ended_at.tzinfo is not None
    assert contract.status == ContractStatus.IN_PROGRESS
    assert contract.version == before_version + 1
    assert _audit_count(db_session, "contract.resumed") == before_audit + 1


def test_terminate_requires_dedicated_domain_command_and_reason(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    lifecycle = ContractLifecycleService()
    actor_id = _actor_id(test_user)

    draft = _contract(db_session, test_user, customer, number="TERMINATE-DRAFT")
    before_version = draft.version
    before_audit = _audit_count(db_session, "contract.terminated")
    with pytest.raises(ContractValidationError):
        lifecycle.terminate(
            db_session,
            actor_id=actor_id,
            contract=draft,
            reason="Расторжение",
        )
    db_session.refresh(draft)
    assert draft.status == ContractStatus.DRAFT
    assert draft.version == before_version
    assert _audit_count(db_session, "contract.terminated") == before_audit

    signed = _contract(db_session, test_user, customer, number="TERMINATE-REASON")
    _set_status(db_session, signed, ContractStatus.SIGNED)
    before_version = signed.version
    before_audit = _audit_count(db_session, "contract.terminated")
    with pytest.raises(ContractValidationError):
        lifecycle.terminate(
            db_session,
            actor_id=actor_id,
            contract=signed,
            reason="   ",
        )
    db_session.refresh(signed)
    assert signed.status == ContractStatus.SIGNED
    assert signed.version == before_version
    assert _audit_count(db_session, "contract.terminated") == before_audit


def test_terminate_from_suspended_closes_open_interval(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="TERMINATE-SUSPENDED")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    lifecycle = ContractLifecycleService()
    actor_id = _actor_id(test_user)
    suspension = lifecycle.suspend(
        db_session,
        actor_id=actor_id,
        contract=contract,
        reason="Пауза до расторжения",
    )
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.terminated")

    result = lifecycle.terminate(
        db_session,
        actor_id=actor_id,
        contract=contract,
        reason="  Решение заказчика  ",
    )

    db_session.refresh(suspension)
    assert result.status == ContractStatus.TERMINATED
    assert result.version == before_version + 1
    assert suspension.ended_at is not None
    assert _audit_count(db_session, "contract.terminated") == before_audit + 1
