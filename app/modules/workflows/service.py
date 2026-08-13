"""Application service for workflow template configuration and instantiation."""

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.tasks.enums import TaskPriority
from app.modules.tasks.models import Task
from app.modules.tasks.service import TaskLinkInput, TaskService
from app.modules.workflows import repository
from app.modules.workflows.models import (
    WorkflowTaskTemplate,
    WorkflowTemplate,
    WorkflowTemplateVersion,
)


class WorkflowValidationError(ValueError):
    """Raised when workflow configuration violates a business rule."""


class WorkflowNotFoundError(LookupError):
    """Raised when a requested workflow resource is unavailable."""


@dataclass(frozen=True, slots=True)
class WorkflowTaskTemplateInput:
    title: str
    description: str | None
    assignee_function_role_id: uuid.UUID
    relative_due_days: int
    priority: TaskPriority = TaskPriority.NORMAL
    sort_order: int = 0
    is_required: bool = True


class WorkflowService:
    def create_template(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        code: str,
        name: str,
    ) -> WorkflowTemplate:
        normalized_code = code.strip().lower()
        normalized_name = name.strip()
        if not normalized_code:
            raise WorkflowValidationError("Код workflow не может быть пустым")
        if not normalized_name:
            raise WorkflowValidationError("Название workflow не может быть пустым")
        if repository.get_template_by_code(db, normalized_code) is not None:
            raise WorkflowValidationError("Workflow с таким кодом уже существует")

        workflow = WorkflowTemplate(
            code=normalized_code,
            name=normalized_name,
            is_active=True,
            created_by=actor_user_id,
        )
        db.add(workflow)
        db.flush()
        write_audit(
            db,
            user_id=actor_user_id,
            action="workflow.template_created",
            entity_type="workflow_template",
            entity_id=workflow.id,
            summary=f"Создан workflow-шаблон {workflow.name}",
            result="success",
            metadata={"code": workflow.code},
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise WorkflowValidationError("Workflow с таким кодом уже существует") from exc
        db.refresh(workflow)
        return workflow

    def create_version(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        template_id: uuid.UUID,
        task_templates: list[WorkflowTaskTemplateInput],
    ) -> WorkflowTemplateVersion:
        steps = tuple(task_templates)
        if not steps:
            raise WorkflowValidationError("Версия workflow должна содержать хотя бы одну задачу")

        orders = [step.sort_order for step in steps]
        if len(orders) != len(set(orders)):
            raise WorkflowValidationError(
                "Нарушен порядок задач workflow: значения должны быть уникальны"
            )
        if any(step.sort_order < 0 for step in steps):
            raise WorkflowValidationError("Порядок задач workflow не может быть отрицательным")
        if any(step.relative_due_days < 0 for step in steps):
            raise WorkflowValidationError("Относительный срок задачи не может быть отрицательным")
        if any(not step.title.strip() for step in steps):
            raise WorkflowValidationError("Название задачи workflow не может быть пустым")

        role_ids = {step.assignee_function_role_id for step in steps}
        active_role_ids = repository.active_function_role_ids(db, role_ids)
        if active_role_ids != role_ids:
            raise WorkflowValidationError("Указанная функциональная роль отсутствует или неактивна")

        workflow = repository.get_template_for_update(db, template_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow-шаблон не найден")
        if not workflow.is_active:
            raise WorkflowValidationError("Workflow-шаблон неактивен")

        version = WorkflowTemplateVersion(
            workflow_template_id=workflow.id,
            version_number=repository.next_version_number(db, workflow.id),
            created_by=actor_user_id,
        )
        db.add(version)
        db.flush()
        for step in sorted(steps, key=lambda item: item.sort_order):
            db.add(
                WorkflowTaskTemplate(
                    workflow_template_version_id=version.id,
                    title=step.title.strip(),
                    description=step.description.strip() if step.description else None,
                    assignee_function_role_id=step.assignee_function_role_id,
                    relative_due_days=step.relative_due_days,
                    priority=step.priority,
                    sort_order=step.sort_order,
                    is_required=step.is_required,
                )
            )
        db.flush()
        write_audit(
            db,
            user_id=actor_user_id,
            action="workflow.version_created",
            entity_type="workflow_template_version",
            entity_id=version.id,
            summary=f"Создана версия workflow {version.version_number}",
            result="success",
            metadata={
                "workflow_template_id": str(workflow.id),
                "version_number": version.version_number,
                "task_count": len(steps),
            },
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise WorkflowValidationError("Не удалось создать новую версию workflow") from exc
        db.refresh(version)
        return version

    def publish_version(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        template_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> WorkflowTemplateVersion:
        workflow = repository.get_template_for_update(db, template_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow-шаблон не найден")
        if not workflow.is_active:
            raise WorkflowValidationError("Workflow-шаблон неактивен")

        version = repository.get_version(db, template_id, version_id, for_update=True)
        if version is None:
            raise WorkflowNotFoundError("Версия workflow не найдена")
        if version.published_at is not None:
            raise WorkflowValidationError("Версия workflow уже опубликована")

        version.published_at = datetime.now(UTC)
        write_audit(
            db,
            user_id=actor_user_id,
            action="workflow.version_published",
            entity_type="workflow_template_version",
            entity_id=version.id,
            summary=f"Опубликована версия workflow {version.version_number}",
            result="success",
            metadata={
                "workflow_template_id": str(workflow.id),
                "version_number": version.version_number,
            },
        )
        db.commit()
        db.refresh(version)
        return version

    def latest_published_version(
        self,
        db: Session,
        template_id: uuid.UUID,
    ) -> WorkflowTemplateVersion:
        workflow = repository.get_template(db, template_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow-шаблон не найден")
        version = repository.latest_published_version(db, template_id)
        if version is None:
            raise WorkflowValidationError("У workflow нет опубликованной версии")
        return version

    def instantiate(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        creator_employee_id: uuid.UUID,
        template_id: uuid.UUID,
        anchor_date: date,
        links: Iterable[TaskLinkInput],
        due_date_resolver: Callable[[date, int], date],
    ) -> list[Task]:
        workflow = repository.get_template(db, template_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow-шаблон не найден")
        if not workflow.is_active:
            raise WorkflowValidationError("Workflow-шаблон неактивен")

        version = repository.latest_published_version(db, template_id)
        if version is None:
            raise WorkflowValidationError("У workflow нет опубликованной версии")
        steps = repository.list_task_templates(db, version.id)
        if not steps:
            raise WorkflowValidationError("Опубликованная версия workflow не содержит задач")

        assignees_by_role: dict[uuid.UUID, list[uuid.UUID]] = {}
        for role_id in {step.assignee_function_role_id for step in steps}:
            employee_ids = repository.eligible_employee_ids_for_function_role(
                db,
                function_role_id=role_id,
                anchor_date=anchor_date,
            )
            if not employee_ids:
                raise WorkflowValidationError(
                    "Не найден доступный сотрудник для функциональной роли workflow"
                )
            assignees_by_role[role_id] = employee_ids

        normalized_links = tuple(links)
        created_tasks: list[Task] = []
        task_service = TaskService()
        try:
            for step in steps:
                task = task_service.create_task(
                    db,
                    actor_user_id=actor_user_id,
                    creator_employee_id=creator_employee_id,
                    title=step.title,
                    description=step.description,
                    due_date=due_date_resolver(anchor_date, step.relative_due_days),
                    priority=step.priority,
                    is_personal=False,
                    assignee_ids=assignees_by_role[step.assignee_function_role_id],
                    links=normalized_links,
                    commit=False,
                )
                task.source_workflow_template_version_id = version.id
                task.source_workflow_task_template_id = step.id
                db.flush()
                created_tasks.append(task)

            write_audit(
                db,
                user_id=actor_user_id,
                action="workflow.instantiated",
                entity_type="workflow_template",
                entity_id=workflow.id,
                summary=f"Созданы задачи workflow {workflow.name}",
                result="success",
                metadata={
                    "workflow_template_version_id": str(version.id),
                    "version_number": version.version_number,
                    "task_count": len(created_tasks),
                },
            )
            db.commit()
            for task in created_tasks:
                db.refresh(task)
        except Exception:
            db.rollback()
            raise
        return created_tasks
