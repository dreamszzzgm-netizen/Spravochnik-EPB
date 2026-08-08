import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.identity.audit import write_audit
from app.modules.identity.models import PasswordResetEvent, User, UserSession
from app.modules.identity.repository import (
    active_sessions_for_user,
    get_session_by_token_hash,
    get_user_by_username,
)
from app.modules.identity.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    password_needs_rehash,
    verify_password,
)


class AuthenticationError(Exception):
    pass


class AccountLockedError(AuthenticationError):
    pass


class SessionExpiredError(AuthenticationError):
    pass


@dataclass(frozen=True)
class LoginResult:
    user: User
    token: str


class AuthService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def login(
        self,
        db: Session,
        *,
        username: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> LoginResult:
        now = self._now()
        normalized_username = username.strip().lower()
        user = get_user_by_username(db, normalized_username, for_update=True)

        if user is None:
            write_audit(
                db,
                action="auth.login_failed",
                summary="Login failed for unknown username",
                result="denied",
                ip_address=ip_address,
                metadata={"username": normalized_username},
            )
            db.commit()
            raise AuthenticationError("Invalid username or password")

        if not user.is_active:
            write_audit(
                db,
                action="auth.login_failed",
                summary="Login rejected for inactive user",
                result="denied",
                user_id=user.id,
                ip_address=ip_address,
            )
            db.commit()
            raise AuthenticationError("Invalid username or password")

        if user.locked_until and user.locked_until > now:
            write_audit(
                db,
                action="auth.login_locked",
                summary="Login rejected for locked user",
                result="denied",
                user_id=user.id,
                ip_address=ip_address,
            )
            db.commit()
            raise AccountLockedError("Account is temporarily locked")

        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= self.settings.failed_login_limit:
                user.locked_until = now + timedelta(minutes=self.settings.failed_login_lock_minutes)
                user.failed_login_count = 0
            write_audit(
                db,
                action="auth.login_failed",
                summary="Login failed: wrong password",
                result="denied",
                user_id=user.id,
                ip_address=ip_address,
            )
            db.commit()
            raise AuthenticationError("Invalid username or password")

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            user.password_changed_at = now

        token = generate_session_token()
        db.add(
            UserSession(
                user_id=user.id,
                session_token_hash=hash_session_token(token),
                created_at=now,
                last_activity_at=now,
                expires_at=now + timedelta(minutes=self.settings.session_absolute_timeout_minutes),
                ip_address=ip_address,
                user_agent=(user_agent or "")[:512] or None,
            )
        )
        write_audit(
            db,
            action="auth.login",
            summary="User logged in",
            result="success",
            user_id=user.id,
            ip_address=ip_address,
        )
        db.commit()
        return LoginResult(user=user, token=token)

    def authenticate_session(
        self, db: Session, *, token: str, touch: bool = True
    ) -> tuple[User, UserSession]:
        now = self._now()
        token_hash = hash_session_token(token)
        session = get_session_by_token_hash(db, token_hash, for_update=touch)
        if session is None or session.revoked_at is not None:
            raise SessionExpiredError("Session is invalid")

        inactive_deadline = session.last_activity_at + timedelta(
            minutes=self.settings.session_inactivity_timeout_minutes
        )
        if session.expires_at <= now or inactive_deadline <= now:
            if session.revoked_at is None:
                session.revoked_at = now
                write_audit(
                    db,
                    action="auth.session_expired",
                    summary="Session expired",
                    result="expired",
                    user_id=session.user_id,
                )
                db.commit()
            raise SessionExpiredError("Session expired")

        user = db.get(User, session.user_id)
        if user is None or not user.is_active:
            raise SessionExpiredError("Session user is unavailable")

        if touch:
            session.last_activity_at = now
            db.commit()
        return user, session

    def logout(self, db: Session, *, token: str, ip_address: str | None = None) -> None:
        session = get_session_by_token_hash(db, hash_session_token(token), for_update=True)
        if session and session.revoked_at is None:
            session.revoked_at = self._now()
            write_audit(
                db,
                action="auth.logout",
                summary="User logged out",
                result="success",
                user_id=session.user_id,
                ip_address=ip_address,
            )
            db.commit()

    def revoke_all_sessions(
        self, db: Session, *, user_id: uuid.UUID, initiated_by: uuid.UUID
    ) -> int:
        now = self._now()
        sessions = active_sessions_for_user(db, user_id, now)
        for session in sessions:
            session.revoked_at = now
        write_audit(
            db,
            action="auth.sessions_revoked",
            summary=f"Revoked {len(sessions)} sessions",
            result="success",
            user_id=initiated_by,
            entity_type="user",
            entity_id=user_id,
        )
        db.commit()
        return len(sessions)

    def administrative_password_reset(
        self,
        db: Session,
        *,
        user: User,
        temporary_password: str,
        initiated_by: uuid.UUID,
        reason: str | None,
    ) -> None:
        now = self._now()
        user.password_hash = hash_password(temporary_password)
        user.password_changed_at = now
        user.must_change_password = True
        user.failed_login_count = 0
        user.locked_until = None
        db.add(
            PasswordResetEvent(
                user_id=user.id,
                initiated_by=initiated_by,
                created_at=now,
                reason=reason,
            )
        )
        for session in active_sessions_for_user(db, user.id, now):
            session.revoked_at = now
        write_audit(
            db,
            action="auth.password_reset",
            summary="Administrative password reset",
            result="success",
            user_id=initiated_by,
            entity_type="user",
            entity_id=user.id,
            metadata={"reason_present": bool(reason)},
        )
        db.commit()

    def change_password(
        self,
        db: Session,
        *,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        now = self._now()
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.must_change_password = False
        reset_event = db.scalar(
            select(PasswordResetEvent)
            .where(
                PasswordResetEvent.user_id == user.id,
                PasswordResetEvent.completed_at.is_(None),
            )
            .order_by(PasswordResetEvent.created_at.desc())
            .limit(1)
        )
        if reset_event is not None:
            reset_event.completed_at = now
        write_audit(
            db,
            action="auth.password_changed",
            summary="Password changed",
            result="success",
            user_id=user.id,
        )
        db.commit()
