# Stage 3 CP2.2-A Authorization Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the scoped authorization core for Stage 3 without changing Stage 3 domain routes or list repositories yet.

**Architecture:** Keep authentication and HTTP permission-presence checks in `identity/dependencies.py`, add one repository query for active scope grants, and add a pure `identity/authorization.py` policy module. `AuthorizationContext` is immutable; `ALL` grants unrestricted access, `RELATED` unions strict `scope_config.organization_ids`, and `ASSIGNED`/`OWN` grant no Stage 3 object access yet.

**Tech Stack:** Python 3, FastAPI dependencies, SQLAlchemy 2.x ORM/select, PostgreSQL JSONB-backed `scope_config`, pytest.

## Global Constraints

- Starting branch: `codex/feat-gigastudio-frontend-integration`.
- Starting HEAD for this plan: `c13b532` or a direct fast-forward descendant containing only approved planning docs.
- Security semantics: unauthenticated -> 401; missing permission -> 403; object outside scope -> 404 at route/policy integration checkpoints.
- `RELATED` uses exactly `scope_config.organization_ids`.
- Malformed `scope_config` fails closed and must not raise HTTP 500.
- `ASSIGNED` and `OWN` do not gain invented Stage 3 semantics.
- Multiple grants are additive; any `ALL` grant wins.
- Superuser is unrestricted.
- No Stage 3 route/repository behavior changes in CP2.2-A.
- No frontend work.
- TDD: write failing tests and observe RED before production changes.

---

## File Structure

- Create `app/modules/identity/authorization.py` — immutable authorization context, strict RELATED scope parser, context builder, pure Stage 3 object policies.
- Modify `app/modules/identity/repository.py` — one query returning active scope grants for a specific user and permission.
- Modify `app/modules/identity/dependencies.py` — new `require_scoped_permission(permission_code)` dependency returning `AuthorizationContext`.
- Create `tests/integration/test_stage3_cp22a_authorization_core.py` — repository/dependency/context regression coverage against the real test database.
- Create `tests/unit/test_stage3_cp22a_authorization_policy.py` only if the repository already has a `tests/unit` tree; otherwise keep pure-policy tests in the integration test file without requiring DB fixtures.

---

### Task 1: AuthorizationContext and strict scope parser

**Files:**
- Create: `app/modules/identity/authorization.py`
- Test: `tests/integration/test_stage3_cp22a_authorization_core.py`

**Interfaces:**
- Produces: `AuthorizationContext`.
- Produces: `build_authorization_context(*, user: User, permission_code: str, grants: list[tuple[ScopeType, dict[str, Any] | None]]) -> AuthorizationContext`.
- Produces pure policies: `can_access_organization`, `can_access_opo`, `can_access_technical_device`, `can_access_building`, `can_create_organization`, `can_reference_organizations`.

- [ ] **Step 1: Write RED tests for context composition**

Add tests covering these exact behaviors:

```python
import uuid

from app.modules.identity.authorization import build_authorization_context
from app.modules.identity.models import ScopeType, User


def test_related_grants_union_organization_ids(make_user):
    user = make_user(is_superuser=False)
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    org_c = uuid.uuid4()

    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (ScopeType.RELATED, {"organization_ids": [str(org_a), str(org_b)]}),
            (ScopeType.RELATED, {"organization_ids": [str(org_b), str(org_c)]}),
        ],
    )

    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset({org_a, org_b, org_c})
    assert ctx.active_scope_types == frozenset({ScopeType.RELATED})


def test_all_scope_overrides_related(make_user):
    user = make_user(is_superuser=False)
    org_id = uuid.uuid4()
    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[
            (ScopeType.RELATED, {"organization_ids": [str(org_id)]}),
            (ScopeType.ALL, None),
        ],
    )
    assert ctx.has_all_scope is True


def test_malformed_related_assignment_fails_closed(make_user):
    user = make_user(is_superuser=False)
    valid_org = uuid.uuid4()

    malformed_configs = [
        None,
        {},
        {"organization_ids": "not-a-list"},
        {"organization_ids": ["not-a-uuid"]},
        {"organization_ids": [str(valid_org)], "all": True},
        {"organizations": [str(valid_org)]},
    ]

    for scope_config in malformed_configs:
        ctx = build_authorization_context(
            user=user,
            permission_code="opo.view",
            grants=[(ScopeType.RELATED, scope_config)],
        )
        assert ctx.has_all_scope is False
        assert ctx.related_organization_ids == frozenset()


def test_assigned_and_own_do_not_grant_stage3_object_scope(make_user):
    user = make_user(is_superuser=False)
    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[(ScopeType.ASSIGNED, None), (ScopeType.OWN, None)],
    )
    assert ctx.has_all_scope is False
    assert ctx.related_organization_ids == frozenset()
    assert ctx.active_scope_types == frozenset({ScopeType.ASSIGNED, ScopeType.OWN})


def test_superuser_context_is_unrestricted(make_user):
    user = make_user(is_superuser=True)
    ctx = build_authorization_context(
        user=user,
        permission_code="opo.view",
        grants=[],
    )
    assert ctx.has_all_scope is True
```

If no `make_user` fixture exists, create a small local helper constructing a non-persisted `User` with UUID `id`, UUID `employee_id`, `username`, `password_hash`, and requested `is_superuser` value. Do not add a global fixture solely for these pure tests.

- [ ] **Step 2: Run RED**

Run:

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

Expected: collection/import failure because `app.modules.identity.authorization` does not exist yet.

- [ ] **Step 3: Implement `authorization.py` exactly around these contracts**

Create:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.modules.buildings.models import Building
from app.modules.identity.models import ScopeType, User
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.technical_devices.models import TechnicalDevice


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    user_id: uuid.UUID
    employee_id: uuid.UUID
    permission_code: str
    is_superuser: bool
    has_all_scope: bool
    related_organization_ids: frozenset[uuid.UUID]
    active_scope_types: frozenset[ScopeType]


def _parse_related_organization_ids(scope_config: dict[str, Any] | None) -> frozenset[uuid.UUID]:
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
    grants: list[tuple[ScopeType, dict[str, Any] | None]],
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

    active_scope_types = frozenset(scope_type for scope_type, _ in grants)
    has_all_scope = ScopeType.ALL in active_scope_types

    related_ids: set[uuid.UUID] = set()
    if not has_all_scope:
        for scope_type, scope_config in grants:
            if scope_type is ScopeType.RELATED:
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


def can_access_organization(ctx: AuthorizationContext, organization: Organization) -> bool:
    return ctx.has_all_scope or organization.id in ctx.related_organization_ids


def can_access_opo(ctx: AuthorizationContext, opo: OPO) -> bool:
    return ctx.has_all_scope or (
        opo.owner_organization_id in ctx.related_organization_ids
        or opo.operating_organization_id in ctx.related_organization_ids
    )


def can_access_technical_device(
    ctx: AuthorizationContext, device: TechnicalDevice
) -> bool:
    return ctx.has_all_scope or (
        device.organization_id is not None
        and device.organization_id in ctx.related_organization_ids
    )


def can_access_building(ctx: AuthorizationContext, building: Building) -> bool:
    return ctx.has_all_scope or (
        building.organization_id is not None
        and building.organization_id in ctx.related_organization_ids
    )


def can_create_organization(ctx: AuthorizationContext) -> bool:
    return ctx.has_all_scope


def can_reference_organizations(
    ctx: AuthorizationContext, *organization_ids: uuid.UUID
) -> bool:
    return ctx.has_all_scope or all(
        organization_id in ctx.related_organization_ids
        for organization_id in organization_ids
    )
```

Do not add FastAPI imports or raise `HTTPException` in this module.

- [ ] **Step 4: Run context tests GREEN**

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

Expected: context tests pass; repository/dependency tests added later may still be absent.

---

### Task 2: Repository query for active permission grants

**Files:**
- Modify: `app/modules/identity/repository.py`
- Test: `tests/integration/test_stage3_cp22a_authorization_core.py`

**Interfaces:**
- Produces: `get_active_permission_scope_grants(db: Session, user_id: uuid.UUID, permission_code: str) -> list[tuple[ScopeType, dict[str, Any] | None]]`.
- Consumed by: `require_scoped_permission()` in Task 3.

- [ ] **Step 1: Write RED repository test**

Create two roles granting the same permission, assign them to one user with different RELATED configs, add a revoked assignment for a third organization, then assert only active grants are returned. Also create an assignment to a role that lacks the requested permission and assert it is excluded.

The final assertion must compare normalized values, for example:

```python
grants = get_active_permission_scope_grants(
    db_session,
    user_id=user.id,
    permission_code="opo.view",
)

assert {(scope_type, tuple(config["organization_ids"])) for scope_type, config in grants} == {
    (ScopeType.RELATED, (str(org_a.id),)),
    (ScopeType.RELATED, (str(org_b.id),)),
}
```

Use the existing identity models `Role`, `Permission`, `RolePermission`, and `UserRoleAssignment`; do not mock SQLAlchemy.

- [ ] **Step 2: Run RED**

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

Expected: FAIL because `get_active_permission_scope_grants` is not defined.

- [ ] **Step 3: Implement repository function**

Add `Any` and `ScopeType` imports as needed, then add:

```python
def get_active_permission_scope_grants(
    db: Session,
    user_id: uuid.UUID,
    permission_code: str,
) -> list[tuple[ScopeType, dict[str, Any] | None]]:
    stmt = (
        select(UserRoleAssignment.scope_type, UserRoleAssignment.scope_config)
        .join(RolePermission, RolePermission.role_id == UserRoleAssignment.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.revoked_at.is_(None),
            Permission.code == permission_code,
        )
        .order_by(UserRoleAssignment.id.asc())
    )
    return [(scope_type, scope_config) for scope_type, scope_config in db.execute(stmt)]
```

Do not change the existing `permission_scopes()` or `get_user_permission_codes()` behavior in CP2.2-A.

- [ ] **Step 4: Run repository tests GREEN**

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

---

### Task 3: Scoped FastAPI dependency

**Files:**
- Modify: `app/modules/identity/dependencies.py`
- Test: `tests/integration/test_stage3_cp22a_authorization_core.py`

**Interfaces:**
- Produces: `require_scoped_permission(permission_code: str) -> Callable`.
- The returned dependency yields `AuthorizationContext`.
- Missing permission yields HTTP 403.
- Superuser yields unrestricted context without requiring role assignments.

- [ ] **Step 1: Write RED dependency tests**

Test the inner dependency directly through a tiny FastAPI test router or through dependency override patterns already used in the repository. Required behaviors:

```text
ordinary user + no active grant for permission -> 403
ordinary user + RELATED grant -> AuthorizationContext with parsed org UUID
ordinary user + malformed RELATED config -> context exists but allowed org set is empty
superuser + no role assignments -> unrestricted AuthorizationContext
```

Do not integrate Stage 3 domain routes yet.

- [ ] **Step 2: Run RED**

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

Expected: FAIL because `require_scoped_permission` is not defined.

- [ ] **Step 3: Implement dependency**

Modify imports in `dependencies.py` to include:

```python
from app.modules.identity.authorization import (
    AuthorizationContext,
    build_authorization_context,
)
from app.modules.identity.repository import (
    get_active_permission_scope_grants,
    permission_scopes,
)
```

Then add:

```python
def require_scoped_permission(permission_code: str) -> Callable:
    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AuthorizationContext:
        if user.is_superuser:
            return build_authorization_context(
                user=user,
                permission_code=permission_code,
                grants=[],
            )

        grants = get_active_permission_scope_grants(
            db,
            user_id=user.id,
            permission_code=permission_code,
        )
        if not grants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

        return build_authorization_context(
            user=user,
            permission_code=permission_code,
            grants=grants,
        )

    return dependency
```

Do not alter `require_permission()` semantics.

- [ ] **Step 4: Run dependency tests GREEN**

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

---

### Task 4: Pure object policy regression tests

**Files:**
- Test: `tests/integration/test_stage3_cp22a_authorization_core.py`

**Interfaces:**
- Verifies the pure policy functions created in Task 1.

- [ ] **Step 1: Add exact object-policy tests**

Cover:

```text
Organization RELATED allowed / foreign denied
OPO owner allowed / operator allowed / fully foreign denied
TechnicalDevice own organization allowed / foreign denied / NULL denied
Building own organization allowed / foreign denied / NULL denied
ALL context allows every object including legacy TD/Building with NULL organization_id
can_create_organization: ALL true, RELATED false
can_reference_organizations: RELATED requires every referenced organization to be allowed
```

Construct transient ORM models; no DB commit is required for these pure tests.

- [ ] **Step 2: Run GREEN**

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

Expected: all CP2.2-A tests pass.

---

### Task 5: Checkpoint verification and commit

**Files:** No new production behavior beyond Tasks 1-4.

- [ ] **Step 1: Run targeted tests**

```powershell
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

Expected: 0 failures, 0 errors.

- [ ] **Step 2: Run existing identity tests and Stage 3 regressions**

Run the identity/auth test files that exist in the repository plus:

```powershell
pytest tests/integration/test_stage3_cp211_migrations.py -q
pytest tests/integration/test_stage3_cp211_migration_regressions.py -q
pytest tests/integration/test_stage3_cp211_service_regressions.py -q
pytest tests/integration/test_stage3_cp21_http_api.py -q
```

Expected: 0 failures, 0 errors.

- [ ] **Step 3: Run full suite**

```powershell
pytest
```

Expected: 0 failures, 0 errors.

- [ ] **Step 4: Lint changed files**

```powershell
ruff check app/modules/identity/authorization.py app/modules/identity/repository.py app/modules/identity/dependencies.py tests/integration/test_stage3_cp22a_authorization_core.py
```

Expected: clean.

- [ ] **Step 5: Verify no unintended schema/migration change**

```powershell
alembic heads
git diff --check
git status
```

Expected: single `0010_stage3` Alembic head; no migration files changed by CP2.2-A.

- [ ] **Step 6: Review scope**

`git diff` must contain only:

```text
app/modules/identity/authorization.py
app/modules/identity/repository.py
app/modules/identity/dependencies.py
tests/integration/test_stage3_cp22a_authorization_core.py
```

plus this already-committed plan/spec history. No Organization/OPO/TD/Building routes or repositories are to be modified in CP2.2-A.

- [ ] **Step 7: Commit and push**

```powershell
git add app/modules/identity/authorization.py app/modules/identity/repository.py app/modules/identity/dependencies.py tests/integration/test_stage3_cp22a_authorization_core.py
git commit -m "feat(stage3 cp2.2-a): add scoped authorization core"
git push origin codex/feat-gigastudio-frontend-integration
```

No force push, rebase, or history rewrite.

## CP2.2-A Acceptance Gate

CP2.2-A is accepted only if all are true:

- `AuthorizationContext` is immutable.
- superuser is unrestricted.
- `ALL` wins over other active grants.
- multiple RELATED grants union organization ids.
- malformed RELATED config fails closed without exceptions escaping.
- `ASSIGNED`/`OWN` grant no Stage 3 object scope.
- active scope grant repository query ignores revoked assignments and roles without the requested permission.
- `require_scoped_permission()` returns context and preserves 403 for missing permission.
- pure Organization/OPO/TD/Building access policies match the design.
- no Stage 3 domain route/list behavior changed yet.
- targeted/full tests and changed-file Ruff verification are green.
- commit is pushed normally for independent audit.
