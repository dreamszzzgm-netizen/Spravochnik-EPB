import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskLinkKind, TaskPriority, TaskStatus


class TaskLinkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TaskLinkKind
    entity_id: uuid.UUID
    is_primary: bool = False


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    is_personal: bool = False
    links: list[TaskLinkPayload] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    due_date: date | None = None
    priority: TaskPriority | None = None
    is_personal: bool | None = None
    links: list[TaskLinkPayload] | None = None
    due_date_change_reason: str | None = None


class TaskAssigneesReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_ids: list[uuid.UUID]


class TaskStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TaskStatus


class TaskLinkResponse(BaseModel):
    kind: TaskLinkKind
    entity_id: uuid.UUID
    is_primary: bool


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    creator_employee_id: uuid.UUID
    due_date: date | None
    priority: TaskPriority
    status: TaskStatus
    is_personal: bool
    assignee_ids: list[uuid.UUID]
    links: list[TaskLinkResponse]
    is_overdue: bool
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    deleted_at: datetime | None
    version: int


class TaskPaginatedResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskAssigneesResponse(BaseModel):
    assignee_ids: list[uuid.UUID]
