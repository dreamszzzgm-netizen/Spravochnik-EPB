import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

NonBlank120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
NonBlank255 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


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
    status: str = "valid"


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


class DocumentRequirementCreate(BaseModel):
    document_type: NonBlank120
    title: NonBlank255
    applicability: Literal["all", "has_opo"] = "all"
    required: bool = True
    expiry_required: bool = False
    active: bool = True


class DocumentRequirementUpdate(BaseModel):
    document_type: NonBlank120 | None = None
    title: NonBlank255 | None = None
    applicability: Literal["all", "has_opo"] | None = None
    required: bool | None = None
    expiry_required: bool | None = None
    active: bool | None = None

    @field_validator("document_type", "title", mode="before")
    @classmethod
    def reject_explicit_null_text(cls, value):
        if value is None:
            raise ValueError("field cannot be null")
        return value
