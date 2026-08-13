from datetime import date

from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.modules.organizations.schemas import OrganizationCreateWithIdentifiers


def test_ip_fields_are_part_of_create_schema() -> None:
    payload = OrganizationCreateWithIdentifiers(
        legal_name="Иванов Иван Иванович",
        organization_type=OrganizationType.INDIVIDUAL_ENTREPRENEUR,
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

    data = payload.model_dump()

    assert data["residence_address"] == "г. Москва, ул. Примерная, д. 10"
    assert data["passport_series"] == "4510"
    assert data["passport_number"] == "123456"
    assert data["passport_issue_date"] == date(2019, 3, 12)
    assert data["bank_bik"] == "044525225"


def test_organization_model_accepts_ip_profile_fields() -> None:
    organization = Organization(
        legal_name="Иванов Иван Иванович",
        organization_type=OrganizationType.INDIVIDUAL_ENTREPRENEUR,
        residence_address="г. Москва",
        passport_series="4510",
        passport_number="123456",
        passport_issued_by="ОМВД России",
        passport_issue_date=date(2019, 3, 12),
        passport_department_code="770-001",
        bank_name="АО Банк",
        bank_bik="044525225",
        bank_account="40802810123450000001",
        correspondent_account="30101810400000000225",
    )

    assert organization.residence_address == "г. Москва"
    assert organization.passport_number == "123456"
    assert organization.bank_account == "40802810123450000001"
