import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.contracts.models import (
    Contract,
    ContractItem,
    ContractItemBuilding,
    ContractItemTechnicalDevice,
    ExpertiseType,
)
from app.modules.expertises.models import ExpertiseSubject
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
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.models import TechnicalDevice


def _login(client, credentials: dict[str, object]) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": credentials["username"], "password": credentials["password"]},
    )
    assert response.status_code == 200


def _scoped_viewer(db: Session, org_id: uuid.UUID) -> dict[str, object]:
    employee = Employee(full_name="Scoped Viewer")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username="scopedviewer",
        password_hash=hash_password("scoped-password-123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    role = Role(code="expertise-scoped-viewer", name="Scoped Expertise Viewer")
    db.add(role)
    db.flush()
    permission = db.execute(
        text("SELECT id FROM permissions WHERE code = 'expertises.view'")
    ).fetchone()
    if permission:
        db.add(RolePermission(role_id=role.id, permission_id=permission[0]))
    db.add(
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            scope_type=ScopeType.RELATED,
            scope_config={"organization_ids": [str(org_id)]},
            assigned_by=user.id,
        )
    )
    db.commit()
    return {"username": "scopedviewer", "password": "scoped-password-123!"}


def _seed(db: Session, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
    org_a = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY, legal_name="Орг А"
    )
    org_b = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY, legal_name="Орг Б"
    )
    db.add_all([org_a, org_b])
    db.flush()

    etype = db.scalar(
        select(ExpertiseType).where(
            ExpertiseType.code == "technical_device_epb",
            ExpertiseType.is_active.is_(True),
        )
    )
    assert etype is not None
    db.flush()

    expert = Employee(full_name="Ответственный эксперт")
    db.add(expert)
    db.flush()

    td1 = TechnicalDevice(
        name="Сосуд-1",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=org_a.id,
    )
    td2 = TechnicalDevice(
        name="Сосуд-2",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=org_a.id,
    )
    b1 = Building(
        name="Здание-1", building_type=BuildingType.INDUSTRIAL, organization_id=org_a.id
    )
    td3 = TechnicalDevice(
        name="Сосуд-Б",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=org_b.id,
    )
    db.add_all([td1, td2, b1, td3])
    db.flush()

    contract1 = Contract(
        customer_organization_id=org_a.id,
        number="Д-1",
        contract_date=date.today(),
        created_by=user_id,
    )
    contract2 = Contract(
        customer_organization_id=org_a.id,
        number="Д-2",
        contract_date=date.today(),
        created_by=user_id,
    )
    contract3 = Contract(
        customer_organization_id=org_b.id,
        number="Д-Б",
        contract_date=date.today(),
        created_by=user_id,
    )
    db.add_all([contract1, contract2, contract3])
    db.flush()

    item1 = ContractItem(
        contract_id=contract1.id,
        name="Предмет 1",
        expertise_type_id=etype.id,
        price=Decimal("100.00"),
    )
    item2 = ContractItem(
        contract_id=contract1.id,
        name="Предмет 2",
        expertise_type_id=etype.id,
        price=Decimal("100.00"),
    )
    item_x = ContractItem(
        contract_id=contract2.id,
        name="Предмет X",
        expertise_type_id=etype.id,
        price=Decimal("100.00"),
    )
    item_y = ContractItem(
        contract_id=contract3.id,
        name="Предмет Y",
        expertise_type_id=etype.id,
        price=Decimal("100.00"),
    )
    db.add_all([item1, item2, item_x, item_y])
    db.flush()

    db.add(ContractItemTechnicalDevice(contract_item_id=item1.id, technical_device_id=td1.id))
    db.add(ContractItemTechnicalDevice(contract_item_id=item1.id, technical_device_id=td2.id))
    db.add(ContractItemBuilding(contract_item_id=item2.id, building_id=b1.id))
    db.add(ContractItemTechnicalDevice(contract_item_id=item_x.id, technical_device_id=td2.id))
    db.add(ContractItemTechnicalDevice(contract_item_id=item_y.id, technical_device_id=td3.id))
    db.commit()

    return {
        "org_a": org_a.id,
        "org_b": org_b.id,
        "etype": etype.id,
        "expert": expert.id,
        "td1": td1.id,
        "td2": td2.id,
        "td3": td3.id,
        "b1": b1.id,
        "contract1": contract1.id,
        "contract2": contract2.id,
        "contract3": contract3.id,
        "item1": item1.id,
        "item2": item2.id,
        "item_x": item_x.id,
        "item_y": item_y.id,
    }


def _create_payload(ids, *, subject, item_ids) -> dict:
    return {
        "contract_id": str(ids["contract1"]),
        "expertise_type_id": str(ids["etype"]),
        "responsible_expert_id": str(ids["expert"]),
        "contract_item_ids": [str(i) for i in item_ids],
        "subject": subject,
    }


def test_create_expertise_with_device_subject_A(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    response = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "preparation"
    assert body["subject"]["technical_device_id"] == str(ids["td1"])
    assert body["contract_item_ids"] == [str(ids["item1"])]
    assert body["version"] == 1


def test_two_expertises_for_two_devices_B(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    first = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    )
    second = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td2"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_create_expertise_with_building_subject_across_items_C(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    response = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": None, "building_id": str(ids["b1"])},
            item_ids=[ids["item1"], ids["item2"]],
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["subject"]["building_id"] == str(ids["b1"])


def test_reject_contract_item_from_other_contract_D(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    response = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td2"]), "building_id": None},
            item_ids=[ids["item_x"]],
        ),
    )
    assert response.status_code == 422


def test_reject_subject_not_in_item_E(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    response = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": None, "building_id": str(ids["b1"])},
            item_ids=[ids["item1"]],
        ),
    )
    assert response.status_code == 422


def test_second_subject_is_rejected_at_db_level_F(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    response = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    )
    assert response.status_code == 201
    expertise_id = uuid.UUID(response.json()["id"])

    with pytest.raises(IntegrityError):
        db_session.add(
            ExpertiseSubject(expertise_id=expertise_id, technical_device_id=ids["td2"])
        )
        db_session.commit()
    db_session.rollback()


def test_status_transition_writes_history(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    created = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    ).json()

    response = client.post(
        f"/api/expertises/{created['id']}/status",
        json={"status": "document_collection", "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "document_collection"
    assert response.json()["version"] == 2

    history = client.get(f"/api/expertises/{created['id']}/status-history")
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 2
    assert rows[0]["from_status"] is None
    assert rows[0]["to_status"] == "preparation"
    assert rows[1]["from_status"] == "preparation"
    assert rows[1]["to_status"] == "document_collection"


def test_arbitrary_status_transition_rejected(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    created = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    ).json()

    response = client.post(
        f"/api/expertises/{created['id']}/status",
        json={"status": "registered", "expected_version": 1},
    )
    assert response.status_code == 422


def test_version_mismatch_returns_409(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    created = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    ).json()

    response = client.patch(
        f"/api/expertises/{created['id']}",
        json={"expected_version": 5, "comment": "новая версия"},
    )
    assert response.status_code == 409


def test_unauthorized_401(client) -> None:
    assert client.get("/api/expertises").status_code == 401


def test_permission_denied_403(
    client, db_session: Session, test_user: dict[str, object]
) -> None:
    _login(client, test_user)
    assert client.get("/api/expertises").status_code == 403


def test_foreign_expertise_is_404_for_scoped_viewer(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    own = client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    ).json()
    foreign = client.post(
        "/api/expertises",
        json={
            "contract_id": str(ids["contract3"]),
            "expertise_type_id": str(ids["etype"]),
            "responsible_expert_id": str(ids["expert"]),
            "contract_item_ids": [str(ids["item_y"])],
            "subject": {"technical_device_id": str(ids["td3"]), "building_id": None},
        },
    ).json()

    viewer = _scoped_viewer(db_session, ids["org_a"])
    _login(client, viewer)

    assert client.get(f"/api/expertises/{own['id']}").status_code == 200
    assert client.get(f"/api/expertises/{foreign['id']}").status_code == 404


def test_list_pagination_does_not_leak_foreign_count(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    client.post(
        "/api/expertises",
        json=_create_payload(
            ids,
            subject={"technical_device_id": str(ids["td1"]), "building_id": None},
            item_ids=[ids["item1"]],
        ),
    )
    client.post(
        "/api/expertises",
        json={
            "contract_id": str(ids["contract3"]),
            "expertise_type_id": str(ids["etype"]),
            "responsible_expert_id": str(ids["expert"]),
            "contract_item_ids": [str(ids["item_y"])],
            "subject": {"technical_device_id": str(ids["td3"]), "building_id": None},
        },
    )

    viewer = _scoped_viewer(db_session, ids["org_a"])
    _login(client, viewer)

    response = client.get("/api/expertises")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["contract_id"] == str(ids["contract1"])
