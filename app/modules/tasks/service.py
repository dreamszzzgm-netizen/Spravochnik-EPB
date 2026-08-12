from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts.models import Contract, ContractItem
from app.modules.identity.audit import write_audit
from app.modules.identity.models import Employee
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.tasks.enums import TaskLinkKind, TaskPriority, TaskStatus
from app.modules.tasks.models import (
    Task,
    TaskAssignee,
    TaskBuilding,
    TaskContract,
    TaskContractItem,
    TaskOPO,
    TaskOrganization,
    TaskTechnicalDevice,
)
from app.modules.technical_devices.models import TechnicalDevice


class TaskNotFoundError(Exception):
    pass


class TaskValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TaskLinkInput:
    kind: TaskLinkKind
    entity_id: uuid.UUID
    is_primary: bool = False


class TaskService:
    def create_task(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        creator_employee_id: uuid.UUID,
        title: str,
        description: str | None,
        due_date: date | None,
        priority: TaskPriority,
        is_personal: bool,
        assignee_ids: Iterable[uuid.UUID],
        links: Iterable[TaskLinkInput],
    ) -> Task:
        clean_title = self._clean_title(title)
        clean_description = self._clean_optional_text(description)
        self._require_active_employee(db, creator_employee_id, label="постановщик")
        normalized_assignees = self._validate_assignees(db, assignee_ids)
        normalized_links = self._validate_links(db, links, is_personal=is_personal)

        task = Task(
            title=clean_title,
            description=clean_description,
            creator_employee_id=creator_employee_id,
            due_date=due_date,
            priority=priority,
            status=TaskStatus.NEW,
            is_personal=is_personal,
            version=1,
        )
        db.add(task)
        try:
            db.flush()
            self._replace_assignee_rows(
                db,
                task_id=task.id,
                employee_ids=normalized_assignees,
                delete_existing=False,
            )
            self._replace_link_rows(
                db,
                task_id=task.id,
                links=normalized_links,
                delete_existing=False,
            )
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="task.created",
                entity_type="task",
                entity_id=task.id,
                summary=f"Создана задача: {task.title}",
                result="success",
            )
            db.commit()
            db.refresh(task)
        except Exception:
            db.rollback()
            raise
        return task

    def update_task(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        task: Task,
        title: str,
        description: str | None,
        due_date: date | None,
        priority: TaskPriority,
        is_personal: bool,
        links: Iterable[TaskLinkInput],
        due_date_change_reason: str | None,
    ) -> Task:
        self._require_active_task(task)
        clean_title = self._clean_title(title)
        clean_description = self._clean_optional_text(description)
        normalized_links = self._validate_links(db, links, is_personal=is_personal)
        clean_reason = self._validate_due_date_change(
            old_due_date=task.due_date,
            new_due_date=due_date,
            reason=due_date_change_reason,
        )
        old_due_date = task.due_date

        task.title = clean_title
        task.description = clean_description
        task.due_date = due_date
        task.priority = priority
        task.is_personal = is_personal
        task.version += 1
        try:
            self._replace_link_rows(
                db,
                task_id=task.id,
                links=normalized_links,
                delete_existing=True,
            )
            db.flush()
            metadata = None
            if old_due_date != due_date:
                metadata = {
                    "old_due_date": old_due_date.isoformat() if old_due_date else None,
                    "new_due_date": due_date.isoformat() if due_date else None,
                    "reason": clean_reason,
                }
            write_audit(
                db,
                user_id=actor_user_id,
                action="task.updated",
                entity_type="task",
                entity_id=task.id,
                summary=f"Изменена задача: {task.title}",
                result="success",
                metadata=metadata,
            )
            db.commit()
            db.refresh(task)
        except Exception:
            db.rollback()
            raise
        return task

    def delete_task(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        task: Task,
    ) -> None:
        self._require_active_task(task)
        task.deleted_at = datetime.now(UTC)
        task.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="task.deleted",
                entity_type="task",
                entity_id=task.id,
                summary=f"Удалена задача: {task.title}",
                result="success",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def restore_task(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        task: Task,
    ) -> None:
        if task.deleted_at is None:
            raise TaskValidationError("Задача не удалена")
        task.deleted_at = None
        task.version += 1
        try:
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="task.restored",
                entity_type="task",
                entity_id=task.id,
                summary=f"Восстановлена задача: {task.title}",
                result="success",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def replace_assignees(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        task: Task,
        employee_ids: Iterable[uuid.UUID],
    ) -> list[uuid.UUID]:
        self._require_active_task(task)
        normalized = self._validate_assignees(db, employee_ids)
        try:
            self._replace_assignee_rows(
                db,
                task_id=task.id,
                employee_ids=normalized,
                delete_existing=True,
            )
            task.version += 1
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="task.assignees_updated",
                entity_type="task",
                entity_id=task.id,
                summary=f"Обновлены исполнители задачи: {task.title}",
                result="success",
            )
            db.commit()
            db.refresh(task)
        except Exception:
            db.rollback()
            raise
        return normalized

    @staticmethod
    def _require_active_task(task: Task) -> None:
        if task.deleted_at is not None:
            raise TaskValidationError("Удалённую задачу нельзя изменить")

    @staticmethod
    def _clean_title(value: str) -> str:
        clean = value.strip()
        if not clean:
            raise TaskValidationError("Название задачи обязательно")
        return clean

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @staticmethod
    def _require_active_employee(
        db: Session,
        employee_id: uuid.UUID,
        *,
        label: str,
    ) -> Employee:
        employee = db.scalar(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.deleted_at.is_(None),
            )
        )
        if employee is None:
            raise TaskValidationError(f"Недоступен {label} задачи")
        return employee

    def _validate_assignees(
        self,
        db: Session,
        employee_ids: Iterable[uuid.UUID],
    ) -> list[uuid.UUID]:
        normalized = sorted(set(employee_ids), key=str)
        for employee_id in normalized:
            self._require_active_employee(db, employee_id, label="исполнитель")
        return normalized

    def _validate_links(
        self,
        db: Session,
        links: Iterable[TaskLinkInput],
        *,
        is_personal: bool,
    ) -> list[TaskLinkInput]:
        merged: dict[tuple[TaskLinkKind, uuid.UUID], TaskLinkInput] = {}
        for link in links:
            key = (link.kind, link.entity_id)
            previous = merged.get(key)
            merged[key] = TaskLinkInput(
                kind=link.kind,
                entity_id=link.entity_id,
                is_primary=link.is_primary or (previous.is_primary if previous else False),
            )
        normalized = sorted(
            merged.values(),
            key=lambda item: (item.kind.value, str(item.entity_id)),
        )
        if not is_personal and not normalized:
            raise TaskValidationError("Рабочая задача должна иметь бизнес-связь")
        if sum(1 for link in normalized if link.is_primary) > 1:
            raise TaskValidationError("У задачи может быть только одна основная связь")

        explicit_contract_ids = {
            link.entity_id for link in normalized if link.kind == TaskLinkKind.CONTRACT
        }
        item_contract_ids: set[uuid.UUID] = set()
        for link in normalized:
            entity = self._require_link_entity(db, link)
            if link.kind == TaskLinkKind.CONTRACT_ITEM:
                assert isinstance(entity, ContractItem)
                item_contract_ids.add(entity.contract_id)
        if explicit_contract_ids and any(
            contract_id not in explicit_contract_ids for contract_id in item_contract_ids
        ):
            raise TaskValidationError("Предмет договора не относится к связанному договору")
        return normalized

    @staticmethod
    def _require_link_entity(db: Session, link: TaskLinkInput) -> object:
        model_by_kind = {
            TaskLinkKind.ORGANIZATION: Organization,
            TaskLinkKind.CONTRACT: Contract,
            TaskLinkKind.CONTRACT_ITEM: ContractItem,
            TaskLinkKind.TECHNICAL_DEVICE: TechnicalDevice,
            TaskLinkKind.BUILDING: Building,
            TaskLinkKind.OPO: OPO,
        }
        model = model_by_kind[link.kind]
        entity = db.get(model, link.entity_id)
        if entity is None or getattr(entity, "deleted_at", None) is not None:
            raise TaskValidationError("Связанная бизнес-сущность недоступна")
        return entity

    def _validate_due_date_change(
        self,
        *,
        old_due_date: date | None,
        new_due_date: date | None,
        reason: str | None,
    ) -> str | None:
        clean_reason = self._clean_optional_text(reason)
        requires_reason = old_due_date is not None and (
            new_due_date is None or new_due_date > old_due_date
        )
        if requires_reason and clean_reason is None:
            raise TaskValidationError("Для увеличения срока задачи обязательна причина")
        return clean_reason

    @staticmethod
    def _replace_assignee_rows(
        db: Session,
        *,
        task_id: uuid.UUID,
        employee_ids: list[uuid.UUID],
        delete_existing: bool,
    ) -> None:
        if delete_existing:
            db.execute(sa.delete(TaskAssignee).where(TaskAssignee.task_id == task_id))
        db.add_all(
            [
                TaskAssignee(task_id=task_id, employee_id=employee_id)
                for employee_id in employee_ids
            ]
        )

    @staticmethod
    def _replace_link_rows(
        db: Session,
        *,
        task_id: uuid.UUID,
        links: list[TaskLinkInput],
        delete_existing: bool,
    ) -> None:
        models = (
            TaskOrganization,
            TaskContract,
            TaskContractItem,
            TaskTechnicalDevice,
            TaskBuilding,
            TaskOPO,
        )
        if delete_existing:
            for model in models:
                db.execute(sa.delete(model).where(model.task_id == task_id))

        row_factories = {
            TaskLinkKind.ORGANIZATION: lambda link: TaskOrganization(
                task_id=task_id,
                organization_id=link.entity_id,
                is_primary=link.is_primary,
            ),
            TaskLinkKind.CONTRACT: lambda link: TaskContract(
                task_id=task_id,
                contract_id=link.entity_id,
                is_primary=link.is_primary,
            ),
            TaskLinkKind.CONTRACT_ITEM: lambda link: TaskContractItem(
                task_id=task_id,
                contract_item_id=link.entity_id,
                is_primary=link.is_primary,
            ),
            TaskLinkKind.TECHNICAL_DEVICE: lambda link: TaskTechnicalDevice(
                task_id=task_id,
                technical_device_id=link.entity_id,
                is_primary=link.is_primary,
            ),
            TaskLinkKind.BUILDING: lambda link: TaskBuilding(
                task_id=task_id,
                building_id=link.entity_id,
                is_primary=link.is_primary,
            ),
            TaskLinkKind.OPO: lambda link: TaskOPO(
                task_id=task_id,
                opo_id=link.entity_id,
                is_primary=link.is_primary,
            ),
        }
        db.add_all([row_factories[link.kind](link) for link in links])
