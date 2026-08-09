import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.identity.models import (
    AuditEvent,
    Employee,
    EmployeeFunctionRole,
    EmployeeFunctionRoleAssignment,
    Permission,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.repository import permission_scopes
from app.modules.identity.security import hash_password, verify_password
from app.modules.identity.service import (
    AccountLockedError,
    AuthenticationError,
    AuthService,
    SessionExpiredError,
)

pytestmark = pytest.mark.integration


@pytest.fixture()
def db() -> Session:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text("""
            TRUNCATE TABLE
                audit_events, password_reset_events, user_sessions,
                user_role_assignments, role_permissions, roles,
                employee_absences, users,
                employee_function_role_assignments, employees
            RESTART IDENTITY CASCADE
        """)
        )
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        app_env="test",
        failed_login_limit=2,
        failed_login_lock_minutes=15,
        session_absolute_timeout_minutes=120,
        session_inactivity_timeout_minutes=30,
    )


def create_user(
    db: Session, username: str = "tester", password: str = "Strong-password-123!"
) -> User:
    employee = Employee(full_name="Test Employee")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=username,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def test_login_wrong_password_lock_and_audit(db: Session, settings: Settings) -> None:
    user = create_user(db)
    service = AuthService(settings)

    with pytest.raises(AuthenticationError):
        service.login(
            db, username="tester", password="wrong", ip_address="127.0.0.1", user_agent="pytest"
        )
    with pytest.raises(AuthenticationError):
        service.login(
            db, username="tester", password="wrong", ip_address="127.0.0.1", user_agent="pytest"
        )
    with pytest.raises(AccountLockedError):
        service.login(
            db,
            username="tester",
            password="Strong-password-123!",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    db.refresh(user)
    assert user.locked_until is not None
    actions = list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.timestamp)))
    assert actions.count("auth.login_failed") == 2
    assert "auth.login_locked" in actions


def test_login_session_revoke_and_inactivity_timeout(db: Session, settings: Settings) -> None:
    user = create_user(db)
    service = AuthService(settings)
    result = service.login(
        db,
        username="tester",
        password="Strong-password-123!",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    current, session = service.authenticate_session(db, token=result.token)
    assert current.id == user.id

    session.last_activity_at = datetime.now(UTC) - timedelta(minutes=31)
    db.commit()
    with pytest.raises(SessionExpiredError):
        service.authenticate_session(db, token=result.token)

    result2 = service.login(
        db,
        username="tester",
        password="Strong-password-123!",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert service.revoke_all_sessions(db, user_id=user.id, initiated_by=user.id) == 1
    with pytest.raises(SessionExpiredError):
        service.authenticate_session(db, token=result2.token)


def test_role_permission_scope_and_employee_function_are_separate(db: Session) -> None:
    user = create_user(db)

    permission = db.scalar(select(Permission).where(Permission.code == "expertises.edit"))
    assert permission is not None
    role = Role(code="expert-test", name="Expert Test")
    function = db.scalar(select(EmployeeFunctionRole).where(EmployeeFunctionRole.code == "expert"))
    assert function is not None
    db.add(role)
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.add(
        UserRoleAssignment(
            user_id=user.id, role_id=role.id, scope_type=ScopeType.ASSIGNED, assigned_by=user.id
        )
    )
    db.add(
        EmployeeFunctionRoleAssignment(employee_id=user.employee_id, function_role_id=function.id)
    )
    db.commit()

    assert permission_scopes(db, user.id, "expertises.edit") == ["ASSIGNED"]
    assert permission_scopes(db, user.id, "users.create") == []


def test_administrative_reset_forces_change_revokes_sessions_and_never_audits_secret(
    db: Session, settings: Settings
) -> None:
    user = create_user(db)
    service = AuthService(settings)
    result = service.login(
        db,
        username="tester",
        password="Strong-password-123!",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    temporary = "Temporary-password-456!"
    service.administrative_password_reset(
        db, user=user, temporary_password=temporary, initiated_by=user.id, reason="test"
    )
    db.refresh(user)
    assert user.must_change_password
    assert verify_password(temporary, user.password_hash)
    with pytest.raises(SessionExpiredError):
        service.authenticate_session(db, token=result.token)

    audits = list(db.scalars(select(AuditEvent)))
    serialized = " ".join(
        (event.summary or "") + " " + str(event.metadata_json or {}) for event in audits
    )
    assert temporary not in serialized


def test_me_returns_permissions(client, db_session, test_user):
    """GET /api/auth/me includes permissions list."""
    login_resp = client.post(
        "/api/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    token = login_resp.cookies.get("spravoshnik_session")
    resp = client.get("/api/auth/me", cookies={"spravoshnik_session": token})
    assert resp.status_code == 200
    body = resp.json()
    assert "permissions" in body
    assert isinstance(body["permissions"], list)
    assert body["username"] == test_user["username"]


def test_me_superuser_has_all_permissions(client, db_session, superuser):
    """Superuser gets all permission codes in /me."""
    login_resp = client.post(
        "/api/auth/login",
        json={"username": superuser["username"], "password": superuser["password"]},
    )
    token = login_resp.cookies.get("spravoshnik_session")
    resp = client.get("/api/auth/me", cookies={"spravoshnik_session": token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_superuser"] is True
    assert len(body["permissions"]) > 0
