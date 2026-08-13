import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_superuser_can_read_management_report(
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

    response = client.get("/api/reports/management")

    assert response.status_code == 200
    payload = response.json()
    assert payload["organizations_total"] == 0
    assert payload["contracts"]["total"] == 0
    assert payload["tasks"]["total"] == 0
    assert payload["tasks"]["overdue"] == 0
    assert payload["documents"]["source_available"] is False
    assert payload["expertises"]["source_available"] is False
