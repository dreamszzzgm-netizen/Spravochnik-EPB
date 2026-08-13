import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskPriority


class WorkflowTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)


class WorkflowTaskTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assignee_function_role_id: uuid.UUID
    relative_due_days: int = Field(ge=0)
    priority: TaskPriority = TaskPriority.NORMAL
    sort_order: int = Field(ge=0)
    is_required: bool = True


class WorkflowVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_templates: list[WorkflowTaskTemplateCreate] = Field(min_length=1)


class WorkflowTaskTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_template_version_id: uuid.UUID
    title: str
    description: str | None
    assignee_function_role_id: uuid.UUID
    relative_due_days: int
    priority: TaskPriority
    sort_order: int
    is_required: bool


class WorkflowVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_template_id: uuid.UUID
    version_number: int
    created_by: uuid.UUID
    created_at: datetime
    published_at: datetime | None
    task_templates: list[WorkflowTaskTemplateResponse] = Field(default_factory=list)


class WorkflowTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int


class WorkflowTemplateDetailResponse(WorkflowTemplateResponse):
    versions: list[WorkflowVersionResponse] = Field(default_factory=list)
