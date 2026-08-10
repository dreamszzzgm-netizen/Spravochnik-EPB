import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.buildings.enums import BuildingType


class BuildingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    building_type: BuildingType
    opo_id: uuid.UUID | None = None
    organization_id: uuid.UUID


class BuildingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    building_type: BuildingType | None = None
    opo_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None


class BuildingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    building_type: str
    opo_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BuildingPaginatedResponse(BaseModel):
    items: list[BuildingResponse]
    total: int
    page: int
    page_size: int
