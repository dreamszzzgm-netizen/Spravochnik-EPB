# Stage 3 CP2.2-F Authorization Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Stage 3 authorization with one focused PostgreSQL integration regression matrix proving final authentication, permission, scope-isolation, fail-closed, reference-resource, and non-enumeration invariants.

**Architecture:** Keep all existing Stage 3 production authorization boundaries intact and add one independently readable matrix under `tests/integration`. Production code is not expected to change; `app/modules/opo/reference_routes.py` is the only allowed production file and may be modified only if a new failing CP2.2-F test proves a real reference-permission defect. Any defect elsewhere is a blocker/new focused fix, not scope for this checkpoint.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, PostgreSQL 17, pytest, Ruff, Alembic.

## Global Constraints

- Repository: `dreamszzzgm-netizen/Spravochnik-EPB`.
- Branch: `agent/stage3-cp22f-authorization-closure`.
- Verified baseline: `1445d8a2f9364c47a590a52e64e429bdd953cf75`.
- Alembic must remain exactly `0010_stage3`.
- PostgreSQL integration tests must execute with `TEST_DATABASE_URL`; skipped integration tests are not acceptable.
- Do not modify `frontend/**`.
- Do not modify Alembic migrations or database schema.
- Do not add permissions, aliases, scope types, deny roles, or new business behavior.
- `401`: unauthenticated or invalid session.
- `403`: authenticated user lacks the requested permission.
- `404`: object is absent/deleted or exists outside the requested action's allowed scope.
- `RELATED` remains strict and fail-closed.
- `ASSIGNED` and `OWN` remain deny-by-default for Stage 3 organization-owned domain entities.
- Authorization scope must be computed only from grants that contain the permission requested by the current action.
- Global reference endpoints and custom-field definitions remain permission-only resources, not organization-scoped.
- Custom-field values remain parent-scoped through CP2.2-E.
- Do not merge, cherry-pick, rebase, or force-push old pilot branches into this branch.

---

## File Map

**Create**
- `tests/integration/test_stage3_cp22f_authorization_matrix.py` — the complete cross-module authorization closure matrix.

**Modify only if a new RED proves a real reference-route bug**
- `app/modules/opo/reference_routes.py` — existing global reference permission boundary only.

**Do not modify**
- `app/modules/identity/**`
- `app/modules/organizations/**`
- `app/modules/technical_devices/**`
- `app/modules/buildings/**`
- `app/modules/custom_fields/**`
- `alembic/**`
- `frontend/**`

If the matrix proves a defect in one of the prohibited modules, stop CP2.2-F as `BLOCKED` and report the exact failing invariant.

---

### Task 1: Create independently readable authorization matrix fixtures

**Files:**
- Create: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Consumes seeded permission rows used by existing Stage 3 integration tests.
- Consumes `Employee`, `User`, `Role`, `RolePermission`, `UserRoleAssignment`, `ScopeType`.
- Consumes `Organization`, `OPO`, `TechnicalDevice`, `Building`, `CustomFieldDefinition`, `CustomFieldValue`.
- Produces only local test helpers; no production interface.

- [ ] **Step 1: Add imports and integration marker**

Start the new file with the concrete imports already established by CP2.2-E:

```python
import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.custom_fields.models import (
    CustomFieldDefinition,
    CustomFieldType,
    CustomFieldValue,
)
from app.modules.identity.models import (
    Employee,
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)
from app.modules.identity.security import hash_password
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.models import TechnicalDevice

pytestmark = pytest.mark.integration
```

- [ ] **Step 2: Add user, grant, and token helpers**

Use exactly this contract:

```python
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
        password_hash=hash_password("test-password-123!"),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.flush()
    return user


def _grant(
    db: Session,
    *,
    user: User,
    permission_code: str,
    role_code: str,
    scope_type: ScopeType,
    scope_config: dict | None,
) -> None:
    role = Role(code=role_code, name=role_code, is_system=False)
    db.add(role)
    db.flush()

    perm_id = db.scalar(
        text("SELECT id FROM permissions WHERE code = :code"),
        {"code": permission_code},
    )
    assert perm_id is not None, f"seeded permission {permission_code!r} must exist"
    db.add(RolePermission(role_id=role.id, permission_id=perm_id))
    db.add(
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            scope_type=scope_type,
            scope_config=scope_config,
            assigned_by=user.id,
        )
    )
    db.flush()


def _token(db: Session, user: User) -> str:
    from app.core.config import get_settings
    from app.modules.identity.service import AuthService

    return AuthService(get_settings()).login(
        db,
        username=user.username,
        password="test-password-123!",
        ip_address="127.0.0.1",
        user_agent="cp22f-test",
    ).token
```

Unique `role_code` values are required per `_grant` call so one test can deliberately attach different permissions/scopes to different roles.

- [ ] **Step 3: Add domain factories**

Use direct model creation so test setup never depends on the HTTP permission currently under test:

```python
def _organization(db: Session, name: str) -> Organization:
    org = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name=name,
        short_name=name,
    )
    db.add(org)
    db.flush()
    return org


def _opo(
    db: Session,
    *,
    owner: Organization,
    operator: Organization,
    name: str,
) -> OPO:
    opo = OPO(
        name=name,
        registration_number=f"REG-{uuid.uuid4()}",
        hazard_class=HazardClass.HAZARD_CLASS_3,
        address=f"{name} address",
        registration_date=date(2026, 1, 1),
        owner_organization_id=owner.id,
        operating_organization_id=operator.id,
    )
    db.add(opo)
    db.flush()
    return opo


def _device(
    db: Session,
    *,
    organization: Organization,
    name: str,
    opo: OPO | None = None,
) -> TechnicalDevice:
    device = TechnicalDevice(
        name=name,
        device_type=TechnicalDeviceType.OTHER,
        organization_id=organization.id,
        opo_id=opo.id if opo else None,
    )
    db.add(device)
    db.flush()
    return device


def _building(
    db: Session,
    *,
    organization: Organization,
    name: str,
    opo: OPO | None = None,
) -> Building:
    building = Building(
        name=name,
        building_type=BuildingType.OTHER,
        organization_id=organization.id,
        opo_id=opo.id if opo else None,
    )
    db.add(building)
    db.flush()
    return building
```

- [ ] **Step 4: Add custom-field factories/count helper**

```python
def _cf_definition(
    db: Session,
    *,
    code: str,
    entity_type: str = "opo",
) -> CustomFieldDefinition:
    definition = CustomFieldDefinition(
        code=code,
        name=f"Field {code}",
        entity_type=entity_type,
        field_type=CustomFieldType.TEXT,
    )
    db.add(definition)
    db.flush()
    return definition


def _cf_value_count(
    db: Session,
    *,
    definition_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> int:
    return int(
        db.scalar(
            text(
                "SELECT count(*) FROM custom_field_values "
                "WHERE field_definition_id = :definition_id "
                "AND entity_id = :entity_id"
            ),
            {"definition_id": definition_id, "entity_id": entity_id},
        )
        or 0
    )
```

- [ ] **Step 5: Verify collection before behavior work**

Run locally with the real test DB enabled:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5433/spravoshnik_test"
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py --collect-only -q
```

Expected: collection succeeds; no import or fixture errors; no integration skip.

- [ ] **Step 6: Commit the fixture skeleton only if working locally**

For local/agentic execution use:

```powershell
git add tests/integration/test_stage3_cp22f_authorization_matrix.py
git commit -m "test(stage3 cp2.2-f): scaffold authorization matrix"
```

For GitHub-first execution, this intermediate commit may be folded into the completed test-file commit because the remote authoring environment cannot execute pytest between commits. The verification report must state that RED/GREEN execution occurred later on the user's PostgreSQL test environment.

---

### Task 2: Prove global reference-data permission boundaries

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Modify only if RED proves a bug: `app/modules/opo/reference_routes.py`

**Interfaces:**
- `GET /api/reference/hazard-signs` -> permission `opo.view`.
- `GET /api/reference/activity-types` -> permission `opo.view`.
- `GET /api/reference/technical-device-types` -> permission `technical_devices.view`.
- `GET /api/reference/building-types` -> permission `buildings.view`.

- [ ] **Step 1: Add a parameter table for reference endpoints**

```python
REFERENCE_CASES = [
    ("/api/reference/hazard-signs", "opo.view", "opo.create"),
    ("/api/reference/activity-types", "opo.view", "opo.create"),
    (
        "/api/reference/technical-device-types",
        "technical_devices.view",
        "technical_devices.create",
    ),
    ("/api/reference/building-types", "buildings.view", "buildings.create"),
]
```

- [ ] **Step 2: Add unauthenticated and wrong-permission reference tests**

Parameterize `REFERENCE_CASES` and assert:

```python
response = client.get(path)
assert response.status_code == 401
```

Then create a user with only the `wrong_permission`, authenticate, call the same endpoint, and assert exactly `403`.

- [ ] **Step 3: Add matching-permission tests across all scope types**

For each matching permission test all of:

```python
ScopeType.ALL
ScopeType.RELATED
ScopeType.ASSIGNED
ScopeType.OWN
```

For `RELATED`, use `scope_config={"organization_ids": []}`. For the other scope types use `scope_config=None`.

Expected for all four: `200` because reference resources are global and `require_permission()` only requires the matching permission to exist.

- [ ] **Step 4: Add superuser reference test**

Use `_create_user(..., is_superuser=True)`, no grants, authenticate, assert `200` for every reference endpoint.

- [ ] **Step 5: Run the reference subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k reference
```

Expected on correct baseline: all PASS, zero skipped.

- [ ] **Step 6: Production-edit decision gate**

If reference tests are GREEN, do not touch production code.

If a test is RED, inspect `app/modules/opo/reference_routes.py`. The only permitted production correction is restoring the documented mapping:

```python
require_permission("opo.view")
require_permission("technical_devices.view")
require_permission("buildings.view")
```

Do not replace reference routes with `require_scoped_permission()`; reference data intentionally remains global.

---

### Task 3: Prove requested-permission scope isolation for VIEW actions

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Organizations list/detail use `organizations.view`.
- OPO list/detail use `opo.view`.
- Technical Devices list/detail use `technical_devices.view`.
- Buildings list/detail use `buildings.view`.

- [ ] **Step 1: Add Organizations VIEW borrowing test**

Arrange:

```text
Role A: organizations.view + RELATED(allowed_org)
Role B: organizations.update + ALL
```

Assert:

```text
GET /api/organizations -> 200, contains allowed_org only, excludes foreign_org
GET /api/organizations/{foreign_org.id} -> 404
```

The unrelated `organizations.update + ALL` role must not widen `organizations.view`.

- [ ] **Step 2: Add OPO VIEW borrowing test**

Arrange an allowed OPO related to `allowed_org` and a foreign OPO related only to `foreign_org`:

```text
Role A: opo.view + RELATED(allowed_org)
Role B: opo.edit + ALL
```

Assert list excludes the foreign OPO and foreign detail returns `404`.

- [ ] **Step 3: Add Technical Device VIEW borrowing test**

Arrange allowed/foreign devices with distinct `organization_id` values:

```text
Role A: technical_devices.view + RELATED(allowed_org)
Role B: technical_devices.edit + ALL
```

Assert list/detail scope only follows `technical_devices.organization_id`.

- [ ] **Step 4: Add Building VIEW borrowing test**

Arrange:

```text
Role A: buildings.view + RELATED(allowed_org)
Role B: buildings.edit + ALL
```

Assert list/detail scope only follows `buildings.organization_id`.

- [ ] **Step 5: Run VIEW isolation subset**

Name these tests with `scope_isolation_view` and run:

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k scope_isolation_view
```

Expected: PASS, zero skipped.

---

### Task 4: Prove requested-permission scope isolation for EDIT actions

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Organizations mutation -> `organizations.update`.
- OPO mutation -> `opo.edit`.
- Technical Device mutation -> `technical_devices.edit`.
- Building mutation -> `buildings.edit`.

- [ ] **Step 1: Add Organizations EDIT borrowing test**

Arrange:

```text
Role A: organizations.update + RELATED(allowed_org)
Role B: organizations.view + ALL
```

PATCH the foreign organization using the real existing update endpoint/payload pattern from Stage 2 integration tests. Assert `404`, refresh the row, and assert the original field value is unchanged.

- [ ] **Step 2: Add OPO EDIT borrowing test**

Arrange:

```text
Role A: opo.edit + RELATED(allowed_org)
Role B: opo.view + ALL
```

PATCH the foreign OPO name. Assert `404`; refresh and prove no mutation.

- [ ] **Step 3: Add Technical Device EDIT borrowing test**

Arrange:

```text
Role A: technical_devices.edit + RELATED(allowed_org)
Role B: technical_devices.view + ALL
```

PATCH the foreign device name. Assert `404`; refresh and prove no mutation.

- [ ] **Step 4: Add Building EDIT borrowing test**

Arrange:

```text
Role A: buildings.edit + RELATED(allowed_org)
Role B: buildings.view + ALL
```

PATCH the foreign building name. Assert `404`; refresh and prove no mutation.

- [ ] **Step 5: Run EDIT isolation subset**

Name these tests with `scope_isolation_edit` and run:

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k scope_isolation_edit
```

Expected: PASS, zero skipped.

If any failure requires production changes outside `reference_routes.py`, stop and report `BLOCKED`.

---

### Task 5: Prove custom-field permission isolation from broader parent permissions

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- `GET /api/custom-fields/values/opo/{entity_id}` -> `custom_fields.manage` plus parent scope.
- `PUT /api/custom-fields/values/opo/{entity_id}/{field_definition_id}` -> same.

- [ ] **Step 1: Create allowed and foreign OPO parents plus one text field definition**

Use `_organization`, `_opo`, and `_cf_definition`.

- [ ] **Step 2: Grant deliberately conflicting roles**

```text
Role A: custom_fields.manage + RELATED(allowed_org)
Role B: opo.view + ALL
```

- [ ] **Step 3: Prove GET cannot borrow OPO ALL scope**

```python
response = client.get(
    f"/api/custom-fields/values/opo/{foreign_opo.id}",
    headers={"Authorization": f"Bearer {token}"},
)
assert response.status_code == 404
```

- [ ] **Step 4: Prove PUT cannot borrow OPO ALL scope and creates no row**

Record `_cf_value_count(...)`, call PUT with a valid text value, assert `404`, then assert the count is unchanged.

- [ ] **Step 5: Run custom-field isolation subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k custom_field_scope_isolation
```

Expected: PASS, zero skipped.

---

### Task 6: Prove strict fail-closed RELATED behavior at HTTP level

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Existing parser accepts only exactly `{"organization_ids": [valid UUID strings...]}`.

- [ ] **Step 1: Parameterize malformed RELATED configs**

Use exactly:

```python
MALFORMED_RELATED_CONFIGS = [
    {"organization_ids": ["not-a-uuid"]},
    {"organization_ids": [str(uuid.uuid4())], "extra": True},
    {"organization_ids": "not-a-list"},
    {"org_ids": [str(uuid.uuid4())]},
]
```

- [ ] **Step 2: Prove Organizations list fails closed without becoming 403**

Grant `organizations.view` only through one malformed RELATED assignment. Assert:

```text
GET /api/organizations -> 200
response JSON total == 0
response JSON items == []
```

This is permission-present-but-no-usable-scope, not permission-missing.

- [ ] **Step 3: Prove existing details become 404**

For the same malformed requested permission pattern, cover existing:

```text
Organization detail
OPO detail
Technical Device detail
Building detail
Custom-field values on an existing OPO parent
```

Expected: `404` for each.

Use the correct requested permission per endpoint; do not reuse an unrelated permission.

- [ ] **Step 4: Run malformed RELATED subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k malformed_related
```

Expected: PASS, zero skipped.

---

### Task 7: Prove ASSIGNED and OWN remain deny-by-default for domain access

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Current Stage 3 domain authorization implements `ALL` and `RELATED` organization semantics only.

- [ ] **Step 1: Parameterize denied scope types**

```python
@pytest.mark.parametrize("scope_type", [ScopeType.ASSIGNED, ScopeType.OWN])
```

- [ ] **Step 2: For each scope type prove Organization detail 404**

Grant `organizations.view` with the parameterized scope type and `scope_config=None`; existing organization detail must be `404`.

- [ ] **Step 3: Repeat with correct view permission for OPO, TD, and Building**

Each endpoint must receive its own requested permission and return `404` for an existing object.

- [ ] **Step 4: Run deny-by-default subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k deny_by_default
```

Expected: PASS, zero skipped.

---

### Task 8: Prove final unauthenticated 401 and missing-permission 403 matrix

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Representative endpoints from every Stage 3 protected resource family.

- [ ] **Step 1: Define representative GET endpoint factory cases**

Include:

```text
/api/organizations
/api/opo
/api/technical-devices
/api/buildings
/api/custom-fields/definitions
/api/custom-fields/values/opo/<random_uuid>
/api/reference/hazard-signs
/api/reference/technical-device-types
/api/reference/building-types
```

- [ ] **Step 2: Add `test_unauthenticated_matrix_returns_401`**

Parameterize the endpoints and assert exactly `401` with no Authorization header/cookie.

- [ ] **Step 3: Add `test_missing_permission_matrix_returns_403`**

Create one authenticated user with a real unrelated permission such as `tasks.view` if seeded; if that permission is not seeded in the verified fixture, use another known seeded permission that is unrelated to the endpoint under test. For every representative endpoint assert exactly `403`.

Do not use a user with zero role assignments if the authentication setup requires a persisted active role; the point is an authenticated principal with the wrong permission.

- [ ] **Step 4: Run the boundary subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k "unauthenticated_matrix or missing_permission_matrix"
```

Expected: PASS, zero skipped.

---

### Task 9: Prove foreign-vs-absent status non-enumeration

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Scoped GET routes for Organization, OPO, TD, Building, and OPO-parent custom-field values.

- [ ] **Step 1: Create allowed and foreign objects**

Grant each requested view/manage permission with `RELATED(allowed_org)`.

- [ ] **Step 2: Compare foreign and random absent Organization IDs**

Call existing-foreign and random-absent detail URLs. Assert both statuses are `404`.

- [ ] **Step 3: Repeat for OPO, Technical Device, and Building**

For OPO scope, ensure foreign OPO owner and operator are both outside `allowed_org`.

For TD/Building, ensure `organization_id` is foreign even if an OPO relation could otherwise look related.

- [ ] **Step 4: Repeat for custom-field values on OPO parent**

Compare:

```text
/api/custom-fields/values/opo/<foreign_existing_id>
/api/custom-fields/values/opo/<random_absent_id>
```

Both must be `404`.

- [ ] **Step 5: Do not over-assert response text**

Only status equivalence is required. Do not require identical JSON detail text unless the existing route contract already guarantees it.

- [ ] **Step 6: Run non-enumeration subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k non_enumeration
```

Expected: PASS, zero skipped.

---

### Task 10: Execute evidence-first RED/GREEN gate

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Possible production file: `app/modules/opo/reference_routes.py`

**Interfaces:**
- Uses only behavior defined by the approved CP2.2-F design.

- [ ] **Step 1: Run the complete new matrix before production edits**

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5433/spravoshnik_test"
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q
```

Acceptable outcomes:

```text
GREEN immediately -> expected/valid closure result; no production edit.
RED in reference permission behavior -> diagnose and minimally fix reference_routes.py.
RED elsewhere -> CP2.2-F BLOCKED; do not widen production scope.
```

- [ ] **Step 2: If reference RED exists, record exact evidence before edit**

Report:

```text
failing test
actual status/body
expected status
requested permission
scope type
affected reference endpoint
root cause in reference_routes.py
```

- [ ] **Step 3: Apply only the minimal reference permission fix if required**

No organization filtering, no scoped dependency, no new permissions.

- [ ] **Step 4: Re-run the full new matrix**

Required:

```text
0 failed
0 errors
0 skipped
```

---

### Task 11: Run Stage 3 authorization regressions

**Files:**
- No code changes expected.

**Interfaces:**
- CP2.2-A through E plus legacy authorization API.

- [ ] **Step 1: Run CP2.2-E**

```powershell
python -m pytest tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py -q
```

- [ ] **Step 2: Run CP2.2-D**

```powershell
python -m pytest tests/integration/test_stage3_cp22d_td_building_http_scope.py -q
```

- [ ] **Step 3: Run CP2.2-C**

```powershell
python -m pytest tests/integration/test_stage3_cp22c_org_opo_http_scope.py -q
```

- [ ] **Step 4: Run CP2.2-B**

```powershell
python -m pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
```

- [ ] **Step 5: Run CP2.2-A**

```powershell
python -m pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

- [ ] **Step 6: Run legacy unit authorization tests**

```powershell
python -m pytest tests/unit/test_authorization.py -q
```

Every integration invocation must show zero skipped tests.

---

### Task 12: Run complete PostgreSQL backend verification and static gates

**Files:**
- No additional changes expected.

**Interfaces:**
- Entire backend test suite and repository hygiene.

- [ ] **Step 1: Verify test database containers are healthy**

```powershell
docker compose ps
```

Required: `postgres` and `postgres-test` healthy.

- [ ] **Step 2: Ensure no parallel pytest is sharing the test DB**

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "pytest" } |
  Select-Object ProcessId, CommandLine
```

Stop only stale pytest processes that are known to belong to this project. Do not terminate unrelated Python processes.

- [ ] **Step 3: Run the full backend suite once**

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5433/spravoshnik_test"
python -m pytest -q
```

Required:

```text
0 failed
0 errors
0 skipped
```

Baseline before CP2.2-F was 319 passed; final count may be higher only because CP2.2-F adds tests.

- [ ] **Step 4: Run Ruff**

```powershell
ruff check tests/integration/test_stage3_cp22f_authorization_matrix.py
```

If `reference_routes.py` changed:

```powershell
ruff check app/modules/opo/reference_routes.py
```

- [ ] **Step 5: Verify migrations unchanged**

```powershell
python -m alembic heads
python -m alembic current
```

Both must report `0010_stage3` with the main PostgreSQL container healthy.

- [ ] **Step 6: Verify Git diff hygiene**

```powershell
git diff --check
git status -sb
git diff --stat 1445d8a...HEAD
git diff 1445d8a...HEAD -- . ":(exclude)docs/superpowers/specs/**" ":(exclude)docs/superpowers/plans/**"
```

Expected implementation diff:

```text
tests/integration/test_stage3_cp22f_authorization_matrix.py
```

plus `app/modules/opo/reference_routes.py` only if a proven reference RED required it.

There must be no frontend or Alembic diff.

---

### Task 13: Commit implementation boundary and hand off for independent local audit

**Files:**
- Add: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Add only if proven: `app/modules/opo/reference_routes.py`

**Interfaces:**
- Produces the exact GitHub commit to be fetched and independently verified locally.

- [ ] **Step 1: Commit test-only closure when production code remains correct**

```powershell
git add tests/integration/test_stage3_cp22f_authorization_matrix.py
git commit -m "test(stage3 cp2.2-f): close authorization regression matrix"
```

- [ ] **Step 2: Alternative commit message only if a proven reference bug was fixed**

```powershell
git add app/modules/opo/reference_routes.py tests/integration/test_stage3_cp22f_authorization_matrix.py
git commit -m "fix(stage3 cp2.2-f): close authorization boundaries"
```

- [ ] **Step 3: Push only the checkpoint branch**

```powershell
git push origin agent/stage3-cp22f-authorization-closure
```

Never push implementation changes to `main` or directly to the baseline integration branch.

- [ ] **Step 4: User fetches exact implementation commit**

```powershell
cd D:\Spravoshnik-EPB
git fetch origin --prune
git switch --track origin/agent/stage3-cp22f-authorization-closure
# if local branch already exists: git switch agent/stage3-cp22f-authorization-closure; git pull --ff-only
git rev-parse --short HEAD
git status -sb
```

The SHA must match the handoff report before agents begin verification.

- [ ] **Step 5: Verification Agent returns a structured report without production edits**

Required report sections:

```text
Branch / HEAD
TEST_DATABASE_URL present
Docker health
CP2.2-F targeted result
CP2.2-E/D/C/B/A results
legacy authorization unit result
full pytest result
Ruff result
Alembic heads/current
git diff --check
blocking findings
verdict PASS/FAIL
```

- [ ] **Step 6: Security Auditor reviews behavior independently**

Audit at minimum:

```text
401 before permission/scope evaluation
403 for missing requested permission
404 foreign-vs-absent non-enumeration
cross-role permission scope borrowing
malformed RELATED fail-closed
ASSIGNED/OWN deny-by-default
global reference permission-only boundary
custom-field parent-scope isolation
no schema/frontend/unrelated production changes
```

The auditor reports findings only; it does not silently repair production code.

---

## Completion Gate

CP2.2-F may be reported `COMPLETE` only after all of these are evidenced on the exact implementation SHA:

```text
CP2.2-F matrix:              PASS, 0 skipped
CP2.2-E regression:          PASS, 0 skipped
CP2.2-D regression:          PASS, 0 skipped
CP2.2-C regression:          PASS, 0 skipped
CP2.2-B regression:          PASS, 0 skipped
CP2.2-A regression:          PASS, 0 skipped
legacy authorization unit:   PASS
full PostgreSQL pytest:       PASS, 0 failed/errors/skipped
Ruff:                         PASS
Alembic heads/current:        0010_stage3
frontend diff:                none
migration diff:               none
unrelated production diff:   none
Verification Agent:           PASS
Security Auditor:             no blocking finding
```

At that point CP2.2-F closes Stage 3 authorization and establishes the security baseline for the next product checkpoint.
