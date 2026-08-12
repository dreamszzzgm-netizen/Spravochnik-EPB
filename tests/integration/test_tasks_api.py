from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

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
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task, TaskAssignee, TaskOrganization

pytestmark = pytest.mark.integration


def _create_user(db: Session, *, username: str) -> User:
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


def _employee(db: Session, user: User) -> Employee:
    employee = db.get(Employee, user.employee_id)
    assert employee is not None
    return employee


def _grant(
    db: Session,
    *,
    user: User,
    permission_code: str,
    scope_type: ScopeType,
    scope_config: dict | None = None,
) -> None:
    role_code = f"task-api-{permission_code.replace('.', '-')}-{uuid.uuid4().hex[:8]}"
    role = Role(code=role_code, name=role_code, is_system=False)
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


def _token(db: Session, user: User) -> str:
    from app.core.config import get_settings
    from app.modules.identity.service import AuthService

    db.commit()
    return AuthService(get_settings()).login(
        db,
        username=user.username,
        password="test-password-123!",
        ip_address="127.0.0.1",
        user_agent="cp51-task-api-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _task(
    db: Session,
    *,
    creator: Employee,
    title: str,
    due_date: date | None = None,
    status: TaskStatus = TaskStatus.NEW,
    priority: TaskPriority = TaskPriority.NORMAL,
    is_personal: bool = True,
) -> Task:
    task = Task(
        title=title,
        creator_employee_id=creator.id,
        due_date=due_date,
        status=status,
        priority=priority,
        is_personal=is_personal,
    )
    db.add(task)
    db.flush()
    return task


def test_tasks_require_authentication_and_exact_read_permission(
    db_session: Session,
    client,
) -> None:
    assert client.get("/api/tasks").status_code == 401

    user = _create_user(db_session, username="tasks-wrong-read-permission")
    _grant(
        db_session,
        user=user,
        permission_code="tasks.edit",
        scope_type=ScopeType.ALL,
    )
    token = _token(db_session, user)

    assert client.get("/api/tasks", headers=_auth(token)).status_code == 403


def test_tasks_assigned_scope_filters_list_and_non_enumerates_detail(
    db_session: Session,
    client,
) -> None:
    creator_user = _create_user(db_session, username="tasks-fixture-creator")
    viewer = _create_user(db_session, username="tasks-assigned-viewer")
    creator_employee = _employee(db_session, creator_user)
    assigned = _task(
        db_session,
        creator=creator_employee,
        title="Assigned visible task",
    )
    foreign = _task(
        db_session,
        creator=creator_employee,
        title="Foreign hidden task",
    )
    db_session.add(TaskAssignee(task_id=assigned.id, employee_id=viewer.employee_id))
    _grant(
        db_session,
        user=viewer,
        permission_code="tasks.view",
        scope_type=ScopeType.ASSIGNED,
    )
    token = _token(db_session, viewer)

    response = client.get("/api/tasks", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [str(assigned.id)]

    detail = client.get(f"/api/tasks/{assigned.id}", headers=_auth(token))
    assert detail.status_code == 200
    assert detail.json()["assignee_ids"] == [str(viewer.employee_id)]

    assert (
        client.get(f"/api/tasks/{foreign.id}", headers=_auth(token)).status_code
        == 404
    )


def test_tasks_view_all_is_global_read_only_override(db_session: Session, client) -> None:
    creator = _create_user(db_session, username="tasks-view-all-creator")
    creator_employee = _employee(db_session, creator)
    _task(db_session, creator=creator_employee, title="Global task one")
    _task(db_session, creator=creator_employee, title="Global task two")
    manager = _create_user(db_session, username="tasks-view-all-manager")
    _grant(
        db_session,
        user=manager,
        permission_code="tasks.view_all",
        scope_type=ScopeType.OWN,
    )
    token = _token(db_session, manager)

    response = client.get("/api/tasks", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["total"] == 2

    create = client.post(
        "/api/tasks",
        headers=_auth(token),
        json={"title": "Must not create", "is_personal": True, "links": []},
    )
    assert create.status_code == 403


def test_create_task_binds_creator_and_rejects_protected_fields(
    db_session: Session,
    client,
) -> None:
    user = _create_user(db_session, username="tasks-create-user")
    _grant(
        db_session,
        user=user,
        permission_code="tasks.create",
        scope_type=ScopeType.ALL,
    )
    token = _token(db_session, user)

    response = client.post(
        "/api/tasks",
        headers=_auth(token),
        json={
            "title": "  Новая ручная задача  ",
            "description": "Описание",
            "due_date": "2026-08-20",
            "priority": "high",
            "is_personal": True,
            "links": [],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Новая ручная задача"
    assert body["creator_employee_id"] == str(user.employee_id)
    assert body["status"] == "new"
    assert body["assignee_ids"] == []
    assert body["is_overdue"] is False

    protected = client.post(
        "/api/tasks",
        headers=_auth(token),
        json={
            "title": "Forged creator",
            "is_personal": True,
            "links": [],
            "creator_employee_id": str(uuid.uuid4()),
            "status": "completed",
        },
    )
    assert protected.status_code == 422


def test_task_patch_is_scoped_and_cannot_write_status(
    db_session: Session,
    client,
) -> None:
    owner = _create_user(db_session, username="tasks-own-editor")
    outsider = _create_user(db_session, username="tasks-own-outsider")
    task = _task(
        db_session,
        creator=_employee(db_session, owner),
        title="Editable task",
    )
    for user in (owner, outsider):
        _grant(
            db_session,
            user=user,
            permission_code="tasks.edit",
            scope_type=ScopeType.OWN,
        )
    owner_token = _token(db_session, owner)
    outsider_token = _token(db_session, outsider)

    response = client.patch(
        f"/api/tasks/{task.id}",
        headers=_auth(owner_token),
        json={"title": "Updated by owner"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated by owner"

    assert (
        client.patch(
            f"/api/tasks/{task.id}",
            headers=_auth(outsider_token),
            json={"title": "Forbidden update"},
        ).status_code
        == 404
    )

    protected = client.patch(
        f"/api/tasks/{task.id}",
        headers=_auth(owner_token),
        json={"status": "completed"},
    )
    assert protected.status_code == 422


def test_assign_and_status_commands_use_separate_permissions(
    db_session: Session,
    client,
) -> None:
    creator = _create_user(db_session, username="tasks-command-creator")
    assignee = _create_user(db_session, username="tasks-command-assignee")
    task = _task(
        db_session,
        creator=_employee(db_session, creator),
        title="Command task",
    )
    editor = _create_user(db_session, username="tasks-command-editor")
    assigner = _create_user(db_session, username="tasks-command-assigner")
    status_user = _create_user(db_session, username="tasks-command-status")
    _grant(db_session, user=editor, permission_code="tasks.edit", scope_type=ScopeType.ALL)
    _grant(db_session, user=assigner, permission_code="tasks.assign", scope_type=ScopeType.ALL)
    _grant(
        db_session,
        user=status_user,
        permission_code="tasks.change_status",
        scope_type=ScopeType.ALL,
    )
    editor_token = _token(db_session, editor)
    assigner_token = _token(db_session, assigner)
    status_token = _token(db_session, status_user)

    assert (
        client.put(
            f"/api/tasks/{task.id}/assignees",
            headers=_auth(editor_token),
            json={"employee_ids": [str(assignee.employee_id)]},
        ).status_code
        == 403
    )
    assigned = client.put(
        f"/api/tasks/{task.id}/assignees",
        headers=_auth(assigner_token),
        json={"employee_ids": [str(assignee.employee_id), str(assignee.employee_id)]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignee_ids"] == [str(assignee.employee_id)]

    assert (
        client.post(
            f"/api/tasks/{task.id}/status",
            headers=_auth(editor_token),
            json={"status": "in_progress"},
        ).status_code
        == 403
    )
    changed = client.post(
        f"/api/tasks/{task.id}/status",
        headers=_auth(status_token),
        json={"status": "in_progress"},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "in_progress"


def test_delete_restore_and_registry_filters(db_session: Session, client) -> None:
    user = _create_user(db_session, username="tasks-delete-restore")
    for permission_code in (
        "tasks.view",
        "tasks.view_all",
        "tasks.delete",
        "tasks.restore",
    ):
        _grant(
            db_session,
            user=user,
            permission_code=permission_code,
            scope_type=ScopeType.ALL,
        )
    organization = Organization(legal_name="Task Filter Organization")
    db_session.add(organization)
    db_session.flush()
    user_employee = _employee(db_session, user)
    overdue = _task(
        db_session,
        creator=user_employee,
        title="Overdue urgent task",
        due_date=date.today() - timedelta(days=2),
        priority=TaskPriority.URGENT,
        is_personal=False,
    )
    db_session.add(
        TaskOrganization(
            task_id=overdue.id,
            organization_id=organization.id,
            is_primary=True,
        )
    )
    completed = _task(
        db_session,
        creator=user_employee,
        title="Completed old task",
        due_date=date.today() - timedelta(days=5),
        status=TaskStatus.COMPLETED,
    )
    token = _token(db_session, user)

    filtered = client.get(
        "/api/tasks",
        headers=_auth(token),
        params={
            "is_overdue": "true",
            "priority": "urgent",
            "organization_id": str(organization.id),
        },
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [str(overdue.id)]

    deleted = client.delete(f"/api/tasks/{overdue.id}", headers=_auth(token))
    assert deleted.status_code == 204
    assert client.get(f"/api/tasks/{overdue.id}", headers=_auth(token)).status_code == 404

    restored = client.post(
        f"/api/tasks/{overdue.id}/restore",
        headers=_auth(token),
    )
    assert restored.status_code == 200
    assert restored.json()["id"] == str(overdue.id)
    assert restored.json()["deleted_at"] is None

    regular = client.get(
        "/api/tasks",
        headers=_auth(token),
        params={"status": "completed"},
    )
    assert regular.status_code == 200
    assert [item["id"] for item in regular.json()["items"]] == [str(completed.id)]
