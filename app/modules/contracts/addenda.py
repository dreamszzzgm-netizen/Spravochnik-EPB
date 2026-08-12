import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.modules.contracts import repository
from app.modules.contracts.commercial import (
    MONEY_QUANTUM,
    calculate_effective_amount,
    recalculate_effective_amount,
)
from app.modules.contracts.enums import ContractAddendumStatus, ContractStatus
from app.modules.contracts.models import Contract, ContractAddendum
from app.modules.contracts.service import ContractValidationError
from app.modules.identity.audit import write_audit

ADDENDUM_PARENT_STATUSES = {
    ContractStatus.SIGNED,
    ContractStatus.IN_PROGRESS,
    ContractStatus.SUSPENDED,
}
ADDENDUM_EDITABLE_STATUSES = {
    ContractAddendumStatus.DRAFT,
    ContractAddendumStatus.APPROVAL,
}
ADDENDUM_TRANSITIONS: dict[ContractAddendumStatus, set[ContractAddendumStatus]] = {
    ContractAddendumStatus.DRAFT: {
        ContractAddendumStatus.APPROVAL,
        ContractAddendumStatus.CANCELLED,
    },
    ContractAddendumStatus.APPROVAL: {
        ContractAddendumStatus.SIGNED,
        ContractAddendumStatus.CANCELLED,
    },
}


class ContractAddendumService:
    def create_addendum(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        number: str,
        addendum_date: date,
        amount_delta: Decimal | None,
        new_end_date: date | None,
        description: str | None,
    ) -> ContractAddendum:
        self._require_parent_allowed(contract)
        addendum = ContractAddendum(
            contract_id=contract.id,
            number=self._clean_number(number),
            addendum_date=addendum_date,
            status=ContractAddendumStatus.DRAFT,
            amount_delta=self._normalize_delta(amount_delta),
            currency=contract.currency,
            new_end_date=new_end_date,
            description=self._clean_optional_text(description),
            signed_at=None,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(addendum)
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract_addendum.created",
                entity_type="contract_addendum",
                entity_id=addendum.id,
                summary=f"Создано допсоглашение {addendum.number} к договору {contract.number}",
                result="success",
            )
            db.commit()
            db.refresh(addendum)
        except Exception:
            db.rollback()
            raise
        return addendum

    def update_addendum(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        addendum: ContractAddendum,
        number: str,
        addendum_date: date,
        amount_delta: Decimal | None,
        new_end_date: date | None,
        description: str | None,
    ) -> ContractAddendum:
        self._require_parent_allowed(contract)
        self._require_addendum_for_contract(contract, addendum)
        self._require_editable(addendum)

        addendum.number = self._clean_number(number)
        addendum.addendum_date = addendum_date
        addendum.amount_delta = self._normalize_delta(amount_delta)
        addendum.new_end_date = new_end_date
        addendum.description = self._clean_optional_text(description)
        addendum.updated_by = actor_id
        addendum.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract_addendum.updated",
                entity_type="contract_addendum",
                entity_id=addendum.id,
                summary=f"Изменено допсоглашение {addendum.number}",
                result="success",
            )
            db.commit()
            db.refresh(addendum)
        except Exception:
            db.rollback()
            raise
        return addendum

    def delete_addendum(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        addendum: ContractAddendum,
    ) -> None:
        self._require_parent_allowed(contract)
        self._require_addendum_for_contract(contract, addendum)
        self._require_editable(addendum)

        addendum.deleted_at = datetime.now(UTC)
        addendum.updated_by = actor_id
        addendum.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract_addendum.deleted",
                entity_type="contract_addendum",
                entity_id=addendum.id,
                summary=f"Удалено допсоглашение {addendum.number}",
                result="success",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def change_status(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        addendum: ContractAddendum,
        target_status: ContractAddendumStatus,
    ) -> ContractAddendum:
        locked_contract = repository.get_contract_for_update(db, contract.id)
        if locked_contract is None:
            raise ContractValidationError("Договор не найден")
        locked_addendum = repository.get_contract_addendum_for_update(
            db,
            locked_contract.id,
            addendum.id,
        )
        if locked_addendum is None:
            raise ContractValidationError("Дополнительное соглашение не найдено")

        contract = locked_contract
        addendum = locked_addendum
        self._require_parent_allowed(contract)
        self._require_addendum_for_contract(contract, addendum)
        source_status = addendum.status
        if target_status not in ADDENDUM_TRANSITIONS.get(source_status, set()):
            raise ContractValidationError(
                "Недопустимый переход статуса дополнительного соглашения: "
                f"{source_status.value} -> {target_status.value}"
            )

        if target_status == ContractAddendumStatus.SIGNED:
            self._sign(
                db,
                actor_id=actor_id,
                contract=contract,
                addendum=addendum,
            )
            return addendum

        addendum.status = target_status
        addendum.updated_by = actor_id
        addendum.version += 1
        action = (
            "contract_addendum.cancelled"
            if target_status == ContractAddendumStatus.CANCELLED
            else "contract_addendum.status_changed"
        )
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action=action,
                entity_type="contract_addendum",
                entity_id=addendum.id,
                summary=(
                    f"Статус допсоглашения {addendum.number}: "
                    f"{source_status.value} -> {target_status.value}"
                ),
                result="success",
                metadata={"from": source_status.value, "to": target_status.value},
            )
            db.commit()
            db.refresh(addendum)
        except Exception:
            db.rollback()
            raise
        return addendum

    def _sign(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        addendum: ContractAddendum,
    ) -> None:
        delta = self._normalize_delta(addendum.amount_delta) or Decimal("0.00")
        has_financial_effect = delta != Decimal("0.00")
        has_deadline_effect = addendum.new_end_date is not None
        if not has_financial_effect and not has_deadline_effect:
            raise ContractValidationError(
                "Дополнительное соглашение должно изменять сумму или срок договора"
            )
        if addendum.currency != contract.currency:
            raise ContractValidationError(
                "Валюта дополнительного соглашения должна совпадать с валютой договора"
            )
        if (
            addendum.new_end_date is not None
            and contract.start_date is not None
            and addendum.new_end_date < contract.start_date
        ):
            raise ContractValidationError(
                "Новый срок окончания не может быть раньше даты начала договора"
            )
        if (
            addendum.new_end_date is not None
            and contract.end_date is not None
            and addendum.new_end_date > contract.end_date
            and self._clean_optional_text(addendum.description) is None
        ):
            raise ContractValidationError(
                "Для увеличения срока договора требуется указать причину"
            )

        projected_amount = calculate_effective_amount(
            db,
            contract.id,
            pending_delta=delta,
        )
        if projected_amount < Decimal("0.00"):
            raise ContractValidationError(
                "Дополнительное соглашение не может сделать сумму договора отрицательной"
            )

        addendum.amount_delta = None if addendum.amount_delta is None else delta
        addendum.status = ContractAddendumStatus.SIGNED
        addendum.signed_at = datetime.now(UTC)
        addendum.updated_by = actor_id
        addendum.version += 1
        if addendum.new_end_date is not None:
            contract.end_date = addendum.new_end_date
        contract.version += 1

        try:
            db.flush()
            recalculate_effective_amount(db, contract)
            write_audit(
                db,
                user_id=actor_id,
                action="contract_addendum.signed",
                entity_type="contract_addendum",
                entity_id=addendum.id,
                summary=f"Подписано допсоглашение {addendum.number}",
                result="success",
                metadata={
                    "amount_delta": str(delta),
                    "new_end_date": (
                        addendum.new_end_date.isoformat()
                        if addendum.new_end_date is not None
                        else None
                    ),
                },
            )
            db.commit()
            db.refresh(contract)
            db.refresh(addendum)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _require_parent_allowed(contract: Contract) -> None:
        if contract.deleted_at is not None:
            raise ContractValidationError("Договор не найден")
        if contract.status not in ADDENDUM_PARENT_STATUSES:
            raise ContractValidationError(
                "Дополнительные соглашения доступны только для подписанного, "
                "выполняемого или приостановленного договора"
            )

    @staticmethod
    def _require_addendum_for_contract(
        contract: Contract,
        addendum: ContractAddendum,
    ) -> None:
        if addendum.deleted_at is not None or addendum.contract_id != contract.id:
            raise ContractValidationError("Дополнительное соглашение не найдено")

    @staticmethod
    def _require_editable(addendum: ContractAddendum) -> None:
        if addendum.status not in ADDENDUM_EDITABLE_STATUSES:
            raise ContractValidationError(
                "Подписанное или отменённое дополнительное соглашение нельзя изменять"
            )

    @staticmethod
    def _clean_number(number: str) -> str:
        clean = number.strip()
        if not clean:
            raise ContractValidationError("Номер дополнительного соглашения обязателен")
        return clean

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @staticmethod
    def _normalize_delta(value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(value).quantize(MONEY_QUANTUM)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ContractValidationError(
                "Некорректное изменение суммы дополнительного соглашения"
            ) from exc
