import io
import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.contracts.models import Contract, ExpertiseType
from app.modules.documents.access import DocumentAccessService, DocumentTargetNotFoundError
from app.modules.documents.models import DocumentLink
from app.modules.documents.service import DocumentLinkConflictError, DocumentService
from app.modules.documents.targets import DocumentTarget
from app.modules.expertises.models import Expertise
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.models import Employee, ScopeType, User
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.modules.tasks.models import Task
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.models import TechnicalDevice
from app.storage.local import LocalFileStorage


def _reset_database(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    document_links, document_versions, documents,
                    audit_events, expertise_status_history, expertise_contract_items,
                    expertise_subjects, expertises, contracts,
                    task_assignees, task_organizations, task_contracts,
                    task_contract_items, task_technical_devices, task_buildings,
                    task_opos, tasks, opo, technical_devices, buildings,
                    organizations, users, employees
                RESTART IDENTITY CASCADE
                """
            )
        )


def _seed_actor(db: Session) -> tuple[Employee, User]:
    employee = Employee(full_name="Document Link Actor")
    db.add(employee)
    db.flush()
    user = User(
        employee_id=employee.id,
        username=f"document-links-{uuid.uuid4()}",
        password_hash="unused",
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.flush()
    return employee, user


def _organization(db: Session, name: str, *, deleted: bool = False) -> Organization:
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name=name,
    )
    db.add(organization)
    db.flush()
    if deleted:
        db.execute(
            text("UPDATE organizations SET deleted_at = now() WHERE id = :id"),
            {"id": organization.id},
        )
        db.expire(organization)
    return organization


def _all_scope(user: User, employee: Employee) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user.id,
        employee_id=employee.id,
        permission_code="documents.edit",
        is_superuser=True,
        has_all_scope=True,
        related_organization_ids=frozenset(),
        active_scope_types=frozenset({ScopeType.ALL}),
    )


def _related_scope(
    user: User,
    employee: Employee,
    organization_id: uuid.UUID,
) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user.id,
        employee_id=employee.id,
        permission_code="documents.view",
        is_superuser=False,
        has_all_scope=False,
        related_organization_ids=frozenset({organization_id}),
        active_scope_types=frozenset({ScopeType.RELATED}),
    )


def _create_document(
    db: Session,
    service: DocumentService,
    *,
    actor_user_id: uuid.UUID,
    organization_id: uuid.UUID,
    title: str,
):
    return service.create_document(
        db,
        actor_user_id=actor_user_id,
        target=DocumentTarget(organization_id=organization_id),
        document_type="other",
        title=title,
        original_filename=f"{title}.pdf",
        content_type="application/pdf",
        source=io.BytesIO(b"%PDF-link-test"),
    )


def test_duplicate_link_is_domain_conflict(tmp_path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            employee, user = _seed_actor(db)
            organization = _organization(db, "Duplicate Link LLC")
            db.commit()
            authorization = _all_scope(user, employee)
            service = DocumentService(storage=LocalFileStorage(tmp_path))
            document = _create_document(
                db,
                service,
                actor_user_id=user.id,
                organization_id=organization.id,
                title="duplicate-link",
            )

            with pytest.raises(DocumentLinkConflictError):
                service.add_link(
                    db,
                    actor_user_id=user.id,
                    authorization=authorization,
                    document=document,
                    target=DocumentTarget(organization_id=organization.id),
                )
    finally:
        engine.dispose()


def test_document_access_uses_any_visible_link_without_leaking_hidden_links(tmp_path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            employee, user = _seed_actor(db)
            organization_a = _organization(db, "Visible A LLC")
            organization_b = _organization(db, "Hidden B LLC")
            db.commit()
            all_scope = _all_scope(user, employee)
            scoped = _related_scope(user, employee, organization_a.id)
            service = DocumentService(storage=LocalFileStorage(tmp_path))
            access = DocumentAccessService()

            shared = _create_document(
                db,
                service,
                actor_user_id=user.id,
                organization_id=organization_a.id,
                title="shared",
            )
            service.add_link(
                db,
                actor_user_id=user.id,
                authorization=all_scope,
                document=shared,
                target=DocumentTarget(organization_id=organization_b.id),
            )
            hidden_only = _create_document(
                db,
                service,
                actor_user_id=user.id,
                organization_id=organization_b.id,
                title="hidden-only",
            )

            assert access.can_access_document(
                db, authorization=scoped, document_id=shared.id
            ) is True
            assert access.can_access_document(
                db, authorization=scoped, document_id=hidden_only.id
            ) is False
            visible_links = access.list_accessible_links(
                db, authorization=scoped, document_id=shared.id
            )
            assert len(visible_links) == 1
            assert visible_links[0].organization_id == organization_a.id
            assert visible_links[0].organization_id != organization_b.id
    finally:
        engine.dispose()


def test_all_seven_typed_targets_persist_and_invalid_targets_fail_closed(tmp_path) -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    _reset_database(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            employee, user = _seed_actor(db)
            organization = _organization(db, "Target Owner LLC")
            deleted_organization = _organization(db, "Deleted Target LLC", deleted=True)
            opo = OPO(
                name="Target OPO",
                registration_number=f"TGT-{uuid.uuid4()}",
                hazard_class=HazardClass.HAZARD_CLASS_3,
                address="Target address",
                registration_date=date(2026, 1, 1),
                owner_organization_id=organization.id,
                operating_organization_id=organization.id,
            )
            device = TechnicalDevice(
                name="Target Device",
                device_type=TechnicalDeviceType.OTHER,
                organization_id=organization.id,
            )
            building = Building(
                name="Target Building",
                building_type=BuildingType.OTHER,
                organization_id=organization.id,
            )
            expertise_type = db.scalar(
                select(ExpertiseType).where(
                    ExpertiseType.code == "technical_device_epb",
                    ExpertiseType.is_active.is_(True),
                )
            )
            assert expertise_type is not None
            db.add_all([opo, device, building])
            db.flush()
            contract = Contract(
                customer_organization_id=organization.id,
                number=f"C-{uuid.uuid4()}",
                contract_date=date(2026, 1, 1),
                created_by=user.id,
            )
            db.add(contract)
            db.flush()
            expertise = Expertise(
                contract_id=contract.id,
                expertise_type_id=expertise_type.id,
                responsible_expert_id=employee.id,
                created_by=user.id,
            )
            task = Task(title="Target task", creator_employee_id=employee.id)
            db.add_all([expertise, task])
            db.commit()

            authorization = _all_scope(user, employee)
            service = DocumentService(storage=LocalFileStorage(tmp_path))
            document = _create_document(
                db,
                service,
                actor_user_id=user.id,
                organization_id=organization.id,
                title="all-targets",
            )

            for target in (
                DocumentTarget(opo_id=opo.id),
                DocumentTarget(technical_device_id=device.id),
                DocumentTarget(building_id=building.id),
                DocumentTarget(contract_id=contract.id),
                DocumentTarget(expertise_id=expertise.id),
                DocumentTarget(task_id=task.id),
            ):
                service.add_link(
                    db,
                    actor_user_id=user.id,
                    authorization=authorization,
                    document=document,
                    target=target,
                )

            links = list(
                db.scalars(
                    select(DocumentLink)
                    .where(DocumentLink.document_id == document.id)
                    .order_by(DocumentLink.created_at.asc())
                ).all()
            )
            assert len(links) == 7
            assert any(link.organization_id == organization.id for link in links)
            assert any(link.opo_id == opo.id for link in links)
            assert any(link.technical_device_id == device.id for link in links)
            assert any(link.building_id == building.id for link in links)
            assert any(link.contract_id == contract.id for link in links)
            assert any(link.expertise_id == expertise.id for link in links)
            assert any(link.task_id == task.id for link in links)

            with pytest.raises(DocumentTargetNotFoundError):
                service.add_link(
                    db,
                    actor_user_id=user.id,
                    authorization=authorization,
                    document=document,
                    target=DocumentTarget(organization_id=deleted_organization.id),
                )
            with pytest.raises(DocumentTargetNotFoundError):
                service.add_link(
                    db,
                    actor_user_id=user.id,
                    authorization=authorization,
                    document=document,
                    target=DocumentTarget(organization_id=uuid.uuid4()),
                )
    finally:
        engine.dispose()
