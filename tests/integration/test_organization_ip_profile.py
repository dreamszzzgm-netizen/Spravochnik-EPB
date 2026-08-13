import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.service import OrganizationService

pytestmark = pytest.mark.integration


def test_service_persists_individual_entrepreneur_profile(
    db_session: Session,
    superuser: dict[str, object],
) -> None:
    service = OrganizationService()

    organization = service.create_organization(
        db_session,
        actor_id=uuid.UUID(str(superuser["id"])),
        legal_name="Иванов Иван Иванович",
        short_name="ИП Иванов И.И.",
        organization_type=OrganizationType.INDIVIDUAL_ENTREPRENEUR,
        parent_id=None,
        residence_address="г. Москва, ул. Примерная, д. 10",
        passport_series="4510",
        passport_number="123456",
        passport_issued_by="ОМВД России по г. Москве",
        passport_issue_date=date(2019, 3, 12),
        passport_department_code="770-001",
        bank_name="АО Банк",
        bank_bik="044525225",
        bank_account="40802810123450000001",
        correspondent_account="30101810400000000225",
    )

    db_session.refresh(organization)
    assert organization.organization_type is OrganizationType.INDIVIDUAL_ENTREPRENEUR
    assert organization.residence_address == "г. Москва, ул. Примерная, д. 10"
    assert organization.passport_series == "4510"
    assert organization.passport_number == "123456"
    assert organization.passport_issue_date == date(2019, 3, 12)
    assert organization.passport_department_code == "770-001"
    assert organization.bank_name == "АО Банк"
    assert organization.bank_bik == "044525225"
    assert organization.bank_account == "40802810123450000001"
    assert organization.correspondent_account == "30101810400000000225"
