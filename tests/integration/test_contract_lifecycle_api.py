import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus, ContractStatus
from app.modules.contracts.models import Contract, ContractAddendum
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


def _create_user(db: Session, *, username: str) -> User:
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
    scope_type: ScopeType = ScopeType.ALL,
    scope_config: dict | None = None,
) -> None:
    role_code = f"cp42-{permission_code.replace('.', '-')}-{uuid.uuid4().hex[:10]}"
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


def _related(*organization_ids: uuid.UUID) -> dict[str, list[str]]:
    return {"organization_ids": [str(value) for value in organization_ids]}


def _token(db: Session, user: User) -> str:
    from app.core.config import get_settings
    from app.modules.identity.service import AuthService

    db.commit()
    return AuthService(get_settings()).login(
        db,
        username=user.username,
        password="test-password-123!",
        ip_address="127.0.0.1",
        user_agent="cp42-contract-lifecycle-api-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _organization(db: Session, name: str) -> Organization:
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name=name,
        short_name=name,
    )
    db.add(organization)
    db.flush()
    return organization


def _contract(
    db: Session,
    *,
    customer: Organization,
    creator: User,
    number: str,
    status: ContractStatus = ContractStatus.DRAFT,
) -> Contract:
    contract = Contract(
        customer_organization_id=customer.id,
        customer_contact_id=None,
        number=number,
        contract_date=date(2026, 8, 11),
        start_date=date(2026, 8, 12),
        end_date=date(2026, 9, 30),
        original_end_date=(date(2026, 9, 30) if status != ContractStatus.DRAFT else None),
        amount=Decimal("100000.00"),
        currency="RUB",
        status=status,
        created_by=creator.id,
    )
    db.add(contract)
    db.flush()
    return contract


def _addendum(
    db: Session,
    *,
    contract: Contract,
    creator: User,
    number: str = "ДС-1",
) -> ContractAddendum:
    addendum = ContractAddendum(
        contract_id=contract.id,
        number=number,
        addendum_date=date(2026, 8, 20),
        status=ContractAddendumStatus.DRAFT,
        amount_delta=Decimal("1000.00"),
        currency="RUB",
        created_by=creator.id,
        updated_by=creator.id,
    )
    db.add(addendum)
    db.flush()
    return addendum


def test_status_endpoint_requires_change_status_permission(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, "Status Org")
    creator = _create_user(db_session, username="cp42-status-creator")
    contract = _contract(db_session, customer=org, creator=creator, number="STATUS-1")

    allowed_user = _create_user(db_session, username="cp42-status-allowed")
    _grant(db_session, user=allowed_user, permission_code="contracts.change_status")
    allowed_token = _token(db_session, allowed_user)
    response = client.post(
        f"/api/contracts/{contract.id}/status",
        json={"status": "approval"},
        headers=_auth(allowed_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approval"

    denied_user = _create_user(db_session, username="cp42-status-denied")
    _grant(db_session, user=denied_user, permission_code="contracts.view")
    denied_token = _token(db_session, denied_user)
    denied = client.post(
        f"/api/contracts/{contract.id}/status",
        json={"status": "signed"},
        headers=_auth(denied_token),
    )
    assert denied.status_code == 403


def test_dedicated_permissions_do_not_grant_each_other(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, "Permission Isolation Org")
    creator = _create_user(db_session, username="cp42-perm-creator")
    signed = _contract(
        db_session,
        customer=org,
        creator=creator,
        number="PERM-SIGNED",
        status=ContractStatus.SIGNED,
    )
    in_progress = _contract(
        db_session,
        customer=org,
        creator=creator,
        number="PERM-INPROGRESS",
        status=ContractStatus.IN_PROGRESS,
    )

    change_user = _create_user(db_session, username="cp42-perm-change")
    _grant(db_session, user=change_user, permission_code="contracts.change_status")
    change_token = _token(db_session, change_user)
    assert client.post(
        f"/api/contracts/{signed.id}/terminate",
        json={"reason": "Нет права"},
        headers=_auth(change_token),
    ).status_code == 403
    assert client.post(
        f"/api/contracts/{in_progress.id}/complete",
        headers=_auth(change_token),
    ).status_code == 403

    terminate_user = _create_user(db_session, username="cp42-perm-terminate")
    _grant(db_session, user=terminate_user, permission_code="contracts.terminate")
    terminate_token = _token(db_session, terminate_user)
    assert client.post(
        f"/api/contracts/{signed.id}/status",
        json={"status": "approval"},
        headers=_auth(terminate_token),
    ).status_code == 403

    complete_user = _create_user(db_session, username="cp42-perm-complete")
    _grant(db_session, user=complete_user, permission_code="contracts.complete")
    complete_token = _token(db_session, complete_user)
    assert client.post(
        f"/api/contracts/{signed.id}/terminate",
        json={"reason": "Нет права"},
        headers=_auth(complete_token),
    ).status_code == 403


def test_patch_contract_rejects_status_field(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, "Patch Status Org")
    creator = _create_user(db_session, username="cp42-patch-creator")
    contract = _contract(db_session, customer=org, creator=creator, number="PATCH-STATUS")
    user = _create_user(db_session, username="cp42-patch-editor")
    _grant(db_session, user=user, permission_code="contracts.edit")
    token = _token(db_session, user)

    response = client.patch(
        f"/api/contracts/{contract.id}",
        json={"status": "signed"},
        headers=_auth(token),
    )
    assert response.status_code == 422
    db_session.refresh(contract)
    assert contract.status == ContractStatus.DRAFT


def test_no_public_command_starts_signed_contract_manually(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, "No Manual Start Org")
    creator = _create_user(db_session, username="cp42-start-creator")
    contract = _contract(
        db_session,
        customer=org,
        creator=creator,
        number="NO-MANUAL-START",
        status=ContractStatus.SIGNED,
    )
    user = _create_user(db_session, username="cp42-start-user")
    _grant(db_session, user=user, permission_code="contracts.change_status")
    token = _token(db_session, user)

    response = client.post(
        f"/api/contracts/{contract.id}/status",
        json={"status": "in_progress"},
        headers=_auth(token),
    )
    assert response.status_code == 422
    db_session.refresh(contract)
    assert contract.status == ContractStatus.SIGNED


def test_completion_readiness_returns_fail_closed_blockers(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, "Readiness API Org")
    creator = _create_user(db_session, username="cp42-ready-creator")
    contract = _contract(
        db_session,
        customer=org,
        creator=creator,
        number="READINESS-API",
        status=ContractStatus.IN_PROGRESS,
    )
    user = _create_user(db_session, username="cp42-ready-viewer")
    _grant(db_session, user=user, permission_code="contracts.view")
    token = _token(db_session, user)

    response = client.get(
        f"/api/contracts/{contract.id}/completion-readiness",
        headers=_auth(token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready_to_complete"] is False
    assert [item["code"] for item in payload["blockers"]] == [
        "tasks_provider_unavailable",
        "expertises_provider_unavailable",
        "documents_provider_unavailable",
        "conclusion_delivery_provider_unavailable",
    ]


def test_addenda_read_and_mutation_use_separate_permissions(
    db_session: Session,
    client,
) -> None:
    org = _organization(db_session, "Addenda Permission Org")
    creator = _create_user(db_session, username="cp42-addenda-creator")
    contract = _contract(
        db_session,
        customer=org,
        creator=creator,
        number="ADDENDA-API",
        status=ContractStatus.SIGNED,
    )
    _addendum(db_session, contract=contract, creator=creator)

    viewer = _create_user(db_session, username="cp42-addenda-viewer")
    _grant(db_session, user=viewer, permission_code="contracts.view")
    viewer_token = _token(db_session, viewer)
    read = client.get(
        f"/api/contracts/{contract.id}/addenda",
        headers=_auth(viewer_token),
    )
    assert read.status_code == 200
    assert len(read.json()) == 1
    denied_create = client.post(
        f"/api/contracts/{contract.id}/addenda",
        json={
            "number": "ДС-2",
            "addendum_date": "2026-08-21",
            "amount_delta": "1000.00",
            "new_end_date": None,
            "description": None,
        },
        headers=_auth(viewer_token),
    )
    assert denied_create.status_code == 403

    manager = _create_user(db_session, username="cp42-addenda-manager")
    _grant(db_session, user=manager, permission_code="contracts.manage_addenda")
    manager_token = _token(db_session, manager)
    created = client.post(
        f"/api/contracts/{contract.id}/addenda",
        json={
            "number": "ДС-2",
            "addendum_date": "2026-08-21",
            "amount_delta": "1000.00",
            "new_end_date": None,
            "description": None,
        },
        headers=_auth(manager_token),
    )
    assert created.status_code == 201
    assert created.json()["number"] == "ДС-2"
    assert client.get(
        f"/api/contracts/{contract.id}/addenda",
        headers=_auth(manager_token),
    ).status_code == 403


def test_foreign_nested_addendum_returns_same_404_as_unknown_id(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, "Allowed Addenda Org")
    foreign_org = _organization(db_session, "Foreign Addenda Org")
    creator = _create_user(db_session, username="cp42-nested-creator")
    allowed_contract = _contract(
        db_session,
        customer=allowed_org,
        creator=creator,
        number="NESTED-ALLOWED",
        status=ContractStatus.SIGNED,
    )
    foreign_contract = _contract(
        db_session,
        customer=foreign_org,
        creator=creator,
        number="NESTED-FOREIGN",
        status=ContractStatus.SIGNED,
    )
    foreign_addendum = _addendum(
        db_session,
        contract=foreign_contract,
        creator=creator,
        number="ДС-FOREIGN",
    )

    user = _create_user(db_session, username="cp42-nested-manager")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.manage_addenda",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed_org.id),
    )
    token = _token(db_session, user)

    foreign = client.patch(
        f"/api/contracts/{foreign_contract.id}/addenda/{foreign_addendum.id}",
        json={"description": "blocked"},
        headers=_auth(token),
    )
    unknown = client.patch(
        f"/api/contracts/{allowed_contract.id}/addenda/{uuid.uuid4()}",
        json={"description": "unknown"},
        headers=_auth(token),
    )
    assert foreign.status_code == 404
    assert unknown.status_code == 404
    assert foreign.json()["detail"] == unknown.json()["detail"]
