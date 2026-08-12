import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.contracts import repository
from app.modules.contracts.commercial import calculate_effective_amount
from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.models import Contract, ContractSuspension
from app.modules.contracts.readiness import (
    REQUIRED_READINESS_KEYS,
    CompletionReadiness,
    CompletionReadinessProvider,
    default_readiness_providers,
    unavailable_readiness_provider,
)
from app.modules.contracts.service import ContractValidationError
from app.modules.identity.audit import write_audit

ORDINARY_TRANSITIONS: dict[ContractStatus, set[ContractStatus]] = {
    ContractStatus.DRAFT: {ContractStatus.APPROVAL},
    ContractStatus.APPROVAL: {ContractStatus.SIGNED},
    ContractStatus.COMPLETED: {ContractStatus.ARCHIVED},
    ContractStatus.TERMINATED: {ContractStatus.ARCHIVED},
}

TERMINATABLE_STATUSES = {
    ContractStatus.SIGNED,
    ContractStatus.IN_PROGRESS,
    ContractStatus.SUSPENDED,
}


class ContractLifecycleService:
    def __init__(
        self,
        *,
        readiness_providers: Mapping[str, CompletionReadinessProvider] | None = None,
    ) -> None:
        self._readiness_providers = (
            dict(readiness_providers)
            if readiness_providers is not None
            else default_readiness_providers()
        )

    def change_status(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        target_status: ContractStatus,
    ) -> Contract:
        self._require_active_contract(contract)
        source_status = contract.status
        if target_status not in ORDINARY_TRANSITIONS.get(source_status, set()):
            raise ContractValidationError(
                f"Переход договора {source_status.value} -> {target_status.value} недопустим"
            )

        effective_amount = None
        if source_status == ContractStatus.APPROVAL and target_status == ContractStatus.SIGNED:
            effective_amount = self._validate_signing(db, contract)

        if target_status == ContractStatus.SIGNED and contract.original_end_date is None:
            contract.original_end_date = contract.end_date
        if effective_amount is not None:
            contract.amount = effective_amount
        contract.status = target_status
        contract.version += 1

        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.status_changed",
                entity_type="contract",
                entity_id=contract.id,
                summary=(
                    f"Статус договора {contract.number}: "
                    f"{source_status.value} -> {target_status.value}"
                ),
                result="success",
                metadata={"from": source_status.value, "to": target_status.value},
            )
            db.commit()
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise
        return contract

    def mark_work_started(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
    ) -> Contract:
        self._require_active_contract(contract)
        if contract.status != ContractStatus.SIGNED:
            raise ContractValidationError(
                "Начать работы можно только по подписанному договору"
            )

        source_status = contract.status
        contract.status = ContractStatus.IN_PROGRESS
        contract.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.work_started",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Начаты работы по договору {contract.number}",
                result="success",
                metadata={
                    "from": source_status.value,
                    "to": ContractStatus.IN_PROGRESS.value,
                },
            )
            db.commit()
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise
        return contract

    def suspend(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        reason: str,
    ) -> ContractSuspension:
        self._require_active_contract(contract)
        clean_reason = self._clean_reason(reason)
        if contract.status != ContractStatus.IN_PROGRESS:
            raise ContractValidationError(
                "Приостановить можно только договор в работе"
            )
        if repository.get_open_contract_suspension(db, contract.id) is not None:
            raise ContractValidationError("У договора уже есть открытая приостановка")

        now = datetime.now(UTC)
        suspension = ContractSuspension(
            contract_id=contract.id,
            started_at=now,
            ended_at=None,
            reason=clean_reason,
            created_by=actor_id,
        )
        contract.status = ContractStatus.SUSPENDED
        contract.version += 1
        db.add(suspension)
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.suspended",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Приостановлен договор {contract.number}",
                result="success",
                metadata={"reason": clean_reason},
            )
            db.commit()
            db.refresh(contract)
            db.refresh(suspension)
        except Exception:
            db.rollback()
            raise
        return suspension

    def resume(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
    ) -> ContractSuspension:
        self._require_active_contract(contract)
        if contract.status != ContractStatus.SUSPENDED:
            raise ContractValidationError(
                "Возобновить можно только приостановленный договор"
            )
        suspension = repository.get_open_contract_suspension(db, contract.id)
        if suspension is None:
            raise ContractValidationError(
                "Для приостановленного договора не найдена открытая приостановка"
            )

        suspension.ended_at = datetime.now(UTC)
        contract.status = ContractStatus.IN_PROGRESS
        contract.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.resumed",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Возобновлён договор {contract.number}",
                result="success",
            )
            db.commit()
            db.refresh(contract)
            db.refresh(suspension)
        except Exception:
            db.rollback()
            raise
        return suspension

    def terminate(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        reason: str,
    ) -> Contract:
        self._require_active_contract(contract)
        clean_reason = self._clean_reason(reason)
        if contract.status not in TERMINATABLE_STATUSES:
            raise ContractValidationError(
                "Расторгнуть можно только подписанный, выполняемый или "
                "приостановленный договор"
            )

        suspension = None
        if contract.status == ContractStatus.SUSPENDED:
            suspension = repository.get_open_contract_suspension(db, contract.id)
            if suspension is None:
                raise ContractValidationError(
                    "Для приостановленного договора не найдена открытая приостановка"
                )

        if suspension is not None:
            suspension.ended_at = datetime.now(UTC)
        contract.status = ContractStatus.TERMINATED
        contract.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.terminated",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Расторгнут договор {contract.number}",
                result="success",
                metadata={"reason": clean_reason},
            )
            db.commit()
            db.refresh(contract)
            if suspension is not None:
                db.refresh(suspension)
        except Exception:
            db.rollback()
            raise
        return contract

    def get_completion_readiness(
        self,
        db: Session,
        *,
        contract: Contract,
    ) -> CompletionReadiness:
        self._require_active_contract(contract)
        checks = []
        blockers = []
        for key in REQUIRED_READINESS_KEYS:
            provider = self._readiness_providers.get(key)
            if provider is None:
                provider = unavailable_readiness_provider(key)
            check = provider.check(db, contract)
            checks.append(check)
            blockers.extend(check.blockers)

        ready_to_complete = not blockers and all(check.passed for check in checks)
        return CompletionReadiness(
            ready_to_complete=ready_to_complete,
            checks=tuple(checks),
            blockers=tuple(blockers),
        )

    def complete(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
    ) -> Contract:
        self._require_active_contract(contract)
        if contract.status != ContractStatus.IN_PROGRESS:
            raise ContractValidationError(
                "Завершить можно только договор в работе"
            )

        readiness = self.get_completion_readiness(db, contract=contract)
        if not readiness.ready_to_complete:
            blocker_codes = ", ".join(blocker.code for blocker in readiness.blockers)
            raise ContractValidationError(
                f"Договор не готов к завершению: {blocker_codes or 'readiness_failed'}"
            )

        contract.status = ContractStatus.COMPLETED
        contract.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.completed",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Завершён договор {contract.number}",
                result="success",
            )
            db.commit()
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise
        return contract

    @staticmethod
    def _require_active_contract(contract: Contract) -> None:
        if contract.deleted_at is not None:
            raise ContractValidationError("Удалённый договор нельзя изменить")

    @staticmethod
    def _clean_reason(reason: str) -> str:
        clean = reason.strip()
        if not clean:
            raise ContractValidationError("Причина обязательна")
        return clean

    @staticmethod
    def _validate_signing(db: Session, contract: Contract) -> Decimal:
        if contract.start_date is None:
            raise ContractValidationError("Для подписания договора нужна дата начала")
        if contract.end_date is None:
            raise ContractValidationError("Для подписания договора нужна дата окончания")
        if repository.count_active_contract_items(db, contract.id) < 1:
            raise ContractValidationError(
                "Для подписания договора нужен минимум один предмет договора"
            )
        if repository.count_contract_responsibles(db, contract.id) < 1:
            raise ContractValidationError(
                "Для подписания договора нужен минимум один ответственный"
            )
        effective_amount = calculate_effective_amount(db, contract.id)
        if effective_amount < 0:
            raise ContractValidationError("Сумма договора не может быть отрицательной")
        return effective_amount
