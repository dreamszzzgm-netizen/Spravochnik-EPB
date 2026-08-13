import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class OrganizationDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    document_type: str
    title: str
    original_filename: str
    content_type: str | None
    sha256: str
    size_bytes: int
    issued_at: date | None
    expires_at: date | None
    created_at: datetime
    updated_at: datetime


class OrganizationDocumentListResponse(BaseModel):
    source_available: bool
    items: list[OrganizationDocumentResponse]


class DocumentRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: str
    title: str
    applicability: str
    required: bool
    expiry_required: bool
    active: bool
