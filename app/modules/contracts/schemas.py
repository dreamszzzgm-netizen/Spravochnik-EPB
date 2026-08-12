import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.contracts.enums import ContractAddendumStatus, ContractStatus


class ContractCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_organization_id: uuid.UUID
    customer_contact_id: uuid.UUID | None = None
    number: str = Field(min_length=1, max_length=120)
    contract_date: date
    start_date: date | None = None
    end_date: date | None = None
    comment: str | None = None


class ContractUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_organization_id: uuid.UUID | None = None
    customer_contact_id: uuid.UUID | None = None
    number: str | None = Field(default=None, max_length=120)
    contract_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    comment: str | None = None


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_organization_id: uuid.UUID
    customer_contact_id: uuid.UUID | None
    number: str
    contract_date: date
    start_date: date | None
    end_date: date | None
    original_end_date: date | None
    amount: Decimal
    currency: str
    status: ContractStatus
    comment: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int


class ContractPaginatedResponse(BaseModel):
    items: list[ContractResponse]
    total: int
    page: int
    page_size: int


class ContractResponsiblesReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_ids: list[uuid.UUID]


class ContractResponsiblesResponse(BaseModel):
    employee_ids: list[uuid.UUID]


class ContractItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    expertise_type_id: uuid.UUID
    price: Decimal
    comment: str | None = None
    technical_device_ids: list[uuid.UUID] = Field(default_factory=list)
    building_ids: list[uuid.UUID] = Field(default_factory=list)


class ContractItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    expertise_type_id: uuid.UUID | None = None
    price: Decimal | None = None
    comment: str | None = None
    technical_device_ids: list[uuid.UUID] | None = None
    building_ids: list[uuid.UUID] | None = None


class ContractItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    name: str
    expertise_type_id: uuid.UUID
    price: Decimal
    currency: str
    comment: str | None
    technical_device_ids: list[uuid.UUID]
    building_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int


class ContractStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ContractStatus


class ContractReasonCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)


class ContractAddendumCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1, max_length=120)
    addendum_date: date
    amount_delta: Decimal | None = None
    new_end_date: date | None = None
    description: str | None = None


class ContractAddendumUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str | None = Field(default=None, max_length=120)
    addendum_date: date | None = None
    amount_delta: Decimal | None = None
    new_end_date: date | None = None
    description: str | None = None


class ContractAddendumStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ContractAddendumStatus


class ContractAddendumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    number: str
    addendum_date: date
    status: ContractAddendumStatus
    amount_delta: Decimal | None
    currency: str
    new_end_date: date | None
    description: str | None
    signed_at: datetime | None
    created_by: uuid.UUID
    updated_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int


class CompletionBlockerResponse(BaseModel):
    code: str
    detail: str


class CompletionCheckResponse(BaseModel):
    key: str
    passed: bool
    blockers: list[CompletionBlockerResponse]


class ContractCompletionReadinessResponse(BaseModel):
    ready_to_complete: bool
    checks: list[CompletionCheckResponse]
    blockers: list[CompletionBlockerResponse]


class ExpertiseTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_active: bool
