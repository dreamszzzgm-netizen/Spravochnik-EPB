import uuid
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.lifecycle import ContractLifecycleService
from app.modules.contracts.service import ContractService, ContractValidationError
from app.modules.identity.models import AuditEvent
from app.modules.organizations.models import Organization, OrganizationType

pytestmark = pytest.mark.integration

REQUIRED_PROVIDER_KEYS = (
    "tasks",
    "expertises",
    "documents",
    "conclusion_delivery",
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


def _satisfied_providers():
    from app.modules.contracts.readiness import CompletionCheck

    class SatisfiedProvider:
        def __init__(self, key: str) -> None:
            self.key = key

        def check(self, db: Session, contract) -> CompletionCheck:
            return CompletionCheck(key=self.key, passed=True, blockers=())

    return {key: SatisfiedProvider(key) for key in REQUIRED_PROVIDER_KEYS}


def test_default_readiness_fails_closed_with_four_provider_blockers(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="READINESS-DEFAULT")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)

    readiness = ContractLifecycleService().get_completion_readiness(
        db_session,
        contract=contract,
    )

    assert readiness.ready_to_complete is False
    assert tuple(check.key for check in readiness.checks) == REQUIRED_PROVIDER_KEYS
    assert tuple(blocker.code for blocker in readiness.blockers) == (
        "tasks_provider_unavailable",
        "expertises_provider_unavailable",
        "documents_provider_unavailable",
        "conclusion_delivery_provider_unavailable",
    )
    assert all(check.passed is False for check in readiness.checks)
    assert all(len(check.blockers) == 1 for check in readiness.checks)


def test_readiness_passes_with_four_satisfied_injected_providers(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="READINESS-PASS")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)

    lifecycle = ContractLifecycleService(readiness_providers=_satisfied_providers())
    readiness = lifecycle.get_completion_readiness(db_session, contract=contract)

    assert readiness.ready_to_complete is True
    assert tuple(check.key for check in readiness.checks) == REQUIRED_PROVIDER_KEYS
    assert readiness.blockers == ()
    assert all(check.passed is True for check in readiness.checks)


def test_complete_rechecks_readiness_and_rejects_new_blocker(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    from app.modules.contracts.readiness import CompletionBlocker, CompletionCheck

    class MutableProvider:
        def __init__(self, key: str) -> None:
            self.key = key
            self.passed = True

        def check(self, db: Session, contract) -> CompletionCheck:
            if self.passed:
                return CompletionCheck(key=self.key, passed=True, blockers=())
            return CompletionCheck(
                key=self.key,
                passed=False,
                blockers=(
                    CompletionBlocker(
                        code=f"{self.key}_not_ready",
                        detail=f"{self.key} became not ready",
                    ),
                ),
            )

    providers = {key: MutableProvider(key) for key in REQUIRED_PROVIDER_KEYS}
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="COMPLETE-RECHECK")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    lifecycle = ContractLifecycleService(readiness_providers=providers)
    actor_id = _actor_id(test_user)

    first = lifecycle.get_completion_readiness(db_session, contract=contract)
    assert first.ready_to_complete is True

    providers["tasks"].passed = False
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.completed")

    with pytest.raises(ContractValidationError):
        lifecycle.complete(
            db_session,
            actor_id=actor_id,
            contract=contract,
        )

    db_session.refresh(contract)
    assert contract.status == ContractStatus.IN_PROGRESS
    assert contract.version == before_version
    assert _audit_count(db_session, "contract.completed") == before_audit


def test_complete_allows_in_progress_with_satisfied_providers(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="COMPLETE-PASS")
    _set_status(db_session, contract, ContractStatus.IN_PROGRESS)
    lifecycle = ContractLifecycleService(readiness_providers=_satisfied_providers())
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.completed")

    result = lifecycle.complete(
        db_session,
        actor_id=_actor_id(test_user),
        contract=contract,
    )

    assert result.status == ContractStatus.COMPLETED
    assert result.version == before_version + 1
    assert _audit_count(db_session, "contract.completed") == before_audit + 1


def test_complete_rejects_non_in_progress_contract(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    customer = _organization(db_session)
    contract = _contract(db_session, test_user, customer, number="COMPLETE-STATUS")
    _set_status(db_session, contract, ContractStatus.SIGNED)
    lifecycle = ContractLifecycleService(readiness_providers=_satisfied_providers())
    before_version = contract.version
    before_audit = _audit_count(db_session, "contract.completed")

    with pytest.raises(ContractValidationError):
        lifecycle.complete(
            db_session,
            actor_id=_actor_id(test_user),
            contract=contract,
        )

    db_session.refresh(contract)
    assert contract.status == ContractStatus.SIGNED
    assert contract.version == before_version
    assert _audit_count(db_session, "contract.completed") == before_audit
