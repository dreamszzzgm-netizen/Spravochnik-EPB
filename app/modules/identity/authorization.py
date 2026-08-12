from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.modules.identity.models import ScopeType, User


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
        return AuthorizationDecision(
            True,
            ScopeType.ALL,
        )

    if ScopeType.OWN in scopes and owner_user_id == user_id:
        return AuthorizationDecision(
            True,
            ScopeType.OWN,
        )

    if ScopeType.ASSIGNED in scopes and user_id in (assigned_user_ids or set()):
        return AuthorizationDecision(
            True,
            ScopeType.ASSIGNED,
        )

    if ScopeType.RELATED in scopes and user_id in (related_user_ids or set()):
        return AuthorizationDecision(
            True,
            ScopeType.RELATED,
        )

    return AuthorizationDecision(False)


def has_permission(
    *,
    is_superuser: bool,
    scopes: set[ScopeType],
) -> bool:
    return is_superuser or bool(scopes)


class OrganizationLike(Protocol):
    id: uuid.UUID


class OPOLike(Protocol):
    owner_organization_id: uuid.UUID
    operating_organization_id: uuid.UUID


class OrganizationOwnedEntityLike(Protocol):
    organization_id: uuid.UUID | None


class ContractLike(Protocol):
    customer_organization_id: uuid.UUID
    created_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    user_id: uuid.UUID
    employee_id: uuid.UUID
    permission_code: str
    is_superuser: bool
    has_all_scope: bool
    related_organization_ids: frozenset[uuid.UUID]
    active_scope_types: frozenset[ScopeType]


def _parse_related_organization_ids(
    scope_config: dict[str, Any] | None,
) -> frozenset[uuid.UUID]:
    if not isinstance(scope_config, dict):
        return frozenset()

    if set(scope_config) != {"organization_ids"}:
        return frozenset()

    raw_ids = scope_config.get("organization_ids")
    if not isinstance(raw_ids, list):
        return frozenset()

    parsed: set[uuid.UUID] = set()

    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            return frozenset()

        try:
            parsed.add(uuid.UUID(raw_id))
        except (ValueError, AttributeError, TypeError):
            return frozenset()

    return frozenset(parsed)


def build_authorization_context(
    *,
    user: User,
    permission_code: str,
    grants: list[
        tuple[
            ScopeType,
            dict[str, Any] | None,
        ]
    ],
) -> AuthorizationContext:
    if user.is_superuser:
        return AuthorizationContext(
            user_id=user.id,
            employee_id=user.employee_id,
            permission_code=permission_code,
            is_superuser=True,
            has_all_scope=True,
            related_organization_ids=frozenset(),
            active_scope_types=frozenset({ScopeType.ALL}),
        )

    active_scope_types = frozenset(scope_type for scope_type, _scope_config in grants)

    has_all_scope = ScopeType.ALL in active_scope_types

    related_ids: set[uuid.UUID] = set()

    if not has_all_scope:
        for scope_type, scope_config in grants:
            if scope_type == ScopeType.RELATED:
                related_ids.update(_parse_related_organization_ids(scope_config))

    return AuthorizationContext(
        user_id=user.id,
        employee_id=user.employee_id,
        permission_code=permission_code,
        is_superuser=False,
        has_all_scope=has_all_scope,
        related_organization_ids=frozenset(related_ids),
        active_scope_types=active_scope_types,
    )


def can_access_organization(
    ctx: AuthorizationContext,
    organization: OrganizationLike,
) -> bool:
    return ctx.has_all_scope or organization.id in ctx.related_organization_ids


def can_access_opo(
    ctx: AuthorizationContext,
    opo: OPOLike,
) -> bool:
    return (
        ctx.has_all_scope
        or opo.owner_organization_id in ctx.related_organization_ids
        or opo.operating_organization_id in ctx.related_organization_ids
    )


def can_access_technical_device(
    ctx: AuthorizationContext,
    device: OrganizationOwnedEntityLike,
) -> bool:
    return ctx.has_all_scope or (
        device.organization_id is not None
        and device.organization_id in ctx.related_organization_ids
    )


def can_access_building(
    ctx: AuthorizationContext,
    building: OrganizationOwnedEntityLike,
) -> bool:
    return ctx.has_all_scope or (
        building.organization_id is not None
        and building.organization_id in ctx.related_organization_ids
    )


def can_access_contract(
    ctx: AuthorizationContext,
    contract: ContractLike,
    *,
    responsible_employee_ids: set[uuid.UUID],
) -> bool:
    if ctx.has_all_scope:
        return True

    return (
        (
            ScopeType.RELATED in ctx.active_scope_types
            and contract.customer_organization_id in ctx.related_organization_ids
        )
        or (
            ScopeType.ASSIGNED in ctx.active_scope_types
            and ctx.employee_id in responsible_employee_ids
        )
        or (
            ScopeType.OWN in ctx.active_scope_types
            and contract.created_by == ctx.user_id
        )
    )


def can_create_organization(
    ctx: AuthorizationContext,
) -> bool:
    return ctx.has_all_scope


def can_reference_organizations(
    ctx: AuthorizationContext,
    *organization_ids: uuid.UUID,
) -> bool:
    if ctx.has_all_scope:
        return True

    return all(
        organization_id in ctx.related_organization_ids
        for organization_id in organization_ids
    )
