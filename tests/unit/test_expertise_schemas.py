import uuid

import pytest
from pydantic import ValidationError

from app.modules.expertises.schemas import ExpertiseSubjectInput


def test_subject_rejects_both_none() -> None:
    with pytest.raises(ValidationError):
        ExpertiseSubjectInput(technical_device_id=None, building_id=None)


def test_subject_rejects_both_set() -> None:
    with pytest.raises(ValidationError):
        ExpertiseSubjectInput(
            technical_device_id=uuid.uuid4(),
            building_id=uuid.uuid4(),
        )


def test_subject_accepts_single_device() -> None:
    device_id = uuid.uuid4()
    subject = ExpertiseSubjectInput(technical_device_id=device_id, building_id=None)
    assert subject.technical_device_id == device_id
    assert subject.building_id is None


def test_subject_accepts_single_building() -> None:
    building_id = uuid.uuid4()
    subject = ExpertiseSubjectInput(technical_device_id=None, building_id=building_id)
    assert subject.technical_device_id is None
    assert subject.building_id == building_id
