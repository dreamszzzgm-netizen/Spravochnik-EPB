import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CustomFieldDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    entity_type: str
    field_type: str


class CustomFieldValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_definition_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    value_text: str | None = None
    value_number: Any | None = None
    value_date: str | None = None
    value_boolean: bool | None = None

    @classmethod
    def model_validate(cls, obj: Any) -> "CustomFieldValueResponse":
        instance = super().model_validate(obj)
        if instance.value_date is not None:
            instance.value_date = str(instance.value_date)
        return instance


class CustomFieldValueSetRequest(BaseModel):
    value: str = Field(min_length=1, max_length=10000)
