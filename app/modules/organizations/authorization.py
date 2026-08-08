import uuid
from dataclasses import dataclass

from app.modules.identity.models import ScopeType


@dataclass(frozen=True)
class OrganizationAuthorizationDecision:
    allowed: bool
    matched_scope: ScopeType | None = None


def evaluate_organization_scope(
    scopes: set[ScopeType],
    *,
    user_id: uuid.UUID,
    owner_user_id: uuid.UUID | None = None,
    assigned_organization_ids: set[uuid.UUID] | None = None,
    organization_id: uuid.UUID | None = None,
) -> OrganizationAuthorizationDecision:
    if ScopeType.ALL in scopes:
        return OrganizationAuthorizationDecision(True, ScopeType.ALL)
    if ScopeType.OWN in scopes and owner_user_id == user_id:
        return OrganizationAuthorizationDecision(True, ScopeType.OWN)
    if (
        ScopeType.ASSIGNED in scopes
        and organization_id is not None
        and organization_id in (assigned_organization_ids or set())
    ):
        return OrganizationAuthorizationDecision(True, ScopeType.ASSIGNED)
    return OrganizationAuthorizationDecision(False)


def can_manage_organization(*, is_superuser: bool, scopes: set[ScopeType]) -> bool:
    return is_superuser or bool(scopes)
