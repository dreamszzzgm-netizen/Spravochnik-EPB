import uuid
from datetime import date, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts.models import (
    Contract,
    ContractItem,
    ContractItemBuilding,
    ContractItemTechnicalDevice,
    ExpertiseType,
)
from app.modules.expertises import repository
from app.modules.expertises.domain import INITIAL_STATUS, can_transition
from app.modules.expertises.enums import ExpertiseParticipantRole, ExpertiseStatus
from app.modules.expertises.models import (
    Expertise,
    ExpertiseContractItem,
    ExpertiseParticipant,
    ExpertiseStatusHistory,
    ExpertiseSubject,
)
from app.modules.identity.audit import write_audit
from app.modules.identity.models import Employee
from app.modules.tasks.enums import TaskLinkKind
from app.modules.tasks.service import TaskLinkInput
from app.modules.technical_devices.models import TechnicalDevice
from app.modules.workflows.service import WorkflowService


class ExpertiseNotFoundError(Exception):
    pass


class ExpertiseValidationError(ValueError):
    pass


class ExpertiseVersionConflictError(Exception):
    pass


class ExpertiseDuplicateParticipantError(Exception):
    pass


class ExpertiseService:
    def create_expertise(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        contract_id: uuid.UUID,
        expertise_type_id: uuid.UUID,
        responsible_expert_id: uuid.UUID,
        internal_number: str | None,
        comment: str | None,
        technical_device_id: uuid.UUID | None,
        building_id: uuid.UUID | None,
        contract_item_ids: list[uuid.UUID],
    ) -> Expertise:
        contract = self._require_active_contract(db, contract_id)
        self._require_expertise_type(db, expertise_type_id)
        self._require_active_expert(db, responsible_expert_id)
        normalized_item_ids = self._validate_contract_items(
            db, contract.id, contract_item_ids
        )
        self._validate_subject(
            db,
            normalized_item_ids,
            technical_device_id=technical_device_id,
            building_id=building_id,
        )

        expertise = Expertise(
            contract_id=contract.id,
            expertise_type_id=expertise_type_id,
            status=INITIAL_STATUS,
            internal_number=self._clean_optional_text(internal_number),
            responsible_expert_id=responsible_expert_id,
            comment=self._clean_optional_text(comment),
            created_by=actor_user_id,
            version=1,
        )
        db.add(expertise)
        try:
            db.flush()
            db.add(
                ExpertiseSubject(
                    expertise_id=expertise.id,
                    technical_device_id=technical_device_id,
                    building_id=building_id,
                )
            )
            db.add_all(
                [
                    ExpertiseContractItem(
                        expertise_id=expertise.id, contract_item_id=item_id
                    )
                    for item_id in normalized_item_ids
                ]
            )
            db.add(
                ExpertiseStatusHistory(
                    expertise_id=expertise.id,
                    from_status=None,
                    to_status=INITIAL_STATUS,
                    changed_by=actor_user_id,
                )
            )
            write_audit(
                db,
                user_id=actor_user_id,
                action="expertise.created",
                entity_type="expertise",
                entity_id=expertise.id,
                summary="Создана экспертиза",
                result="success",
            )
            db.commit()
            db.refresh(expertise)
        except Exception:
            db.rollback()
            raise
        return expertise

    def update_expertise(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        expertise: Expertise,
        expected_version: int,
        expertise_type_id: uuid.UUID | None,
        responsible_expert_id: uuid.UUID | None,
        internal_number: str | None,
        comment: str | None,
    ) -> Expertise:
        self._require_active_expertise(expertise)
        self._check_version(expertise, expected_version)

        if expertise_type_id is not None:
            self._require_expertise_type(db, expertise_type_id)
        if responsible_expert_id is not None:
            self._require_active_expert(db, responsible_expert_id)

        if expertise_type_id is not None:
            expertise.expertise_type_id = expertise_type_id
        if responsible_expert_id is not None:
            expertise.responsible_expert_id = responsible_expert_id
        if internal_number is not None:
            expertise.internal_number = self._clean_optional_text(internal_number)
        if comment is not None:
            expertise.comment = self._clean_optional_text(comment)

        expertise.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="expertise.updated",
                entity_type="expertise",
                entity_id=expertise.id,
                summary="Изменена экспертиза",
                result="success",
            )
            db.commit()
            db.refresh(expertise)
        except Exception:
            db.rollback()
            raise
        return expertise

    def change_status(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        expertise: Expertise,
        target_status: ExpertiseStatus,
        reason: str | None,
        expected_version: int,
    ) -> Expertise:
        self._require_active_expertise(expertise)
        self._check_version(expertise, expected_version)
        source_status = expertise.status
        if not can_transition(source_status, target_status):
            raise ExpertiseValidationError(
                f"Переход экспертизы {source_status.value} -> {target_status.value} недопустим"
            )

        clean_reason = self._clean_optional_text(reason)
        expertise.status = target_status
        expertise.version += 1
        try:
            db.flush()
            db.add(
                ExpertiseStatusHistory(
                    expertise_id=expertise.id,
                    from_status=source_status,
                    to_status=target_status,
                    changed_by=actor_user_id,
                    reason=clean_reason,
                )
            )
            write_audit(
                db,
                user_id=actor_user_id,
                action="expertise.status_changed",
                entity_type="expertise",
                entity_id=expertise.id,
                summary=(
                    f"Статус экспертизы: {source_status.value} -> {target_status.value}"
                ),
                result="success",
                metadata={"from": source_status.value, "to": target_status.value},
            )
            db.commit()
            db.refresh(expertise)
        except Exception:
            db.rollback()
            raise
        return expertise

    def add_participant(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        expertise: Expertise,
        employee_id: uuid.UUID,
        participation_role: ExpertiseParticipantRole,
    ) -> ExpertiseParticipant:
        self._require_active_expertise(expertise)
        self._require_active_expert(db, employee_id)
        if repository.get_participant(db, expertise.id, employee_id) is not None:
            raise ExpertiseDuplicateParticipantError(
                "Сотрудник уже является участником экспертизы в этой роли"
            )
        participant = ExpertiseParticipant(
            expertise_id=expertise.id,
            employee_id=employee_id,
            participation_role=participation_role,
        )
        db.add(participant)
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="expertise.participant_added",
                entity_type="expertise",
                entity_id=expertise.id,
                summary="Добавлен участник экспертизы",
                result="success",
                metadata={
                    "employee_id": str(employee_id),
                    "participation_role": participation_role.value,
                },
            )
            db.commit()
            db.refresh(participant)
        except Exception:
            db.rollback()
            raise
        return participant

    def remove_participant(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        expertise: Expertise,
        employee_id: uuid.UUID,
    ) -> None:
        self._require_active_expertise(expertise)
        participant = repository.get_participant(db, expertise.id, employee_id)
        if participant is None:
            raise ExpertiseValidationError("Участник не найден")
        db.delete(participant)
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="expertise.participant_removed",
                entity_type="expertise",
                entity_id=expertise.id,
                summary="Удалён участник экспертизы",
                result="success",
                metadata={"employee_id": str(employee_id)},
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def start_workflow(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        creator_employee_id: uuid.UUID,
        expertise: Expertise,
        workflow_template_id: uuid.UUID,
        anchor_date: date,
    ) -> list:
        self._require_active_expertise(expertise)
        workflow_service = WorkflowService()
        return workflow_service.instantiate(
            db,
            actor_user_id=actor_user_id,
            creator_employee_id=creator_employee_id,
            template_id=workflow_template_id,
            anchor_date=anchor_date,
            links=[
                TaskLinkInput(
                    kind=TaskLinkKind.EXPERTISE,
                    entity_id=expertise.id,
                    is_primary=True,
                )
            ],
            due_date_resolver=lambda start, days: start + timedelta(days=days),
        )

    @staticmethod
    def _check_version(expertise: Expertise, expected_version: int) -> None:
        if expertise.version != expected_version:
            raise ExpertiseVersionConflictError(
                f"Версия экспертизы изменилась: ожидалось {expected_version}, "
                f"текущая {expertise.version}"
            )

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @staticmethod
    def _require_active_expertise(expertise: Expertise) -> None:
        if expertise.deleted_at is not None:
            raise ExpertiseNotFoundError("Экспертиза не найдена")

    @staticmethod
    def _require_active_contract(db: Session, contract_id: uuid.UUID) -> Contract:
        contract = db.scalar(
            sa.select(Contract).where(
                Contract.id == contract_id,
                Contract.deleted_at.is_(None),
            )
        )
        if contract is None:
            raise ExpertiseValidationError("Договор не найден")
        return contract

    @staticmethod
    def _require_expertise_type(db: Session, expertise_type_id: uuid.UUID) -> None:
        expertise_type = db.scalar(
            sa.select(ExpertiseType).where(
                ExpertiseType.id == expertise_type_id,
                ExpertiseType.is_active.is_(True),
            )
        )
        if expertise_type is None:
            raise ExpertiseValidationError("Тип экспертизы не найден")

    @staticmethod
    def _require_active_expert(db: Session, employee_id: uuid.UUID) -> None:
        employee = db.scalar(
            sa.select(Employee).where(
                Employee.id == employee_id,
                Employee.deleted_at.is_(None),
            )
        )
        if employee is None:
            raise ExpertiseValidationError("Ответственный эксперт не найден")

    @staticmethod
    def _validate_contract_items(
        db: Session,
        contract_id: uuid.UUID,
        contract_item_ids: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        normalized = sorted(set(contract_item_ids), key=str)
        if not normalized:
            raise ExpertiseValidationError(
                "Экспертиза должна быть связана минимум с одним предметом договора"
            )
        found_ids = set(
            db.scalars(
                sa.select(ContractItem.id).where(
                    ContractItem.id.in_(normalized),
                    ContractItem.contract_id == contract_id,
                    ContractItem.deleted_at.is_(None),
                )
            ).all()
        )
        if found_ids != set(normalized):
            raise ExpertiseValidationError(
                "Один или несколько предметов договора не относятся к выбранному договору"
            )
        return normalized

    @staticmethod
    def _validate_subject(
        db: Session,
        contract_item_ids: list[uuid.UUID],
        *,
        technical_device_id: uuid.UUID | None,
        building_id: uuid.UUID | None,
    ) -> None:
        has_device = technical_device_id is not None
        has_building = building_id is not None
        if has_device == has_building:
            raise ExpertiseValidationError(
                "Экспертиза должна иметь ровно один предмет (устройство или здание)"
            )

        if has_device:
            device = db.scalar(
                sa.select(TechnicalDevice).where(
                    TechnicalDevice.id == technical_device_id,
                    TechnicalDevice.deleted_at.is_(None),
                )
            )
            if device is None:
                raise ExpertiseValidationError("Техническое устройство не найдено")
            linked = db.scalar(
                sa.select(ContractItemTechnicalDevice.contract_item_id).where(
                    ContractItemTechnicalDevice.contract_item_id.in_(contract_item_ids),
                    ContractItemTechnicalDevice.technical_device_id == technical_device_id,
                )
            )
        else:
            building = db.scalar(
                sa.select(Building).where(
                    Building.id == building_id,
                    Building.deleted_at.is_(None),
                )
            )
            if building is None:
                raise ExpertiseValidationError("Здание/сооружение не найдено")
            linked = db.scalar(
                sa.select(ContractItemBuilding.contract_item_id).where(
                    ContractItemBuilding.contract_item_id.in_(contract_item_ids),
                    ContractItemBuilding.building_id == building_id,
                )
            )

        if linked is None:
            raise ExpertiseValidationError(
                "Предмет экспертизы должен входить в один из выбранных предметов договора"
            )
