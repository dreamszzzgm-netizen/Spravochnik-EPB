import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.modules.expertises.enums import ExpertiseStatus


class ExpertiseSubjectInput(BaseModel):
    technical_device_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def exactly_one_subject(self) -> "ExpertiseSubjectInput":
        has_device = self.technical_device_id is not None
        has_building = self.building_id is not None
        if has_device == has_building:
            raise ValueError("Укажите ровно один предмет экспертизы: устройство или здание")
        return self


class ExpertiseCreate(BaseModel):
    contract_id: uuid.UUID
    expertise_type_id: uuid.UUID
    responsible_expert_id: uuid.UUID
    contract_item_ids: list[uuid.UUID]
    internal_number: str | None = None
    comment: str | None = None
    subject: ExpertiseSubjectInput


class ExpertiseUpdate(BaseModel):
    expected_version: int
    expertise_type_id: uuid.UUID | None = None
    responsible_expert_id: uuid.UUID | None = None
    internal_number: str | None = None
    comment: str | None = None


class ExpertiseStatusChange(BaseModel):
    status: ExpertiseStatus
    expected_version: int
    reason: str | None = None


class ExpertiseSubjectResponse(BaseModel):
    technical_device_id: uuid.UUID | None
    building_id: uuid.UUID | None


class ExpertiseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    expertise_type_id: uuid.UUID
    status: ExpertiseStatus
    internal_number: str | None
    responsible_expert_id: uuid.UUID
    comment: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    subject: ExpertiseSubjectResponse
    contract_item_ids: list[uuid.UUID]
    contract_number: str | None = None
    organization_name: str | None = None
    expertise_type_name: str | None = None
    responsible_expert_name: str | None = None
    subject_kind: str | None = None
    subject_name: str | None = None


class ExpertiseListResponse(BaseModel):
    items: list[ExpertiseResponse]
    total: int
    page: int
    page_size: int


class ExpertiseStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: ExpertiseStatus | None
    to_status: ExpertiseStatus
    changed_at: datetime
    changed_by: uuid.UUID
    reason: str | None
