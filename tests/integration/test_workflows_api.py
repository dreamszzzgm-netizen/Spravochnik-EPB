from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.identity.models import (
    Employee,
    EmployeeFunctionRole,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password

pytestmark = pytest.mark.integration


def _create_user(db: Session, *, username: str, superuser: bool = False) -> User:
    employee = Employee(full_name=f"{username} Employee")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=username,
        password_hash=hash_password("test-password-123!"),
        is_active=True,
        is_superuser=superuser,
    )
    db.add(user)
    db.flush()
    return user


def _grant(db: Session, *, user: User, permission_code: str) -> None:
    role_code = f"workflow-api-{uuid.uuid4().hex[:10]}"
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
            scope_type=ScopeType.ALL,
            scope_config=None,
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
        user_agent="cp52-workflow-api-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _expert_role(db: Session) -> EmployeeFunctionRole:
    role = db.scalar(select(EmployeeFunctionRole).where(EmployeeFunctionRole.code == "expert"))
    assert role is not None
    return role


def test_workflow_api_requires_authentication_and_exact_permission(
    db_session: Session,
    client,
) -> None:
    assert client.get("/api/workflows").status_code == 401

    user = _create_user(db_session, username="workflow-api-wrong-permission")
    _grant(db_session, user=user, permission_code="tasks.create")
    token = _token(db_session, user)

    assert client.get("/api/workflows", headers=_auth(token)).status_code == 403


def test_workflow_management_api_create_version_publish_and_read(
    db_session: Session,
    client,
) -> None:
    user = _create_user(db_session, username="workflow-api-manager")
    _grant(db_session, user=user, permission_code="workflows.manage")
    token = _token(db_session, user)
    headers = _auth(token)
    expert_role = _expert_role(db_session)

    created = client.post(
        "/api/workflows",
        headers=headers,
        json={"code": "  API-EXPERTISE  ", "name": "  API Workflow  "},
    )
    assert created.status_code == 201
    workflow = created.json()
    assert workflow["code"] == "api-expertise"
    assert workflow["name"] == "API Workflow"

    version_response = client.post(
        f"/api/workflows/{workflow['id']}/versions",
        headers=headers,
        json={
            "task_templates": [
                {
                    "title": "Request documents",
                    "description": None,
                    "assignee_function_role_id": str(expert_role.id),
                    "relative_due_days": 3,
                    "priority": "normal",
                    "sort_order": 10,
                    "is_required": True,
                }
            ]
        },
    )
    assert version_response.status_code == 201
    version = version_response.json()
    assert version["version_number"] == 1
    assert version["published_at"] is None
    assert [item["title"] for item in version["task_templates"]] == ["Request documents"]

    published = client.post(
        f"/api/workflows/{workflow['id']}/versions/{version['id']}/publish",
        headers=headers,
    )
    assert published.status_code == 200
    assert published.json()["published_at"] is not None

    detail = client.get(f"/api/workflows/{workflow['id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["code"] == "api-expertise"
    assert [item["version_number"] for item in body["versions"]] == [1]

    listing = client.get("/api/workflows", headers=headers)
    assert listing.status_code == 200
    assert workflow["id"] in {item["id"] for item in listing.json()}


def test_workflow_api_rejects_double_publish_and_duplicate_sort_order(
    db_session: Session,
    client,
) -> None:
    user = _create_user(db_session, username="workflow-api-validation")
    _grant(db_session, user=user, permission_code="workflows.manage")
    token = _token(db_session, user)
    headers = _auth(token)
    expert_role = _expert_role(db_session)

    created = client.post(
        "/api/workflows",
        headers=headers,
        json={"code": f"validation-{uuid.uuid4().hex[:8]}", "name": "Validation Workflow"},
    )
    assert created.status_code == 201
    workflow_id = created.json()["id"]

    duplicate = client.post(
        f"/api/workflows/{workflow_id}/versions",
        headers=headers,
        json={
            "task_templates": [
                {
                    "title": "A",
                    "assignee_function_role_id": str(expert_role.id),
                    "relative_due_days": 1,
                    "priority": "normal",
                    "sort_order": 10,
                    "is_required": True,
                },
                {
                    "title": "B",
                    "assignee_function_role_id": str(expert_role.id),
                    "relative_due_days": 2,
                    "priority": "normal",
                    "sort_order": 10,
                    "is_required": True,
                },
            ]
        },
    )
    assert duplicate.status_code == 422

    version_response = client.post(
        f"/api/workflows/{workflow_id}/versions",
        headers=headers,
        json={
            "task_templates": [
                {
                    "title": "A",
                    "assignee_function_role_id": str(expert_role.id),
                    "relative_due_days": 1,
                    "priority": "normal",
                    "sort_order": 10,
                    "is_required": True,
                }
            ]
        },
    )
    assert version_response.status_code == 201
    version_id = version_response.json()["id"]

    first = client.post(
        f"/api/workflows/{workflow_id}/versions/{version_id}/publish",
        headers=headers,
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/workflows/{workflow_id}/versions/{version_id}/publish",
        headers=headers,
    )
    assert second.status_code == 422
