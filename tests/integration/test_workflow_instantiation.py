from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.models import (
    AbsenceType,
    Employee,
    EmployeeAbsence,
    EmployeeFunctionRole,
    EmployeeFunctionRoleAssignment,
    User,
)
from app.modules.organizations.models import Organization
from app.modules.tasks.enums import TaskLinkKind, TaskPriority
from app.modules.tasks.models import Task, TaskAssignee
from app.modules.tasks.service import TaskLinkInput
from app.modules.workflows.models import WorkflowTaskTemplate

pytestmark = pytest.mark.integration


def _actor(db: Session, suffix: str) -> tuple[User, Employee]:
    employee = Employee(full_name=f"Workflow Instantiation Actor {suffix}")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"workflow-inst-{suffix}-{uuid.uuid4().hex[:8]}",
        password_hash="not-used-by-service-tests",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return user, employee


def _expert_role(db: Session) -> EmployeeFunctionRole:
    role = db.scalar(select(EmployeeFunctionRole).where(EmployeeFunctionRole.code == "expert"))
    assert role is not None
    return role


def _assign_role(db: Session, employee: Employee, role: EmployeeFunctionRole) -> None:
    db.add(
        EmployeeFunctionRoleAssignment(
            employee_id=employee.id,
            function_role_id=role.id,
        )
    )
    db.flush()


def _published_workflow(db: Session, actor: User, role: EmployeeFunctionRole):
    from app.modules.workflows.service import WorkflowService, WorkflowTaskTemplateInput

    service = WorkflowService()
    workflow = service.create_template(
        db,
        actor_user_id=actor.id,
        code=f"inst-{uuid.uuid4().hex[:8]}",
        name="Workflow instantiation",
    )
    version = service.create_version(
        db,
        actor_user_id=actor.id,
        template_id=workflow.id,
        task_templates=[
            WorkflowTaskTemplateInput(
                title="First generated task",
                description=None,
                assignee_function_role_id=role.id,
                relative_due_days=2,
                priority=TaskPriority.NORMAL,
                sort_order=10,
                is_required=True,
            ),
            WorkflowTaskTemplateInput(
                title="Second generated task",
                description="Generated from workflow",
                assignee_function_role_id=role.id,
                relative_due_days=5,
                priority=TaskPriority.HIGH,
                sort_order=20,
                is_required=True,
            ),
        ],
    )
    service.publish_version(
        db,
        actor_user_id=actor.id,
        template_id=workflow.id,
        version_id=version.id,
    )
    return workflow, version


def _organization(db: Session) -> Organization:
    organization = Organization(legal_name=f"Workflow Org {uuid.uuid4().hex[:8]}")
    db.add(organization)
    db.commit()
    return organization


def test_instantiate_creates_normal_tasks_with_exact_workflow_provenance(
    db_session: Session,
) -> None:
    from app.modules.workflows.service import WorkflowService

    actor, creator = _actor(db_session, "happy")
    role = _expert_role(db_session)
    assignee = Employee(full_name="Eligible Expert")
    db_session.add(assignee)
    db_session.flush()
    _assign_role(db_session, assignee, role)
    db_session.commit()
    workflow, version = _published_workflow(db_session, actor, role)
    organization = _organization(db_session)
    anchor = date(2026, 8, 13)

    tasks = WorkflowService().instantiate(
        db_session,
        actor_user_id=actor.id,
        creator_employee_id=creator.id,
        template_id=workflow.id,
        anchor_date=anchor,
        links=[
            TaskLinkInput(
                kind=TaskLinkKind.ORGANIZATION,
                entity_id=organization.id,
                is_primary=True,
            )
        ],
        due_date_resolver=lambda start, days: start + timedelta(days=days),
    )

    assert [task.title for task in tasks] == [
        "First generated task",
        "Second generated task",
    ]
    assert [task.due_date for task in tasks] == [anchor + timedelta(days=2), anchor + timedelta(days=5)]
    templates = db_session.scalars(
        select(WorkflowTaskTemplate)
        .where(WorkflowTaskTemplate.workflow_template_version_id == version.id)
        .order_by(WorkflowTaskTemplate.sort_order)
    ).all()
    assert [task.source_workflow_template_version_id for task in tasks] == [version.id, version.id]
    assert [task.source_workflow_task_template_id for task in tasks] == [
        templates[0].id,
        templates[1].id,
    ]
    for task in tasks:
        assert db_session.scalars(
            select(TaskAssignee.employee_id).where(TaskAssignee.task_id == task.id)
        ).all() == [assignee.id]


def test_instantiate_excludes_absent_and_deleted_employees(db_session: Session) -> None:
    from app.modules.workflows.service import WorkflowService

    actor, creator = _actor(db_session, "availability")
    role = _expert_role(db_session)
    eligible = Employee(full_name="Available Expert")
    absent = Employee(full_name="Absent Expert")
    deleted = Employee(full_name="Deleted Expert")
    db_session.add_all([eligible, absent, deleted])
    db_session.flush()
    for employee in (eligible, absent, deleted):
        _assign_role(db_session, employee, role)
    anchor = date(2026, 8, 13)
    db_session.add(
        EmployeeAbsence(
            employee_id=absent.id,
            absence_type=AbsenceType.VACATION,
            date_from=anchor - timedelta(days=1),
            date_to=anchor + timedelta(days=1),
            created_by=actor.id,
        )
    )
    deleted.deleted_at = __import__("datetime").datetime.now(__import__("datetime").UTC)
    db_session.commit()
    workflow, _ = _published_workflow(db_session, actor, role)
    organization = _organization(db_session)

    tasks = WorkflowService().instantiate(
        db_session,
        actor_user_id=actor.id,
        creator_employee_id=creator.id,
        template_id=workflow.id,
        anchor_date=anchor,
        links=[TaskLinkInput(kind=TaskLinkKind.ORGANIZATION, entity_id=organization.id, is_primary=True)],
        due_date_resolver=lambda start, days: start + timedelta(days=days),
    )

    for task in tasks:
        assert db_session.scalars(
            select(TaskAssignee.employee_id).where(TaskAssignee.task_id == task.id)
        ).all() == [eligible.id]


def test_instantiate_fails_closed_when_no_eligible_assignee(db_session: Session) -> None:
    from app.modules.workflows.service import WorkflowService, WorkflowValidationError

    actor, creator = _actor(db_session, "no-assignee")
    role = _expert_role(db_session)
    workflow, _ = _published_workflow(db_session, actor, role)
    organization = _organization(db_session)
    before = db_session.scalar(select(func.count()).select_from(Task))

    with pytest.raises(WorkflowValidationError, match="сотрудник"):
        WorkflowService().instantiate(
            db_session,
            actor_user_id=actor.id,
            creator_employee_id=creator.id,
            template_id=workflow.id,
            anchor_date=date(2026, 8, 13),
            links=[TaskLinkInput(kind=TaskLinkKind.ORGANIZATION, entity_id=organization.id, is_primary=True)],
            due_date_resolver=lambda start, days: start + timedelta(days=days),
        )

    after = db_session.scalar(select(func.count()).select_from(Task))
    assert after == before


def test_instantiate_rolls_back_all_generated_tasks_on_late_failure(db_session: Session) -> None:
    from app.modules.workflows.service import WorkflowService

    actor, creator = _actor(db_session, "rollback")
    role = _expert_role(db_session)
    assignee = Employee(full_name="Rollback Expert")
    db_session.add(assignee)
    db_session.flush()
    _assign_role(db_session, assignee, role)
    db_session.commit()
    workflow, _ = _published_workflow(db_session, actor, role)
    organization = _organization(db_session)
    before = db_session.scalar(select(func.count()).select_from(Task))
    calls = 0

    def resolver(start: date, days: int) -> date:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic late workflow failure")
        return start + timedelta(days=days)

    with pytest.raises(RuntimeError, match="synthetic"):
        WorkflowService().instantiate(
            db_session,
            actor_user_id=actor.id,
            creator_employee_id=creator.id,
            template_id=workflow.id,
            anchor_date=date(2026, 8, 13),
            links=[TaskLinkInput(kind=TaskLinkKind.ORGANIZATION, entity_id=organization.id, is_primary=True)],
            due_date_resolver=resolver,
        )

    after = db_session.scalar(select(func.count()).select_from(Task))
    assert after == before
