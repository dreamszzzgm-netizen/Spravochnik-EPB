import uuid
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.identity.models import (
    Permission,
    RolePermission,
    User,
    UserRoleAssignment,
    UserSession,
)


def get_user_by_username(db: Session, username: str, *, for_update: bool = False) -> User | None:
    stmt: Select[tuple[User]] = select(User).where(User.username == username.strip().lower())
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_session_by_token_hash(
    db: Session, token_hash: str, *, for_update: bool = False
) -> UserSession | None:
    stmt: Select[tuple[UserSession]] = select(UserSession).where(
        UserSession.session_token_hash == token_hash
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def permission_scopes(db: Session, user_id: uuid.UUID, permission_code: str) -> list[str]:
    stmt = (
        select(UserRoleAssignment.scope_type)
        .join(RolePermission, RolePermission.role_id == UserRoleAssignment.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.revoked_at.is_(None),
            Permission.code == permission_code,
        )
        .distinct()
    )
    return [scope.value for scope in db.scalars(stmt).all()]


def active_sessions_for_user(db: Session, user_id: uuid.UUID, now: datetime) -> list[UserSession]:
    stmt = select(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.revoked_at.is_(None),
        UserSession.expires_at > now,
    )
    return list(db.scalars(stmt))
