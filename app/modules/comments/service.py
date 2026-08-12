from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.comments.models import Comment, CommentTask
from app.modules.identity.audit import write_audit


class CommentValidationError(ValueError):
    pass


class CommentService:
    def add_task_comment(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        author_employee_id: uuid.UUID,
        task_id: uuid.UUID,
        text: str,
    ) -> Comment:
        clean_text = text.strip()
        if not clean_text:
            raise CommentValidationError("Текст комментария обязателен")

        comment = Comment(
            author_employee_id=author_employee_id,
            text=clean_text,
        )
        db.add(comment)
        try:
            db.flush()
            db.add(CommentTask(comment_id=comment.id, task_id=task_id))
            db.flush()
            write_audit(
                db,
                user_id=actor_user_id,
                action="task.comment_added",
                entity_type="task",
                entity_id=task_id,
                summary="Добавлен комментарий к задаче",
                result="success",
            )
            db.commit()
            db.refresh(comment)
        except Exception:
            db.rollback()
            raise
        return comment
