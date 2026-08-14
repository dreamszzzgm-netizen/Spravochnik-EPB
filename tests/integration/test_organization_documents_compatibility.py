import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.documents import repository
from app.modules.documents import routes as document_routes
from app.modules.documents.models import Document, DocumentVersion
from app.modules.documents.service import DOCUMENT_MAX_BYTES, DocumentService
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.models import Employee, ScopeType, User
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.storage.local import LocalFileStorage


def _reset_database(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    document_links, document_versions, documents, document_requirements,
                    audit_events, opo, organizations, users, employees
                RESTART IDENTITY CASCADE
                """
            )
        )


def _seed_actor_and_organization(db: Session) -> tuple[User, Organization]:
    employee = Employee(full_name="Compatibility Actor")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"documents-compat-{uuid.uuid4()}",
        password_hash="unused",
        is_active=True,
        is_superuser=True,
    )
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name="Compatibility Customer LLC",
    )
    db.add_all([user, organization])
    db.commit()
    return user, organization


def _authorization(user: User) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user.id,
        employee_id=user.employee_id,
        permission_code="documents.view",
        is_superuser=True,
        has_all_scope=True,
        related_organization_ids=frozenset(),
        active_scope_types=frozenset({ScopeType.ALL}),
    )


@contextmanager
def _client(
    db: Session,
    authorization: AuthorizationContext,
) -> Generator[TestClient, None, None]:
    app = FastAPI()
    app.include_router(document_routes.router)

    def override_db() -> Generator[Session, None, None]:
        yield db

    def override_authorization() -> AuthorizationContext:
        return authorization

    app.dependency_overrides[get_db] = override_db
    for dependency in (
        document_routes._dep_view,
        document_routes._dep_download,
        document_routes._dep_upload,
        document_routes._dep_delete,
    ):
        app.dependency_overrides[dependency.dependency] = override_authorization

    with TestClient(app) as client:
        yield client


def test_existing_organization_document_api_preserves_contract_and_soft_delete(
    tmp_path: Path, monkeypatch
) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user, organization = _seed_actor_and_organization(db)
            storage = LocalFileStorage(tmp_path)
            service = DocumentService(storage=storage)
            monkeypatch.setattr(document_routes, "service", service)
            authorization = _authorization(user)
            content = b"%PDF-1.7\ncompatibility-document\n"

            with _client(db, authorization) as client:
                upload = client.post(
                    f"/api/organizations/{organization.id}/documents",
                    data={
                        "document_type": "insurance",
                        "title": "Insurance 2026",
                        "issued_at": "2026-01-10",
                        "expires_at": "2026-12-31",
                    },
                    files={"file": ("insurance.pdf", content, "application/pdf")},
                )
                assert upload.status_code == 201, upload.text
                payload = upload.json()
                document_id = uuid.UUID(payload["id"])
                assert payload["organization_id"] == str(organization.id)
                assert payload["document_type"] == "insurance"
                assert payload["title"] == "Insurance 2026"
                assert payload["original_filename"] == "insurance.pdf"
                assert payload["size_bytes"] == len(content)
                assert "storage_key" not in payload

                listed = client.get(
                    f"/api/organizations/{organization.id}/documents"
                )
                assert listed.status_code == 200
                assert listed.json()["source_available"] is True
                assert [item["id"] for item in listed.json()["items"]] == [payload["id"]]

                downloaded = client.get(
                    f"/api/organizations/{organization.id}/documents/"
                    f"{document_id}/download"
                )
                assert downloaded.status_code == 200
                assert downloaded.content == content
                assert "insurance.pdf" in downloaded.headers["content-disposition"]

                deleted = client.delete(
                    f"/api/organizations/{organization.id}/documents/{document_id}"
                )
                assert deleted.status_code == 204

                after_delete = client.get(
                    f"/api/organizations/{organization.id}/documents"
                )
                assert after_delete.status_code == 200
                assert after_delete.json() == {"source_available": True, "items": []}

            logical = repository.get_document(db, document_id, include_deleted=True)
            assert logical is not None
            assert logical.deleted_at is not None
            assert logical.deleted_by == user.id
            assert logical.version == 2
            current = repository.get_current_version(db, document_id)
            assert current is not None
            assert storage.exists(current.storage_key)
            assert db.scalar(select(func.count()).select_from(DocumentVersion)) == 1
    finally:
        engine.dispose()


def test_existing_upload_rejects_disallowed_extension_without_storage_write(
    tmp_path: Path, monkeypatch
) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user, organization = _seed_actor_and_organization(db)
            storage = LocalFileStorage(tmp_path)
            monkeypatch.setattr(document_routes, "service", DocumentService(storage=storage))

            with _client(db, _authorization(user)) as client:
                response = client.post(
                    f"/api/organizations/{organization.id}/documents",
                    data={"document_type": "other", "title": "Blocked"},
                    files={
                        "file": (
                            "payload.exe",
                            b"MZ-blocked",
                            "application/octet-stream",
                        )
                    },
                )

            assert response.status_code == 422
            assert db.scalar(select(func.count()).select_from(Document)) == 0
            assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
    finally:
        engine.dispose()


def test_existing_upload_streaming_limit_returns_413_without_orphan(
    tmp_path: Path, monkeypatch
) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user, organization = _seed_actor_and_organization(db)
            storage = LocalFileStorage(tmp_path)
            monkeypatch.setattr(document_routes, "service", DocumentService(storage=storage))
            oversized = b"x" * (DOCUMENT_MAX_BYTES + 1)

            with _client(db, _authorization(user)) as client:
                response = client.post(
                    f"/api/organizations/{organization.id}/documents",
                    data={"document_type": "other", "title": "Too large"},
                    files={"file": ("too-large.pdf", oversized, "application/pdf")},
                )

            assert response.status_code == 413
            assert db.scalar(select(func.count()).select_from(Document)) == 0
            assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
    finally:
        engine.dispose()
