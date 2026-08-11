import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.identity.models import (
    Employee,
    Permission,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.technical_devices.models import TechnicalDevice

pytestmark = pytest.mark.integration


def _transient_user(*, is_superuser: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        username=f"user-{uuid.uuid4()}",
        password_hash="not-used",
        is_active=True,
        is_superuser=is_superuser,
    )


def _create_user(
    db: Session,
    *,
    username: str,
    is_superuser: bool = False,
) -> User:
    employee = Employee(full_name=f"{username} Employee")
    db.add(employee)
    db.flush()

    user = User(
        employee_id=employee.id,
        username=username,
        password_hash="not-used",
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.flush()
    return user


def _get_permission(db: Session, code: str) -> Permission:
    permission = db.scalar(select(Permission).where(Permission.code == code))
    assert permission is not None, f"seeded permission {code!r} must exist"
    return permission


def _grant_scope(
    db: Session,
    *,
    user: User,
    permission_code: str,
    role_code: str,
    scope_type: ScopeType,
    scope_config: dict | None,
    revoked: bool = False,
    grant_permission: bool = True,
) -> UserRoleAssignment:
    role = Role(
        code=role_code,
        name=role_code,
        is_system=False,
    )
    db.add(role)
    db.flush()

    if grant_permission:
        permission = _get_permission(db, permission_code)
        db.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission.id,
            )
        )

    assignment = UserRoleAssignment(
        user_id=user.id,
        role_id=role.id,
        scope_type=scope_type,
        scope_config=scope_config,
        assigned_by=user.id,
        revoked_at=datetime.now(UTC) if revoked else None,
    )
    db.add(assignment)
    db.flush()
    return assignment


# ---------------------------------------------------------------------------
# AuthorizationContext
# ---------------------------------------------------------------------------


def test_related_grants_union_organization_ids() -> None:
    from app.modules.identity.authorization import build_authorization_context

    user = _transient_user()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    org_c = uuid.uuid4()

    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (
                ScopeType.RELATED,
                {"organization_ids": [str(org_a), str(org_b)]},
            ),
            (
                ScopeType.RELATED,
                {"organization_ids": [str(org_b), str(org_c)]},
            ),
        ],
    )

    assert ctx.user_id == user.id
    assert ctx.employee_id == user.employee_id
    assert ctx.permission_code == "opo.view"
    assert ctx.is_superuser is False
    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset(
        {org_a, org_b, org_c}
    )
    assert ctx.active_scope_types == frozenset({ScopeType.RELATED})


def test_all_scope_overrides_related() -> None:
    from app.modules.identity.authorization import build_authorization_context

    user = _transient_user()
    org_id = uuid.uuid4()

    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (
                ScopeType.RELATED,
                {"organization_ids": [str(org_id)]},
            ),
            (ScopeType.ALL, None),
        ],
    )

    assert ctx.has_all_scope is True
    assert ctx.active_scope_types == frozenset(
        {ScopeType.ALL, ScopeType.RELATED}
    )


@pytest.mark.parametrize(
    "scope_config",
    [
        None,
        {},
        {"organization_ids": "not-a-list"},
        {"organization_ids": ["not-a-uuid"]},
        {
            "organization_ids": [
                "550e8400-e29b-41d4-a716-446655440000"
            ],
            "all": True,
        },
        {
            "organizations": [
                "550e8400-e29b-41d4-a716-446655440000"
            ]
        },
    ],
)
def test_malformed_related_assignment_fails_closed(
    scope_config: dict | None,
) -> None:
    from app.modules.identity.authorization import build_authorization_context

    user = _transient_user()

    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (
                ScopeType.RELATED,
                scope_config,
            )
        ],
    )

    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset()
    assert ctx.active_scope_types == frozenset({ScopeType.RELATED})


def test_empty_related_list_grants_zero_organizations() -> None:
    from app.modules.identity.authorization import build_authorization_context

    user = _transient_user()

    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (
                ScopeType.RELATED,
                {"organization_ids": []},
            )
        ],
    )

    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset()


def test_assigned_and_own_do_not_grant_stage3_object_scope() -> None:
    from app.modules.identity.authorization import build_authorization_context

    user = _transient_user()

    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (ScopeType.ASSIGNED, None),
            (ScopeType.OWN, None),
        ],
    )

    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset()
    assert ctx.active_scope_types == frozenset(
        {ScopeType.ASSIGNED, ScopeType.OWN}
    )


def test_superuser_context_is_unrestricted() -> None:
    from app.modules.identity.authorization import build_authorization_context

    user = _transient_user(is_superuser=True)

    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[],
    )

    assert ctx.is_superuser is True
    assert ctx.has_all_scope is True
    assert ctx.active_scope_types == frozenset({ScopeType.ALL})


# ---------------------------------------------------------------------------
# Repository grants
# ---------------------------------------------------------------------------


def test_active_permission_scope_grants_exclude_revoked_and_wrong_roles(
    db_session: Session,
) -> None:
    from app.modules.identity.repository import (
        get_active_permission_scope_grants,
    )

    user = _create_user(
        db_session,
        username="scope-query-user",
    )

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    org_revoked = uuid.uuid4()
    org_wrong_role = uuid.uuid4()

    _grant_scope(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="scope-related-a",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org_a)]},
    )
    _grant_scope(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="scope-related-b",
        scope_type=ScopeType.RELATED,
        scope_config={"organization_ids": [str(org_b)]},
    )
    _grant_scope(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="scope-revoked",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org_revoked)]
        },
        revoked=True,
    )
    _grant_scope(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="scope-wrong-role",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org_wrong_role)]
        },
        grant_permission=False,
    )

    grants = get_active_permission_scope_grants(
        db_session,
        user_id=user.id,
        permission_code="opo.view",
    )

    normalized = {
        (
            scope_type,
            tuple(
                scope_config["organization_ids"]
                if scope_config is not None
                else []
            ),
        )
        for scope_type, scope_config in grants
    }

    assert normalized == {
        (
            ScopeType.RELATED,
            (str(org_a),),
        ),
        (
            ScopeType.RELATED,
            (str(org_b),),
        ),
    }


# ---------------------------------------------------------------------------
# Scoped dependency
# ---------------------------------------------------------------------------


def test_scoped_dependency_missing_permission_returns_403(
    db_session: Session,
) -> None:
    from app.modules.identity.dependencies import require_scoped_permission

    user = _create_user(
        db_session,
        username="no-permission-user",
    )

    dependency = require_scoped_permission("opo.view")

    with pytest.raises(HTTPException) as exc_info:
        dependency(
            user=user,
            db=db_session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Permission denied"


def test_scoped_dependency_related_returns_context(
    db_session: Session,
) -> None:
    from app.modules.identity.dependencies import require_scoped_permission

    user = _create_user(
        db_session,
        username="related-user",
    )
    org_id = uuid.uuid4()

    _grant_scope(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="related-opo-view",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": [str(org_id)]
        },
    )

    dependency = require_scoped_permission("opo.view")
    ctx = dependency(
        user=user,
        db=db_session,
    )

    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset({org_id})
    assert ctx.active_scope_types == frozenset({ScopeType.RELATED})


def test_scoped_dependency_malformed_related_returns_empty_scope(
    db_session: Session,
) -> None:
    from app.modules.identity.dependencies import require_scoped_permission

    user = _create_user(
        db_session,
        username="malformed-related-user",
    )

    _grant_scope(
        db_session,
        user=user,
        permission_code="opo.view",
        role_code="malformed-related-role",
        scope_type=ScopeType.RELATED,
        scope_config={
            "organization_ids": ["not-a-uuid"]
        },
    )

    dependency = require_scoped_permission("opo.view")
    ctx = dependency(
        user=user,
        db=db_session,
    )

    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset()
    assert ctx.active_scope_types == frozenset({ScopeType.RELATED})


def test_scoped_dependency_superuser_is_unrestricted_without_roles(
    db_session: Session,
) -> None:
    from app.modules.identity.dependencies import require_scoped_permission

    user = _create_user(
        db_session,
        username="scope-superuser",
        is_superuser=True,
    )

    dependency = require_scoped_permission("opo.view")
    ctx = dependency(
        user=user,
        db=db_session,
    )

    assert ctx.is_superuser is True
    assert ctx.has_all_scope is True
    assert ctx.active_scope_types == frozenset({ScopeType.ALL})


# ---------------------------------------------------------------------------
# Object policies
# ---------------------------------------------------------------------------


def _related_context(
    allowed_organization_ids: set[uuid.UUID],
):
    from app.modules.identity.authorization import build_authorization_context

    user = _transient_user()
    return build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (
                ScopeType.RELATED,
                {
                    "organization_ids": [
                        str(item)
                        for item in allowed_organization_ids
                    ]
                },
            )
        ],
    )


def test_organization_policy_related_allowed_and_foreign_denied() -> None:
    from app.modules.identity.authorization import can_access_organization

    allowed_id = uuid.uuid4()
    foreign_id = uuid.uuid4()

    ctx = _related_context({allowed_id})

    assert can_access_organization(
        ctx,
        Organization(id=allowed_id),
    )
    assert not can_access_organization(
        ctx,
        Organization(id=foreign_id),
    )


def test_opo_policy_accepts_allowed_owner_or_operator() -> None:
    from app.modules.identity.authorization import can_access_opo

    allowed_id = uuid.uuid4()
    foreign_a = uuid.uuid4()
    foreign_b = uuid.uuid4()

    ctx = _related_context({allowed_id})

    owner_allowed = OPO(
        id=uuid.uuid4(),
        owner_organization_id=allowed_id,
        operating_organization_id=foreign_a,
    )
    operator_allowed = OPO(
        id=uuid.uuid4(),
        owner_organization_id=foreign_a,
        operating_organization_id=allowed_id,
    )
    fully_foreign = OPO(
        id=uuid.uuid4(),
        owner_organization_id=foreign_a,
        operating_organization_id=foreign_b,
    )

    assert can_access_opo(ctx, owner_allowed)
    assert can_access_opo(ctx, operator_allowed)
    assert not can_access_opo(ctx, fully_foreign)


def test_technical_device_policy_uses_own_organization_only() -> None:
    from app.modules.identity.authorization import (
        can_access_technical_device,
    )

    allowed_id = uuid.uuid4()
    foreign_id = uuid.uuid4()

    ctx = _related_context({allowed_id})

    allowed = TechnicalDevice(
        id=uuid.uuid4(),
        organization_id=allowed_id,
    )
    foreign = TechnicalDevice(
        id=uuid.uuid4(),
        organization_id=foreign_id,
    )
    legacy_null = TechnicalDevice(
        id=uuid.uuid4(),
        organization_id=None,
    )

    assert can_access_technical_device(ctx, allowed)
    assert not can_access_technical_device(ctx, foreign)
    assert not can_access_technical_device(ctx, legacy_null)


def test_building_policy_uses_own_organization_only() -> None:
    from app.modules.identity.authorization import can_access_building

    allowed_id = uuid.uuid4()
    foreign_id = uuid.uuid4()

    ctx = _related_context({allowed_id})

    allowed = Building(
        id=uuid.uuid4(),
        organization_id=allowed_id,
    )
    foreign = Building(
        id=uuid.uuid4(),
        organization_id=foreign_id,
    )
    legacy_null = Building(
        id=uuid.uuid4(),
        organization_id=None,
    )

    assert can_access_building(ctx, allowed)
    assert not can_access_building(ctx, foreign)
    assert not can_access_building(ctx, legacy_null)


def test_all_scope_allows_legacy_null_entities() -> None:
    from app.modules.identity.authorization import (
        build_authorization_context,
        can_access_building,
        can_access_technical_device,
    )

    ctx = build_authorization_context(
        user=_transient_user(is_superuser=True),
        permission_code="technical_devices.view",
        grants=[],
    )

    assert can_access_technical_device(
        ctx,
        TechnicalDevice(
            id=uuid.uuid4(),
            organization_id=None,
        ),
    )
    assert can_access_building(
        ctx,
        Building(
            id=uuid.uuid4(),
            organization_id=None,
        ),
    )


def test_create_organization_requires_all_scope() -> None:
    from app.modules.identity.authorization import (
        build_authorization_context,
        can_create_organization,
    )

    related_org = uuid.uuid4()
    related_ctx = _related_context({related_org})

    all_ctx = build_authorization_context(
        user=_transient_user(is_superuser=True),
        permission_code="organizations.create",
        grants=[],
    )

    assert can_create_organization(all_ctx)
    assert not can_create_organization(related_ctx)


def test_reference_organizations_requires_every_id_in_related_scope() -> None:
    from app.modules.identity.authorization import (
        can_reference_organizations,
    )

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    foreign = uuid.uuid4()

    ctx = _related_context({org_a, org_b})

    assert can_reference_organizations(
        ctx,
        org_a,
        org_b,
    )
    assert not can_reference_organizations(
        ctx,
        org_a,
        foreign,
    )