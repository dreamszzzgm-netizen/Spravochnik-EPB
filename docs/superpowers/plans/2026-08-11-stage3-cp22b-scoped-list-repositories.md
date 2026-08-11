# Stage 3 CP2.2-B — Scoped LIST Repositories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Follow TDD and verification-before-completion. Do not redesign the approved authorization model.

**Goal:** Make Organization, OPO, TechnicalDevice, and Building paginated repository queries optionally apply `AuthorizationContext` at SQL level before `COUNT`, `OFFSET`, and `LIMIT`, without changing Stage 3 HTTP behavior yet.

**Architecture:** Existing repository functions gain an optional `authorization: AuthorizationContext | None = None` parameter. `None` and `has_all_scope=True` preserve unrestricted legacy behavior. A non-ALL context filters by `related_organization_ids`; empty RELATED/ASSIGNED/OWN scope becomes SQL false. No route changes occur in CP2.2-B.

**Tech Stack:** Python 3, SQLAlchemy 2, PostgreSQL, pytest.

## Global Constraints

- Starting branch: `codex/feat-gigastudio-frontend-integration`.
- Expected implementation start HEAD is the commit containing this plan.
- Approved design: `docs/superpowers/specs/2026-08-11-stage3-cp22-authorization-design.md`.
- Security scope must be applied before count/pagination.
- Query filters may narrow but never replace security scope.
- `total` must count only rows inside security scope.
- OPO RELATED scope: owner OR operator organization is allowed.
- TD/Building RELATED scope: entity's own `organization_id` only.
- Legacy `organization_id IS NULL`: visible to ALL/unrestricted, hidden from non-ALL scopes.
- `ASSIGNED`/`OWN` currently produce no related organization ids and therefore empty scoped lists.
- No route/API wiring in CP2.2-B.
- No migrations, services, frontend, or custom-fields changes.

---

## File Structure

**Modify**
- `app/modules/organizations/repository.py`
- `app/modules/opo/repository.py`
- `app/modules/technical_devices/repository.py`
- `app/modules/buildings/repository.py`

**Create**
- `tests/integration/test_stage3_cp22b_scoped_repositories.py`

No other production files are required.

---

### Task 1: Write scoped repository regression tests

**Interfaces consumed:**
- `app.modules.identity.authorization.AuthorizationContext`
- existing four paginated list repository functions

**Expected new call pattern:**

```python
items, total = list_organizations_paginated(
    db,
    page=1,
    page_size=20,
    authorization=ctx,
)
```

Equivalent optional `authorization` keyword is required for OPO, TD, and Building paginated list functions.

- [ ] Add integration tests covering ALL/unrestricted, RELATED, empty scope, count leakage, pagination-after-scope, OPO owner/operator OR semantics, user organization filters AND security scope, TD/Building own organization, legacy NULL visibility, and deleted-row exclusion.
- [ ] Run the new test file before implementation and record RED caused by unsupported `authorization` keyword.

Run:

```powershell
pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
```

Expected before production changes: failures such as `TypeError: ... got an unexpected keyword argument 'authorization'`.

---

### Task 2: Scope Organization list in SQL

**Modify:** `app/modules/organizations/repository.py`

Add:

```python
from sqlalchemy import Select, false, func, or_, select
from app.modules.identity.authorization import AuthorizationContext
```

Change signature:

```python
def list_organizations_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[Organization], int]:
```

Immediately after non-deleted base statement, apply:

```python
if authorization is not None and not authorization.has_all_scope:
    allowed_ids = authorization.related_organization_ids
    if allowed_ids:
        stmt = stmt.where(Organization.id.in_(allowed_ids))
    else:
        stmt = stmt.where(false())
```

Search, count, ordering, pagination remain otherwise unchanged.

---

### Task 3: Scope OPO list in SQL

**Modify:** `app/modules/opo/repository.py`

Use module-level `or_` and `false`; remove the local `from sqlalchemy import or_` from inside the function.

Change signature:

```python
def list_opo_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    organization_id: uuid.UUID | None = None,
    include_deleted: bool = False,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[OPO], int]:
```

After deleted filtering and before user `organization_id`/search filters:

```python
if authorization is not None and not authorization.has_all_scope:
    allowed_ids = authorization.related_organization_ids
    if allowed_ids:
        stmt = stmt.where(
            or_(
                OPO.owner_organization_id.in_(allowed_ids),
                OPO.operating_organization_id.in_(allowed_ids),
            )
        )
    else:
        stmt = stmt.where(false())
```

Existing `organization_id` filter remains additional AND narrowing.

---

### Task 4: Scope TechnicalDevice list in SQL

**Modify:** `app/modules/technical_devices/repository.py`

Change signature:

```python
def list_technical_devices_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[TechnicalDevice], int]:
```

After base `deleted_at IS NULL` statement:

```python
if authorization is not None and not authorization.has_all_scope:
    allowed_ids = authorization.related_organization_ids
    if allowed_ids:
        stmt = stmt.where(TechnicalDevice.organization_id.in_(allowed_ids))
    else:
        stmt = stmt.where(false())
```

Existing organization/opo/search filters remain additional AND conditions.

---

### Task 5: Scope Building list in SQL

**Modify:** `app/modules/buildings/repository.py`

Change signature:

```python
def list_buildings_paginated(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    organization_id: uuid.UUID | None = None,
    opo_id: uuid.UUID | None = None,
    authorization: AuthorizationContext | None = None,
) -> tuple[list[Building], int]:
```

After base `deleted_at IS NULL` statement:

```python
if authorization is not None and not authorization.has_all_scope:
    allowed_ids = authorization.related_organization_ids
    if allowed_ids:
        stmt = stmt.where(Building.organization_id.in_(allowed_ids))
    else:
        stmt = stmt.where(false())
```

Existing filters remain additional AND conditions.

---

### Task 6: Verification and commit

Run:

```powershell
pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
pytest tests/unit/test_authorization.py -q
pytest tests/integration/test_stage3_cp21_http_api.py -q
pytest
ruff check app/modules/organizations/repository.py app/modules/opo/repository.py app/modules/technical_devices/repository.py app/modules/buildings/repository.py tests/integration/test_stage3_cp22b_scoped_repositories.py
git diff --check
alembic heads
```

Acceptance:
- all new tests pass;
- zero full-suite failures/errors;
- no route/API behavior changes;
- only five implementation files above changed since plan commit;
- Alembic remains single `0010_stage3` head.

Commit exactly:

```text
feat(stage3 cp2.2-b): add SQL scoped list repositories
```

Normal push only. No force push, rebase, reset of published history, or amend of published commits.
