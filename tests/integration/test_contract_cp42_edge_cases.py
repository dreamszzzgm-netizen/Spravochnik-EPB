import os
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.modules.contracts.addenda import ContractAddendumService
from app.modules.contracts.enums import ContractAddendumStatus, ContractStatus
from app.modules.contracts.models import Contract, ContractAddendum, ContractResponsible
from app.modules.contracts.service import ContractValidationError
from app.modules.identity.models import (
    Employee,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization

pytestmark = pytest.mark.integration


def _actor_id(test_user: dict[str, object]) -> uuid.UUID:
    return uuid.UUID(str(test_user["id"]))


def _organization(db: Session, name: str) -> Organization:
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name=name,
        short_name=name,
    )
    db.add(organization)
    db.flush()
    return organization


def _user(db: Session, username: str) -> User:
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
    scope_config: dict | None = None,
) -> None:
    role_code = f"cp42edge-{permission_code.replace('.', '-')}-{uuid.uuid4().hex[:10]}"
    role = Role(code=role_code, name=role_code, is_system=False)
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
            scope_config=scope_config,
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
        user_agent="cp42-edge-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _contract(
    db: Session,
    *,
    customer: Organization,
    creator: User,
    number: str,
    status: ContractStatus,
) -> Contract:
    contract = Contract(
        customer_organization_id=customer.id,
        customer_contact_id=None,
        number=number,
        contract_date=date(2026, 8, 11),
        start_date=date(2026, 8, 12),
        end_date=date(2026, 9, 30),
        original_end_date=(
            date(2026, 9, 30)
            if status not in {ContractStatus.DRAFT, ContractStatus.APPROVAL}
            else None
        ),
        amount=Decimal("100000.00"),
        currency="RUB",
        status=status,
        created_by=creator.id,
    )
    db.add(contract)
    db.flush()
    return contract


def _approval_addendum(
    db: Session,
    *,
    contract: Contract,
    actor_id: uuid.UUID,
    number: str,
    amount_delta: Decimal | None = Decimal("1000.00"),
    new_end_date: date | None = None,
    description: str | None = None,
) -> ContractAddendum:
    addendum = ContractAddendum(
        contract_id=contract.id,
        number=number,
        addendum_date=date(2026, 8, 20),
        status=ContractAddendumStatus.APPROVAL,
        amount_delta=amount_delta,
        currency=contract.currency,
        new_end_date=new_end_date,
        description=description,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(addendum)
    db.flush()
    return addendum


def test_addendum_signing_rejects_currency_mismatch_without_mutation(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    actor_id = _actor_id(test_user)
    actor = db_session.get(User, actor_id)
    assert actor is not None
    organization = _organization(db_session, "Currency Org")
    contract = _contract(
        db_session,
        customer=organization,
        creator=actor,
        number="CURRENCY",
        status=ContractStatus.SIGNED,
    )
    addendum = _approval_addendum(
        db_session,
        contract=contract,
        actor_id=actor_id,
        number="ДС-CURRENCY",
    )
    addendum.currency = "USD"
    db_session.commit()
    before_contract_version = contract.version
    before_addendum_version = addendum.version

    with pytest.raises(ContractValidationError):
        ContractAddendumService().change_status(
            db_session,
            actor_id=actor_id,
            contract=contract,
            addendum=addendum,
            target_status=ContractAddendumStatus.SIGNED,
        )

    db_session.refresh(contract)
    db_session.refresh(addendum)
    assert contract.amount == Decimal("100000.00")
    assert contract.version == before_contract_version
    assert addendum.status == ContractAddendumStatus.APPROVAL
    assert addendum.signed_at is None
    assert addendum.version == before_addendum_version


def test_deadline_shortening_does_not_require_extension_reason(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    actor_id = _actor_id(test_user)
    actor = db_session.get(User, actor_id)
    assert actor is not None
    organization = _organization(db_session, "Shortening Org")
    contract = _contract(
        db_session,
        customer=organization,
        creator=actor,
        number="SHORTEN",
        status=ContractStatus.SIGNED,
    )
    addendum = _approval_addendum(
        db_session,
        contract=contract,
        actor_id=actor_id,
        number="ДС-SHORTEN",
        amount_delta=None,
        new_end_date=date(2026, 9, 15),
        description=None,
    )
    db_session.commit()

    ContractAddendumService().change_status(
        db_session,
        actor_id=actor_id,
        contract=contract,
        addendum=addendum,
        target_status=ContractAddendumStatus.SIGNED,
    )

    assert contract.end_date == date(2026, 9, 15)
    assert contract.original_end_date == date(2026, 9, 30)
    assert addendum.status == ContractAddendumStatus.SIGNED


def test_addendum_cannot_sign_after_parent_becomes_terminal(
    db_session: Session,
    test_user: dict[str, object],
) -> None:
    actor_id = _actor_id(test_user)
    actor = db_session.get(User, actor_id)
    assert actor is not None
    organization = _organization(db_session, "Terminal Parent Org")
    contract = _contract(
        db_session,
        customer=organization,
        creator=actor,
        number="TERMINAL-PARENT",
        status=ContractStatus.SIGNED,
    )
    addendum = _approval_addendum(
        db_session,
        contract=contract,
        actor_id=actor_id,
        number="ДС-TERMINAL",
    )
    contract.status = ContractStatus.TERMINATED
    db_session.commit()
    before_version = addendum.version

    with pytest.raises(ContractValidationError):
        ContractAddendumService().change_status(
            db_session,
            actor_id=actor_id,
            contract=contract,
            addendum=addendum,
            target_status=ContractAddendumStatus.SIGNED,
        )

    db_session.refresh(addendum)
    assert addendum.status == ContractAddendumStatus.APPROVAL
    assert addendum.signed_at is None
    assert addendum.version == before_version


def _scope_target(
    db: Session,
    *,
    scope_type: ScopeType,
    permission_code: str,
    suffix: str,
    status: ContractStatus,
) -> tuple[User, Contract]:
    user = _user(db, f"edge-{permission_code.split('.')[-1]}-{scope_type.value}-{suffix}")
    organization = _organization(db, f"Scope Org {scope_type.value} {suffix}")
    scope_config = (
        {"organization_ids": [str(organization.id)]}
        if scope_type == ScopeType.RELATED
        else None
    )
    _grant(
        db,
        user=user,
        permission_code=permission_code,
        scope_type=scope_type,
        scope_config=scope_config,
    )
    creator = (
        user
        if scope_type == ScopeType.OWN
        else _user(db, f"edge-creator-{scope_type.value}-{suffix}")
    )
    contract = _contract(
        db,
        customer=organization,
        creator=creator,
        number=f"SCOPE-{scope_type.value}-{suffix}",
        status=status,
    )
    if scope_type == ScopeType.ASSIGNED:
        assert user.employee_id is not None
        db.add(
            ContractResponsible(
                contract_id=contract.id,
                employee_id=user.employee_id,
            )
        )
        db.flush()
    return user, contract


@pytest.mark.parametrize(
    "scope_type",
    [ScopeType.ALL, ScopeType.RELATED, ScopeType.ASSIGNED, ScopeType.OWN],
)
def test_status_command_honors_all_contract_scope_types(
    db_session: Session,
    client,
    scope_type: ScopeType,
) -> None:
    user, contract = _scope_target(
        db_session,
        scope_type=scope_type,
        permission_code="contracts.change_status",
        suffix="status",
        status=ContractStatus.DRAFT,
    )
    response = client.post(
        f"/api/contracts/{contract.id}/status",
        json={"status": "approval"},
        headers=_auth(_token(db_session, user)),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approval"


@pytest.mark.parametrize(
    "scope_type",
    [ScopeType.ALL, ScopeType.RELATED, ScopeType.ASSIGNED, ScopeType.OWN],
)
def test_addendum_mutation_honors_all_contract_scope_types(
    db_session: Session,
    client,
    scope_type: ScopeType,
) -> None:
    user, contract = _scope_target(
        db_session,
        scope_type=scope_type,
        permission_code="contracts.manage_addenda",
        suffix="addenda",
        status=ContractStatus.SIGNED,
    )
    response = client.post(
        f"/api/contracts/{contract.id}/addenda",
        json={
            "number": f"ДС-{scope_type.value}",
            "addendum_date": "2026-08-21",
            "amount_delta": "1000.00",
            "new_end_date": None,
            "description": None,
        },
        headers=_auth(_token(db_session, user)),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
    return config


def test_cp42_migration_downgrade_upgrade_round_trip() -> None:
    config = _alembic_config()
    previous_database_url = os.environ.get("DATABASE_URL")
    previous_app_env = os.environ.get("APP_ENV")
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ["APP_ENV"] = "test"
    try:
        command.downgrade(config, "0011_stage4_contracts_core")
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            assert "contract_addenda" not in inspector.get_table_names()
            assert "contract_suspensions" not in inspector.get_table_names()
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0011_stage4_contracts_core"
            )
        engine.dispose()

        command.upgrade(config, "0012_stage4_contract_lifecycle")
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            assert "contract_addenda" in inspector.get_table_names()
            assert "contract_suspensions" in inspector.get_table_names()
            index_names = {
                index["name"]
                for index in inspector.get_indexes("contract_suspensions")
            }
            assert "uq_contract_suspensions_one_open" in index_names
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0012_stage4_contract_lifecycle"
            )
        engine.dispose()
    finally:
        try:
            command.upgrade(config, "0012_stage4_contract_lifecycle")
        finally:
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url
            if previous_app_env is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = previous_app_env
