# Stage 3 CP2.2-F Authorization Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Stage 3 authorization with an integration regression matrix proving 401/403/404 boundaries, action-specific scope isolation, fail-closed RELATED behavior, and global reference-data permission boundaries.

**Architecture:** Stage 3 domain objects remain protected by `require_scoped_permission()` and action-specific `AuthorizationContext`. Global reference data and custom-field definitions remain permission-only resources and must not be organization-scoped. CP2.2-F is primarily a verification checkpoint: add one focused integration matrix and change production code only if a new failing test proves a real authorization defect.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, PostgreSQL 17, pytest, existing Stage 3 authorization helpers.

## Global Constraints

- Work only in `D:\Spravoshnik-EPB-opencode` on branch `pilot/opencode-cp22c`.
- Expected starting implementation base after pulling this plan is the plan commit itself.
- PostgreSQL integration tests must execute with `TEST_DATABASE_URL`; skipped integration tests are not acceptable.
- Do not change database schema or Alembic migrations.
- Do not change frontend files.
- Do not add permissions, scope types, aliases, deny-role semantics, or new business behavior.
- `401`: unauthenticated/invalid session.
- `403`: authenticated user lacks the requested permission.
- `404`: requested domain object exists but is outside the requested action's allowed scope, or is absent/deleted.
- `RELATED` parsing remains strict and fail-closed.
- `ASSIGNED` and `OWN` remain deny-by-default for Stage 3 domain entities.
- Scope must be computed only from role assignments that contain the requested permission; an unrelated role must never widen another action.
- Reference endpoints are global resources gated by their existing view permission; they are not organization-scoped.
- Custom-field definitions remain global and permission-only; custom-field values remain parent-scoped from CP2.2-E.
- Do not merge, rebase, cherry-pick into integration, or force-push.

---

## File Map

**Create:**
- `tests/integration/test_stage3_cp22f_authorization_matrix.py` — final cross-module authorization regression matrix.

**Production file allowed only if a failing CP2.2-F test proves a real bug:**
- `app/modules/opo/reference_routes.py`

No other production file is in scope. If a failing matrix test requires changing Organizations/OPO/Technical Devices/Buildings/Custom Fields/Identity code, stop and report the exact blocker instead of widening scope.

---

### Task 1: Build the cross-module authorization test fixtures

**Files:**
- Create: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Consumes existing `Employee`, `User`, `Role`, `Permission`, `RolePermission`, `UserRoleAssignment`, `ScopeType`.
- Consumes existing domain models `Organization`, `OPO`, `TechnicalDevice`, `Building`.
- Produces local test helpers only; no production interface.

- [ ] **Step 1: Add local user/grant/session helpers**

Create helpers following the patterns already used in CP2.2-C/D/E tests:

```python
def _create_user(db: Session, *, username: str, is_superuser: bool = False) -> User:
    ...


def _grant(
    db: Session,
    *,
    user: User,
    permission_code: str,
    role_code: str,
    scope_type: ScopeType,
    scope_config: dict | None,
) -> None:
    ...


def _token(db: Session, user: User) -> str:
    ...
```

Use unique role codes per grant so tests can deliberately place different permissions in different roles.

- [ ] **Step 2: Add domain factories**

Add focused factories for:

```python
def _organization(db: Session, name: str) -> Organization: ...
def _opo(db: Session, *, owner: Organization, operator: Organization, name: str) -> OPO: ...
def _device(db: Session, *, organization: Organization, opo: OPO | None = None) -> TechnicalDevice: ...
def _building(db: Session, *, organization: Organization, opo: OPO | None = None) -> Building: ...
```

Do not use HTTP creation helpers for setup because setup must be independent of the action permission being tested.

- [ ] **Step 3: Confirm test collection before behavior tests**

Run:

```powershell
pytest tests/integration/test_stage3_cp22f_authorization_matrix.py --collect-only -q
```

Expected: collection succeeds with no import errors.

---

### Task 2: Prove global reference-data boundaries

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Modify only if RED proves a bug: `app/modules/opo/reference_routes.py`

**Interfaces:**
- `GET /api/reference/hazard-signs` requires `opo.view`.
- `GET /api/reference/activity-types` requires `opo.view`.
- `GET /api/reference/technical-device-types` requires `technical_devices.view`.
- `GET /api/reference/building-types` requires `buildings.view`.

- [ ] **Step 1: Write reference boundary tests**

Cover all of the following:

```text
no auth -> 401
wrong permission only -> 403
matching view permission -> 200
matching view permission with RELATED empty organization_ids -> 200
matching view permission with ASSIGNED -> 200
matching view permission with OWN -> 200
superuser -> 200
```

The important invariant is that reference data is global: scope type does not filter enum/reference rows once the matching permission exists.

Also prove:

```text
opo.create without opo.view -> hazard-signs/activity-types = 403
technical_devices.create without technical_devices.view -> technical-device-types = 403
buildings.create without buildings.view -> building-types = 403
```

This is intentional and must be documented by tests; frontend CP2.1 handles optional lookup decoupling.

- [ ] **Step 2: Run the reference subset**

```powershell
pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k reference
```

Expected on correct current code: PASS. If it fails, inspect root cause before editing `reference_routes.py`.

---

### Task 3: Prove requested-permission scope isolation

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Organization: `organizations.view`, `organizations.update`.
- OPO: `opo.view`, `opo.edit`.
- TD: `technical_devices.view`, `technical_devices.edit`.
- Building: `buildings.view`, `buildings.edit`.
- Custom field values: `custom_fields.manage`.

- [ ] **Step 1: Add cross-role scope borrowing tests**

For each domain, create two organizations `allowed_org` and `foreign_org` plus objects in both.

Test pattern A — unrelated ALL must not widen requested VIEW:

```text
Role A: requested *.view + RELATED(allowed_org)
Role B: some other permission + ALL
GET foreign object -> 404
LIST -> only allowed objects
```

Use a genuinely different permission for Role B, for example `organizations.update` when testing `organizations.view`, or `opo.edit` when testing `opo.view`.

Test pattern B — unrelated VIEW ALL must not widen requested EDIT:

```text
Role A: requested *.edit + RELATED(allowed_org)
Role B: same module *.view + ALL
PATCH foreign object -> 404
DB unchanged
```

Apply this pattern to:

```text
Organizations
OPO
Technical Devices
Buildings
```

For OPO, allowed scope means owner OR operator organization.
For TD/Building, only `organization_id` counts; linked OPO access must not widen scope.

- [ ] **Step 2: Add custom-fields permission isolation test**

Create:

```text
Role A: custom_fields.manage + RELATED(allowed_org)
Role B: opo.view + ALL
```

Then for a foreign OPO parent:

```text
GET custom field values -> 404
PUT custom field value -> 404 and no row inserted
```

This proves an ALL grant from `opo.view` cannot widen `custom_fields.manage`.

- [ ] **Step 3: Run permission-isolation tests**

```powershell
pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k "scope_isolation or borrowing"
```

Expected: PASS on correct CP2.2-A-E implementation.

---

### Task 4: Prove fail-closed scope types at HTTP level

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Uses strict RELATED parser already implemented in `authorization.py`.
- No production changes expected.

- [ ] **Step 1: Add malformed RELATED tests**

For a user who has the requested permission only through malformed RELATED config, test these configs separately:

```python
{"organization_ids": ["not-a-uuid"]}
{"organization_ids": [str(valid_org_id)], "extra": True}
{"organization_ids": "not-a-list"}
{"org_ids": [str(valid_org_id)]}
```

At minimum prove via HTTP:

```text
Organizations LIST -> 200 with total=0/items=[]
Organization detail -> 404
OPO detail -> 404
TD detail -> 404
Building detail -> 404
Custom field values on an existing parent -> 404
```

The malformed assignment still contains the requested permission, so the response is not 403; its usable RELATED organization set is empty.

- [ ] **Step 2: Add ASSIGNED/OWN deny-by-default HTTP tests**

For each of `ScopeType.ASSIGNED` and `ScopeType.OWN`, with a valid requested Stage 3 permission:

```text
Organization detail -> 404
OPO detail -> 404
TD detail -> 404
Building detail -> 404
```

Use one parameterized test where possible. Do not invent owner/assignee semantics.

- [ ] **Step 3: Run fail-closed subset**

```powershell
pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k "malformed or deny_by_default"
```

Expected: PASS.

---

### Task 5: Prove final 401/403/404 matrix and non-enumeration behavior

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- All Stage 3 domain/resource routes already exist.

- [ ] **Step 1: Add unauthenticated 401 matrix**

Parameterize representative endpoints:

```text
GET /api/organizations
GET /api/opo
GET /api/technical-devices
GET /api/buildings
GET /api/custom-fields/definitions
GET /api/custom-fields/values/opo/<uuid>
GET /api/reference/hazard-signs
GET /api/reference/technical-device-types
GET /api/reference/building-types
```

Every response must be exactly `401`.

- [ ] **Step 2: Add missing-permission 403 matrix**

Use an authenticated user that has a real but unrelated permission. Verify representative endpoints return `403` before object existence/scope is evaluated.

Include at least:

```text
organizations.view
opo.view
technical_devices.view
buildings.view
custom_fields.manage
reference opo.view
reference technical_devices.view
reference buildings.view
```

- [ ] **Step 3: Add foreign-vs-absent non-enumeration matrix**

For each scoped domain action, compare status for:

```text
existing foreign UUID
random absent UUID
```

Both must return `404` for:

```text
Organization GET
OPO GET
TD GET
Building GET
Custom Field values GET on OPO parent
```

Do not assert identical response text unless the existing route contract already guarantees it; status non-enumeration is the required invariant.

- [ ] **Step 4: Run matrix subset**

```powershell
pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k "unauthenticated or missing_permission or non_enumeration"
```

Expected: PASS.

---

### Task 6: Run CP2.2-F RED/GREEN discipline and full regression

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Possible production file only if proven: `app/modules/opo/reference_routes.py`

- [ ] **Step 1: Establish RED only if a real missing behavior exists**

Before any production edit, run the completed new matrix:

```powershell
pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q
```

Two acceptable outcomes:

1. **GREEN immediately** — CP2.2-A-E already satisfy the final security matrix. This is valid for a hardening/closure checkpoint; do not create unnecessary production changes.
2. **RED** — record exact failing test and root cause. Only modify `app/modules/opo/reference_routes.py` if the defect is actually in reference permission behavior and the expected behavior above is unambiguous. If the defect is in any other production module, STOP and report `BLOCKED` because it is outside CP2.2-F allowed production scope.

Never manufacture a RED by weakening tests or changing correct code.

- [ ] **Step 2: Run CP2.2-F targeted suite**

```powershell
pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q
```

Required:

```text
0 failed
0 errors
0 skipped
```

- [ ] **Step 3: Run authorization checkpoint regressions**

```powershell
pytest tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py -q
pytest tests/integration/test_stage3_cp22d_td_building_http_scope.py -q
pytest tests/integration/test_stage3_cp22c_org_opo_http_scope.py -q
pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
pytest tests/unit/test_authorization.py -q
```

Required: all GREEN, no skipped integration tests.

- [ ] **Step 4: Run the full PostgreSQL suite exactly once without parallel pytest**

Before full suite, verify no other pytest process is using this worktree/test database.

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "pytest" } |
  Select-Object ProcessId, CommandLine
```

Then run:

```powershell
pytest -q
```

Required:

```text
0 failed
0 errors
0 skipped
```

- [ ] **Step 5: Static verification**

```powershell
ruff check tests/integration/test_stage3_cp22f_authorization_matrix.py
```

If `reference_routes.py` was modified, also run:

```powershell
ruff check app/modules/opo/reference_routes.py
```

Then:

```powershell
git diff --check
alembic heads
git status
git diff --stat
git diff
```

Alembic must remain exactly:

```text
0010_stage3
```

---

### Task 7: Commit and stop Stage 3 authorization work

**Files:**
- Add: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Add `app/modules/opo/reference_routes.py` only if a proven reference bug required a fix.

- [ ] **Step 1: Commit only checkpoint files**

If tests were sufficient and no production bug existed:

```powershell
git add tests/integration/test_stage3_cp22f_authorization_matrix.py
git commit -m "test(stage3 cp2.2-f): close authorization regression matrix"
```

If a reference-route bug was proven and fixed:

```powershell
git add app/modules/opo/reference_routes.py tests/integration/test_stage3_cp22f_authorization_matrix.py
git commit -m "fix(stage3 cp2.2-f): close authorization boundaries"
```

- [ ] **Step 2: Push only the OpenCode branch**

```powershell
git push origin pilot/opencode-cp22c
```

- [ ] **Step 3: Stop**

Do not start Contracts, CP2.3, or any next backend feature. Return the structured CP2.2-F report for independent audit.
