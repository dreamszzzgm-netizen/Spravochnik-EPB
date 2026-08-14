import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, and_, inspect, select
from sqlalchemy.orm import Session

from app.modules.documents.models import (
    Document,
    DocumentLink,
    DocumentRequirement,
    DocumentVersion,
)

_REQUIRED_TABLES = (
    "documents",
    "document_versions",
    "document_links",
    "document_requirements",
)


@dataclass(frozen=True, slots=True)
class OrganizationDocumentProjection:
    id: uuid.UUID
    organization_id: uuid.UUID
    document_type: str
    title: str
    original_filename: str
    content_type: str | None
    storage_key: str
    sha256: str
    size_bytes: int
    issued_at: date | None
    expires_at: date | None
    created_at: datetime
    updated_at: datetime


def document_tables_available(db: Session) -> bool:
    schema = inspect(db.get_bind())
    return all(schema.has_table(table_name) for table_name in _REQUIRED_TABLES)


def get_document(
    db: Session,
    document_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Document | None:
    statement = select(Document).where(Document.id == document_id)
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    return db.scalar(statement)


def get_document_for_update(
    db: Session,
    document_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Document | None:
    statement = select(Document).where(Document.id == document_id)
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    return db.scalar(statement.with_for_update())


def get_current_version(
    db: Session,
    document_id: uuid.UUID,
) -> DocumentVersion | None:
    return db.scalar(
        select(DocumentVersion)
        .join(
            Document,
            and_(
                Document.id == DocumentVersion.document_id,
                Document.current_version_id == DocumentVersion.id,
            ),
        )
        .where(Document.id == document_id)
    )


def list_versions(db: Session, document_id: uuid.UUID) -> list[DocumentVersion]:
    return list(
        db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.asc())
        ).all()
    )


def list_document_links(db: Session, document_id: uuid.UUID) -> list[DocumentLink]:
    return list(
        db.scalars(
            select(DocumentLink)
            .where(DocumentLink.document_id == document_id)
            .order_by(DocumentLink.created_at.asc(), DocumentLink.id.asc())
        ).all()
    )


def _organization_projection_statement() -> Select:
    return (
        select(
            Document.id.label("id"),
            DocumentLink.organization_id.label("organization_id"),
            Document.document_type.label("document_type"),
            Document.title.label("title"),
            DocumentVersion.original_filename.label("original_filename"),
            DocumentVersion.content_type.label("content_type"),
            DocumentVersion.storage_key.label("storage_key"),
            DocumentVersion.sha256.label("sha256"),
            DocumentVersion.size_bytes.label("size_bytes"),
            Document.issued_at.label("issued_at"),
            Document.expires_at.label("expires_at"),
            Document.created_at.label("created_at"),
            Document.updated_at.label("updated_at"),
        )
        .join(
            DocumentLink,
            and_(
                DocumentLink.document_id == Document.id,
                DocumentLink.organization_id.is_not(None),
            ),
        )
        .join(
            DocumentVersion,
            and_(
                DocumentVersion.document_id == Document.id,
                DocumentVersion.id == Document.current_version_id,
            ),
        )
        .where(Document.deleted_at.is_(None))
    )


def _to_organization_projection(row) -> OrganizationDocumentProjection:
    return OrganizationDocumentProjection(
        id=row.id,
        organization_id=row.organization_id,
        document_type=row.document_type,
        title=row.title,
        original_filename=row.original_filename,
        content_type=row.content_type,
        storage_key=row.storage_key,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        issued_at=row.issued_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_organization_documents(
    db: Session,
    organization_id: uuid.UUID,
) -> list[OrganizationDocumentProjection]:
    rows = db.execute(
        _organization_projection_statement()
        .where(DocumentLink.organization_id == organization_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    return [_to_organization_projection(row) for row in rows]


def get_organization_document(
    db: Session,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
) -> OrganizationDocumentProjection | None:
    row = db.execute(
        _organization_projection_statement().where(
            Document.id == document_id,
            DocumentLink.organization_id == organization_id,
        )
    ).one_or_none()
    return _to_organization_projection(row) if row is not None else None


def list_active_requirements(db: Session) -> list[DocumentRequirement]:
    return list(
        db.scalars(
            select(DocumentRequirement)
            .where(DocumentRequirement.active.is_(True))
            .order_by(DocumentRequirement.title.asc())
        ).all()
    )


def list_requirements(db: Session) -> list[DocumentRequirement]:
    return list(
        db.scalars(select(DocumentRequirement).order_by(DocumentRequirement.title.asc())).all()
    )


def get_requirement(
    db: Session, requirement_id: uuid.UUID
) -> DocumentRequirement | None:
    return db.get(DocumentRequirement, requirement_id)
