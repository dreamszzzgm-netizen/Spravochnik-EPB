import os
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts.models import Contract
from app.modules.documents import repository
from app.modules.documents.models import Document, DocumentLink, DocumentVersion
from app.modules.expertises.models import Expertise
from app.modules.identity.models import User
from app.modules.opo.models import OPO
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.modules.tasks.models import Task
from app.modules.technical_devices.models import TechnicalDevice

_MODEL_BOOTSTRAP = (Building, Contract, Expertise, User, OPO, Task, TechnicalDevice)


def _reset_database(engine) -> None:
    assert _MODEL_BOOTSTRAP
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    document_links, document_versions, documents,
                    organizations
                RESTART IDENTITY CASCADE
                """
            )
        )


def _add_document(
    db: Session,
    *,
    organization_id,
    title: str,
    storage_key: str,
    deleted: bool = False,
) -> Document:
    document = Document(
        document_type="insurance",
        title=title,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        original_filename=f"{title}.pdf",
        content_type="application/pdf",
        storage_key=storage_key,
        sha256="a" * 64,
        size_bytes=8,
    )
    link = DocumentLink(document_id=document.id, organization_id=organization_id)
    db.add_all([version, link])
    db.flush()
    document.current_version_id = version.id
    db.flush()
    return document


def test_organization_projection_reads_only_current_visible_documents() -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            organization = Organization(
                organization_type=OrganizationType.LEGAL_ENTITY,
                legal_name="Projection Customer LLC",
            )
            other = Organization(
                organization_type=OrganizationType.LEGAL_ENTITY,
                legal_name="Other Customer LLC",
            )
            db.add_all([organization, other])
            db.flush()

            visible = _add_document(
                db,
                organization_id=organization.id,
                title="passport",
                storage_key="projection-passport",
            )
            _add_document(
                db,
                organization_id=organization.id,
                title="deleted",
                storage_key="projection-deleted",
                deleted=True,
            )
            _add_document(
                db,
                organization_id=other.id,
                title="foreign",
                storage_key="projection-foreign",
            )
            db.commit()

            rows = repository.list_organization_documents(db, organization.id)
            assert len(rows) == 1
            row = rows[0]
            assert row.id == visible.id
            assert row.organization_id == organization.id
            assert row.original_filename == "passport.pdf"
            assert row.storage_key == "projection-passport"

            scoped = repository.get_organization_document(
                db, organization.id, visible.id
            )
            assert scoped is not None
            assert scoped.id == visible.id
            assert repository.get_organization_document(db, other.id, visible.id) is None
            assert repository.document_tables_available(db) is True
    finally:
        engine.dispose()
