import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.organizations.models import Organization

pytestmark = pytest.mark.integration


def test_import_candidate_does_not_create_organization(
    client: TestClient,
    db_session: Session,
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
    before = db_session.scalar(select(func.count()).select_from(Organization))

    response = client.post(
        "/api/organizations/import-candidate",
        files={
            "file": (
                "ip-card.txt",
                (
                    "Индивидуальный предприниматель Иванов Иван Иванович\n"
                    "ИНН: 123456789012\n"
                    "ОГРНИП: 321123456789012\n"
                    "Место жительства: г. Москва, ул. Примерная, д. 10\n"
                    "Паспорт: серия 4510 номер 123456\n"
                ).encode("utf-8"),
                "text/plain",
            )
        },
    )

    after = db_session.scalar(select(func.count()).select_from(Organization))
    assert response.status_code == 200
    payload = response.json()
    assert payload["organization_type"] == "individual_entrepreneur"
    assert payload["legal_name"] == "Иванов Иван Иванович"
    assert payload["identifiers"]["inn"] == "123456789012"
    assert payload["identifiers"]["ogrnip"] == "321123456789012"
    assert payload["requires_review"] is True
    assert after == before


def test_import_candidate_rejects_unsupported_binary_without_external_processing(
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
        "/api/organizations/import-candidate",
        files={"file": ("passport.jpg", b"not-an-image", "image/jpeg")},
    )

    assert response.status_code == 415
    assert "локаль" in response.json()["detail"].lower()
