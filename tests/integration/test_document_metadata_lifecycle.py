import io
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.documents import repository
from app.modules.documents.models import DocumentVersion
from app.modules.documents.service import DocumentService, DocumentVersionConflictError
from app.modules.documents.targets import DocumentTarget
from app.modules.identity.models import AuditEvent, Employee, User
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.storage.local import LocalFileStorage


def _reset_database(engine) -> None:
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


def _seed_document(db: Session, storage_root: Path):
    employee = Employee(full_name="Document Lifecycle Actor")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"document-lifecycle-{uuid.uuid4()}",
        password_hash="unused",
        is_active=True,
        is_superuser=True,
    )
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name="Document Lifecycle LLC",
    )
    db.add_all([user, organization])
    db.commit()
    service = DocumentService(storage=LocalFileStorage(storage_root))
    document = service.create_document(
        db,
        actor_user_id=user.id,
        target=DocumentTarget(organization_id=organization.id),
        document_type="insurance",
        title="Original title",
        original_filename="lifecycle.pdf",
        content_type="application/pdf",
        source=io.BytesIO(b"%PDF-lifecycle"),
    )
    return user, service, document


def test_metadata_update_uses_optimistic_lock_and_rejects_stale_write(tmp_path: Path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user, service, document = _seed_document(db, tmp_path)

            updated = service.update_metadata(
                db,
                actor_user_id=user.id,
                document=document,
                expected_version=1,
                title="Updated title",
            )
            assert updated.title == "Updated title"
            assert updated.version == 2

            with pytest.raises(DocumentVersionConflictError):
                service.update_metadata(
                    db,
                    actor_user_id=user.id,
                    document=document,
                    expected_version=1,
                    title="Lost update",
                )

            current = repository.get_document(db, document.id)
            assert current is not None
            assert current.title == "Updated title"
            assert current.version == 2
    finally:
        engine.dispose()


def test_soft_delete_restore_preserves_file_versions_and_audits_safely(tmp_path: Path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user, service, document = _seed_document(db, tmp_path)
            current_version = repository.get_current_version(db, document.id)
            assert current_version is not None
            storage_key = current_version.storage_key
            original_version_id = current_version.id
            assert service.storage.exists(storage_key)

            service.update_metadata(
                db,
                actor_user_id=user.id,
                document=document,
                expected_version=1,
                title="Audited metadata",
            )
            deleted = service.soft_delete_document(
                db,
                actor_user_id=user.id,
                document=document,
                expected_version=2,
            )
            assert deleted.deleted_at is not None
            assert deleted.deleted_by == user.id
            assert deleted.version == 3
            assert repository.get_document(db, document.id) is None
            assert repository.get_document(db, document.id, include_deleted=True) is not None
            assert service.storage.exists(storage_key)
            versions = repository.list_versions(db, document.id)
            assert [item.id for item in versions] == [original_version_id]
            assert db.scalar(select(DocumentVersion).where(DocumentVersion.id == original_version_id))

            restored = service.restore_document(
                db,
                actor_user_id=user.id,
                document=document,
                expected_version=3,
            )
            assert restored.deleted_at is None
            assert restored.deleted_by is None
            assert restored.version == 4
            assert repository.get_document(db, document.id) is not None
            assert service.storage.exists(storage_key)

            events = list(
                db.scalars(
                    select(AuditEvent)
                    .where(
                        AuditEvent.entity_type == "document",
                        AuditEvent.entity_id == document.id,
                    )
                    .order_by(AuditEvent.timestamp.asc())
                ).all()
            )
            actions = [event.action for event in events]
            assert "document.metadata_updated" in actions
            assert "document.deleted" in actions
            assert "document.restored" in actions
            for event in events:
                serialized_metadata = repr(event.metadata_json).lower()
                assert "lifecycle.pdf" not in serialized_metadata
                assert "%pdf" not in serialized_metadata
                assert "filename" not in serialized_metadata
                assert "content" not in serialized_metadata
    finally:
        engine.dispose()


def test_legacy_delete_without_expected_version_serializes_current_state(tmp_path: Path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user, service, document = _seed_document(db, tmp_path)
            service.update_metadata(
                db,
                actor_user_id=user.id,
                document=document,
                expected_version=1,
                title="Version two",
            )

            deleted = service.soft_delete_document(
                db,
                actor_user_id=user.id,
                document=document,
                expected_version=None,
            )
            assert deleted.version == 3
            assert deleted.deleted_by == user.id
    finally:
        engine.dispose()
