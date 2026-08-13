from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.models import AuditEvent, Employee, User
from app.modules.tasks.enums import TaskPriority
from app.modules.tasks.models import Task

pytestmark = pytest.mark.integration


def _make_actor(db: Session) -> tuple[User, Employee]:
    employee = Employee(full_name="Transactional Task Actor")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"task-tx-{uuid.uuid4().hex[:8]}",
        password_hash="not-used-by-service-tests",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return user, employee


def _audit_count(db: Session, action: str) -> int:
    return int(
        db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action))
        or 0
    )


def test_create_task_commit_false_can_be_rolled_back(db_session: Session) -> None:
    from app.modules.tasks.service import TaskService

    actor, employee = _make_actor(db_session)
    before_audit = _audit_count(db_session, "task.created")

    task = TaskService().create_task(
        db_session,
        actor_user_id=actor.id,
        creator_employee_id=employee.id,
        title="Workflow generated task",
        description=None,
        due_date=date(2026, 8, 20),
        priority=TaskPriority.NORMAL,
        is_personal=True,
        assignee_ids=[employee.id],
        links=[],
        commit=False,
    )
    task_id = task.id

    assert db_session.in_transaction()
    assert db_session.scalar(select(Task.id).where(Task.id == task_id)) == task_id
    assert _audit_count(db_session, "task.created") == before_audit + 1

    db_session.rollback()

    assert db_session.scalar(select(func.count()).select_from(Task).where(Task.id == task_id)) == 0
    assert _audit_count(db_session, "task.created") == before_audit
