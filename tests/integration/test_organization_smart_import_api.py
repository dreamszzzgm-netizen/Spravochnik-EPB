import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.organizations.models import Organization

pytestmark = pytest.mark.integration


def _login(client: TestClient, superuser: dict[str, object]) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": superuser["username"], "password": superuser["password"]},
    )
    assert response.status_code == 200


def test_import_preview_is_read_only_and_returns_ip_candidate(
    client: TestClient, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    before = db_session.scalar(select(func.count()).select_from(Organization)) or 0

    response = client.post(
        "/api/organizations/import-preview",
        json={
            "text": """
            Индивидуальный предприниматель Иванов Иван Иванович
            ИНН: 770123456789
            ОГРНИП: 326770000123456
            Место жительства: г. Москва, ул. Примерная, д. 1
            Паспорт: 45 01 123456, выдан ОВД Примерный 01.02.2010
            """
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate"]["organization_type"] == "individual_entrepreneur"
    assert body["candidate"]["residence_address"] == "г. Москва, ул. Примерная, д. 1"
    assert {item["identifier_type"] for item in body["candidate"]["identifiers"]} == {
        "inn",
        "ogrnip",
    }
    after = db_session.scalar(select(func.count()).select_from(Organization)) or 0
    assert after == before


def test_individual_entrepreneur_fields_round_trip_through_api(
    client: TestClient, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    response = client.post(
        "/api/organizations",
        json={
            "legal_name": "ИП Иванов Иван Иванович",
            "organization_type": "individual_entrepreneur",
            "residence_address": "г. Москва, ул. Примерная, д. 1",
            "passport_details": "45 01 123456, выдан ОВД Примерный 01.02.2010",
            "identifiers": [
                {
                    "identifier_type": "inn",
                    "identifier_value": "770123456789",
                    "is_primary": True,
                },
                {
                    "identifier_type": "ogrnip",
                    "identifier_value": "326770000123456",
                    "is_primary": False,
                },
            ],
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["residence_address"] == "г. Москва, ул. Примерная, д. 1"
    assert created["passport_details"].startswith("45 01 123456")

    read = client.get(f"/api/organizations/{created['id']}")
    assert read.status_code == 200
    assert read.json()["residence_address"] == created["residence_address"]
    assert read.json()["passport_details"] == created["passport_details"]


def test_import_preview_warns_about_existing_identifier(
    client: TestClient, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    created = client.post(
        "/api/organizations",
        json={
            "legal_name": "ООО Существующая",
            "organization_type": "legal_entity",
            "identifiers": [
                {
                    "identifier_type": "inn",
                    "identifier_value": "7701234567",
                    "is_primary": True,
                }
            ],
        },
    )
    assert created.status_code == 201

    preview = client.post(
        "/api/organizations/import-preview",
        json={"text": "ООО Новая\nИНН: 7701234567\nКПП: 770101001\nОГРН: 1027700123456"},
    )
    assert preview.status_code == 200
    assert preview.json()["duplicate_warnings"]
