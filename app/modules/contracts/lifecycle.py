import uuid

from sqlalchemy.orm import Session

from app.modules.contracts import repository
from app.modules.contracts.commercial import calculate_effective_amount
from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.models import Contract
from app.modules.contracts.service import ContractValidationError
from app.modules.identity.audit import write_audit

ORDINARY_TRANSITIONS: dict[ContractStatus, set[ContractStatus]] = {
    ContractStatus.DRAFT: {ContractStatus.APPROVAL},
    ContractStatus.APPROVAL: {ContractStatus.SIGNED},
    ContractStatus.COMPLETED: {ContractStatus.ARCHIVED},
    ContractStatus.TERMINATED: {ContractStatus.ARCHIVED},
}


class ContractLifecycleService:
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

    @staticmethod
    def _require_active_contract(contract: Contract) -> None:
        if contract.deleted_at is not None:
            raise ContractValidationError("Удалённый договор нельзя изменить")

    @staticmethod
    def _validate_signing(db: Session, contract: Contract):
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
