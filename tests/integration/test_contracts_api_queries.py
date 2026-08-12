import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.models import Contract, ContractItem, ContractItemBuilding
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

BUILDING_EXPERTISE_TYPE_ID = uuid.UUID("0312543b-b525-530e-ac8d-efa8e8b2391d")


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
    role_code = f"cp41q-{permission_code.replace('.', '-')}-{uuid.uuid4().hex[:10]}"
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
        user_agent="cp41-contract-query-test",
    ).token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
        amount=Decimal("0.00"),
        currency="RUB",
        status=status,
        created_by=creator.id,
    )
    db.add(contract)
    db.flush()
    return contract


def _building(db: Session, organization: Organization) -> Building:
    building = Building(
        name="Query Building",
        building_type=BuildingType.OTHER,
        organization_id=organization.id,
    )
    db.add(building)
    db.flush()
    return building


def _item(
    db: Session,
    *,
    contract: Contract,
    building: Building,
    name: str,
    deleted: bool = False,
) -> ContractItem:
    item = ContractItem(
        contract_id=contract.id,
        name=name,
        expertise_type_id=BUILDING_EXPERTISE_TYPE_ID,
        price=Decimal("1000.25"),
        currency="RUB",
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(item)
    db.flush()
    db.add(
        ContractItemBuilding(
            contract_item_id=item.id,
            building_id=building.id,
        )
    )
    db.flush()
    return item


def test_contract_registry_supports_customer_status_and_text_filters(
    db_session: Session,
    client,
) -> None:
    customer_a = _organization(db_session, "Query Customer A")
    customer_b = _organization(db_session, "Query Customer B")
    creator = _user(db_session, "query-contract-creator")
    expected = _contract(
        db_session,
        customer=customer_a,
        creator=creator,
        number="FILTER-DRAFT-A",
    )
    _contract(
        db_session,
        customer=customer_a,
        creator=creator,
        number="FILTER-APPROVAL-A",
        status=ContractStatus.APPROVAL,
    )
    _contract(
        db_session,
        customer=customer_b,
        creator=creator,
        number="FILTER-DRAFT-B",
    )

    user = _user(db_session, "query-contract-viewer")
    _grant(
        db_session,
        user=user,
        permission_code="contracts.view",
        scope_type=ScopeType.ALL,
    )
    token = _token(db_session, user)

    response = client.get(
        "/api/contracts",
        params={
            "q": "FILTER",
            "customer_organization_id": str(customer_a.id),
            "status": ContractStatus.DRAFT.value,
        },
        headers=_auth(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == [str(expected.id)]
    assert payload["page"] == 1
    assert payload["page_size"] == 20


def test_contract_item_reads_require_view_scope_and_hide_deleted_items(
    db_session: Session,
    client,
) -> None:
    allowed_org = _organization(db_session, "Item Read Allowed Org")
    foreign_org = _organization(db_session, "Item Read Foreign Org")
    creator = _user(db_session, "item-read-creator")
    allowed_contract = _contract(
        db_session,
        customer=allowed_org,
        creator=creator,
        number="ITEM-READ-ALLOWED",
    )
    foreign_contract = _contract(
        db_session,
        customer=foreign_org,
        creator=creator,
        number="ITEM-READ-FOREIGN",
    )
    building = _building(db_session, allowed_org)
    active_item = _item(
        db_session,
        contract=allowed_contract,
        building=building,
        name="Visible Item",
    )
    _item(
        db_session,
        contract=allowed_contract,
        building=building,
        name="Deleted Item",
        deleted=True,
    )

    viewer = _user(db_session, "item-read-viewer")
    _grant(
        db_session,
        user=viewer,
        permission_code="contracts.view",
        scope_type=ScopeType.RELATED,
        scope_config=_related(allowed_org.id),
    )
    viewer_token = _token(db_session, viewer)

    response = client.get(
        f"/api/contracts/{allowed_contract.id}/items",
        headers=_auth(viewer_token),
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(active_item.id)]
    assert response.json()[0]["building_ids"] == [str(building.id)]

    foreign_response = client.get(
        f"/api/contracts/{foreign_contract.id}/items",
        headers=_auth(viewer_token),
    )
    absent_response = client.get(
        f"/api/contracts/{uuid.uuid4()}/items",
        headers=_auth(viewer_token),
    )
    assert foreign_response.status_code == absent_response.status_code == 404
    assert foreign_response.json() == absent_response.json()

    manager = _user(db_session, "item-read-manager-without-view")
    _grant(
        db_session,
        user=manager,
        permission_code="contracts.manage_items",
        scope_type=ScopeType.ALL,
    )
    manager_token = _token(db_session, manager)
    assert (
        client.get(
            f"/api/contracts/{allowed_contract.id}/items",
            headers=_auth(manager_token),
        ).status_code
        == 403
    )
