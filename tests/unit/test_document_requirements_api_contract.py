import uuid

import pytest
from pydantic import ValidationError

from app.modules.documents.schemas import (
    DocumentRequirementCreate,
    DocumentRequirementUpdate,
)


def test_requirement_create_accepts_only_supported_applicability() -> None:
    requirement = DocumentRequirementCreate(
        document_type="insurance",
        title="Insurance",
        applicability="has_opo",
        required=True,
        expiry_required=True,
    )
    assert requirement.applicability == "has_opo"


def test_requirement_update_is_partial_and_can_disable() -> None:
    update = DocumentRequirementUpdate(active=False)
    assert update.model_dump(exclude_unset=True) == {"active": False}


def test_requirement_response_exposes_identifier_and_flags() -> None:
    requirement_id = uuid.uuid4()
    payload = {
        "id": requirement_id,
        "document_type": "company_card",
        "title": "Company card",
        "applicability": "all",
        "required": True,
        "expiry_required": False,
        "active": True,
    }
    assert payload["id"] == requirement_id


def test_requirement_rejects_blank_metadata_and_null_patch_fields() -> None:
    with pytest.raises(ValidationError):
        DocumentRequirementCreate(document_type=" ", title="Insurance")
    with pytest.raises(ValidationError):
        DocumentRequirementUpdate(title=None)
