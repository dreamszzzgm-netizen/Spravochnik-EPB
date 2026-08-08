import uuid
from dataclasses import dataclass

from app.modules.identity.models import ScopeType


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    matched_scope: ScopeType | None = None


def evaluate_scopes(
    scopes: set[ScopeType],
    *,
    user_id: uuid.UUID,
    owner_user_id: uuid.UUID | None = None,
    assigned_user_ids: set[uuid.UUID] | None = None,
    related_user_ids: set[uuid.UUID] | None = None,
) -> AuthorizationDecision:
    if ScopeType.ALL in scopes:
        return AuthorizationDecision(True, ScopeType.ALL)
    if ScopeType.OWN in scopes and owner_user_id == user_id:
        return AuthorizationDecision(True, ScopeType.OWN)
    if ScopeType.ASSIGNED in scopes and user_id in (assigned_user_ids or set()):
        return AuthorizationDecision(True, ScopeType.ASSIGNED)
    if ScopeType.RELATED in scopes and user_id in (related_user_ids or set()):
        return AuthorizationDecision(True, ScopeType.RELATED)
    return AuthorizationDecision(False)


def has_permission(*, is_superuser: bool, scopes: set[ScopeType]) -> bool:
    return is_superuser or bool(scopes)
