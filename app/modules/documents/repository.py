import uuid

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.modules.documents.models import DocumentRequirement, OrganizationDocument

_REQUIRED_TABLES = ("organization_documents", "document_requirements")


def document_tables_available(db: Session) -> bool:
    schema = inspect(db.get_bind())
    return all(schema.has_table(table_name) for table_name in _REQUIRED_TABLES)


def list_organization_documents(
    db: Session,
    organization_id: uuid.UUID,
) -> list[OrganizationDocument]:
    return list(
        db.scalars(
            select(OrganizationDocument)
            .where(
                OrganizationDocument.organization_id == organization_id,
                OrganizationDocument.deleted_at.is_(None),
            )
            .order_by(OrganizationDocument.created_at.desc())
        ).all()
    )


def get_organization_document(
    db: Session,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
) -> OrganizationDocument | None:
    return db.scalar(
        select(OrganizationDocument).where(
            OrganizationDocument.id == document_id,
            OrganizationDocument.organization_id == organization_id,
            OrganizationDocument.deleted_at.is_(None),
        )
    )


def list_active_requirements(db: Session) -> list[DocumentRequirement]:
    return list(
        db.scalars(
            select(DocumentRequirement)
            .where(DocumentRequirement.active.is_(True))
            .order_by(DocumentRequirement.title.asc())
        ).all()
    )
