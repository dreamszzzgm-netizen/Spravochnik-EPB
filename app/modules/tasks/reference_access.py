from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.contracts import repository as contract_repository
from app.modules.contracts.models import ContractItem
from app.modules.expertises import repository as expertise_repository
from app.modules.identity.authorization import (
    AuthorizationContext,
    build_authorization_context,
    can_access_building,
    can_access_opo,
    can_access_organization,
    can_access_technical_device,
)
from app.modules.identity.models import User
from app.modules.identity.repository import get_active_permission_scope_grants
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.tasks.enums import TaskLinkKind
from app.modules.tasks.service import TaskLinkInput
from app.modules.technical_devices.models import TechnicalDevice


class TaskReferenceAccessError(LookupError):
    pass


_PERMISSION_BY_KIND = {
    TaskLinkKind.ORGANIZATION: "organizations.view",
    TaskLinkKind.CONTRACT: "contracts.view",
    TaskLinkKind.CONTRACT_ITEM: "contracts.view",
    TaskLinkKind.TECHNICAL_DEVICE: "technical_devices.view",
    TaskLinkKind.BUILDING: "buildings.view",
    TaskLinkKind.OPO: "opo.view",
    TaskLinkKind.EXPERTISE: "expertises.view",
}


def require_task_link_reference_access(
    db: Session,
    *,
    actor_authorization: AuthorizationContext,
    links: Iterable[TaskLinkInput],
) -> None:
    contexts: dict[str, AuthorizationContext | None] = {}

    for link in links:
        permission_code = _PERMISSION_BY_KIND[link.kind]
        if permission_code not in contexts:
            contexts[permission_code] = _build_view_context(
                db,
                actor_authorization=actor_authorization,
                permission_code=permission_code,
            )
        _require_link_access(db, link=link, context=contexts[permission_code])


def _build_view_context(
    db: Session,
    *,
    actor_authorization: AuthorizationContext,
    permission_code: str,
) -> AuthorizationContext | None:
    if actor_authorization.is_superuser:
        return None

    user = db.get(User, actor_authorization.user_id)
    if user is None or not user.is_active:
        raise TaskReferenceAccessError

    grants = get_active_permission_scope_grants(
        db,
        user_id=user.id,
        permission_code=permission_code,
    )
    if not grants:
        raise TaskReferenceAccessError

    return build_authorization_context(
        user=user,
        permission_code=permission_code,
        grants=grants,
    )


def _require_link_access(
    db: Session,
    *,
    link: TaskLinkInput,
    context: AuthorizationContext | None,
) -> None:
    if link.kind == TaskLinkKind.ORGANIZATION:
        organization = db.get(Organization, link.entity_id)
        if (
            organization is None
            or organization.deleted_at is not None
            or (context is not None and not can_access_organization(context, organization))
        ):
            raise TaskReferenceAccessError
        return

    if link.kind == TaskLinkKind.CONTRACT:
        contract = contract_repository.get_contract(
            db,
            link.entity_id,
            authorization=context,
        )
        if contract is None:
            raise TaskReferenceAccessError
        return

    if link.kind == TaskLinkKind.CONTRACT_ITEM:
        item = db.get(ContractItem, link.entity_id)
        if item is None or item.deleted_at is not None:
            raise TaskReferenceAccessError
        contract = contract_repository.get_contract(
            db,
            item.contract_id,
            authorization=context,
        )
        if contract is None:
            raise TaskReferenceAccessError
        return

    if link.kind == TaskLinkKind.TECHNICAL_DEVICE:
        device = db.get(TechnicalDevice, link.entity_id)
        if (
            device is None
            or device.deleted_at is not None
            or (context is not None and not can_access_technical_device(context, device))
        ):
            raise TaskReferenceAccessError
        return

    if link.kind == TaskLinkKind.BUILDING:
        building = db.get(Building, link.entity_id)
        if (
            building is None
            or building.deleted_at is not None
            or (context is not None and not can_access_building(context, building))
        ):
            raise TaskReferenceAccessError
        return

    if link.kind == TaskLinkKind.OPO:
        opo = db.get(OPO, link.entity_id)
        if (
            opo is None
            or opo.deleted_at is not None
            or (context is not None and not can_access_opo(context, opo))
        ):
            raise TaskReferenceAccessError
        return

    if link.kind == TaskLinkKind.EXPERTISE:
        expertise = expertise_repository.get_expertise(
            db,
            link.entity_id,
            authorization=context,
        )
        if expertise is None:
            raise TaskReferenceAccessError
        return

    raise TaskReferenceAccessError
