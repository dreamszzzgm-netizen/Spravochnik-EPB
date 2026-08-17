import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.import_.enums import CandidateAction, CandidateStatus, ImportSessionStatus


class ImportSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source: str
    filename: str | None
    import_type: str
    status: ImportSessionStatus
    candidate_count: int
    added_count: int
    updated_count: int
    skipped_count: int
    duplicate_count: int
    conflict_count: int
    error_count: int
    result_summary: dict | None
    created_at: datetime
    updated_at: datetime


class ImportCandidateNormalizedData(BaseModel):
    organization_type: str | None = None
    legal_name: str | None = None
    short_name: str | None = None
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    ogrnip: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    residence_address: str | None = None
    director_name: str | None = None
    phone: str | None = None
    email: str | None = None
    bank_details: str | None = None
    parent_inn: str | None = None
    parent_kpp: str | None = None


class ImportCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    row_number: int
    raw_data: dict | None
    normalized_data: dict | None
    validation_errors: list | None
    warnings: list | None
    candidate_status: CandidateStatus
    proposed_action: CandidateAction
    matched_organization_id: uuid.UUID | None
    conflict_details: dict | None
    created_at: datetime
    updated_at: datetime


class ImportSessionListResponse(BaseModel):
    items: list[ImportSessionResponse]
    total: int


class ImportConfirmRequest(BaseModel):
    session_id: uuid.UUID


class ImportReportResponse(BaseModel):
    session: ImportSessionResponse
    candidates: list[ImportCandidateResponse]


class ImportCandidateUpdateRequest(BaseModel):
    proposed_action: CandidateAction
    normalized_data: ImportCandidateNormalizedData | None = None
