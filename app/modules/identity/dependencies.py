from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.modules.identity.models import ScopeType, User
from app.modules.identity.repository import permission_scopes
from app.modules.identity.service import AuthService, SessionExpiredError


def get_session_token(request: Request) -> str:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return token


def get_current_user(
    token: str = Depends(get_session_token),
    db: Session = Depends(get_db),
) -> User:
    try:
        user, _ = AuthService(get_settings()).authenticate_session(db, token=token)
        return user
    except SessionExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_permission(permission_code: str) -> Callable:
    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if user.is_superuser:
            return user
        scopes = permission_scopes(db, user.id, permission_code)
        if not scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


def get_permission_scopes_for_user(
    db: Session, *, user: User, permission_code: str
) -> set[ScopeType]:
    if user.is_superuser:
        return {ScopeType.ALL}
    return {ScopeType(value) for value in permission_scopes(db, user.id, permission_code)}
