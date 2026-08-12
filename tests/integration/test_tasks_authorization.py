from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.contracts.models import Contract, ContractItem
from app.modules.identity.authorization import (
    AuthorizationContext,
    build_authorization_context,
)
from app.modules.identity.models import (
    Employee,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.repository import get_active_permission_scope_grants
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.tasks.models import Task, TaskAssignee, TaskContractItem, TaskOPO

pytestmark = pytest.mark.integration


def _employee(db: Session, name: str) -> Employee:
    employee = Employee(full_name=name)
    db.add(employee)
    db.flush()
    return employee


def _user(db: Session, employee: Employee, prefix: str) -> User:
    user = User(
        employee_id=employee.id,
        username=f"{prefix}-{uuid.uuid4().hex[:10]}",
        password_hash="not-used",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _ctx(
    *,
    user_id: uuid.UUID,
    employee_id: uuid.UUID,
    scopes: set[ScopeType],
    related: set[uuid.UUID] | None = None,
) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user_id,
        employee_id=employee_id,
        permission_code="tasks.view",
        is_superuser=False,
        has_all_scope=ScopeType.ALL in scopes,
        related_organization_ids=frozenset(related or set()),
        active_scope_types=frozenset(scopes),
    )


def _task(db: Session, creator: Employee, *, title: str = "Scoped task") -> Task:
    task = Task(
        title=title,
        creator_employee_id=creator.id,
        is_personal=True,
    )
    db.add(task)
    db.flush()
    return task


def _grant(
    db: Session,
    *,
    user: User,
    permission_code: str,
    scope_type: ScopeType,
    scope_config: dict | None = None,
) -> None:
    role = Role(
        code=f"task-auth-{uuid.uuid4().hex[:12]}",
        name="Task auth test role",
        is_system=False,
    )
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


def test_can_access_task_all_assigned_and_own(db_session: Session) -> None:
    from app.modules.identity.authorization import can_access_task

    creator = _employee(db_session, "Task Creator")
    assignee = _employee(db_session, "Task Assignee")
    outsider = _employee(db_session, "Task Outsider")
    actor = _user(db_session, outsider, "task-all")
    task = _task(db_session, creator)

    all_ctx = _ctx(
        user_id=actor.id,
        employee_id=outsider.id,
        scopes={ScopeType.ALL},
    )
    assert can_access_task(
        all_ctx,
        task,
        assignee_employee_ids=set(),
        related_organization_ids=set(),
    )

    assigned_ctx = _ctx(
        user_id=actor.id,
        employee_id=assignee.id,
        scopes={ScopeType.ASSIGNED},
    )
    assert can_access_task(
        assigned_ctx,
        task,
        assignee_employee_ids={creator.id, assignee.id},
        related_organization_ids=set(),
    )

    own_ctx = _ctx(
        user_id=actor.id,
        employee_id=creator.id,
        scopes={ScopeType.OWN},
    )
    assert can_access_task(
        own_ctx,
        task,
        assignee_employee_ids=set(),
        related_organization_ids=set(),
    )


def test_can_access_task_denies_unmatched_scope(db_session: Session) -> None:
    from app.modules.identity.authorization import can_access_task

    creator = _employee(db_session, "Denied Creator")
    outsider = _employee(db_session, "Denied Outsider")
    actor = _user(db_session, outsider, "task-denied")
    task = _task(db_session, creator)
    ctx = _ctx(
        user_id=actor.id,
        employee_id=outsider.id,
        scopes={ScopeType.ASSIGNED, ScopeType.OWN, ScopeType.RELATED},
        related={uuid.uuid4()},
    )

    assert not can_access_task(
        ctx,
        task,
        assignee_employee_ids=set(),
        related_organization_ids={uuid.uuid4()},
    )


def test_related_scope_resolves_opo_owner_and_operator(db_session: Session) -> None:
    from app.modules.identity.authorization import can_access_task
    from app.modules.tasks import repository

    owner = Organization(legal_name="OPO Owner")
    operator = Organization(legal_name="OPO Operator")
    db_session.add_all([owner, operator])
    db_session.flush()
    opo = OPO(
        name="Scoped OPO",
        registration_number=f"REG-{uuid.uuid4()}",
        hazard_class=HazardClass.HAZARD_CLASS_3,
        address="Scoped address",
        registration_date=date(2026, 1, 1),
        owner_organization_id=owner.id,
        operating_organization_id=operator.id,
    )
    db_session.add(opo)
    db_session.flush()
    creator = _employee(db_session, "OPO Creator")
    actor_employee = _employee(db_session, "OPO Actor")
    actor = _user(db_session, actor_employee, "task-opo")
    task = _task(db_session, creator, title="OPO task")
    db_session.add(TaskOPO(task_id=task.id, opo_id=opo.id, is_primary=True))
    db_session.flush()

    related_ids = repository.get_task_related_organization_ids(db_session, task.id)
    assert related_ids == {owner.id, operator.id}

    for organization_id in (owner.id, operator.id):
        ctx = _ctx(
            user_id=actor.id,
            employee_id=actor_employee.id,
            scopes={ScopeType.RELATED},
            related={organization_id},
        )
        assert can_access_task(
            ctx,
            task,
            assignee_employee_ids=set(),
            related_organization_ids=related_ids,
        )


def test_related_scope_resolves_contract_item_customer(db_session: Session) -> None:
    from app.modules.tasks import repository

    organization = Organization(legal_name="Contract Item Customer")
    db_session.add(organization)
    creator = _employee(db_session, "Contract Item Creator")
    actor_user = _user(db_session, creator, "task-contract-item")
    db_session.flush()
    expertise_type_id = db_session.scalar(text("SELECT id FROM expertise_types LIMIT 1"))
    assert expertise_type_id is not None
    contract = Contract(
        customer_organization_id=organization.id,
        number=f"C-{uuid.uuid4().hex[:8]}",
        contract_date=date(2026, 8, 12),
        created_by=actor_user.id,
    )
    db_session.add(contract)
    db_session.flush()
    item = ContractItem(
        contract_id=contract.id,
        name="Scoped item",
        expertise_type_id=expertise_type_id,
        price=0,
    )
    task = _task(db_session, creator, title="Contract item task")
    db_session.add_all([item])
    db_session.flush()
    db_session.add(
        TaskContractItem(
            task_id=task.id,
            contract_item_id=item.id,
            is_primary=True,
        )
    )
    db_session.flush()

    assert repository.get_task_related_organization_ids(db_session, task.id) == {
        organization.id
    }


def test_malformed_related_scope_fails_closed(db_session: Session) -> None:
    from app.modules.identity.authorization import can_access_task

    employee = _employee(db_session, "Malformed Actor")
    user = _user(db_session, employee, "task-malformed")
    task = _task(db_session, employee, title="Malformed related task")
    ctx = build_authorization_context(
        user=user,
        permission_code="tasks.view",
        grants=[(ScopeType.RELATED, {"organization_ids": ["not-a-uuid"]})],
    )
    assert ctx.related_organization_ids == frozenset()
    assert not can_access_task(
        ctx,
        task,
        assignee_employee_ids=set(),
        related_organization_ids={uuid.uuid4()},
    )


def test_permission_grants_are_isolated_by_exact_code(db_session: Session) -> None:
    employee = _employee(db_session, "Permission Isolation")
    user = _user(db_session, employee, "task-permission")
    _grant(
        db_session,
        user=user,
        permission_code="tasks.edit",
        scope_type=ScopeType.ALL,
    )
    db_session.commit()

    assert get_active_permission_scope_grants(db_session, user.id, "tasks.edit") == [
        (ScopeType.ALL, None)
    ]
    assert get_active_permission_scope_grants(db_session, user.id, "tasks.view") == []
    assert get_active_permission_scope_grants(db_session, user.id, "tasks.view_all") == []


def test_multiple_assignees_do_not_change_scope_semantics(db_session: Session) -> None:
    from app.modules.identity.authorization import can_access_task

    creator = _employee(db_session, "Multi Creator")
    assignee_a = _employee(db_session, "Multi A")
    assignee_b = _employee(db_session, "Multi B")
    task = _task(db_session, creator, title="Multi assignee task")
    db_session.add_all(
        [
            TaskAssignee(task_id=task.id, employee_id=assignee_a.id),
            TaskAssignee(task_id=task.id, employee_id=assignee_b.id),
        ]
    )
    db_session.flush()

    for employee in (assignee_a, assignee_b):
        ctx = _ctx(
            user_id=uuid.uuid4(),
            employee_id=employee.id,
            scopes={ScopeType.ASSIGNED},
        )
        assert can_access_task(
            ctx,
            task,
            assignee_employee_ids={assignee_a.id, assignee_b.id},
            related_organization_ids=set(),
        )
