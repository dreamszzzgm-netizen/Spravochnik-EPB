import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.organizations.models import (
    ContactType,
    IdentifierType,
    OrganizationType,
)


class OrganizationBase(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    short_name: str | None = Field(default=None, max_length=120)
    organization_type: OrganizationType = OrganizationType.LEGAL_ENTITY
    parent_id: uuid.UUID | None = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    short_name: str | None = Field(default=None, min_length=1, max_length=120)
    organization_type: OrganizationType | None = None
    parent_id: uuid.UUID | None = None


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_type: OrganizationType
    legal_name: str
    short_name: str | None
    parent_id: uuid.UUID | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrganizationContactCreate(BaseModel):
    contact_type: ContactType = ContactType.OTHER
    full_name: str = Field(min_length=1, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=320)
    is_primary: bool = False


class OrganizationContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    contact_type: ContactType
    full_name: str
    position: str | None
    phone: str | None
    email: str | None
    is_primary: bool


class OrganizationIdentifierCreate(BaseModel):
    identifier_type: IdentifierType
    identifier_value: str = Field(min_length=1, max_length=40)
    is_primary: bool = False


class OrganizationIdentifierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    identifier_type: IdentifierType
    identifier_value: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime
