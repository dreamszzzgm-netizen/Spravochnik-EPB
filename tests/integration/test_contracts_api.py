import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.contracts.models import Contract, ContractResponsible, ContractStatus
from app.modules.identity.models import (
    Employee,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password
from app.modules.organizations.models import Organization, OrganizationType
from app.modules.technical_devices.models import TechnicalDevice, TechnicalDeviceType

pytestmark = pytest.mark.integration

TECHNICAL_DEVICE_EXPERTISE_TYPE_ID = "c79c5348-2ee9-53a6-9417-224e63de5a74"


def _create_user(db: Session, *, username: str, is_superuser: bool = False) -> User:
    employee = Employee(full_name=f"{username} Employee")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=username,
        password_hash=hash_password("test-password-123!"),
        is_active=True,
        is_superuser=is_superuser,
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
    role_code = f"cp41-{permission_code.replace('.', '-')}-{uuid.uuid4().hex[:10]}"
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
        user_agent="cp41-contract-test",
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
) -> Contract:
    contract = Contract(
        customer_organization_id=customer.id,
        customer_contact_id=None,
        number=number,
        contract_date=date(2026, 8, 11),
        start_date=date(2026, 8, 12),
        end_date=date(2026, 9, 30),
        amount=Decimal("0.00"),
        currency="RUB",
        status=ContractStatus.DRAFT,
        created_by=creator.id,
    )
    db.add(contract)
    db.flush()
    return contract


def _device(db: Session, *, organization: Organization, name: str) -> TechnicalDevice:
    device = TechnicalDevice(
        name=name,
        device_type=TechnicalDeviceType.OTHER,
        organization_id=organization.id,
    )
    db.add(device)
    db.flush()
    return device


def _contract_payload(customer_id: uuid.UUID, number: str) -> dict[str, object]:
    return {
        "customer_organization_id": str(customer_id),
        "customer_contact_id": None,
        "number": number,
        "contract_date": "2026-08-11",
        "start_date": "2026-08-12",
        "end_date": "2026-09-30",
        "comment": None,
    }


def _item_payload(device_id: uuid.UUID) -> dict[str, object]:
    return {
        "name": "ЭПБ технического устройства",
        "expertise_type_id": TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
        "price": "125000.10",
        "comment": None,
        "technical_device_ids": [str(device_id)],
        "building_ids": [],
    }


def test_contracts_require_authentication_and_exact_permission(
    db_session: Session,
    client,
) -> None:
    assert client.get("/api/contracts").status_code == 401

    user = _create_user(db_session, username="contracts-wrong-permission")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.edit",
        scope_type=ScopeType.ALL,
    )
    token = _token(db_session, user)

    assert client.get("/api/contracts", headers=_auth(token)).status_code == 403


def test_contract_view_related_filters_list_and_non_enumerates_detail(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Contract Org")
    foreign = _organization(db_session, "Foreign Contract Org")
    creator = _create_user(db_session, username="contract-fixture-creator")
    allowed_contract = _contract(
        db_session,
        customer=allowed,
        creator=creator,
        number="REL-1",
    )
    foreign_contract = _contract(
        db_session,
        customer=foreign,
        creator=creator,
        number="REL-2",
    )
    user = _create_user(db_session, username="contracts-related-view")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.view",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _token(db_session, user)

    response = client.get("/api/contracts", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [
        str(allowed_contract.id)
    ]

    assert (
        client.get(
            f"/api/contracts/{allowed_contract.id}", headers=_auth(token)
        ).status_code
        == 200
    )
    foreign_response = client.get(
        f"/api/contracts/{foreign_contract.id}", headers=_auth(token)
    )
    absent_response = client.get(
        f"/api/contracts/{uuid.uuid4()}", headers=_auth(token)
    )
    assert foreign_response.status_code == absent_response.status_code == 404
    assert foreign_response.json() == absent_response.json()


@pytest.mark.parametrize("scope_type", [ScopeType.ASSIGNED, ScopeType.OWN])
def test_contract_view_assigned_and_own_are_entity_specific(
    db_session: Session,
    client,
    scope_type: ScopeType,
) -> None:
    customer = _organization(db_session, f"{scope_type.value} Contract Org")
    user = _create_user(
        db_session,
        username=f"contracts-{scope_type.value.lower()}-view",
    )
    other = _create_user(
        db_session,
        username=f"contracts-{scope_type.value.lower()}-other",
    )
    allowed_creator = user if scope_type == ScopeType.OWN else other
    allowed = _contract(
        db_session,
        customer=customer,
        creator=allowed_creator,
        number=f"{scope_type.value}-1",
    )
    blocked = _contract(
        db_session,
        customer=customer,
        creator=other,
        number=f"{scope_type.value}-2",
    )
    if scope_type == ScopeType.ASSIGNED:
        db_session.add(
            ContractResponsible(
                contract_id=allowed.id,
                employee_id=user.employee_id,
            )
        )
    _grant(
        db_session,
        user=user,
        permission_code="contracts.view",
        scope_type=scope_type,
    )
    token = _token(db_session, user)

    assert (
        client.get(f"/api/contracts/{allowed.id}", headers=_auth(token)).status_code
        == 200
    )
    assert (
        client.get(f"/api/contracts/{blocked.id}", headers=_auth(token)).status_code
        == 404
    )


def test_contract_create_related_can_only_reference_related_customer(
    db_session: Session,
    client,
) -> None:
    allowed = _organization(db_session, "Allowed Contract Create Org")
    foreign = _organization(db_session, "Foreign Contract Create Org")
    user = _create_user(db_session, username="contracts-related-create")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.create",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed.id),
    )
    token = _token(db_session, user)

    allowed_response = client.post(
        "/api/contracts",
        json=_contract_payload(allowed.id, "CREATE-1"),
        headers=_auth(token),
    )
    assert allowed_response.status_code == 201
    assert allowed_response.json()["status"] == "draft"
    assert allowed_response.json()["amount"] == "0.00"

    foreign_response = client.post(
        "/api/contracts",
        json=_contract_payload(foreign.id, "CREATE-2"),
        headers=_auth(token),
    )
    assert foreign_response.status_code == 404


def test_contract_responsibles_require_exact_permission(
    db_session: Session,
    client,
) -> None:
    customer = _organization(db_session, "Responsibles Org")
    creator = _create_user(db_session, username="responsibles-creator")
    contract = _contract(
        db_session,
        customer=customer,
        creator=creator,
        number="RESP-1",
    )
    target = Employee(full_name="Contract Responsible Target")
    db_session.add(target)
    db_session.flush()

    wrong_user = _create_user(db_session, username="responsibles-wrong")
    _grant(
        db_session,
        user=wrong_user,
        permission_code="contracts.edit",
        scope_type=ScopeType.ALL,
    )
    wrong_token = _token(db_session, wrong_user)
    assert (
        client.put(
            f"/api/contracts/{contract.id}/responsibles",
            json={"employee_ids": [str(target.id)]},
            headers=_auth(wrong_token),
        ).status_code
        == 403
    )

    user = _create_user(db_session, username="responsibles-ok")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.manage_responsibles",
        scope_type=ScopeType.RELATED,
        scope_config=_related(customer.id),
    )
    token = _token(db_session, user)
    response = client.put(
        f"/api/contracts/{contract.id}/responsibles",
        json={"employee_ids": [str(target.id)]},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json() == {"employee_ids": [str(target.id)]}


def test_contract_item_link_requires_separate_subject_view_scope(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, "Allowed Subject Org")
    foreign_org = _organization(db_session, "Foreign Subject Org")
    creator = _create_user(db_session, username="item-fixture-creator")
    contract = _contract(
        db_session,
        customer=allowed_org,
        creator=creator,
        number="ITEM-1",
    )
    allowed_device = _device(
        db_session,
        organization=allowed_org,
        name="Allowed Device",
    )
    foreign_device = _device(
        db_session,
        organization=foreign_org,
        name="Foreign Device",
    )

    user = _create_user(db_session, username="item-scoped-user")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.manage_items",
        scope_type=ScopeType.ALL,
    )
    _grant(
        db_session,
        user=user,
        permission_code="technical_devices.view",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed_org.id),
    )
    token = _token(db_session, user)

    foreign_response = client.post(
        f"/api/contracts/{contract.id}/items",
        json=_item_payload(foreign_device.id),
        headers=_auth(token),
    )
    assert foreign_response.status_code == 404

    allowed_response = client.post(
        f"/api/contracts/{contract.id}/items",
        json=_item_payload(allowed_device.id),
        headers=_auth(token),
    )
    assert allowed_response.status_code == 201
    assert allowed_response.json()["price"] == "125000.10"
    assert allowed_response.json()["technical_device_ids"] == [
        str(allowed_device.id)
    ]

    db_session.refresh(contract)
    assert contract.amount == Decimal("125000.10")


def test_contract_item_missing_subject_view_permission_is_hidden_as_404(
    db_session: Session,
    client,
) -> None:
    customer = _organization(db_session, "Hidden Subject Org")
    creator = _create_user(db_session, username="hidden-subject-creator")
    contract = _contract(
        db_session,
        customer=customer,
        creator=creator,
        number="ITEM-2",
    )
    device = _device(db_session, organization=customer, name="Hidden Device")
    user = _create_user(db_session, username="hidden-subject-user")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.manage_items",
        scope_type=ScopeType.ALL,
    )
    token = _token(db_session, user)

    response = client.post(
        f"/api/contracts/{contract.id}/items",
        json=_item_payload(device.id),
        headers=_auth(token),
    )
    assert response.status_code == 404


def test_expertise_type_reference_requires_contracts_view_permission(
    db_session: Session,
    client,
) -> None:
    assert client.get("/api/reference/expertise-types").status_code == 401

    wrong = _create_user(db_session, username="expertise-types-wrong")
    _grant(
        db_session,
        user=wrong,
        permission_code="contracts.create",
        scope_type=ScopeType.ALL,
    )
    wrong_token = _token(db_session, wrong)
    assert (
        client.get(
            "/api/reference/expertise-types", headers=_auth(wrong_token)
        ).status_code
        == 403
    )

    user = _create_user(db_session, username="expertise-types-view")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.view",
        scope_type=ScopeType.OWN,
    )
    token = _token(db_session, user)
    response = client.get("/api/reference/expertise-types", headers=_auth(token))
    assert response.status_code == 200
    assert {item["code"] for item in response.json()} == {
        "technical_device_epb",
        "building_epb",
    }
