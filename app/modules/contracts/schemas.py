import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.contracts.enums import ContractStatus


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


class ExpertiseTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_active: bool
