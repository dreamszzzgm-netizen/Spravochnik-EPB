from __future__ import annotations

from datetime import date, datetime, UTC
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.models import Contract, ContractItem, ExpertiseType
from app.modules.identity.models import AuditEvent, Employee, User
from app.modules.organizations.models import Organization
from app.modules.tasks.enums import TaskLinkKind, TaskPriority, TaskStatus
from app.modules.tasks.models import TaskAssignee, TaskContract, TaskOrganization

pytestmark = pytest.mark.integration


def _make_actor(db: Session, suffix: str) -> tuple[User, Employee]:
    employee = Employee(full_name=f"Task Actor {suffix}")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"task-actor-{suffix}-{uuid.uuid4().hex[:8]}",
        password_hash="not-used-by-service-tests",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return user, employee


def _make_employee(db: Session, name: str) -> Employee:
    employee = Employee(full_name=name)
    db.add(employee)
    db.commit()
    return employee


def _make_organization(db: Session, name: str) -> Organization:
    organization = Organization(legal_name=name)
    db.add(organization)
    db.commit()
    return organization


def _make_contract(
    db: Session,
    *,
    actor: User,
    organization: Organization,
    number: str,
) -> Contract:
    contract = Contract(
        customer_organization_id=organization.id,
        number=number,
        contract_date=date(2026, 8, 12),
        amount=Decimal("0.00"),
        currency="RUB",
        status=ContractStatus.DRAFT,
        created_by=actor.id,
    )
    db.add(contract)
    db.commit()
    return contract


def _audit_count(db: Session, action: str) -> int:
    return int(
        db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action))
        or 0
    )


def test_create_personal_task_trims_title_and_normalizes_assignees(
    db_session: Session,
) -> None:
    from app.modules.tasks.service import TaskService

    actor, actor_employee = _make_actor(db_session, "create")
    employee_a = _make_employee(db_session, "Assignee A")
    employee_b = _make_employee(db_session, "Assignee B")

    task = TaskService().create_task(
        db_session,
        actor_user_id=actor.id,
        creator_employee_id=actor_employee.id,
        title="  Inspect vessel  ",
        description="Check shell condition",
        due_date=date(2026, 8, 20),
        priority=TaskPriority.NORMAL,
        is_personal=True,
        assignee_ids=[employee_a.id, employee_b.id, employee_a.id],
        links=[],
    )

    assert task.title == "Inspect vessel"
    assert task.status == TaskStatus.NEW
    assert task.priority == TaskPriority.NORMAL
    assert task.version == 1
    assert task.creator_employee_id == actor_employee.id

    assignee_ids = set(
        db_session.scalars(
            select(TaskAssignee.employee_id).where(TaskAssignee.task_id == task.id)
        ).all()
    )
    assert assignee_ids == {employee_a.id, employee_b.id}
    assert _audit_count(db_session, "task.created") == 1


def test_non_personal_task_requires_business_link(db_session: Session) -> None:
    from app.modules.tasks.service import TaskService, TaskValidationError

    actor, actor_employee = _make_actor(db_session, "non-personal")
    before_audit = _audit_count(db_session, "task.created")

    with pytest.raises(TaskValidationError, match="связ"):
        TaskService().create_task(
            db_session,
            actor_user_id=actor.id,
            creator_employee_id=actor_employee.id,
            title="Business task",
            description=None,
            due_date=None,
            priority=TaskPriority.NORMAL,
            is_personal=False,
            assignee_ids=[],
            links=[],
        )

    assert _audit_count(db_session, "task.created") == before_audit


def test_task_links_normalize_duplicates_and_allow_only_one_primary(
    db_session: Session,
) -> None:
    from app.modules.tasks.service import TaskLinkInput, TaskService, TaskValidationError

    actor, actor_employee = _make_actor(db_session, "links")
    organization = _make_organization(db_session, "Linked Organization")

    task = TaskService().create_task(
        db_session,
        actor_user_id=actor.id,
        creator_employee_id=actor_employee.id,
        title="Linked task",
        description=None,
        due_date=None,
        priority=TaskPriority.HIGH,
        is_personal=False,
        assignee_ids=[],
        links=[
            TaskLinkInput(
                kind=TaskLinkKind.ORGANIZATION,
                entity_id=organization.id,
                is_primary=True,
            ),
            TaskLinkInput(
                kind=TaskLinkKind.ORGANIZATION,
                entity_id=organization.id,
                is_primary=True,
            ),
        ],
    )

    rows = db_session.scalars(
        select(TaskOrganization).where(TaskOrganization.task_id == task.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].organization_id == organization.id
    assert rows[0].is_primary is True

    second_org = _make_organization(db_session, "Second Linked Organization")
    before_version = task.version
    before_audit = _audit_count(db_session, "task.updated")

    with pytest.raises(TaskValidationError, match="основ"):
        TaskService().update_task(
            db_session,
            actor_user_id=actor.id,
            task=task,
            title=task.title,
            description=task.description,
            due_date=task.due_date,
            priority=task.priority,
            is_personal=False,
            links=[
                TaskLinkInput(TaskLinkKind.ORGANIZATION, organization.id, True),
                TaskLinkInput(TaskLinkKind.ORGANIZATION, second_org.id, True),
            ],
            due_date_change_reason=None,
        )

    db_session.refresh(task)
    assert task.version == before_version
    assert _audit_count(db_session, "task.updated") == before_audit


def test_soft_deleted_employee_cannot_be_assigned(db_session: Session) -> None:
    from app.modules.tasks.service import TaskService, TaskValidationError

    actor, actor_employee = _make_actor(db_session, "deleted-assignee")
    employee = _make_employee(db_session, "Deleted Assignee")
    employee.deleted_at = datetime.now(UTC)
    db_session.commit()

    with pytest.raises(TaskValidationError, match="исполн"):
        TaskService().create_task(
            db_session,
            actor_user_id=actor.id,
            creator_employee_id=actor_employee.id,
            title="Personal task",
            description=None,
            due_date=None,
            priority=TaskPriority.NORMAL,
            is_personal=True,
            assignee_ids=[employee.id],
            links=[],
        )


def test_contract_item_link_must_match_explicit_contract_link(db_session: Session) -> None:
    from app.modules.tasks.service import TaskLinkInput, TaskService, TaskValidationError

    actor, actor_employee = _make_actor(db_session, "contract-mismatch")
    organization = _make_organization(db_session, "Contract Customer")
    contract_a = _make_contract(
        db_session, actor=actor, organization=organization, number="TASK-A"
    )
    contract_b = _make_contract(
        db_session, actor=actor, organization=organization, number="TASK-B"
    )
    expertise_type = db_session.scalar(select(ExpertiseType).limit(1))
    assert expertise_type is not None
    item = ContractItem(
        contract_id=contract_a.id,
        name="Contract A item",
        expertise_type_id=expertise_type.id,
        price=Decimal("100.00"),
        currency="RUB",
    )
    db_session.add(item)
    db_session.commit()

    with pytest.raises(TaskValidationError, match="договор"):
        TaskService().create_task(
            db_session,
            actor_user_id=actor.id,
            creator_employee_id=actor_employee.id,
            title="Mismatched contract task",
            description=None,
            due_date=None,
            priority=TaskPriority.NORMAL,
            is_personal=False,
            assignee_ids=[],
            links=[
                TaskLinkInput(TaskLinkKind.CONTRACT, contract_b.id, True),
                TaskLinkInput(TaskLinkKind.CONTRACT_ITEM, item.id, False),
            ],
        )

    assert db_session.scalar(select(func.count()).select_from(TaskContract)) == 0


def test_delete_restore_and_repository_include_deleted(db_session: Session) -> None:
    from app.modules.tasks import repository
    from app.modules.tasks.service import TaskService

    actor, actor_employee = _make_actor(db_session, "delete-restore")
    task = TaskService().create_task(
        db_session,
        actor_user_id=actor.id,
        creator_employee_id=actor_employee.id,
        title="Disposable task",
        description=None,
        due_date=None,
        priority=TaskPriority.LOW,
        is_personal=True,
        assignee_ids=[],
        links=[],
    )

    TaskService().delete_task(db_session, actor_user_id=actor.id, task=task)
    assert repository.get_task(db_session, task.id) is None
    deleted = repository.get_task(db_session, task.id, include_deleted=True)
    assert deleted is not None
    assert deleted.deleted_at is not None

    TaskService().restore_task(db_session, actor_user_id=actor.id, task=deleted)
    restored = repository.get_task(db_session, task.id)
    assert restored is not None
    assert restored.deleted_at is None
    assert _audit_count(db_session, "task.deleted") == 1
    assert _audit_count(db_session, "task.restored") == 1


def test_basic_update_changes_mutable_fields_atomically(db_session: Session) -> None:
    from app.modules.tasks.service import TaskService

    actor, actor_employee = _make_actor(db_session, "update")
    task = TaskService().create_task(
        db_session,
        actor_user_id=actor.id,
        creator_employee_id=actor_employee.id,
        title="Initial title",
        description="Initial description",
        due_date=date(2026, 8, 20),
        priority=TaskPriority.NORMAL,
        is_personal=True,
        assignee_ids=[],
        links=[],
    )

    updated = TaskService().update_task(
        db_session,
        actor_user_id=actor.id,
        task=task,
        title="  Updated title  ",
        description="Updated description",
        due_date=date(2026, 8, 19),
        priority=TaskPriority.URGENT,
        is_personal=True,
        links=[],
        due_date_change_reason=None,
    )

    assert updated.title == "Updated title"
    assert updated.description == "Updated description"
    assert updated.due_date == date(2026, 8, 19)
    assert updated.priority == TaskPriority.URGENT
    assert updated.version == 2
    assert _audit_count(db_session, "task.updated") == 1
