from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.identity.models import Employee, User
from app.modules.organizations.models import Organization
from app.modules.tasks.enums import TaskLinkKind, TaskPriority
from app.modules.tasks.models import Task, TaskOrganization

pytestmark = pytest.mark.integration


def _actor(db: Session, suffix: str) -> tuple[User, Employee]:
    employee = Employee(full_name=f"Review Actor {suffix}")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"review-task-{suffix}-{uuid.uuid4().hex[:8]}",
        password_hash="not-used",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return user, employee


def test_create_task_rejects_soft_deleted_creator(db_session: Session) -> None:
    from app.modules.tasks.service import TaskService, TaskValidationError

    actor, employee = _actor(db_session, "deleted-creator")
    employee.deleted_at = datetime.now(UTC)
    db_session.commit()

    with pytest.raises(TaskValidationError, match="постанов"):
        TaskService().create_task(
            db_session,
            actor_user_id=actor.id,
            creator_employee_id=employee.id,
            title="Invalid creator task",
            description=None,
            due_date=None,
            priority=TaskPriority.NORMAL,
            is_personal=True,
            assignee_ids=[],
            links=[],
        )


def test_repository_exposes_normalized_links_and_related_organizations(
    db_session: Session,
) -> None:
    from app.modules.tasks import repository

    _user, employee = _actor(db_session, "repository-links")
    organization = Organization(legal_name="Repository Related Organization")
    db_session.add(organization)
    db_session.flush()
    task = Task(
        title="Repository links",
        creator_employee_id=employee.id,
        priority=TaskPriority.NORMAL,
        is_personal=False,
    )
    db_session.add(task)
    db_session.flush()
    db_session.add(
        TaskOrganization(
            task_id=task.id,
            organization_id=organization.id,
            is_primary=True,
        )
    )
    db_session.commit()

    assert repository.get_task_links(db_session, task.id) == [
        (TaskLinkKind.ORGANIZATION, organization.id, True)
    ]
    assert repository.get_task_related_organization_ids(db_session, task.id) == {
        organization.id
    }
