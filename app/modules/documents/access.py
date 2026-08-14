import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts import repository as contracts_repository
from app.modules.documents import repository
from app.modules.documents.models import DocumentLink
from app.modules.documents.targets import DocumentTarget
from app.modules.expertises import repository as expertises_repository
from app.modules.identity.authorization import (
    AuthorizationContext,
    can_access_building,
    can_access_opo,
    can_access_organization,
    can_access_task,
    can_access_technical_device,
)
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.tasks import repository as tasks_repository
from app.modules.technical_devices.models import TechnicalDevice


class DocumentTargetNotFoundError(RuntimeError):
    pass


def target_from_link(link: DocumentLink) -> DocumentTarget:
    return DocumentTarget(
        organization_id=link.organization_id,
        opo_id=link.opo_id,
        technical_device_id=link.technical_device_id,
        building_id=link.building_id,
        contract_id=link.contract_id,
        expertise_id=link.expertise_id,
        task_id=link.task_id,
    )


class DocumentAccessService:
    def can_access_target(
        self,
        db: Session,
        *,
        authorization: AuthorizationContext,
        target: DocumentTarget,
    ) -> bool:
        target_name, target_id = target.non_null_items()[0]

        if target_name == "organization_id":
            entity = db.scalar(
                select(Organization).where(
                    Organization.id == target_id,
                    Organization.deleted_at.is_(None),
                )
            )
            return entity is not None and can_access_organization(authorization, entity)

        if target_name == "opo_id":
            entity = db.scalar(
                select(OPO).where(OPO.id == target_id, OPO.deleted_at.is_(None))
            )
            return entity is not None and can_access_opo(authorization, entity)

        if target_name == "technical_device_id":
            entity = db.scalar(
                select(TechnicalDevice).where(
                    TechnicalDevice.id == target_id,
                    TechnicalDevice.deleted_at.is_(None),
                )
            )
            return entity is not None and can_access_technical_device(
                authorization, entity
            )

        if target_name == "building_id":
            entity = db.scalar(
                select(Building).where(
                    Building.id == target_id,
                    Building.deleted_at.is_(None),
                )
            )
            return entity is not None and can_access_building(authorization, entity)

        if target_name == "contract_id":
            return (
                contracts_repository.get_contract(
                    db,
                    target_id,
                    authorization=authorization,
                )
                is not None
            )

        if target_name == "expertise_id":
            return (
                expertises_repository.get_expertise(
                    db,
                    target_id,
                    authorization=authorization,
                )
                is not None
            )

        if target_name == "task_id":
            task = tasks_repository.get_task(db, target_id)
            if task is None:
                return False
            if authorization.has_all_scope:
                return True
            return can_access_task(
                authorization,
                task,
                assignee_employee_ids=tasks_repository.get_task_assignee_ids(
                    db, task.id
                ),
                related_organization_ids=tasks_repository.get_task_related_organization_ids(
                    db, task.id
                ),
            )

        return False

    def require_accessible_target(
        self,
        db: Session,
        *,
        authorization: AuthorizationContext,
        target: DocumentTarget,
    ) -> None:
        if not self.can_access_target(
            db,
            authorization=authorization,
            target=target,
        ):
            raise DocumentTargetNotFoundError("document target not found")

    def list_accessible_links(
        self,
        db: Session,
        *,
        authorization: AuthorizationContext,
        document_id: uuid.UUID,
    ) -> list[DocumentLink]:
        if repository.get_document(db, document_id) is None:
            return []
        return [
            link
            for link in repository.list_document_links(db, document_id)
            if self.can_access_target(
                db,
                authorization=authorization,
                target=target_from_link(link),
            )
        ]

    def can_access_document(
        self,
        db: Session,
        *,
        authorization: AuthorizationContext,
        document_id: uuid.UUID,
    ) -> bool:
        return bool(
            self.list_accessible_links(
                db,
                authorization=authorization,
                document_id=document_id,
            )
        )
