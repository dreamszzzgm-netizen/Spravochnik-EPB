from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web.middleware import RequestContextMiddleware


def test_request_context_headers_are_returned() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/")
    def root() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/", headers={"X-Correlation-ID": "corr-123"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-123"
    assert response.headers["X-Request-ID"]
