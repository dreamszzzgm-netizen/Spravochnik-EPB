import uuid

import pytest

from app.modules.documents.targets import DocumentTarget, DocumentTargetError


def test_document_target_requires_exactly_one_id() -> None:
    with pytest.raises(DocumentTargetError):
        DocumentTarget()
    with pytest.raises(DocumentTargetError):
        DocumentTarget(organization_id=uuid.uuid4(), contract_id=uuid.uuid4())


def test_document_target_accepts_one_organization() -> None:
    organization_id = uuid.uuid4()
    target = DocumentTarget(organization_id=organization_id)
    assert target.organization_id == organization_id
