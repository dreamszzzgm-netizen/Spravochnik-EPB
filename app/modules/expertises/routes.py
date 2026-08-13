import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.buildings.models import Building
from app.modules.contracts import repository as contracts_repository
from app.modules.contracts.models import Contract, ExpertiseType
from app.modules.expertises import repository
from app.modules.expertises.enums import ExpertiseStatus
from app.modules.expertises.models import Expertise
from app.modules.expertises.schemas import (
    ExpertiseCreate,
    ExpertiseListResponse,
    ExpertiseParticipantAdd,
    ExpertiseParticipantResponse,
    ExpertiseResponse,
    ExpertiseStatusChange,
    ExpertiseStatusHistoryResponse,
    ExpertiseSubjectResponse,
    ExpertiseTaskSummary,
    ExpertiseUpdate,
    WorkflowStart,
    WorkflowStartedTask,
    WorkflowTemplateOption,
)
from app.modules.expertises.service import (
    ExpertiseDuplicateParticipantError,
    ExpertiseService,
    ExpertiseValidationError,
    ExpertiseVersionConflictError,
)
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.identity.models import Employee
from app.modules.organizations.models import Organization
from app.modules.technical_devices.models import TechnicalDevice
from app.modules.workflows import repository as workflows_repository
from app.modules.workflows.service import WorkflowNotFoundError, WorkflowValidationError

router = APIRouter(prefix="/api/expertises", tags=["expertises"])
service = ExpertiseService()

_dep_view = Depends(require_scoped_permission("expertises.view"))  # noqa: B008
_dep_create = Depends(require_scoped_permission("expertises.create"))  # noqa: B008
_dep_edit = Depends(require_scoped_permission("expertises.edit"))  # noqa: B008
_dep_status = Depends(require_scoped_permission("expertises.change_status"))  # noqa: B008
_dep_assign = Depends(require_scoped_permission("expertises.assign_experts"))  # noqa: B008


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expertise not found")


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _display_map(db: Session, expertises: list[Expertise]) -> dict[uuid.UUID, dict]:
    if not expertises:
        return {}

    contract_ids = [e.contract_id for e in expertises]
    type_ids = [e.expertise_type_id for e in expertises]
    expert_ids = [e.responsible_expert_id for e in expertises]
    expertise_ids = [e.id for e in expertises]

    contracts = {
        c.id: c
        for c in db.scalars(select(Contract).where(Contract.id.in_(contract_ids))).all()
    }
    organization_ids = [c.customer_organization_id for c in contracts.values()]
    organizations = {
        o.id: o
        for o in db.scalars(
            select(Organization).where(Organization.id.in_(organization_ids))
        ).all()
    }
    expertise_types = {
        t.id: t
        for t in db.scalars(
            select(ExpertiseType).where(ExpertiseType.id.in_(type_ids))
        ).all()
    }
    employees = {
        e.id: e
        for e in db.scalars(select(Employee).where(Employee.id.in_(expert_ids))).all()
    }
    subjects = repository.get_expertise_subjects_by_ids(db, expertise_ids)
    device_ids = [
        s.technical_device_id for s in subjects.values() if s.technical_device_id
    ]
    building_ids = [s.building_id for s in subjects.values() if s.building_id]
    devices = {
        d.id: d
        for d in db.scalars(
            select(TechnicalDevice).where(TechnicalDevice.id.in_(device_ids))
        ).all()
    }
    buildings = {
        b.id: b
        for b in db.scalars(select(Building).where(Building.id.in_(building_ids))).all()
    }

    result: dict[uuid.UUID, dict] = {}
    for expertise in expertises:
        contract = contracts.get(expertise.contract_id)
        organization = organizations.get(contract.customer_organization_id) if contract else None
        subject = subjects.get(expertise.id)
        subject_kind: str | None = None
        subject_name: str | None = None
        if subject is not None and subject.technical_device_id is not None:
            subject_kind = "technical_device"
            device = devices.get(subject.technical_device_id)
            subject_name = device.name if device else None
        elif subject is not None and subject.building_id is not None:
            subject_kind = "building"
            building = buildings.get(subject.building_id)
            subject_name = building.name if building else None
        result[expertise.id] = {
            "contract_number": contract.number if contract else None,
            "organization_name": (
                (organization.short_name or organization.legal_name)
                if organization
                else None
            ),
            "expertise_type_name": (
                expertise_types[expertise.expertise_type_id].name
                if expertise.expertise_type_id in expertise_types
                else None
            ),
            "responsible_expert_name": (
                employees[expertise.responsible_expert_id].full_name
                if expertise.responsible_expert_id in employees
                else None
            ),
            "subject_kind": subject_kind,
            "subject_name": subject_name,
        }
    return result


def _expertise_response(
    db: Session, expertise: Expertise, display: dict | None = None
) -> ExpertiseResponse:
    subject = repository.get_expertise_subject(db, expertise.id)
    info = display or _display_map(db, [expertise]).get(expertise.id, {})
    return ExpertiseResponse(
        id=expertise.id,
        contract_id=expertise.contract_id,
        expertise_type_id=expertise.expertise_type_id,
        status=expertise.status,
        internal_number=expertise.internal_number,
        responsible_expert_id=expertise.responsible_expert_id,
        comment=expertise.comment,
        version=expertise.version,
        created_at=expertise.created_at,
        updated_at=expertise.updated_at,
        deleted_at=expertise.deleted_at,
        subject=ExpertiseSubjectResponse(
            technical_device_id=subject.technical_device_id if subject else None,
            building_id=subject.building_id if subject else None,
        ),
        contract_item_ids=repository.get_expertise_contract_item_ids(db, expertise.id),
        contract_number=info.get("contract_number"),
        organization_name=info.get("organization_name"),
        expertise_type_name=info.get("expertise_type_name"),
        responsible_expert_name=info.get("responsible_expert_name"),
        subject_kind=info.get("subject_kind"),
        subject_name=info.get("subject_name"),
    )


def _expertise_for_read_or_404(
    db: Session,
    expertise_id: uuid.UUID,
    authorization: AuthorizationContext,
) -> Expertise:
    expertise = repository.get_expertise(db, expertise_id, authorization=authorization)
    if expertise is None:
        raise _not_found()
    return expertise


def _expertise_for_mutation_or_404(
    db: Session,
    expertise_id: uuid.UUID,
    authorization: AuthorizationContext,
) -> Expertise:
    if repository.get_expertise(db, expertise_id, authorization=authorization) is None:
        raise _not_found()
    expertise = repository.get_expertise_for_update(db, expertise_id)
    if expertise is None:
        raise _not_found()
    return expertise


@router.get("", response_model=ExpertiseListResponse)
def list_expertises(
    db: Session = Depends(get_db),
    authorization: AuthorizationContext = _dep_view,
    q: str = "",
    contract_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    expertise_status: Annotated[ExpertiseStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ExpertiseListResponse:
    items, total = repository.list_expertises_paginated(
        db,
        q=q,
        contract_id=contract_id,
        organization_id=organization_id,
        status=expertise_status,
        page=page,
        page_size=page_size,
        authorization=authorization,
    )
    display = _display_map(db, items)
    return ExpertiseListResponse(
        items=[
            _expertise_response(db, expertise, display.get(expertise.id))
            for expertise in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ExpertiseResponse, status_code=status.HTTP_201_CREATED)
def create_expertise(
    payload: ExpertiseCreate,
    authorization: AuthorizationContext = _dep_create,
    db: Session = Depends(get_db),
) -> ExpertiseResponse:
    if (
        contracts_repository.get_contract(
            db, payload.contract_id, authorization=authorization
        )
        is None
    ):
        raise _not_found()
    try:
        expertise = service.create_expertise(
            db,
            actor_user_id=authorization.user_id,
            contract_id=payload.contract_id,
            expertise_type_id=payload.expertise_type_id,
            responsible_expert_id=payload.responsible_expert_id,
            internal_number=payload.internal_number,
            comment=payload.comment,
            technical_device_id=payload.subject.technical_device_id,
            building_id=payload.subject.building_id,
            contract_item_ids=payload.contract_item_ids,
        )
    except ExpertiseValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _expertise_response(db, expertise)


@router.get("/workflow-templates", response_model=list[WorkflowTemplateOption])
def list_workflow_templates(
    _authorization: AuthorizationContext = _dep_edit,
    db: Session = Depends(get_db),
) -> list[WorkflowTemplateOption]:
    return [
        WorkflowTemplateOption(id=template.id, code=template.code, name=template.name)
        for template in workflows_repository.list_templates_with_published_version(db)
    ]


@router.get("/{expertise_id}", response_model=ExpertiseResponse)
def get_expertise(
    expertise_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
) -> ExpertiseResponse:
    expertise = _expertise_for_read_or_404(db, expertise_id, authorization)
    return _expertise_response(db, expertise)


@router.patch("/{expertise_id}", response_model=ExpertiseResponse)
def update_expertise(
    expertise_id: uuid.UUID,
    payload: ExpertiseUpdate,
    authorization: AuthorizationContext = _dep_edit,
    db: Session = Depends(get_db),
) -> ExpertiseResponse:
    expertise = _expertise_for_mutation_or_404(db, expertise_id, authorization)
    try:
        expertise = service.update_expertise(
            db,
            actor_user_id=authorization.user_id,
            expertise=expertise,
            expected_version=payload.expected_version,
            expertise_type_id=payload.expertise_type_id,
            responsible_expert_id=payload.responsible_expert_id,
            internal_number=payload.internal_number,
            comment=payload.comment,
        )
    except ExpertiseVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExpertiseValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _expertise_response(db, expertise)


@router.post("/{expertise_id}/status", response_model=ExpertiseResponse)
def change_status(
    expertise_id: uuid.UUID,
    payload: ExpertiseStatusChange,
    authorization: AuthorizationContext = _dep_status,
    db: Session = Depends(get_db),
) -> ExpertiseResponse:
    expertise = _expertise_for_mutation_or_404(db, expertise_id, authorization)
    try:
        expertise = service.change_status(
            db,
            actor_user_id=authorization.user_id,
            expertise=expertise,
            target_status=payload.status,
            reason=payload.reason,
            expected_version=payload.expected_version,
        )
    except ExpertiseVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExpertiseValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _expertise_response(db, expertise)


@router.get("/{expertise_id}/status-history", response_model=list[ExpertiseStatusHistoryResponse])
def list_status_history(
    expertise_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
) -> list[ExpertiseStatusHistoryResponse]:
    _expertise_for_read_or_404(db, expertise_id, authorization)
    return [
        ExpertiseStatusHistoryResponse.model_validate(row)
        for row in repository.list_expertise_status_history(db, expertise_id)
    ]


@router.get("/{expertise_id}/participants", response_model=list[ExpertiseParticipantResponse])
def list_participants(
    expertise_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
) -> list[ExpertiseParticipantResponse]:
    _expertise_for_read_or_404(db, expertise_id, authorization)
    rows = repository.list_participants_with_employees(db, expertise_id)
    return [
        ExpertiseParticipantResponse(
            id=participant.id,
            expertise_id=participant.expertise_id,
            employee_id=participant.employee_id,
            participation_role=participant.participation_role,
            employee_name=employee.full_name if employee else None,
            position=employee.position if employee else None,
        )
        for participant, employee in rows
    ]


@router.post(
    "/{expertise_id}/participants",
    response_model=ExpertiseParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_participant(
    expertise_id: uuid.UUID,
    payload: ExpertiseParticipantAdd,
    authorization: AuthorizationContext = _dep_assign,
    db: Session = Depends(get_db),
) -> ExpertiseParticipantResponse:
    expertise = _expertise_for_mutation_or_404(db, expertise_id, authorization)
    try:
        participant = service.add_participant(
            db,
            actor_user_id=authorization.user_id,
            expertise=expertise,
            employee_id=payload.employee_id,
            participation_role=payload.participation_role,
        )
    except ExpertiseDuplicateParticipantError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExpertiseValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    employee = db.get(Employee, participant.employee_id)
    return ExpertiseParticipantResponse(
        id=participant.id,
        expertise_id=participant.expertise_id,
        employee_id=participant.employee_id,
        participation_role=participant.participation_role,
        employee_name=employee.full_name if employee else None,
        position=employee.position if employee else None,
    )


@router.delete(
    "/{expertise_id}/participants/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_participant(
    expertise_id: uuid.UUID,
    employee_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_assign,
    db: Session = Depends(get_db),
):
    expertise = _expertise_for_mutation_or_404(db, expertise_id, authorization)
    try:
        service.remove_participant(
            db,
            actor_user_id=authorization.user_id,
            expertise=expertise,
            employee_id=employee_id,
        )
    except ExpertiseValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.get("/{expertise_id}/tasks", response_model=list[ExpertiseTaskSummary])
def list_expertise_tasks(
    expertise_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
) -> list[ExpertiseTaskSummary]:
    _expertise_for_read_or_404(db, expertise_id, authorization)
    return [
        ExpertiseTaskSummary(
            id=task.id,
            title=task.title,
            status=task.status.value,
            priority=task.priority.value,
            due_date=task.due_date,
            created_at=task.created_at,
        )
        for task in repository.list_expertise_tasks(db, expertise_id)
    ]


@router.post(
    "/{expertise_id}/workflow/start",
    response_model=list[WorkflowStartedTask],
    status_code=status.HTTP_201_CREATED,
)
def start_workflow(
    expertise_id: uuid.UUID,
    payload: WorkflowStart,
    authorization: AuthorizationContext = _dep_edit,
    db: Session = Depends(get_db),
) -> list[WorkflowStartedTask]:
    expertise = _expertise_for_mutation_or_404(db, expertise_id, authorization)
    try:
        tasks = service.start_workflow(
            db,
            actor_user_id=authorization.user_id,
            creator_employee_id=authorization.employee_id,
            expertise=expertise,
            workflow_template_id=payload.workflow_template_id,
            anchor_date=date.today(),
        )
    except ExpertiseValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except WorkflowValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return [
        WorkflowStartedTask(
            id=task.id,
            title=task.title,
            status=task.status.value,
            source_workflow_template_version_id=task.source_workflow_template_version_id,
            source_workflow_task_template_id=task.source_workflow_task_template_id,
        )
        for task in tasks
    ]
