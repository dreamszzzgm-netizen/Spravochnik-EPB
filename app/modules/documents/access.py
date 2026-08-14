import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts import repository as contracts_repository
from app.modules.contracts.models import Contract, ContractItem
from app.modules.documents import repository
from app.modules.documents.models import DocumentLink
from app.modules.documents.targets import DocumentTarget
from app.modules.expertises import repository as expertises_repository
from app.modules.identity.authorization import (
    AuthorizationContext,
    can_access_building,
    can_access_organization,
    can_access_opo,
    can_access_task,
    can_access_technical_device,
)
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.tasks import repository as tasks_repository
from app.modules.tasks.models import (
    TaskBuilding,
    TaskContract,
    TaskContractItem,
    TaskOPO,
    TaskOrganization,
    TaskTechnicalDevice,
)
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
    def _task_related_organization_ids(
        self,
        db: Session,
        task_id: uuid.UUID,
    ) -> set[uuid.UUID]:
        related = set(
            db.scalars(
                sa.select(TaskOrganization.organization_id).where(
                    TaskOrganization.task_id == task_id
                )
            ).all()
        )
        related.update(
            db.scalars(
                sa.select(Contract.customer_organization_id)
                .join(TaskContract, TaskContract.contract_id == Contract.id)
                .where(TaskContract.task_id == task_id)
            ).all()
        )
        related.update(
            db.scalars(
                sa.select(Contract.customer_organization_id)
                .join(ContractItem, ContractItem.contract_id == Contract.id)
                .join(
                    TaskContractItem,
                    TaskContractItem.contract_item_id == ContractItem.id,
                )
                .where(TaskContractItem.task_id == task_id)
            ).all()
        )
        related.update(
            value
            for value in db.scalars(
                sa.select(TechnicalDevice.organization_id)
                .join(
                    TaskTechnicalDevice,
                    TaskTechnicalDevice.technical_device_id == TechnicalDevice.id,
                )
                .where(TaskTechnicalDevice.task_id == task_id)
            ).all()
            if value is not None
        )
        related.update(
            value
            for value in db.scalars(
                sa.select(Building.organization_id)
                .join(TaskBuilding, TaskBuilding.building_id == Building.id)
                .where(TaskBuilding.task_id == task_id)
            ).all()
            if value is not None
        )
        opo_rows = db.execute(
            sa.select(OPO.owner_organization_id, OPO.operating_organization_id)
            .join(TaskOPO, TaskOPO.opo_id == OPO.id)
            .where(TaskOPO.task_id == task_id)
        ).all()
        for owner_id, operating_id in opo_rows:
            related.add(owner_id)
            related.add(operating_id)
        return related

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
                sa.select(Organization).where(
                    Organization.id == target_id,
                    Organization.deleted_at.is_(None),
                )
            )
            return entity is not None and can_access_organization(authorization, entity)

        if target_name == "opo_id":
            entity = db.scalar(
                sa.select(OPO).where(OPO.id == target_id, OPO.deleted_at.is_(None))
            )
            return entity is not None and can_access_opo(authorization, entity)

        if target_name == "technical_device_id":
            entity = db.scalar(
                sa.select(TechnicalDevice).where(
                    TechnicalDevice.id == target_id,
                    TechnicalDevice.deleted_at.is_(None),
                )
            )
            return entity is not None and can_access_technical_device(
                authorization, entity
            )

        if target_name == "building_id":
            entity = db.scalar(
                sa.select(Building).where(
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
                related_organization_ids=self._task_related_organization_ids(
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
