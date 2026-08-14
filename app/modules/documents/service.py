import uuid
from datetime import date
from typing import BinaryIO, Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.documents import repository
from app.modules.documents.access import (
    DocumentAccessService,
    DocumentTargetNotFoundError,
    target_from_link,
)
from app.modules.documents.enums import DocumentLifecycleStatus
from app.modules.documents.models import Document, DocumentLink, DocumentVersion
from app.modules.documents.policy import validate_document_upload
from app.modules.documents.targets import DocumentTarget
from app.modules.identity.audit import write_audit
from app.modules.identity.authorization import AuthorizationContext
from app.storage.local import LocalFileStorage

DOCUMENT_MAX_BYTES = 20 * 1024 * 1024


class DocumentVersionConflictError(RuntimeError):
    pass


class DocumentNotFoundError(RuntimeError):
    pass


class DocumentLinkConflictError(RuntimeError):
    pass


class StoredObjectLike(Protocol):
    storage_key: str


class DocumentService:
    def __init__(self, storage: LocalFileStorage | None = None) -> None:
        self.storage = storage or LocalFileStorage(get_settings().storage_root)
        self.access = DocumentAccessService()

    def create_document(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        target: DocumentTarget,
        document_type: str,
        title: str,
        original_filename: str,
        content_type: str | None,
        source: BinaryIO,
        issued_at: date | None = None,
        expires_at: date | None = None,
    ) -> Document:
        validate_document_upload(original_filename, content_type)
        stored = self.storage.put(source, max_bytes=DOCUMENT_MAX_BYTES)
        document = Document(
            document_type=document_type.strip(),
            title=title.strip(),
            status=DocumentLifecycleStatus.WORKING.value,
            issued_at=issued_at,
            expires_at=expires_at,
            created_by=actor_user_id,
            version=1,
        )
        db.add(document)
        try:
            db.flush()
            version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                original_filename=original_filename[:255],
                content_type=content_type,
                storage_key=stored.storage_key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                created_by=actor_user_id,
            )
            link = DocumentLink(document_id=document.id, **target.as_link_kwargs())
            db.add_all([version, link])
            db.flush()
            document.current_version_id = version.id
            write_audit(
                db,
                action="document.created",
                summary="Document created",
                result="success",
                user_id=actor_user_id,
                entity_type="document",
                entity_id=document.id,
            )
            db.commit()
        except Exception:
            db.rollback()
            self.storage.delete(stored.storage_key)
            raise
        return document

    def add_version(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        document: Document,
        expected_version: int,
        original_filename: str,
        content_type: str | None,
        source: BinaryIO,
    ) -> DocumentVersion:
        locked = repository.get_document_for_update(db, document.id)
        if locked is None:
            raise DocumentNotFoundError("document not found")
        if locked.version != expected_version:
            raise DocumentVersionConflictError(
                f"document version conflict: expected {expected_version}, current {locked.version}"
            )

        current_file_version = repository.get_current_version(db, locked.id)
        if current_file_version is None:
            raise DocumentNotFoundError("document current file version not found")

        validate_document_upload(original_filename, content_type)
        stored = self.storage.put(source, max_bytes=DOCUMENT_MAX_BYTES)
        try:
            version = DocumentVersion(
                document_id=locked.id,
                version_number=current_file_version.version_number + 1,
                original_filename=original_filename[:255],
                content_type=content_type,
                storage_key=stored.storage_key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                created_by=actor_user_id,
            )
            db.add(version)
            db.flush()
            locked.current_version_id = version.id
            locked.version += 1
            write_audit(
                db,
                action="document.version_uploaded",
                summary="Document version uploaded",
                result="success",
                user_id=actor_user_id,
                entity_type="document",
                entity_id=locked.id,
                metadata={"version_number": version.version_number},
            )
            db.commit()
        except Exception:
            db.rollback()
            self.storage.delete(stored.storage_key)
            raise
        return version

    def add_link(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        authorization: AuthorizationContext,
        document: Document,
        target: DocumentTarget,
    ) -> DocumentLink:
        locked = repository.get_document_for_update(db, document.id)
        if locked is None or not self.access.can_access_document(
            db,
            authorization=authorization,
            document_id=document.id,
        ):
            db.rollback()
            raise DocumentNotFoundError("document not found")
        self.access.require_accessible_target(
            db,
            authorization=authorization,
            target=target,
        )
        if repository.find_document_link_for_target(db, locked.id, target) is not None:
            db.rollback()
            raise DocumentLinkConflictError("document link already exists")

        target_name, _target_id = target.non_null_items()[0]
        link = DocumentLink(document_id=locked.id, **target.as_link_kwargs())
        db.add(link)
        try:
            db.flush()
            write_audit(
                db,
                action="document.link_added",
                summary="Document link added",
                result="success",
                user_id=actor_user_id,
                entity_type="document",
                entity_id=locked.id,
                metadata={"target_type": target_name.removesuffix("_id")},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DocumentLinkConflictError("document link already exists") from exc
        return link

    def remove_link(
        self,
        db: Session,
        *,
        actor_user_id: uuid.UUID,
        authorization: AuthorizationContext,
        document: Document,
        link_id: uuid.UUID,
    ) -> None:
        locked = repository.get_document_for_update(db, document.id)
        if locked is None or not self.access.can_access_document(
            db,
            authorization=authorization,
            document_id=document.id,
        ):
            db.rollback()
            raise DocumentNotFoundError("document not found")
        link = repository.get_document_link(db, locked.id, link_id)
        if link is None or not self.access.can_access_target(
            db,
            authorization=authorization,
            target=target_from_link(link),
        ):
            db.rollback()
            raise DocumentTargetNotFoundError("document link not found")

        target_name, _target_id = target_from_link(link).non_null_items()[0]
        db.delete(link)
        write_audit(
            db,
            action="document.link_removed",
            summary="Document link removed",
            result="success",
            user_id=actor_user_id,
            entity_type="document",
            entity_id=locked.id,
            metadata={"target_type": target_name.removesuffix("_id")},
        )
        db.commit()

    def open_document(self, stored_object: StoredObjectLike) -> BinaryIO:
        return self.storage.open(stored_object.storage_key)
