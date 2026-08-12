import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.contracts.models import Contract, ContractStatus
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

BUILDING_EXPERTISE_TYPE_ID = "0312543b-b525-530e-ac8d-efa8e8b2391d"


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
    scope_type: ScopeType,
    scope_config: dict | None = None,
) -> None:
    role_code = f"cp41m-{permission_code.replace('.', '-')}-{uuid.uuid4().hex[:10]}"
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
        user_agent="cp41-contract-mutation-test",
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


def _building(db: Session, *, organization: Organization, name: str) -> Building:
    building = Building(
        name=name,
        building_type=BuildingType.OTHER,
        organization_id=organization.id,
    )
    db.add(building)
    db.flush()
    return building


def _building_item_payload(
    building_id: uuid.UUID,
    *,
    name: str = "ЭПБ здания",
    price: str = "100000.00",
) -> dict[str, object]:
    return {
        "name": name,
        "expertise_type_id": BUILDING_EXPERTISE_TYPE_ID,
        "price": price,
        "comment": None,
        "technical_device_ids": [],
        "building_ids": [str(building_id)],
    }


def test_contract_update_uses_exact_edit_scope_and_hides_foreign_customer(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, "Mutation Allowed Org")
    foreign_org = _organization(db_session, "Mutation Foreign Org")
    creator = _create_user(db_session, username="mutation-contract-creator")
    allowed = _contract(
        db_session,
        customer=allowed_org,
        creator=creator,
        number="MUT-EDIT-1",
    )
    foreign = _contract(
        db_session,
        customer=foreign_org,
        creator=creator,
        number="MUT-EDIT-2",
    )
    user = _create_user(db_session, username="mutation-contract-editor")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.view",
        scope_type=ScopeType.ALL,
    )
    _grant(
        db_session,
        user=user,
        permission_code="contracts.edit",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed_org.id),
    )
    token = _token(db_session, user)

    foreign_contract_response = client.patch(
        f"/api/contracts/{foreign.id}",
        json={"comment": "blocked"},
        headers=_auth(token),
    )
    assert foreign_contract_response.status_code == 404

    foreign_customer_response = client.patch(
        f"/api/contracts/{allowed.id}",
        json={"customer_organization_id": str(foreign_org.id)},
        headers=_auth(token),
    )
    assert foreign_customer_response.status_code == 404

    response = client.patch(
        f"/api/contracts/{allowed.id}",
        json={"number": "  MUT-EDIT-OK  ", "comment": "updated"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["number"] == "MUT-EDIT-OK"
    assert response.json()["comment"] == "updated"
    assert response.json()["version"] == 2

    db_session.refresh(allowed)
    assert allowed.customer_organization_id == allowed_org.id


def test_contract_delete_and_restore_use_operation_specific_scope(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, "Delete Restore Allowed Org")
    foreign_org = _organization(db_session, "Delete Restore Foreign Org")
    creator = _create_user(db_session, username="delete-restore-creator")
    allowed = _contract(
        db_session,
        customer=allowed_org,
        creator=creator,
        number="MUT-DELETE-1",
    )
    foreign = _contract(
        db_session,
        customer=foreign_org,
        creator=creator,
        number="MUT-DELETE-2",
    )
    user = _create_user(db_session, username="delete-restore-user")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.delete",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed_org.id),
    )
    _grant(
        db_session,
        user=user,
        permission_code="contracts.restore",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed_org.id),
    )
    token = _token(db_session, user)

    assert (
        client.delete(f"/api/contracts/{foreign.id}", headers=_auth(token)).status_code
        == 404
    )
    response = client.delete(
        f"/api/contracts/{allowed.id}",
        headers=_auth(token),
    )
    assert response.status_code == 204
    db_session.refresh(allowed)
    assert allowed.deleted_at is not None

    restore_response = client.post(
        f"/api/contracts/{allowed.id}/restore",
        headers=_auth(token),
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["deleted_at"] is None
    db_session.refresh(allowed)
    assert allowed.deleted_at is None


def test_contract_item_patch_and_delete_recalculate_amount(
    db_session: Session,
    client,
) -> None:
    customer = _organization(db_session, "Item Mutation Org")
    creator = _create_user(db_session, username="item-mutation-creator")
    contract = _contract(
        db_session,
        customer=customer,
        creator=creator,
        number="MUT-ITEM-1",
    )
    first = _building(db_session, organization=customer, name="First Building")
    second = _building(db_session, organization=customer, name="Second Building")
    user = _create_user(db_session, username="item-mutation-user")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.manage_items",
        scope_type=ScopeType.ALL,
    )
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        scope_type=ScopeType.RELATED,
        scope_config=_related(customer.id),
    )
    token = _token(db_session, user)

    create_response = client.post(
        f"/api/contracts/{contract.id}/items",
        json=_building_item_payload(first.id),
        headers=_auth(token),
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/contracts/{contract.id}/items/{item_id}",
        json=_building_item_payload(
            second.id,
            name="ЭПБ здания — уточнено",
            price="200000.50",
        ),
        headers=_auth(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["price"] == "200000.50"
    assert update_response.json()["building_ids"] == [str(second.id)]

    db_session.refresh(contract)
    assert contract.amount == Decimal("200000.50")

    delete_response = client.delete(
        f"/api/contracts/{contract.id}/items/{item_id}",
        headers=_auth(token),
    )
    assert delete_response.status_code == 204
    db_session.refresh(contract)
    assert contract.amount == Decimal("0.00")


def test_contract_item_building_scope_hides_foreign_missing_and_deleted_subjects(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, "Building Scope Allowed Org")
    foreign_org = _organization(db_session, "Building Scope Foreign Org")
    creator = _create_user(db_session, username="building-scope-creator")
    contract = _contract(
        db_session,
        customer=allowed_org,
        creator=creator,
        number="MUT-BUILDING-1",
    )
    allowed = _building(db_session, organization=allowed_org, name="Allowed Building")
    foreign = _building(db_session, organization=foreign_org, name="Foreign Building")
    deleted = _building(db_session, organization=allowed_org, name="Deleted Building")
    deleted.deleted_at = datetime.now(UTC)
    db_session.flush()

    user = _create_user(db_session, username="building-scope-user")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.manage_items",
        scope_type=ScopeType.ALL,
    )
    _grant(
        db_session,
        user=user,
        permission_code="buildings.view",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed_org.id),
    )
    token = _token(db_session, user)

    hidden_responses = [
        client.post(
            f"/api/contracts/{contract.id}/items",
            json=_building_item_payload(building_id),
            headers=_auth(token),
        )
        for building_id in (foreign.id, deleted.id, uuid.uuid4())
    ]
    assert [response.status_code for response in hidden_responses] == [404, 404, 404]
    assert hidden_responses[0].json() == hidden_responses[1].json() == hidden_responses[2].json()

    allowed_response = client.post(
        f"/api/contracts/{contract.id}/items",
        json=_building_item_payload(allowed.id),
        headers=_auth(token),
    )
    assert allowed_response.status_code == 201
    assert allowed_response.json()["building_ids"] == [str(allowed.id)]
