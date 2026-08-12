from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.comments.models import Comment, CommentTask


def list_task_comments(db: Session, task_id: uuid.UUID) -> list[Comment]:
    return list(
        db.scalars(
            select(Comment)
            .join(CommentTask, CommentTask.comment_id == Comment.id)
            .where(
                CommentTask.task_id == task_id,
                Comment.deleted_at.is_(None),
            )
            .order_by(Comment.created_at.asc(), Comment.id.asc())
        ).all()
    )
