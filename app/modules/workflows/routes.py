import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.workflows import repository
from app.modules.workflows.schemas import (
    WorkflowTaskTemplateResponse,
    WorkflowTemplateCreate,
    WorkflowTemplateDetailResponse,
    WorkflowTemplateResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
)
from app.modules.workflows.service import (
    WorkflowNotFoundError,
    WorkflowService,
    WorkflowTaskTemplateInput,
    WorkflowValidationError,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])
service = WorkflowService()
_manage_dependency = Depends(require_scoped_permission("workflows.manage"))  # noqa: B008


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Workflow not found",
    )


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message,
    )


def _version_response(db: Session, version) -> WorkflowVersionResponse:
    task_templates = repository.list_task_templates(db, version.id)
    return WorkflowVersionResponse(
        id=version.id,
        workflow_template_id=version.workflow_template_id,
        version_number=version.version_number,
        created_by=version.created_by,
        created_at=version.created_at,
        published_at=version.published_at,
        task_templates=[
            WorkflowTaskTemplateResponse.model_validate(task_template)
            for task_template in task_templates
        ],
    )


@router.get("", response_model=list[WorkflowTemplateResponse])
def read_workflows(
    ctx: AuthorizationContext = _manage_dependency,
    db: Session = Depends(get_db),
):
    del ctx
    return repository.list_templates(db)


@router.post(
    "",
    response_model=WorkflowTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow(
    payload: WorkflowTemplateCreate,
    ctx: AuthorizationContext = _manage_dependency,
    db: Session = Depends(get_db),
):
    try:
        return service.create_template(
            db,
            actor_user_id=ctx.user_id,
            code=payload.code,
            name=payload.name,
        )
    except WorkflowValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.get("/{template_id}", response_model=WorkflowTemplateDetailResponse)
def read_workflow(
    template_id: uuid.UUID,
    ctx: AuthorizationContext = _manage_dependency,
    db: Session = Depends(get_db),
):
    del ctx
    workflow = repository.get_template(db, template_id)
    if workflow is None:
        raise _not_found()
    versions = repository.list_versions(db, workflow.id)
    return WorkflowTemplateDetailResponse(
        id=workflow.id,
        code=workflow.code,
        name=workflow.name,
        is_active=workflow.is_active,
        created_by=workflow.created_by,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        deleted_at=workflow.deleted_at,
        version=workflow.version,
        versions=[_version_response(db, version) for version in versions],
    )


@router.get("/{template_id}/versions", response_model=list[WorkflowVersionResponse])
def read_workflow_versions(
    template_id: uuid.UUID,
    ctx: AuthorizationContext = _manage_dependency,
    db: Session = Depends(get_db),
):
    del ctx
    if repository.get_template(db, template_id) is None:
        raise _not_found()
    return [
        _version_response(db, version)
        for version in repository.list_versions(db, template_id)
    ]


@router.post(
    "/{template_id}/versions",
    response_model=WorkflowVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_version(
    template_id: uuid.UUID,
    payload: WorkflowVersionCreate,
    ctx: AuthorizationContext = _manage_dependency,
    db: Session = Depends(get_db),
):
    try:
        version = service.create_version(
            db,
            actor_user_id=ctx.user_id,
            template_id=template_id,
            task_templates=[
                WorkflowTaskTemplateInput(
                    title=item.title,
                    description=item.description,
                    assignee_function_role_id=item.assignee_function_role_id,
                    relative_due_days=item.relative_due_days,
                    priority=item.priority,
                    sort_order=item.sort_order,
                    is_required=item.is_required,
                )
                for item in payload.task_templates
            ],
        )
    except WorkflowNotFoundError as exc:
        raise _not_found() from exc
    except WorkflowValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _version_response(db, version)


@router.post(
    "/{template_id}/versions/{version_id}/publish",
    response_model=WorkflowVersionResponse,
)
def publish_workflow_version(
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    ctx: AuthorizationContext = _manage_dependency,
    db: Session = Depends(get_db),
):
    try:
        version = service.publish_version(
            db,
            actor_user_id=ctx.user_id,
            template_id=template_id,
            version_id=version_id,
        )
    except WorkflowNotFoundError as exc:
        raise _not_found() from exc
    except WorkflowValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _version_response(db, version)
