import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.technical_devices.enums import TechnicalDeviceType


class TechnicalDeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    device_type: TechnicalDeviceType
    serial_number: str | None = Field(default=None, max_length=100)
    opo_id: uuid.UUID | None = None
    organization_id: uuid.UUID


class TechnicalDeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    device_type: TechnicalDeviceType | None = None
    serial_number: str | None = None
    opo_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None


class TechnicalDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    device_type: str
    serial_number: str | None
    opo_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TechnicalDevicePaginatedResponse(BaseModel):
    items: list[TechnicalDeviceResponse]
    total: int
    page: int
    page_size: int
