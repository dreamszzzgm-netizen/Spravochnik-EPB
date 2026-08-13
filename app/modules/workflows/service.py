"""Application service for workflow template configuration."""

from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.tasks.enums import TaskPriority
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
            actor_user_id=actor_user_id,
            action="workflow.template_created",
            entity_type="workflow_template",
            entity_id=workflow.id,
            summary=f"Создан workflow-шаблон {workflow.name}",
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
            raise WorkflowValidationError("Порядок задач workflow должен быть уникальным")
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
            actor_user_id=actor_user_id,
            action="workflow.version_created",
            entity_type="workflow_template_version",
            entity_id=version.id,
            summary=f"Создана версия workflow {version.version_number}",
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
            actor_user_id=actor_user_id,
            action="workflow.version_published",
            entity_type="workflow_template_version",
            entity_id=version.id,
            summary=f"Опубликована версия workflow {version.version_number}",
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
