from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tasks.models import Task, TaskAssignee


def get_task(
    db: Session,
    task_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Task | None:
    stmt = select(Task).where(Task.id == task_id)
    if not include_deleted:
        stmt = stmt.where(Task.deleted_at.is_(None))
    return db.scalar(stmt)


def get_task_for_update(
    db: Session,
    task_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Task | None:
    stmt = select(Task).where(Task.id == task_id)
    if not include_deleted:
        stmt = stmt.where(Task.deleted_at.is_(None))
    return db.scalar(stmt.with_for_update())


def get_task_assignee_ids(db: Session, task_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.scalars(
            select(TaskAssignee.employee_id).where(TaskAssignee.task_id == task_id)
        ).all()
    )
