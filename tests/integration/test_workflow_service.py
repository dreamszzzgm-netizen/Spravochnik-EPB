from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.models import AuditEvent, Employee, EmployeeFunctionRole, User
from app.modules.tasks.enums import TaskPriority
from app.modules.workflows.models import WorkflowTaskTemplate

pytestmark = pytest.mark.integration


def _make_actor(db: Session, suffix: str) -> tuple[User, Employee]:
    employee = Employee(full_name=f"Workflow Actor {suffix}")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"workflow-actor-{suffix}-{uuid.uuid4().hex[:8]}",
        password_hash="not-used-by-service-tests",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return user, employee


def _function_role(db: Session, code: str = "expert") -> EmployeeFunctionRole:
    role = db.scalar(select(EmployeeFunctionRole).where(EmployeeFunctionRole.code == code))
    assert role is not None
    return role


def _audit_count(db: Session, action: str) -> int:
    return int(
        db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action))
        or 0
    )


def _step(role: EmployeeFunctionRole, *, title: str, order: int, days: int = 3):
    from app.modules.workflows.service import WorkflowTaskTemplateInput

    return WorkflowTaskTemplateInput(
        title=title,
        description=None,
        assignee_function_role_id=role.id,
        relative_due_days=days,
        priority=TaskPriority.NORMAL,
        sort_order=order,
        is_required=True,
    )


def test_create_template_normalizes_code_name_and_audits(db_session: Session) -> None:
    from app.modules.workflows.service import WorkflowService

    actor, _ = _make_actor(db_session, "create")
    workflow = WorkflowService().create_template(
        db_session,
        actor_user_id=actor.id,
        code="  EXPERTISE-DEFAULT  ",
        name="  Типовой процесс экспертизы  ",
    )

    assert workflow.code == "expertise-default"
    assert workflow.name == "Типовой процесс экспертизы"
    assert workflow.is_active is True
    assert workflow.version == 1
    assert _audit_count(db_session, "workflow.template_created") == 1


def test_versions_are_sequential_published_snapshots(db_session: Session) -> None:
    from app.modules.workflows.service import WorkflowService

    actor, _ = _make_actor(db_session, "versions")
    role = _function_role(db_session)
    service = WorkflowService()
    workflow = service.create_template(
        db_session,
        actor_user_id=actor.id,
        code="expertise-versioned",
        name="Версионируемый процесс",
    )

    version_one = service.create_version(
        db_session,
        actor_user_id=actor.id,
        template_id=workflow.id,
        task_templates=[_step(role, title="Запросить документы", order=10)],
    )
    assert version_one.version_number == 1
    service.publish_version(
        db_session,
        actor_user_id=actor.id,
        template_id=workflow.id,
        version_id=version_one.id,
    )

    version_two = service.create_version(
        db_session,
        actor_user_id=actor.id,
        template_id=workflow.id,
        task_templates=[
            _step(role, title="Проверить комплектность", order=10, days=2),
            _step(role, title="Подготовить программу", order=20, days=5),
        ],
    )
    assert version_two.version_number == 2

    latest_before_publish = service.latest_published_version(db_session, workflow.id)
    assert latest_before_publish.id == version_one.id

    service.publish_version(
        db_session,
        actor_user_id=actor.id,
        template_id=workflow.id,
        version_id=version_two.id,
    )
    latest = service.latest_published_version(db_session, workflow.id)
    assert latest.id == version_two.id

    first_snapshot_titles = db_session.scalars(
        select(WorkflowTaskTemplate.title)
        .where(WorkflowTaskTemplate.workflow_template_version_id == version_one.id)
        .order_by(WorkflowTaskTemplate.sort_order)
    ).all()
    assert first_snapshot_titles == ["Запросить документы"]
    assert _audit_count(db_session, "workflow.version_created") == 2
    assert _audit_count(db_session, "workflow.version_published") == 2


def test_version_validation_rejects_empty_duplicate_order_and_inactive_role(
    db_session: Session,
) -> None:
    from app.modules.workflows.service import WorkflowService, WorkflowValidationError

    actor, _ = _make_actor(db_session, "validation")
    role = _function_role(db_session)
    service = WorkflowService()
    workflow = service.create_template(
        db_session,
        actor_user_id=actor.id,
        code="validation-workflow",
        name="Проверка шаблона",
    )

    with pytest.raises(WorkflowValidationError, match="задач"):
        service.create_version(
            db_session,
            actor_user_id=actor.id,
            template_id=workflow.id,
            task_templates=[],
        )

    with pytest.raises(WorkflowValidationError, match="поряд"):
        service.create_version(
            db_session,
            actor_user_id=actor.id,
            template_id=workflow.id,
            task_templates=[
                _step(role, title="A", order=10),
                _step(role, title="B", order=10),
            ],
        )

    role.is_active = False
    db_session.commit()
    with pytest.raises(WorkflowValidationError, match="роль"):
        service.create_version(
            db_session,
            actor_user_id=actor.id,
            template_id=workflow.id,
            task_templates=[_step(role, title="A", order=10)],
        )


def test_publishing_same_version_twice_is_rejected(db_session: Session) -> None:
    from app.modules.workflows.service import WorkflowService, WorkflowValidationError

    actor, _ = _make_actor(db_session, "publish")
    role = _function_role(db_session)
    service = WorkflowService()
    workflow = service.create_template(
        db_session,
        actor_user_id=actor.id,
        code="publish-once",
        name="Однократная публикация",
    )
    version = service.create_version(
        db_session,
        actor_user_id=actor.id,
        template_id=workflow.id,
        task_templates=[_step(role, title="A", order=10)],
    )
    service.publish_version(
        db_session,
        actor_user_id=actor.id,
        template_id=workflow.id,
        version_id=version.id,
    )

    with pytest.raises(WorkflowValidationError, match="опублик"):
        service.publish_version(
            db_session,
            actor_user_id=actor.id,
            template_id=workflow.id,
            version_id=version.id,
        )
