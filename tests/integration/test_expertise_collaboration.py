import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.contracts.models import (
    Contract,
    ContractItem,
    ContractItemTechnicalDevice,
    ExpertiseType,
)
from app.modules.expertises.models import ExpertiseParticipant
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

pytestmark = pytest.mark.integration


def _login(client, credentials: dict[str, object]) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": credentials["username"], "password": credentials["password"]},
    )
    assert response.status_code == 200


def _employee(db: Session, name: str) -> uuid.UUID:
    employee = Employee(full_name=name)
    db.add(employee)
    db.flush()
    return employee.id


def _seed(db: Session, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
    org_a = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY, legal_name="Орг А"
    )
    db.add(org_a)
    db.flush()

    etype = db.scalar(
        select(ExpertiseType).where(
            ExpertiseType.code == "technical_device_epb",
            ExpertiseType.is_active.is_(True),
        )
    )
    assert etype is not None

    expert = Employee(full_name="Ответственный эксперт")
    db.add(expert)
    db.flush()

    td1 = TechnicalDevice(
        name="Сосуд-1",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=org_a.id,
    )
    db.add(td1)
    db.flush()

    contract1 = Contract(
        customer_organization_id=org_a.id,
        number="Д-1",
        contract_date=date.today(),
        created_by=user_id,
    )
    db.add(contract1)
    db.flush()

    item1 = ContractItem(
        contract_id=contract1.id,
        name="Предмет 1",
        expertise_type_id=etype.id,
        price=Decimal("100.00"),
    )
    db.add(item1)
    db.flush()
    db.add(ContractItemTechnicalDevice(contract_item_id=item1.id, technical_device_id=td1.id))
    db.commit()

    return {
        "org_a": org_a.id,
        "etype": etype.id,
        "expert": expert.id,
        "td1": td1.id,
        "contract1": contract1.id,
        "item1": item1.id,
    }


def _create_expertise(client, ids, *, contract_id=None) -> dict:
    response = client.post(
        "/api/expertises",
        json={
            "contract_id": str(contract_id or ids["contract1"]),
            "expertise_type_id": str(ids["etype"]),
            "responsible_expert_id": str(ids["expert"]),
            "contract_item_ids": [str(ids["item1"])],
            "subject": {"technical_device_id": str(ids["td1"]), "building_id": None},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_add_participant_returns_participant(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)
    specialist = _employee(db_session, "Специалист НК")

    response = client.post(
        f"/api/expertises/{expertise['id']}/participants",
        json={"employee_id": str(specialist), "participation_role": "specialist"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["employee_id"] == str(specialist)
    assert body["participation_role"] == "specialist"


def test_duplicate_participant_rejected(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)
    specialist = _employee(db_session, "Специалист НК")

    payload = {"employee_id": str(specialist), "participation_role": "specialist"}
    assert (
        client.post(f"/api/expertises/{expertise['id']}/participants", json=payload).status_code
        == 201
    )
    assert (
        client.post(f"/api/expertises/{expertise['id']}/participants", json=payload).status_code
        == 409
    )


def test_duplicate_participant_rejected_at_db_level(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)
    db_session.add(
        ExpertiseParticipant(
            expertise_id=uuid.UUID(expertise["id"]),
            employee_id=ids["expert"],
            participation_role="expert",
        )
    )
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(
            ExpertiseParticipant(
                expertise_id=uuid.UUID(expertise["id"]),
                employee_id=ids["expert"],
                participation_role="expert",
            )
        )
        db_session.flush()
    db_session.rollback()


def test_participant_requires_existing_employee(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)

    response = client.post(
        f"/api/expertises/{expertise['id']}/participants",
        json={"employee_id": str(uuid.uuid4()), "participation_role": "specialist"},
    )
    assert response.status_code == 422


def test_foreign_expertise_participant_forbidden_for_scoped_viewer(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)

    viewer = _scoped_viewer(db_session, ids["org_a"])
    _login(client, viewer)
    # viewer has expertises.view (RELATED) but NOT expertises.assign_experts
    assert client.post(
        f"/api/expertises/{expertise['id']}/participants",
        json={"employee_id": str(ids["expert"]), "participation_role": "expert"},
    ).status_code == 403


def test_responsible_expert_unchanged_by_participant_add(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)
    responsible_before = expertise["responsible_expert_id"]

    specialist = _employee(db_session, "Специалист НК")
    client.post(
        f"/api/expertises/{expertise['id']}/participants",
        json={"employee_id": str(specialist), "participation_role": "specialist"},
    )

    detail = client.get(f"/api/expertises/{expertise['id']}").json()
    assert detail["responsible_expert_id"] == responsible_before


def test_list_participants_and_remove(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)
    specialist = _employee(db_session, "Специалист НК")

    client.post(
        f"/api/expertises/{expertise['id']}/participants",
        json={"employee_id": str(specialist), "participation_role": "specialist"},
    )
    listed = client.get(f"/api/expertises/{expertise['id']}/participants").json()
    assert len(listed) == 1
    assert listed[0]["participation_role"] == "specialist"

    removed = client.delete(
        f"/api/expertises/{expertise['id']}/participants/{specialist}"
    )
    assert removed.status_code == 204
    assert client.get(f"/api/expertises/{expertise['id']}/participants").json() == []


def test_task_expertise_link_via_task_api(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)

    response = client.post(
        "/api/tasks",
        json={
            "title": "Задача по экспертизе",
            "links": [
                {
                    "kind": "expertise",
                    "entity_id": str(expertise["id"]),
                    "is_primary": True,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    task_id = response.json()["id"]

    linked = client.get(f"/api/expertises/{expertise['id']}/tasks").json()
    assert len(linked) == 1
    assert linked[0]["id"] == task_id


def test_duplicate_task_expertise_link_deduplicated(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)
    task_id = client.post(
        "/api/tasks",
        json={
            "title": "Задача по экспертизе",
            "links": [{"kind": "expertise", "entity_id": str(expertise["id"]), "is_primary": True}],
        },
    ).json()["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={
            "links": [
                {"kind": "expertise", "entity_id": str(expertise["id"]), "is_primary": True},
                {"kind": "expertise", "entity_id": str(expertise["id"]), "is_primary": True},
            ],
        },
    )
    assert response.status_code == 200, response.text
    expertise_links = [
        link for link in response.json()["links"] if link["kind"] == "expertise"
    ]
    assert len(expertise_links) == 1


def test_foreign_task_link_rejected(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    _create_expertise(client, ids)
    # linking a task to a non-existent expertise must fail (404 via reference access)
    response = client.post(
        "/api/tasks",
        json={
            "title": "Задача с несуществующей экспертизой",
            "links": [{"kind": "expertise", "entity_id": str(uuid.uuid4()), "is_primary": True}],
        },
    )
    assert response.status_code == 404


def test_workflow_start_links_generated_tasks_to_expertise(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    from app.modules.identity.models import EmployeeFunctionRole, EmployeeFunctionRoleAssignment
    from app.modules.workflows.service import WorkflowService, WorkflowTaskTemplateInput

    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)

    role = db_session.scalar(
        select(EmployeeFunctionRole).where(EmployeeFunctionRole.code == "expert")
    )
    assert role is not None
    assignee = Employee(full_name="Эксперт для workflow")
    db_session.add(assignee)
    db_session.flush()
    db_session.add(
        EmployeeFunctionRoleAssignment(employee_id=assignee.id, function_role_id=role.id)
    )
    db_session.commit()

    workflow = WorkflowService().create_template(
        db_session,
        actor_user_id=uuid.UUID(superuser["id"]),
        code=f"cp62-{uuid.uuid4().hex[:8]}",
        name="CP6.2 workflow",
    )
    version = WorkflowService().create_version(
        db_session,
        actor_user_id=uuid.UUID(superuser["id"]),
        template_id=workflow.id,
        task_templates=[
            WorkflowTaskTemplateInput(
                title="Задача из workflow",
                description=None,
                assignee_function_role_id=role.id,
                relative_due_days=1,
                sort_order=10,
                is_required=True,
            )
        ],
    )
    WorkflowService().publish_version(
        db_session,
        actor_user_id=uuid.UUID(superuser["id"]),
        template_id=workflow.id,
        version_id=version.id,
    )

    response = client.post(
        f"/api/expertises/{expertise['id']}/workflow/start",
        json={"workflow_template_id": str(workflow.id)},
    )
    assert response.status_code == 201, response.text
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["source_workflow_template_version_id"] is not None

    linked = client.get(f"/api/expertises/{expertise['id']}/tasks").json()
    assert len(linked) == 1
    assert linked[0]["id"] == tasks[0]["id"]


def test_duplicate_workflow_start_creates_second_instance(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    from app.modules.identity.models import EmployeeFunctionRole, EmployeeFunctionRoleAssignment
    from app.modules.workflows.service import WorkflowService, WorkflowTaskTemplateInput

    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)

    role = db_session.scalar(
        select(EmployeeFunctionRole).where(EmployeeFunctionRole.code == "expert")
    )
    assignee = Employee(full_name="Эксперт для workflow 2")
    db_session.add(assignee)
    db_session.flush()
    db_session.add(
        EmployeeFunctionRoleAssignment(employee_id=assignee.id, function_role_id=role.id)
    )
    db_session.commit()

    workflow = WorkflowService().create_template(
        db_session,
        actor_user_id=uuid.UUID(superuser["id"]),
        code=f"cp62b-{uuid.uuid4().hex[:8]}",
        name="CP6.2 workflow duplicate",
    )
    version = WorkflowService().create_version(
        db_session,
        actor_user_id=uuid.UUID(superuser["id"]),
        template_id=workflow.id,
        task_templates=[
            WorkflowTaskTemplateInput(
                title="Задача из workflow",
                description=None,
                assignee_function_role_id=role.id,
                relative_due_days=1,
                sort_order=10,
                is_required=True,
            )
        ],
    )
    WorkflowService().publish_version(
        db_session,
        actor_user_id=uuid.UUID(superuser["id"]),
        template_id=workflow.id,
        version_id=version.id,
    )

    first = client.post(
        f"/api/expertises/{expertise['id']}/workflow/start",
        json={"workflow_template_id": str(workflow.id)},
    )
    second = client.post(
        f"/api/expertises/{expertise['id']}/workflow/start",
        json={"workflow_template_id": str(workflow.id)},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()[0]["id"] != second.json()[0]["id"]

    linked = client.get(f"/api/expertises/{expertise['id']}/tasks").json()
    assert len(linked) == 2


def test_employee_selector_requires_permission(
    client, db_session: Session, test_user: dict[str, object]
) -> None:
    _login(client, test_user)
    assert client.get("/api/employees").status_code == 403


def test_employee_selector_returns_active_employees_only(
    client, db_session: Session, superuser: dict[str, object]
) -> None:

    _login(client, superuser)
    active = _employee(db_session, "Активный сотрудник")
    deleted = _employee(db_session, "Удалённый сотрудник")
    db_session.execute(
        text("UPDATE employees SET deleted_at = now() WHERE id = :id"),
        {"id": deleted},
    )
    db_session.commit()

    response = client.get("/api/employees")
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body}
    assert str(active) in ids
    assert str(deleted) not in ids


def test_cp61_optimistic_locking_still_intact(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    expertise = _create_expertise(client, ids)

    response = client.patch(
        f"/api/expertises/{expertise['id']}",
        json={"expected_version": 999, "comment": "конфликт"},
    )
    assert response.status_code == 409


def test_workflow_start_foreign_expertise_404_for_scoped_editor(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    ids = _seed(db_session, uuid.UUID(superuser["id"]))
    # create a foreign expertise on a second organization
    org_b = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY, legal_name="Орг Б"
    )
    db_session.add(org_b)
    db_session.flush()
    foreign_contract = Contract(
        customer_organization_id=org_b.id,
        number="Д-Б",
        contract_date=date.today(),
        created_by=uuid.UUID(superuser["id"]),
    )
    db_session.add(foreign_contract)
    db_session.flush()
    foreign_item = ContractItem(
        contract_id=foreign_contract.id,
        name="Предмет Б",
        expertise_type_id=ids["etype"],
        price=Decimal("100.00"),
    )
    db_session.add(foreign_item)
    db_session.flush()
    td_b = TechnicalDevice(
        name="Сосуд-Б",
        device_type=TechnicalDeviceType.PRESSURE_VESSEL,
        organization_id=org_b.id,
    )
    db_session.add(td_b)
    db_session.flush()
    db_session.add(
        ContractItemTechnicalDevice(contract_item_id=foreign_item.id, technical_device_id=td_b.id)
    )
    db_session.commit()

    foreign_expertise = client.post(
        "/api/expertises",
        json={
            "contract_id": str(foreign_contract.id),
            "expertise_type_id": str(ids["etype"]),
            "responsible_expert_id": str(ids["expert"]),
            "contract_item_ids": [str(foreign_item.id)],
            "subject": {"technical_device_id": str(td_b.id), "building_id": None},
        },
    ).json()

    editor = _scoped_editor(db_session, ids["org_a"])
    _login(client, editor)
    response = client.post(
        f"/api/expertises/{foreign_expertise['id']}/workflow/start",
        json={"workflow_template_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def _scoped_editor(db: Session, org_id: uuid.UUID) -> dict[str, object]:
    employee = Employee(full_name="Scoped Editor CP62")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"scopededitor-cp62-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("scoped-password-123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    role = Role(code=f"expertise-scoped-edit-{uuid.uuid4().hex[:8]}", name="Scoped Editor")
    db.add(role)
    db.flush()
    for code in ("expertises.view", "expertises.edit"):
        permission = db.execute(
            text("SELECT id FROM permissions WHERE code = :code"), {"code": code}
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
    return {"username": user.username, "password": "scoped-password-123!"}


def _scoped_viewer(db: Session, org_id: uuid.UUID) -> dict[str, object]:
    employee = Employee(full_name="Scoped Viewer CP62")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"scopedviewer-cp62-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("scoped-password-123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    role = Role(code=f"expertise-scoped-cp62-{uuid.uuid4().hex[:8]}", name="Scoped Viewer")
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
    return {"username": user.username, "password": "scoped-password-123!"}
