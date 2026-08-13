import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.documents.models import OrganizationDocument
from app.storage.local import LocalFileStorage


class DocumentService:
    def __init__(self) -> None:
        self.storage = LocalFileStorage(get_settings().storage_root)

    def create_document(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        document_type: str,
        title: str,
        original_filename: str,
        content_type: str | None,
        source: BinaryIO,
        issued_at: date | None,
        expires_at: date | None,
    ) -> OrganizationDocument:
        stored = self.storage.put(source)
        document = OrganizationDocument(
            organization_id=organization_id,
            document_type=document_type.strip(),
            title=title.strip(),
            original_filename=Path(original_filename).name[:255] or "document",
            content_type=content_type,
            storage_key=stored.storage_key,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        db.add(document)
        try:
            db.commit()
            db.refresh(document)
        except Exception:
            db.rollback()
            self.storage.delete(stored.storage_key)
            raise
        return document

    def soft_delete_document(self, db: Session, document: OrganizationDocument) -> None:
        document.deleted_at = datetime.now(UTC)
        db.commit()

    def open_document(self, document: OrganizationDocument) -> BinaryIO:
        return self.storage.open(document.storage_key)
