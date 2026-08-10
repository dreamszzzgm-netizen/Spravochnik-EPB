import uuid
from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.opo.enums import HazardClass


class OPOHazardSignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str


class OPOActivityTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str


class OPOCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    registration_number: str = Field(min_length=1, max_length=100)
    hazard_class: HazardClass
    address: str = Field(min_length=1, max_length=500)
    registration_date: date_type | None = None
    owner_organization_id: uuid.UUID
    operating_organization_id: uuid.UUID
    hazard_sign_ids: list[uuid.UUID] = []
    activity_type_ids: list[uuid.UUID] = []
    comment: str | None = None


class OPOUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    registration_number: str | None = Field(default=None, min_length=1, max_length=100)
    hazard_class: HazardClass | None = None
    address: str | None = Field(default=None, min_length=1, max_length=500)
    registration_date: date_type | None = None
    owner_organization_id: uuid.UUID | None = None
    operating_organization_id: uuid.UUID | None = None
    hazard_sign_ids: list[uuid.UUID] | None = None
    activity_type_ids: list[uuid.UUID] | None = None
    comment: str | None = None


class OPOResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    registration_number: str
    hazard_class: str
    address: str
    registration_date: date_type
    owner_organization_id: uuid.UUID
    operating_organization_id: uuid.UUID
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OPODetailResponse(OPOResponse):
    hazard_signs: list[OPOHazardSignResponse] = []
    activity_types: list[OPOActivityTypeResponse] = []


class OPOPaginatedResponse(BaseModel):
    items: list[OPOResponse]
    total: int
    page: int
    page_size: int
