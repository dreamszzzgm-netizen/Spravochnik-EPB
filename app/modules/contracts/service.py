import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts import repository
from app.modules.contracts.commercial import MONEY_QUANTUM, recalculate_effective_amount
from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.models import (
    Contract,
    ContractItem,
    ContractItemBuilding,
    ContractItemTechnicalDevice,
    ContractResponsible,
)
from app.modules.identity.audit import write_audit
from app.modules.identity.models import Employee
from app.modules.organizations.models import Organization, OrganizationContact
from app.modules.technical_devices.models import TechnicalDevice

EDITABLE_TERM_STATUSES = {ContractStatus.DRAFT, ContractStatus.APPROVAL}
COMMENT_EDITABLE_STATUSES = {
    ContractStatus.SIGNED,
    ContractStatus.IN_PROGRESS,
    ContractStatus.SUSPENDED,
    ContractStatus.COMPLETED,
    ContractStatus.TERMINATED,
}
RESPONSIBLE_EDITABLE_STATUSES = {
    ContractStatus.DRAFT,
    ContractStatus.APPROVAL,
    ContractStatus.SIGNED,
    ContractStatus.IN_PROGRESS,
    ContractStatus.SUSPENDED,
}


class ContractNotFoundError(Exception):
    pass


class ContractItemNotFoundError(Exception):
    pass


class ContractValidationError(ValueError):
    pass


class ContractService:
    def create_contract(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        customer_organization_id: uuid.UUID,
        customer_contact_id: uuid.UUID | None,
        number: str,
        contract_date: date,
        start_date: date | None,
        end_date: date | None,
        comment: str | None,
    ) -> Contract:
        clean_number = self._validate_number(number)
        self._validate_dates(start_date, end_date)
        self._require_customer(db, customer_organization_id)
        self._validate_contact(db, customer_organization_id, customer_contact_id)

        contract = Contract(
            customer_organization_id=customer_organization_id,
            customer_contact_id=customer_contact_id,
            number=clean_number,
            contract_date=contract_date,
            start_date=start_date,
            end_date=end_date,
            amount=Decimal("0.00"),
            currency="RUB",
            status=ContractStatus.DRAFT,
            comment=self._clean_optional_text(comment),
            created_by=actor_id,
        )
        db.add(contract)
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.created",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Создан договор {contract.number}",
                result="success",
            )
            db.commit()
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise
        return contract

    def update_contract(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        customer_organization_id: uuid.UUID,
        customer_contact_id: uuid.UUID | None,
        number: str,
        contract_date: date,
        start_date: date | None,
        end_date: date | None,
        comment: str | None,
    ) -> Contract:
        self._require_active_contract(contract)
        clean_number = self._validate_number(number)
        clean_comment = self._clean_optional_text(comment)

        if contract.status in EDITABLE_TERM_STATUSES:
            self._validate_dates(start_date, end_date)
            self._require_customer(db, customer_organization_id)
            self._validate_contact(db, customer_organization_id, customer_contact_id)
            contract.customer_organization_id = customer_organization_id
            contract.customer_contact_id = customer_contact_id
            contract.number = clean_number
            contract.contract_date = contract_date
            contract.start_date = start_date
            contract.end_date = end_date
        elif contract.status in COMMENT_EDITABLE_STATUSES:
            legal_fields_changed = any(
                (
                    customer_organization_id != contract.customer_organization_id,
                    customer_contact_id != contract.customer_contact_id,
                    clean_number != contract.number,
                    contract_date != contract.contract_date,
                    start_date != contract.start_date,
                    end_date != contract.end_date,
                )
            )
            if legal_fields_changed:
                raise ContractValidationError(
                    "Юридически значимые условия подписанного договора "
                    "изменяются только через дополнительное соглашение"
                )
        else:
            raise ContractValidationError("Архивный договор нельзя изменять")

        contract.comment = clean_comment
        contract.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.updated",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Изменён договор {contract.number}",
                result="success",
            )
            db.commit()
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise
        return contract

    def delete_contract(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
    ) -> None:
        self._require_active_contract(contract)
        if contract.status not in EDITABLE_TERM_STATUSES:
            raise ContractValidationError(
                "Удалить можно только договор в статусе черновика или согласования"
            )
        contract.deleted_at = datetime.now(UTC)
        contract.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.deleted",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Удалён договор {contract.number}",
                result="success",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def restore_contract(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
    ) -> None:
        if contract.deleted_at is None:
            raise ContractValidationError("Договор не удалён")
        contract.deleted_at = None
        contract.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.restored",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Восстановлен договор {contract.number}",
                result="success",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def replace_responsibles(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        employee_ids: Iterable[uuid.UUID],
    ) -> list[uuid.UUID]:
        self._require_active_contract(contract)
        if contract.status not in RESPONSIBLE_EDITABLE_STATUSES:
            raise ContractValidationError(
                "Ответственных нельзя изменять для завершённого, расторгнутого "
                "или архивного договора"
            )
        normalized_ids = sorted(set(employee_ids), key=str)
        self._validate_employees(db, normalized_ids)

        try:
            db.execute(
                sa.delete(ContractResponsible).where(
                    ContractResponsible.contract_id == contract.id
                )
            )
            db.add_all(
                [
                    ContractResponsible(contract_id=contract.id, employee_id=employee_id)
                    for employee_id in normalized_ids
                ]
            )
            db.flush()
            write_audit(
                db,
                user_id=actor_id,
                action="contract.responsibles_updated",
                entity_type="contract",
                entity_id=contract.id,
                summary=f"Обновлены ответственные договора {contract.number}",
                result="success",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return normalized_ids

    def create_item(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        name: str,
        expertise_type_id: uuid.UUID,
        price: Decimal,
        technical_device_ids: Iterable[uuid.UUID],
        building_ids: Iterable[uuid.UUID],
        comment: str | None,
    ) -> ContractItem:
        self._require_items_editable(contract)
        clean_name = self._validate_item_name(name)
        clean_price = self._normalize_money(price)
        self._require_expertise_type(db, expertise_type_id)
        device_ids, normalized_building_ids = self._validate_subjects(
            db,
            technical_device_ids=technical_device_ids,
            building_ids=building_ids,
        )

        item = ContractItem(
            contract_id=contract.id,
            name=clean_name,
            expertise_type_id=expertise_type_id,
            price=clean_price,
            currency="RUB",
            comment=self._clean_optional_text(comment),
        )
        db.add(item)
        try:
            db.flush()
            self._replace_subject_rows(
                db,
                item_id=item.id,
                technical_device_ids=device_ids,
                building_ids=normalized_building_ids,
                delete_existing=False,
            )
            db.flush()
            recalculate_effective_amount(db, contract)
            write_audit(
                db,
                user_id=actor_id,
                action="contract_item.created",
                entity_type="contract_item",
                entity_id=item.id,
                summary=f"Добавлен предмет договора: {item.name}",
                result="success",
            )
            db.commit()
            db.refresh(item)
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise
        return item

    def update_item(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        item: ContractItem,
        name: str,
        expertise_type_id: uuid.UUID,
        price: Decimal,
        technical_device_ids: Iterable[uuid.UUID],
        building_ids: Iterable[uuid.UUID],
        comment: str | None,
    ) -> ContractItem:
        self._require_items_editable(contract)
        self._require_item_for_contract(contract, item)
        clean_name = self._validate_item_name(name)
        clean_price = self._normalize_money(price)
        self._require_expertise_type(db, expertise_type_id)
        device_ids, normalized_building_ids = self._validate_subjects(
            db,
            technical_device_ids=technical_device_ids,
            building_ids=building_ids,
        )

        item.name = clean_name
        item.expertise_type_id = expertise_type_id
        item.price = clean_price
        item.comment = self._clean_optional_text(comment)
        item.version += 1
        try:
            self._replace_subject_rows(
                db,
                item_id=item.id,
                technical_device_ids=device_ids,
                building_ids=normalized_building_ids,
                delete_existing=True,
            )
            db.flush()
            recalculate_effective_amount(db, contract)
            write_audit(
                db,
                user_id=actor_id,
                action="contract_item.updated",
                entity_type="contract_item",
                entity_id=item.id,
                summary=f"Изменён предмет договора: {item.name}",
                result="success",
            )
            db.commit()
            db.refresh(item)
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise
        return item

    def delete_item(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        item: ContractItem,
    ) -> None:
        self._require_items_editable(contract)
        self._require_item_for_contract(contract, item)
        item.deleted_at = datetime.now(UTC)
        item.version += 1
        try:
            db.flush()
            recalculate_effective_amount(db, contract)
            write_audit(
                db,
                user_id=actor_id,
                action="contract_item.deleted",
                entity_type="contract_item",
                entity_id=item.id,
                summary=f"Удалён предмет договора: {item.name}",
                result="success",
            )
            db.commit()
            db.refresh(contract)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _validate_number(number: str) -> str:
        clean = number.strip()
        if not clean:
            raise ContractValidationError("Номер договора обязателен")
        return clean

    @staticmethod
    def _validate_item_name(name: str) -> str:
        clean = name.strip()
        if not clean:
            raise ContractValidationError("Наименование предмета договора обязательно")
        return clean

    @staticmethod
    def _validate_dates(start_date: date | None, end_date: date | None) -> None:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ContractValidationError("Дата начала не может быть позже даты окончания")

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @staticmethod
    def _normalize_money(value: Decimal) -> Decimal:
        try:
            money = Decimal(value).quantize(MONEY_QUANTUM)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ContractValidationError("Некорректная стоимость предмета договора") from exc
        if money < 0:
            raise ContractValidationError("Стоимость предмета договора не может быть отрицательной")
        return money

    @staticmethod
    def _require_customer(db: Session, organization_id: uuid.UUID) -> Organization:
        organization = db.scalar(
            sa.select(Organization).where(
                Organization.id == organization_id,
                Organization.deleted_at.is_(None),
            )
        )
        if organization is None:
            raise ContractValidationError("Организация-заказчик не найдена")
        return organization

    @staticmethod
    def _validate_contact(
        db: Session,
        organization_id: uuid.UUID,
        contact_id: uuid.UUID | None,
    ) -> None:
        if contact_id is None:
            return
        contact = db.scalar(
            sa.select(OrganizationContact).where(
                OrganizationContact.id == contact_id,
                OrganizationContact.deleted_at.is_(None),
            )
        )
        if contact is None or contact.organization_id != organization_id:
            raise ContractValidationError("Контакт заказчика не найден")

    @staticmethod
    def _validate_employees(db: Session, employee_ids: list[uuid.UUID]) -> None:
        if not employee_ids:
            return
        found_ids = set(
            db.scalars(
                sa.select(Employee.id).where(
                    Employee.id.in_(employee_ids),
                    Employee.deleted_at.is_(None),
                )
            ).all()
        )
        if found_ids != set(employee_ids):
            raise ContractValidationError("Один или несколько ответственных не найдены")

    @staticmethod
    def _require_expertise_type(db: Session, expertise_type_id: uuid.UUID) -> None:
        if repository.get_active_expertise_type(db, expertise_type_id) is None:
            raise ContractValidationError("Тип экспертизы не найден")

    @staticmethod
    def _require_active_contract(contract: Contract) -> None:
        if contract.deleted_at is not None:
            raise ContractNotFoundError("Договор не найден")

    @classmethod
    def _require_items_editable(cls, contract: Contract) -> None:
        cls._require_active_contract(contract)
        if contract.status not in EDITABLE_TERM_STATUSES:
            raise ContractValidationError(
                "Предметы подписанного договора нельзя изменять"
            )

    @staticmethod
    def _require_item_for_contract(contract: Contract, item: ContractItem) -> None:
        if item.deleted_at is not None or item.contract_id != contract.id:
            raise ContractItemNotFoundError("Предмет договора не найден")

    @staticmethod
    def _validate_subjects(
        db: Session,
        *,
        technical_device_ids: Iterable[uuid.UUID],
        building_ids: Iterable[uuid.UUID],
    ) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        device_ids = sorted(set(technical_device_ids), key=str)
        normalized_building_ids = sorted(set(building_ids), key=str)
        if not device_ids and not normalized_building_ids:
            raise ContractValidationError(
                "Предмет договора должен содержать минимум один предмет экспертизы"
            )

        if device_ids:
            found_device_ids = set(
                db.scalars(
                    sa.select(TechnicalDevice.id).where(
                        TechnicalDevice.id.in_(device_ids),
                        TechnicalDevice.deleted_at.is_(None),
                    )
                ).all()
            )
            if found_device_ids != set(device_ids):
                raise ContractValidationError("Техническое устройство не найдено")

        if normalized_building_ids:
            found_building_ids = set(
                db.scalars(
                    sa.select(Building.id).where(
                        Building.id.in_(normalized_building_ids),
                        Building.deleted_at.is_(None),
                    )
                ).all()
            )
            if found_building_ids != set(normalized_building_ids):
                raise ContractValidationError("Здание/сооружение не найдено")

        return device_ids, normalized_building_ids

    @staticmethod
    def _replace_subject_rows(
        db: Session,
        *,
        item_id: uuid.UUID,
        technical_device_ids: list[uuid.UUID],
        building_ids: list[uuid.UUID],
        delete_existing: bool,
    ) -> None:
        if delete_existing:
            db.execute(
                sa.delete(ContractItemTechnicalDevice).where(
                    ContractItemTechnicalDevice.contract_item_id == item_id
                )
            )
            db.execute(
                sa.delete(ContractItemBuilding).where(
                    ContractItemBuilding.contract_item_id == item_id
                )
            )
        db.add_all(
            [
                ContractItemTechnicalDevice(
                    contract_item_id=item_id,
                    technical_device_id=device_id,
                )
                for device_id in technical_device_ids
            ]
        )
        db.add_all(
            [
                ContractItemBuilding(contract_item_id=item_id, building_id=building_id)
                for building_id in building_ids
            ]
        )
