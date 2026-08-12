from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.models import AuditEvent, Employee, EmploymentType, User
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.service import TaskService, TaskValidationError


def _actor(db: Session) -> tuple[User, Employee]:
    employee = Employee(
        full_name="Task lifecycle actor",
        employment_type=EmploymentType.STAFF,
    )
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"task-life-{uuid.uuid4().hex[:10]}",
        password_hash="not-used",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user, employee


def _task(
    db: Session,
    *,
    creator_employee_id: uuid.UUID,
    status: TaskStatus = TaskStatus.NEW,
    due_date: date | None = date(2026, 8, 20),
) -> Task:
    task = Task(
        title="Lifecycle task",
        creator_employee_id=creator_employee_id,
        due_date=due_date,
        priority=TaskPriority.NORMAL,
        status=status,
        is_personal=True,
        version=1,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _audit_count(db: Session, task_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.entity_type == "task",
                AuditEvent.entity_id == task_id,
            )
        )
        or 0
    )


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (TaskStatus.NEW, TaskStatus.IN_PROGRESS),
        (TaskStatus.NEW, TaskStatus.CANCELLED),
        (TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED),
        (TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED),
    ],
)
def test_allowed_task_status_transitions(
    db_session: Session,
    source: TaskStatus,
    target: TaskStatus,
) -> None:
    actor, employee = _actor(db_session)
    task = _task(db_session, creator_employee_id=employee.id, status=source)

    changed = TaskService().change_status(
        db_session,
        actor_user_id=actor.id,
        task=task,
        target_status=target,
    )

    assert changed.status == target
    assert changed.version == 2
    assert (changed.completed_at is not None) is (target == TaskStatus.COMPLETED)
    assert (changed.cancelled_at is not None) is (target == TaskStatus.CANCELLED)
    assert _audit_count(db_session, task.id) == 1


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (TaskStatus.NEW, TaskStatus.COMPLETED),
        (TaskStatus.NEW, TaskStatus.NEW),
        (TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS),
        (TaskStatus.CANCELLED, TaskStatus.IN_PROGRESS),
    ],
)
def test_rejected_task_status_transition_keeps_state_version_and_audit(
    db_session: Session,
    source: TaskStatus,
    target: TaskStatus,
) -> None:
    actor, employee = _actor(db_session)
    task = _task(db_session, creator_employee_id=employee.id, status=source)
    original_version = task.version
    original_audit = _audit_count(db_session, task.id)

    with pytest.raises(TaskValidationError):
        TaskService().change_status(
            db_session,
            actor_user_id=actor.id,
            task=task,
            target_status=target,
        )

    db_session.refresh(task)
    assert task.status == source
    assert task.version == original_version
    assert _audit_count(db_session, task.id) == original_audit


def test_deleted_task_cannot_change_status(db_session: Session) -> None:
    actor, employee = _actor(db_session)
    task = _task(db_session, creator_employee_id=employee.id)
    TaskService().delete_task(db_session, actor_user_id=actor.id, task=task)
    original_version = task.version
    original_audit = _audit_count(db_session, task.id)

    with pytest.raises(TaskValidationError):
        TaskService().change_status(
            db_session,
            actor_user_id=actor.id,
            task=task,
            target_status=TaskStatus.IN_PROGRESS,
        )

    db_session.refresh(task)
    assert task.version == original_version
    assert _audit_count(db_session, task.id) == original_audit


def test_due_date_extension_and_removal_require_reason(db_session: Session) -> None:
    actor, employee = _actor(db_session)
    service = TaskService()

    later = _task(db_session, creator_employee_id=employee.id)
    with pytest.raises(TaskValidationError):
        service.update_task(
            db_session,
            actor_user_id=actor.id,
            task=later,
            title=later.title,
            description=None,
            due_date=date(2026, 8, 21),
            priority=later.priority,
            is_personal=True,
            links=[],
            due_date_change_reason=None,
        )
    db_session.refresh(later)
    assert later.due_date == date(2026, 8, 20)
    assert later.version == 1

    removed = _task(db_session, creator_employee_id=employee.id)
    with pytest.raises(TaskValidationError):
        service.update_task(
            db_session,
            actor_user_id=actor.id,
            task=removed,
            title=removed.title,
            description=None,
            due_date=None,
            priority=removed.priority,
            is_personal=True,
            links=[],
            due_date_change_reason="  ",
        )
    db_session.refresh(removed)
    assert removed.due_date == date(2026, 8, 20)
    assert removed.version == 1


def test_due_date_extension_with_reason_is_audited(db_session: Session) -> None:
    actor, employee = _actor(db_session)
    task = _task(db_session, creator_employee_id=employee.id)

    updated = TaskService().update_task(
        db_session,
        actor_user_id=actor.id,
        task=task,
        title=task.title,
        description=None,
        due_date=date(2026, 8, 21),
        priority=task.priority,
        is_personal=True,
        links=[],
        due_date_change_reason="Customer requested extension",
    )

    event = db_session.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "task",
            AuditEvent.entity_id == task.id,
            AuditEvent.action == "task.updated",
        )
        .order_by(AuditEvent.timestamp.desc())
    )
    assert updated.due_date == date(2026, 8, 21)
    assert event is not None
    assert event.metadata_json == {
        "old_due_date": "2026-08-20",
        "new_due_date": "2026-08-21",
        "reason": "Customer requested extension",
    }


def test_is_task_overdue_is_computed_not_persisted(db_session: Session) -> None:
    from app.modules.tasks.service import is_task_overdue

    _actor_user, employee = _actor(db_session)
    open_task = _task(
        db_session,
        creator_employee_id=employee.id,
        due_date=date(2026, 8, 11),
    )
    completed = _task(
        db_session,
        creator_employee_id=employee.id,
        status=TaskStatus.COMPLETED,
        due_date=date(2026, 8, 11),
    )
    no_due = _task(db_session, creator_employee_id=employee.id, due_date=None)

    assert is_task_overdue(open_task, today=date(2026, 8, 12)) is True
    assert is_task_overdue(completed, today=date(2026, 8, 12)) is False
    assert is_task_overdue(no_due, today=date(2026, 8, 12)) is False
    assert "is_overdue" not in Task.__table__.columns
