import io
import os
import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.documents.models import DocumentLink
from app.modules.documents.service import DocumentService
from app.modules.documents.targets import DocumentTarget
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.models import AuditEvent, Employee, ScopeType, User
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.storage.local import LocalFileStorage


def test_remove_link_deletes_only_link_and_writes_audit(tmp_path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE document_links, document_versions, documents,
                    audit_events, organizations, users, employees
                RESTART IDENTITY CASCADE
                """
            )
        )
    try:
        with Session(engine, expire_on_commit=False) as db:
            employee = Employee(full_name="Link Removal Actor")
            db.add(employee)
            db.flush()
            user = User(
                employee_id=employee.id,
                username=f"link-removal-{uuid.uuid4()}",
                password_hash="unused",
                is_active=True,
                is_superuser=True,
            )
            organization_a = Organization(
                organization_type=OrganizationType.LEGAL_ENTITY,
                legal_name="Removal A LLC",
            )
            organization_b = Organization(
                organization_type=OrganizationType.LEGAL_ENTITY,
                legal_name="Removal B LLC",
            )
            db.add_all([user, organization_a, organization_b])
            db.commit()
            authorization = AuthorizationContext(
                user_id=user.id,
                employee_id=employee.id,
                permission_code="documents.edit",
                is_superuser=True,
                has_all_scope=True,
                related_organization_ids=frozenset(),
                active_scope_types=frozenset({ScopeType.ALL}),
            )
            service = DocumentService(storage=LocalFileStorage(tmp_path))
            document = service.create_document(
                db,
                actor_user_id=user.id,
                target=DocumentTarget(organization_id=organization_a.id),
                document_type="other",
                title="removal",
                original_filename="removal.pdf",
                content_type="application/pdf",
                source=io.BytesIO(b"%PDF-removal"),
            )
            removable = service.add_link(
                db,
                actor_user_id=user.id,
                authorization=authorization,
                document=document,
                target=DocumentTarget(organization_id=organization_b.id),
            )

            service.remove_link(
                db,
                actor_user_id=user.id,
                authorization=authorization,
                document=document,
                link_id=removable.id,
            )

            assert db.get(DocumentLink, removable.id) is None
            remaining = list(
                db.scalars(
                    select(DocumentLink).where(DocumentLink.document_id == document.id)
                ).all()
            )
            assert len(remaining) == 1
            assert remaining[0].organization_id == organization_a.id
            actions = set(
                db.scalars(
                    select(AuditEvent.action).where(AuditEvent.entity_id == document.id)
                ).all()
            )
            assert "document.link_added" in actions
            assert "document.link_removed" in actions
    finally:
        engine.dispose()
