from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.comments import repository as comment_repository
from app.modules.comments.service import CommentService, CommentValidationError
from app.modules.identity.authorization import (
    AuthorizationContext,
    build_authorization_context,
    can_access_task,
)
from app.modules.identity.dependencies import get_current_user, require_scoped_permission
from app.modules.identity.models import User
from app.modules.identity.repository import get_active_permission_scope_grants
from app.modules.tasks import repository
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.reference_access import (
    TaskReferenceAccessError,
    require_task_link_reference_access,
)
from app.modules.tasks.schemas import (
    TaskAssigneesReplace,
    TaskAssigneesResponse,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskLinkResponse,
    TaskPaginatedResponse,
    TaskResponse,
    TaskStatusChange,
    TaskUpdate,
)
from app.modules.tasks.service import (
    TaskLinkInput,
    TaskService,
    TaskValidationError,
    is_task_overdue,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
service = TaskService()
comment_service = CommentService()

_dep_create = Depends(require_scoped_permission("tasks.create"))  # noqa: B008
_dep_edit = Depends(require_scoped_permission("tasks.edit"))  # noqa: B008
_dep_assign = Depends(require_scoped_permission("tasks.assign"))  # noqa: B008
_dep_status = Depends(require_scoped_permission("tasks.change_status"))  # noqa: B008
_dep_delete = Depends(require_scoped_permission("tasks.delete"))  # noqa: B008
_dep_restore = Depends(require_scoped_permission("tasks.restore"))  # noqa: B008
_dep_comment = Depends(require_scoped_permission("tasks.comment"))  # noqa: B008


@dataclass(frozen=True, slots=True)
class TaskReadAccess:
    user: User
    authorization: AuthorizationContext | None
    read_all: bool


def _require_task_read_access(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskReadAccess:
    if user.is_superuser:
        return TaskReadAccess(user=user, authorization=None, read_all=True)

    view_all_grants = get_active_permission_scope_grants(
        db,
        user_id=user.id,
        permission_code="tasks.view_all",
    )
    if view_all_grants:
        return TaskReadAccess(user=user, authorization=None, read_all=True)

    grants = get_active_permission_scope_grants(
        db,
        user_id=user.id,
        permission_code="tasks.view",
    )
    if not grants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return TaskReadAccess(
        user=user,
        authorization=build_authorization_context(
            user=user,
            permission_code="tasks.view",
            grants=grants,
        ),
        read_all=False,
    )


_dep_read = Depends(_require_task_read_access)  # noqa: B008


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Task not found",
    )


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _can_access_task(
    db: Session,
    task: Task,
    authorization: AuthorizationContext,
) -> bool:
    return can_access_task(
        authorization,
        task,
        assignee_employee_ids=repository.get_task_assignee_ids(db, task.id),
        related_organization_ids=repository.get_task_related_organization_ids(
            db,
            task.id,
        ),
    )


def _task_for_read_or_404(
    db: Session,
    task_id: uuid.UUID,
    access: TaskReadAccess,
    *,
    include_deleted: bool = False,
) -> Task:
    task = repository.get_task(db, task_id, include_deleted=include_deleted)
    if task is None:
        raise _not_found()
    if (
        not access.read_all
        and access.authorization is not None
        and not _can_access_task(db, task, access.authorization)
    ):
        raise _not_found()
    return task


def _task_for_mutation_or_404(
    db: Session,
    task_id: uuid.UUID,
    authorization: AuthorizationContext,
    *,
    include_deleted: bool = False,
) -> Task:
    task = repository.get_task_for_update(
        db,
        task_id,
        include_deleted=include_deleted,
    )
    if task is None or not _can_access_task(db, task, authorization):
        raise _not_found()
    return task


def _link_inputs(payloads) -> list[TaskLinkInput]:
    return [
        TaskLinkInput(
            kind=item.kind,
            entity_id=item.entity_id,
            is_primary=item.is_primary,
        )
        for item in payloads
    ]


def _require_link_access_or_404(
    db: Session,
    authorization: AuthorizationContext,
    links: list[TaskLinkInput],
) -> None:
    try:
        require_task_link_reference_access(
            db,
            actor_authorization=authorization,
            links=links,
        )
    except TaskReferenceAccessError as exc:
        raise _not_found() from exc


def _task_response(db: Session, task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        creator_employee_id=task.creator_employee_id,
        due_date=task.due_date,
        priority=task.priority,
        status=task.status,
        is_personal=task.is_personal,
        assignee_ids=sorted(repository.get_task_assignee_ids(db, task.id), key=str),
        links=[
            TaskLinkResponse(kind=kind, entity_id=entity_id, is_primary=is_primary)
            for kind, entity_id, is_primary in repository.get_task_links(db, task.id)
        ],
        is_overdue=is_task_overdue(task, today=date.today()),
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        cancelled_at=task.cancelled_at,
        deleted_at=task.deleted_at,
        version=task.version,
    )


def _comment_response(comment) -> TaskCommentResponse:
    return TaskCommentResponse(
        id=comment.id,
        author_employee_id=comment.author_employee_id,
        text=comment.text,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.get("", response_model=TaskPaginatedResponse)
def list_tasks(
    access: TaskReadAccess = _dep_read,
    db: Session = Depends(get_db),
    assignee_id: uuid.UUID | None = None,
    creator_employee_id: uuid.UUID | None = None,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    contract_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    is_overdue: bool | None = None,
    include_deleted: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TaskPaginatedResponse:
    if include_deleted and not access.read_all:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    items, total = repository.list_tasks_paginated(
        db,
        assignee_id=assignee_id,
        creator_employee_id=creator_employee_id,
        task_status=task_status,
        priority=priority,
        due_from=due_from,
        due_to=due_to,
        contract_id=contract_id,
        organization_id=organization_id,
        is_overdue=is_overdue,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
        authorization=None if access.read_all else access.authorization,
    )
    return TaskPaginatedResponse(
        items=[_task_response(db, task) for task in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    authorization: AuthorizationContext = _dep_create,
    db: Session = Depends(get_db),
) -> TaskResponse:
    links = _link_inputs(payload.links)
    _require_link_access_or_404(db, authorization, links)
    try:
        task = service.create_task(
            db,
            actor_user_id=authorization.user_id,
            creator_employee_id=authorization.employee_id,
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
            priority=payload.priority,
            is_personal=payload.is_personal,
            assignee_ids=[],
            links=links,
        )
    except TaskValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _task_response(db, task)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: uuid.UUID,
    access: TaskReadAccess = _dep_read,
    db: Session = Depends(get_db),
) -> TaskResponse:
    return _task_response(db, _task_for_read_or_404(db, task_id, access))


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    authorization: AuthorizationContext = _dep_edit,
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = _task_for_mutation_or_404(db, task_id, authorization)
    fields = payload.model_fields_set
    if "title" in fields and payload.title is None:
        raise _unprocessable("Название задачи обязательно")
    if "priority" in fields and payload.priority is None:
        raise _unprocessable("Приоритет задачи обязателен")
    if "is_personal" in fields and payload.is_personal is None:
        raise _unprocessable("Тип задачи обязателен")
    if "links" in fields and payload.links is None:
        raise _unprocessable("Связи задачи должны быть списком")

    current_links = [
        TaskLinkInput(kind=kind, entity_id=entity_id, is_primary=is_primary)
        for kind, entity_id, is_primary in repository.get_task_links(db, task.id)
    ]
    new_links = None
    if "links" in fields:
        new_links = _link_inputs(payload.links or [])
        _require_link_access_or_404(db, authorization, new_links)

    try:
        task = service.update_task(
            db,
            actor_user_id=authorization.user_id,
            task=task,
            title=payload.title if "title" in fields else task.title,
            description=(
                payload.description if "description" in fields else task.description
            ),
            due_date=payload.due_date if "due_date" in fields else task.due_date,
            priority=payload.priority if "priority" in fields else task.priority,
            is_personal=(
                payload.is_personal if "is_personal" in fields else task.is_personal
            ),
            links=new_links if new_links is not None else current_links,
            due_date_change_reason=payload.due_date_change_reason,
        )
    except TaskValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _task_response(db, task)


@router.put("/{task_id}/assignees", response_model=TaskAssigneesResponse)
def replace_assignees(
    task_id: uuid.UUID,
    payload: TaskAssigneesReplace,
    authorization: AuthorizationContext = _dep_assign,
    db: Session = Depends(get_db),
) -> TaskAssigneesResponse:
    task = _task_for_mutation_or_404(db, task_id, authorization)
    try:
        assignee_ids = service.replace_assignees(
            db,
            actor_user_id=authorization.user_id,
            task=task,
            employee_ids=payload.employee_ids,
        )
    except TaskValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return TaskAssigneesResponse(assignee_ids=assignee_ids)


@router.post("/{task_id}/status", response_model=TaskResponse)
def change_status(
    task_id: uuid.UUID,
    payload: TaskStatusChange,
    authorization: AuthorizationContext = _dep_status,
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = _task_for_mutation_or_404(db, task_id, authorization)
    try:
        task = service.change_status(
            db,
            actor_user_id=authorization.user_id,
            task=task,
            target_status=payload.status,
        )
    except TaskValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _task_response(db, task)


@router.get("/{task_id}/comments", response_model=list[TaskCommentResponse])
def list_task_comments(
    task_id: uuid.UUID,
    access: TaskReadAccess = _dep_read,
    db: Session = Depends(get_db),
) -> list[TaskCommentResponse]:
    _task_for_read_or_404(db, task_id, access)
    return [
        _comment_response(comment)
        for comment in comment_repository.list_task_comments(db, task_id)
    ]


@router.post(
    "/{task_id}/comments",
    response_model=TaskCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_task_comment(
    task_id: uuid.UUID,
    payload: TaskCommentCreate,
    authorization: AuthorizationContext = _dep_comment,
    db: Session = Depends(get_db),
) -> TaskCommentResponse:
    _task_for_mutation_or_404(db, task_id, authorization)
    try:
        comment = comment_service.add_task_comment(
            db,
            actor_user_id=authorization.user_id,
            author_employee_id=authorization.employee_id,
            task_id=task_id,
            text=payload.text,
        )
    except CommentValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _comment_response(comment)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_delete,
    db: Session = Depends(get_db),
) -> Response:
    task = _task_for_mutation_or_404(db, task_id, authorization)
    try:
        service.delete_task(
            db,
            actor_user_id=authorization.user_id,
            task=task,
        )
    except TaskValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/restore", response_model=TaskResponse)
def restore_task(
    task_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_restore,
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = _task_for_mutation_or_404(
        db,
        task_id,
        authorization,
        include_deleted=True,
    )
    try:
        service.restore_task(
            db,
            actor_user_id=authorization.user_id,
            task=task,
        )
    except TaskValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _task_response(db, task)
