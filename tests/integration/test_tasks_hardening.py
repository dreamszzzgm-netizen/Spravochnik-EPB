from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.contracts.models import Contract
from app.modules.identity.models import (
    Employee,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password
from app.modules.organizations.models import Organization
from app.modules.tasks.enums import TaskLinkKind, TaskPriority, TaskStatus
from app.modules.tasks.models import Task, TaskContract, TaskOrganization
from app.modules.tasks.service import TaskLinkInput, TaskService, TaskValidationError

pytestmark = pytest.mark.integration


def _user(db: Session, username: str) -> User:
    employee = Employee(full_name=f"{username} Employee")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=username,
        password_hash=hash_password("test-password-123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _grant(
    db: Session,
    *,
    user: User,
    permission_code: str,
    scope_type: ScopeType,
    scope_config: dict | None = None,
) -> None:
    role = Role(
        code=f"task-hardening-{uuid.uuid4().hex[:10]}",
        name="Task hardening role",
        is_system=False,
    )
    db.add(role)
    db.flush()
    permission_id = db.scalar(
        text("SELECT id FROM permissions WHERE code = :code"),
        {"code": permission_code},
    )
    assert permission_id is not None
    db.add(RolePermission(role_id=role.id, permission_id=permission_id))
    db.add(
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            scope_type=scope_type,
            scope_config=scope_config,
            assigned_by=user.id,
        )
    )
    db.flush()


def _related(*organization_ids: uuid.UUID) -> dict[str, list[str]]:
    return {"organization_ids": [str(value) for value in organization_ids]}


def _token(db: Session, user: User) -> str:
    from app.core.config import get_settings
    from app.modules.identity.service import AuthService

    db.commit()
    return AuthService(get_settings()).login(
        db,
        username=user.username,
        password="test-password-123!",
        ip_address="127.0.0.1",
        user_agent="cp51-hardening-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_task_cannot_reference_foreign_organization(
    db_session: Session,
    client,
) -> None:
    actor = _user(db_session, "task-reference-create")
    allowed = Organization(legal_name="Allowed task organization")
    foreign = Organization(legal_name="Foreign task organization")
    db_session.add_all([allowed, foreign])
    db_session.flush()
    _grant(
        db_session,
        user=actor,
        permission_code="tasks.create",
        scope_type=ScopeType.ALL,
    )
    _grant(
        db_session,
        user=actor,
        permission_code="organizations.view",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _token(db_session, actor)

    forbidden = client.post(
        "/api/tasks",
        headers=_auth(token),
        json={
            "title": "Foreign reference",
            "is_personal": False,
            "links": [
                {
                    "kind": "organization",
                    "entity_id": str(foreign.id),
                    "is_primary": True,
                }
            ],
        },
    )
    assert forbidden.status_code == 404

    allowed_response = client.post(
        "/api/tasks",
        headers=_auth(token),
        json={
            "title": "Allowed reference",
            "is_personal": False,
            "links": [
                {
                    "kind": "organization",
                    "entity_id": str(allowed.id),
                    "is_primary": True,
                }
            ],
        },
    )
    assert allowed_response.status_code == 201


def test_update_links_cannot_escape_related_scope_and_keeps_old_link(
    db_session: Session,
    client,
) -> None:
    from app.modules.tasks import repository

    actor = _user(db_session, "task-reference-update")
    allowed = Organization(legal_name="Allowed update organization")
    foreign = Organization(legal_name="Foreign update organization")
    db_session.add_all([allowed, foreign])
    db_session.flush()
    task = Task(
        title="Scoped link update",
        creator_employee_id=actor.employee_id,
        priority=TaskPriority.NORMAL,
        status=TaskStatus.NEW,
        is_personal=False,
    )
    db_session.add(task)
    db_session.flush()
    db_session.add(
        TaskOrganization(
            task_id=task.id,
            organization_id=allowed.id,
            is_primary=True,
        )
    )
    _grant(
        db_session,
        user=actor,
        permission_code="tasks.edit",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    _grant(
        db_session,
        user=actor,
        permission_code="organizations.view",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _token(db_session, actor)

    response = client.patch(
        f"/api/tasks/{task.id}",
        headers=_auth(token),
        json={
            "links": [
                {
                    "kind": "organization",
                    "entity_id": str(foreign.id),
                    "is_primary": True,
                }
            ]
        },
    )
    assert response.status_code == 404
    assert repository.get_task_links(db_session, task.id) == [
        (TaskLinkKind.ORGANIZATION, allowed.id, True)
    ]


def test_failed_multi_primary_update_preserves_existing_links(db_session: Session) -> None:
    from app.modules.tasks import repository

    actor = _user(db_session, "task-primary-rollback")
    first = Organization(legal_name="Primary first")
    second = Organization(legal_name="Primary second")
    db_session.add_all([first, second])
    db_session.flush()
    task = Task(
        title="Primary rollback",
        creator_employee_id=actor.employee_id,
        priority=TaskPriority.NORMAL,
        status=TaskStatus.NEW,
        is_personal=False,
    )
    db_session.add(task)
    db_session.flush()
    db_session.add(
        TaskOrganization(task_id=task.id, organization_id=first.id, is_primary=True)
    )
    db_session.commit()

    with pytest.raises(TaskValidationError):
        TaskService().update_task(
            db_session,
            actor_user_id=actor.id,
            task=task,
            title=task.title,
            description=task.description,
            due_date=task.due_date,
            priority=task.priority,
            is_personal=False,
            links=[
                TaskLinkInput(TaskLinkKind.ORGANIZATION, first.id, True),
                TaskLinkInput(TaskLinkKind.ORGANIZATION, second.id, True),
            ],
            due_date_change_reason=None,
        )

    assert repository.get_task_links(db_session, task.id) == [
        (TaskLinkKind.ORGANIZATION, first.id, True)
    ]


def test_registry_organization_filter_does_not_duplicate_task(db_session: Session) -> None:
    from app.modules.tasks import repository

    actor = _user(db_session, "task-registry-dedupe")
    organization = Organization(legal_name="Registry dedupe organization")
    db_session.add(organization)
    db_session.flush()
    contract = Contract(
        customer_organization_id=organization.id,
        number=f"D-{uuid.uuid4().hex[:8]}",
        contract_date=date(2026, 8, 12),
        created_by=actor.id,
    )
    db_session.add(contract)
    db_session.flush()
    task = Task(
        title="Deduplicated registry task",
        creator_employee_id=actor.employee_id,
        priority=TaskPriority.NORMAL,
        status=TaskStatus.NEW,
        is_personal=False,
    )
    db_session.add(task)
    db_session.flush()
    db_session.add_all(
        [
            TaskOrganization(
                task_id=task.id,
                organization_id=organization.id,
                is_primary=True,
            ),
            TaskContract(
                task_id=task.id,
                contract_id=contract.id,
                is_primary=False,
            ),
        ]
    )
    db_session.commit()

    items, total = repository.list_tasks_paginated(
        db_session,
        organization_id=organization.id,
        page=1,
        page_size=20,
    )
    assert total == 1
    assert [item.id for item in items] == [task.id]


def test_restore_preserves_terminal_state_and_timestamp(db_session: Session) -> None:
    actor = _user(db_session, "task-terminal-restore")
    completed_at = datetime(2026, 8, 12, 10, 30, tzinfo=UTC)
    task = Task(
        title="Completed restore",
        creator_employee_id=actor.employee_id,
        priority=TaskPriority.NORMAL,
        status=TaskStatus.COMPLETED,
        is_personal=True,
        completed_at=completed_at,
    )
    db_session.add(task)
    db_session.commit()

    service = TaskService()
    service.delete_task(db_session, actor_user_id=actor.id, task=task)
    service.restore_task(db_session, actor_user_id=actor.id, task=task)

    assert task.status == TaskStatus.COMPLETED
    assert task.completed_at == completed_at
    assert task.deleted_at is None
