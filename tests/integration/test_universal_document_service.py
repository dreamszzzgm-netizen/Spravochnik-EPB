import io
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts.models import Contract
from app.modules.documents import repository
from app.modules.documents.models import Document, DocumentLink, DocumentVersion
from app.modules.documents.service import DocumentService, DocumentVersionConflictError
from app.modules.documents.targets import DocumentTarget
from app.modules.expertises.models import Expertise
from app.modules.identity.models import Employee, User
from app.modules.opo.models import OPO
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.modules.tasks.models import Task
from app.modules.technical_devices.models import TechnicalDevice
from app.storage.local import LocalFileStorage

_MODEL_BOOTSTRAP = (Building, Contract, Expertise, OPO, Task, TechnicalDevice)


def _reset_database(engine) -> None:
    assert _MODEL_BOOTSTRAP
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    document_links, document_versions, documents,
                    audit_events, organizations, users, employees
                RESTART IDENTITY CASCADE
                """
            )
        )


def _seed_actor_and_organization(db: Session) -> tuple[uuid.UUID, Organization]:
    employee = Employee(full_name="Document Service Actor")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"doc-service-{uuid.uuid4()}",
        password_hash="not-used-in-this-test",
        is_active=True,
        is_superuser=True,
    )
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name="Universal Document Customer LLC",
    )
    db.add_all([user, organization])
    db.commit()
    return user.id, organization


def _service(tmp_path: Path) -> DocumentService:
    return DocumentService(storage=LocalFileStorage(tmp_path))


def test_create_document_creates_v1_link_actor_and_current_pointer(tmp_path: Path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            actor_user_id, organization = _seed_actor_and_organization(db)
            service = _service(tmp_path)

            document = service.create_document(
                db,
                actor_user_id=actor_user_id,
                target=DocumentTarget(organization_id=organization.id),
                document_type="insurance",
                title="Insurance 2026",
                original_filename="insurance.pdf",
                content_type="application/pdf",
                source=io.BytesIO(b"%PDF-test"),
            )

            assert document.current_version_id is not None
            assert document.created_by == actor_user_id
            assert document.version == 1
            assert db.scalar(select(func.count()).select_from(DocumentVersion)) == 1
            assert db.scalar(select(func.count()).select_from(DocumentLink)) == 1
            current = repository.get_current_version(db, document.id)
            assert current is not None
            assert current.version_number == 1
            assert current.created_by == actor_user_id
            assert service.storage.exists(current.storage_key)
    finally:
        engine.dispose()


def test_create_document_removes_storage_object_when_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            actor_user_id, organization = _seed_actor_and_organization(db)
            service = _service(tmp_path)

            def fail_commit() -> None:
                raise RuntimeError("forced commit failure")

            monkeypatch.setattr(db, "commit", fail_commit)
            with pytest.raises(RuntimeError, match="forced commit failure"):
                service.create_document(
                    db,
                    actor_user_id=actor_user_id,
                    target=DocumentTarget(organization_id=organization.id),
                    document_type="insurance",
                    title="Compensation",
                    original_filename="compensation.pdf",
                    content_type="application/pdf",
                    source=io.BytesIO(b"%PDF-compensation"),
                )

            assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
            assert db.scalar(select(func.count()).select_from(Document)) == 0
    finally:
        engine.dispose()


def test_add_version_is_immutable_and_rejects_stale_lock(tmp_path: Path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            actor_user_id, organization = _seed_actor_and_organization(db)
            service = _service(tmp_path)
            document = service.create_document(
                db,
                actor_user_id=actor_user_id,
                target=DocumentTarget(organization_id=organization.id),
                document_type="insurance",
                title="Versioned",
                original_filename="v1.pdf",
                content_type="application/pdf",
                source=io.BytesIO(b"%PDF-v1"),
            )
            v1 = repository.get_current_version(db, document.id)
            assert v1 is not None

            version2 = service.add_version(
                db,
                actor_user_id=actor_user_id,
                document=document,
                expected_version=1,
                original_filename="v2.pdf",
                content_type="application/pdf",
                source=io.BytesIO(b"%PDF-v2"),
            )

            assert version2.version_number == 2
            assert document.current_version_id == version2.id
            assert document.version == 2
            versions = repository.list_versions(db, document.id)
            assert [item.version_number for item in versions] == [1, 2]
            assert versions[0].id == v1.id
            assert versions[0].sha256 == v1.sha256
            files_before_stale = sorted(path.name for path in tmp_path.iterdir())

            with pytest.raises(DocumentVersionConflictError):
                service.add_version(
                    db,
                    actor_user_id=actor_user_id,
                    document=document,
                    expected_version=1,
                    original_filename="stale.pdf",
                    content_type="application/pdf",
                    source=io.BytesIO(b"%PDF-stale"),
                )

            assert [item.version_number for item in repository.list_versions(db, document.id)] == [
                1,
                2,
            ]
            assert sorted(path.name for path in tmp_path.iterdir()) == files_before_stale
    finally:
        engine.dispose()


def test_file_version_number_is_independent_from_document_lock_version(tmp_path: Path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            actor_user_id, organization = _seed_actor_and_organization(db)
            service = _service(tmp_path)
            document = service.create_document(
                db,
                actor_user_id=actor_user_id,
                target=DocumentTarget(organization_id=organization.id),
                document_type="insurance",
                title="Independent counters",
                original_filename="v1.pdf",
                content_type="application/pdf",
                source=io.BytesIO(b"%PDF-v1"),
            )
            document.version = 2
            db.commit()

            version2 = service.add_version(
                db,
                actor_user_id=actor_user_id,
                document=document,
                expected_version=2,
                original_filename="v2.pdf",
                content_type="application/pdf",
                source=io.BytesIO(b"%PDF-v2"),
            )

            assert version2.version_number == 2
            assert document.version == 3
    finally:
        engine.dispose()
