import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Ensure Alembic migrations target the test database
if os.getenv("TEST_DATABASE_URL"):
    os.environ["APP_ENV"] = "test"

from app.database.session import get_db
from app.main import app
from app.modules.identity.models import (
    Employee,
    Role,
    RolePermission,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("TEST_DATABASE_URL"):
        return

    skip_pg = pytest.mark.skip(
        reason="TEST_DATABASE_URL is not set; PostgreSQL integration test skipped"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_pg)


@pytest.fixture(scope="session", autouse=True)
def _ensure_migrations():
    if not os.getenv("TEST_DATABASE_URL"):
        return
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine as _create_engine

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

    engine = _create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        if current_rev == "0011_stage4_contracts_core":
            command.downgrade(alembic_cfg, "0010_stage3")
        elif current_rev == "0010_stage3":
            command.downgrade(alembic_cfg, "0009_stage3")
    engine.dispose()
    command.upgrade(alembic_cfg, "head")


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Session SQLAlchemy, управляющая транзакцией в тестовой БД."""
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text("""
            TRUNCATE TABLE
                comment_tasks,
                task_assignees,
                task_organizations, task_contracts, task_contract_items,
                task_technical_devices, task_buildings, task_opos,
                comments, tasks,
                audit_events,
                contract_item_technical_devices, contract_item_buildings,
                contract_items, contract_responsibles, contracts,
                custom_field_values, custom_field_definitions,
                opo_hazard_signs, opo_activity_types, opo,
                technical_devices,
                buildings,
                organization_identifiers, organization_contacts, organizations,
                role_permissions, user_role_assignments,
                user_sessions, password_reset_events, users,
                employee_function_role_assignments,
                employees,
                roles
            RESTART IDENTITY CASCADE
        """)
        )
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient с переопределённой зависимостью get_db."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session: Session) -> dict[str, object]:
    """Создаёт обычного пользователя с правом organizations.view."""
    employee = Employee(full_name="Test User Employee")
    db_session.add(employee)
    db_session.flush()

    user = User(
        employee_id=employee.id,
        username="testuser",
        password_hash=hash_password("test-password-123!"),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    role = Role(code="test-org-viewer", name="Test Org Viewer")
    db_session.add(role)
    db_session.flush()

    permission = db_session.execute(
        text("SELECT id FROM permissions WHERE code = 'organizations.view'")
    ).fetchone()
    if permission:
        db_session.add(RolePermission(role_id=role.id, permission_id=permission[0]))

    from app.modules.identity.models import ScopeType

    db_session.add(
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            scope_type=ScopeType.ASSIGNED,
            assigned_by=user.id,
        )
    )

    db_session.commit()
    return {"username": "testuser", "password": "test-password-123!", "id": str(user.id)}


@pytest.fixture()
def superuser(db_session: Session) -> dict[str, object]:
    """Создаёт суперпользователя."""
    employee = Employee(full_name="Superuser Employee")
    db_session.add(employee)
    db_session.flush()

    user = User(
        employee_id=employee.id,
        username="superuser",
        password_hash=hash_password("super-password-123!"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    return {"username": "superuser", "password": "super-password-123!", "id": str(user.id)}
