import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_create_ip_profile_through_api(
    client: TestClient,
    superuser: dict[str, object],
) -> None:
    login = client.post(
        "/api/auth/login",
        json={
            "username": str(superuser["username"]),
            "password": str(superuser["password"]),
        },
    )
    assert login.status_code == 200

    response = client.post(
        "/api/organizations",
        json={
            "legal_name": "Иванов Иван Иванович",
            "short_name": "ИП Иванов И.И.",
            "organization_type": "individual_entrepreneur",
            "residence_address": "г. Москва, ул. Примерная, д. 10",
            "passport_series": "4510",
            "passport_number": "123456",
            "passport_issued_by": "ОМВД России по г. Москве",
            "passport_issue_date": "2019-03-12",
            "passport_department_code": "770-001",
            "bank_name": "АО Банк",
            "bank_bik": "044525225",
            "bank_account": "40802810123450000001",
            "correspondent_account": "30101810400000000225",
            "identifiers": [
                {
                    "identifier_type": "inn",
                    "identifier_value": "123456789012",
                    "is_primary": True,
                },
                {
                    "identifier_type": "ogrnip",
                    "identifier_value": "321123456789012",
                    "is_primary": False,
                },
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["organization_type"] == "individual_entrepreneur"
    assert payload["residence_address"] == "г. Москва, ул. Примерная, д. 10"
    assert payload["passport_series"] == "4510"
    assert payload["passport_number"] == "123456"
    assert payload["passport_issue_date"] == "2019-03-12"
    assert payload["bank_bik"] == "044525225"
    assert payload["bank_account"] == "40802810123450000001"
