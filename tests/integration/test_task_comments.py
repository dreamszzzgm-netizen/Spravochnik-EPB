from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.comments.models import Comment, CommentTask
from app.modules.identity.models import (
    AuditEvent,
    Employee,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password
from app.modules.tasks.models import Task, TaskAssignee

pytestmark = pytest.mark.integration


def _create_user(db: Session, username: str) -> User:
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
) -> None:
    role = Role(
        code=f"task-comment-{uuid.uuid4().hex[:12]}",
        name="Task comment test role",
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
        user_agent="cp51-comment-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _task(db: Session, creator: User, title: str = "Commented task") -> Task:
    task = Task(
        title=title,
        creator_employee_id=creator.employee_id,
        is_personal=True,
    )
    db.add(task)
    db.flush()
    return task


def test_comment_service_creates_trimmed_task_comment_and_audit(
    db_session: Session,
) -> None:
    from app.modules.comments.service import CommentService

    user = _create_user(db_session, "comment-service-author")
    task = _task(db_session, user)

    comment = CommentService().add_task_comment(
        db_session,
        actor_user_id=user.id,
        author_employee_id=user.employee_id,
        task_id=task.id,
        text="  Проверить исходные данные  ",
    )

    assert comment.text == "Проверить исходные данные"
    assert comment.author_employee_id == user.employee_id
    link = db_session.get(CommentTask, comment.id)
    assert link is not None
    assert link.task_id == task.id
    event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "task.comment_added",
            AuditEvent.entity_id == task.id,
        )
    )
    assert event is not None
    assert event.user_id == user.id


def test_comment_service_rejects_blank_text_without_side_effects(
    db_session: Session,
) -> None:
    from app.modules.comments.service import CommentService, CommentValidationError

    user = _create_user(db_session, "comment-service-blank")
    task = _task(db_session, user, title="Blank comment task")
    before_comments = db_session.scalar(select(text("count(*)")).select_from(Comment))

    with pytest.raises(CommentValidationError, match="Текст"):
        CommentService().add_task_comment(
            db_session,
            actor_user_id=user.id,
            author_employee_id=user.employee_id,
            task_id=task.id,
            text="   ",
        )

    after_comments = db_session.scalar(select(text("count(*)")).select_from(Comment))
    assert after_comments == before_comments
    assert db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "task.comment_added",
            AuditEvent.entity_id == task.id,
        )
    ) is None


def test_task_comments_read_inherits_task_scope_and_anti_enumeration(
    db_session: Session,
    client,
) -> None:
    creator = _create_user(db_session, "comment-read-creator")
    viewer = _create_user(db_session, "comment-read-viewer")
    visible = _task(db_session, creator, title="Visible comments")
    hidden = _task(db_session, creator, title="Hidden comments")
    db_session.add(TaskAssignee(task_id=visible.id, employee_id=viewer.employee_id))
    _grant(
        db_session,
        user=viewer,
        permission_code="tasks.view",
        scope_type=ScopeType.ASSIGNED,
    )
    token = _token(db_session, viewer)

    visible_response = client.get(
        f"/api/tasks/{visible.id}/comments",
        headers=_auth(token),
    )
    assert visible_response.status_code == 200
    assert visible_response.json() == []
    assert (
        client.get(
            f"/api/tasks/{hidden.id}/comments",
            headers=_auth(token),
        ).status_code
        == 404
    )


def test_add_task_comment_requires_exact_permission_and_binds_author(
    db_session: Session,
    client,
) -> None:
    creator = _create_user(db_session, "comment-api-creator")
    task = _task(db_session, creator, title="Comment API task")
    editor = _create_user(db_session, "comment-api-editor")
    commenter = _create_user(db_session, "comment-api-commenter")
    _grant(
        db_session,
        user=editor,
        permission_code="tasks.edit",
        scope_type=ScopeType.ALL,
    )
    _grant(
        db_session,
        user=commenter,
        permission_code="tasks.comment",
        scope_type=ScopeType.ALL,
    )
    editor_token = _token(db_session, editor)
    commenter_token = _token(db_session, commenter)

    assert (
        client.post(
            f"/api/tasks/{task.id}/comments",
            headers=_auth(editor_token),
            json={"text": "Не должно пройти"},
        ).status_code
        == 403
    )

    response = client.post(
        f"/api/tasks/{task.id}/comments",
        headers=_auth(commenter_token),
        json={"text": "  Комментарий исполнителя  "},
    )
    assert response.status_code == 201
    assert response.json()["text"] == "Комментарий исполнителя"
    assert response.json()["author_employee_id"] == str(commenter.employee_id)

    forged = client.post(
        f"/api/tasks/{task.id}/comments",
        headers=_auth(commenter_token),
        json={
            "text": "Поддельный автор",
            "author_employee_id": str(creator.employee_id),
        },
    )
    assert forged.status_code == 422


def test_add_comment_respects_own_scope_and_rejects_blank_text(
    db_session: Session,
    client,
) -> None:
    owner = _create_user(db_session, "comment-own-owner")
    outsider = _create_user(db_session, "comment-own-outsider")
    task = _task(db_session, owner, title="Own comment task")
    for user in (owner, outsider):
        _grant(
            db_session,
            user=user,
            permission_code="tasks.comment",
            scope_type=ScopeType.OWN,
        )
    owner_token = _token(db_session, owner)
    outsider_token = _token(db_session, outsider)

    assert (
        client.post(
            f"/api/tasks/{task.id}/comments",
            headers=_auth(outsider_token),
            json={"text": "Чужая задача"},
        ).status_code
        == 404
    )
    blank = client.post(
        f"/api/tasks/{task.id}/comments",
        headers=_auth(owner_token),
        json={"text": "   "},
    )
    assert blank.status_code == 422
