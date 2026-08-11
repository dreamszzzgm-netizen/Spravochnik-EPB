# Stage 3 CP2.2-F Authorization Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Stage 3 authorization with one PostgreSQL integration regression matrix proving authentication, requested-permission isolation, fail-closed scope handling, global reference boundaries, and non-enumeration.

**Architecture:** Keep the current Stage 3 authorization implementation unchanged unless the new matrix proves a real defect in the one explicitly allowed production file, `app/modules/opo/reference_routes.py`. The checkpoint creates one focused integration test module. Any defect in Organizations, OPO, Technical Devices, Buildings, Custom Fields, Identity, repositories, migrations, or frontend is reported as a blocker and handled in a separate focused checkpoint.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, PostgreSQL 17, pytest, Ruff, Alembic, GitHub Actions.

## Global Constraints

- Repository: `dreamszzzgm-netizen/Spravochnik-EPB`.
- Branch: `agent/stage3-cp22f-authorization-closure`.
- Verified baseline: `1445d8a2f9364c47a590a52e64e429bdd953cf75`.
- Alembic head/current must remain `0010_stage3`.
- Integration verification must use a real PostgreSQL test database with `TEST_DATABASE_URL`; skipped integration tests are not acceptable.
- CI already runs on every push with PostgreSQL 17, Ruff, Alembic upgrade, and full pytest.
- Do not modify `frontend/**`.
- Do not modify `alembic/**` or database schema.
- Do not add permissions, aliases, scope types, deny-role semantics, or new business behavior.
- `401` means no valid authenticated session.
- `403` means authenticated user lacks the requested permission.
- `404` means scoped domain object is absent/deleted or outside the requested action's usable scope.
- `RELATED` stays strict and fail-closed.
- `ASSIGNED` and `OWN` stay deny-by-default for Stage 3 organization-owned domain entities.
- Scope is built only from grants that contain the permission requested by the current action.
- Reference endpoints and custom-field definitions are global permission-only resources.
- Custom-field values stay parent-scoped.
- Do not merge/cherry-pick/rebase the old `pilot/opencode-cp22c` branch.

---

## File Map

**Create**
- `tests/integration/test_stage3_cp22f_authorization_matrix.py` — complete closure matrix.

**Modify only if a new failing matrix test proves a real reference-permission bug**
- `app/modules/opo/reference_routes.py`.

**Out of scope for production edits**
- `app/modules/identity/**`
- `app/modules/organizations/**`
- `app/modules/technical_devices/**`
- `app/modules/buildings/**`
- `app/modules/custom_fields/**`
- `alembic/**`
- `frontend/**`

---

### Task 1: Build self-contained test fixtures

**Files:**
- Create: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

**Interfaces:**
- Consumes seeded permission rows.
- Consumes `Employee`, `User`, `Role`, `RolePermission`, `UserRoleAssignment`, `ScopeType`.
- Consumes `Organization`, `OPO`, `TechnicalDevice`, `Building`, `CustomFieldDefinition`.
- Produces local helpers only.

- [ ] **Step 1: Add imports and integration marker**

```python
import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.custom_fields.models import CustomFieldDefinition, CustomFieldType
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

- [ ] **Step 2: Add identity helpers**

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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 3: Add domain factories**

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


def _cf_definition(db: Session, *, code: str) -> CustomFieldDefinition:
    definition = CustomFieldDefinition(
        code=code,
        name=f"Field {code}",
        entity_type="opo",
        field_type=CustomFieldType.TEXT,
    )
    db.add(definition)
    db.flush()
    return definition
```

- [ ] **Step 4: Add value-count helper for mutation denial proof**

```python
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

- [ ] **Step 5: Verify collection locally**

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5433/spravoshnik_test"
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py --collect-only -q
```

Expected: collection succeeds and nothing is skipped.

For GitHub-first authoring, the completed test file may be committed before local RED/GREEN execution; GitHub Actions and the user's local PostgreSQL verification provide execution evidence.

---

### Task 2: Prove global reference permission boundaries

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Possible production file: `app/modules/opo/reference_routes.py`

**Interfaces:**
- `GET /api/reference/hazard-signs` -> `opo.view`.
- `GET /api/reference/activity-types` -> `opo.view`.
- `GET /api/reference/technical-device-types` -> `technical_devices.view`.
- `GET /api/reference/building-types` -> `buildings.view`.

- [ ] **Step 1: Add exact reference case table**

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

- [ ] **Step 2: Add 401 and 403 reference tests**

For every row assert unauthenticated `GET` returns `401`. Then create a user granted only `wrong_permission + ALL`; authenticated `GET` must return `403`.

- [ ] **Step 3: Prove matching permission ignores organization scope**

Parameterize `ScopeType.ALL`, `RELATED`, `ASSIGNED`, and `OWN`.

Use `scope_config={"organization_ids": []}` for `RELATED`, otherwise `None`. Grant the matching view permission. Each reference endpoint must return `200`.

- [ ] **Step 4: Prove superuser gets 200 without role grants**

Create a superuser and assert every reference endpoint returns `200`.

- [ ] **Step 5: Run subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k reference
```

If GREEN, production code stays untouched. If RED proves reference permission mapping is wrong, only restore the existing permission-only mapping in `reference_routes.py`; never replace it with `require_scoped_permission()`.

---

### Task 3: Prove VIEW scope cannot borrow unrelated ALL grants

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

- [ ] **Step 1: Organizations**

Arrange:

```text
Role A: organizations.view + RELATED(allowed_org)
Role B: organizations.update + ALL
```

Assert:

```text
GET /api/organizations -> 200; allowed_org present; foreign_org absent
GET /api/organizations/{foreign_org.id} -> 404
```

- [ ] **Step 2: OPO**

Arrange:

```text
Role A: opo.view + RELATED(allowed_org)
Role B: opo.edit + ALL
```

Create one OPO owned/operated by allowed orgs and one whose owner/operator are both foreign. Assert list excludes foreign and `GET /api/opo/{foreign_opo.id}` returns `404`.

- [ ] **Step 3: Technical Device**

Arrange:

```text
Role A: technical_devices.view + RELATED(allowed_org)
Role B: technical_devices.edit + ALL
```

Assert list excludes foreign device and `GET /api/technical-devices/{foreign_device.id}` returns `404`. Scope follows `organization_id`, not linked OPO.

- [ ] **Step 4: Building**

Arrange:

```text
Role A: buildings.view + RELATED(allowed_org)
Role B: buildings.edit + ALL
```

Assert list excludes foreign building and `GET /api/buildings/{foreign_building.id}` returns `404`.

- [ ] **Step 5: Run subset**

Name these tests `test_scope_isolation_view_*` and run:

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k scope_isolation_view
```

---

### Task 4: Prove EDIT scope cannot borrow broader VIEW grants

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

- [ ] **Step 1: Organizations**

Arrange:

```text
Role A: organizations.update + RELATED(allowed_org)
Role B: organizations.view + ALL
```

Execute exactly:

```python
response = client.patch(
    f"/api/organizations/{foreign_org.id}",
    json={"legal_name": "Mutated Foreign Organization"},
    headers=_auth(token),
)
assert response.status_code == 404
db_session.refresh(foreign_org)
assert foreign_org.legal_name == original_name
```

- [ ] **Step 2: OPO**

Arrange `opo.edit + RELATED(allowed_org)` plus `opo.view + ALL`, then execute:

```python
response = client.patch(
    f"/api/opo/{foreign_opo.id}",
    json={"name": "Mutated Foreign OPO"},
    headers=_auth(token),
)
assert response.status_code == 404
db_session.refresh(foreign_opo)
assert foreign_opo.name == original_name
```

- [ ] **Step 3: Technical Device**

Arrange `technical_devices.edit + RELATED(allowed_org)` plus `technical_devices.view + ALL`, then execute:

```python
response = client.patch(
    f"/api/technical-devices/{foreign_device.id}",
    json={"name": "Mutated Foreign Device"},
    headers=_auth(token),
)
assert response.status_code == 404
db_session.refresh(foreign_device)
assert foreign_device.name == original_name
```

- [ ] **Step 4: Building**

Arrange `buildings.edit + RELATED(allowed_org)` plus `buildings.view + ALL`, then execute:

```python
response = client.patch(
    f"/api/buildings/{foreign_building.id}",
    json={"name": "Mutated Foreign Building"},
    headers=_auth(token),
)
assert response.status_code == 404
db_session.refresh(foreign_building)
assert foreign_building.name == original_name
```

- [ ] **Step 5: Run subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k scope_isolation_edit
```

Any RED requiring production edits outside `reference_routes.py` stops this checkpoint as `BLOCKED`.

---

### Task 5: Prove custom-field manage scope cannot borrow OPO view ALL

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

- [ ] **Step 1: Arrange conflicting roles**

```text
Role A: custom_fields.manage + RELATED(allowed_org)
Role B: opo.view + ALL
```

Create a foreign OPO and a text custom-field definition.

- [ ] **Step 2: Prove foreign GET stays 404**

```python
response = client.get(
    f"/api/custom-fields/values/opo/{foreign_opo.id}",
    headers=_auth(token),
)
assert response.status_code == 404
```

- [ ] **Step 3: Prove foreign PUT stays 404 and inserts nothing**

```python
before = _cf_value_count(
    db_session,
    definition_id=definition.id,
    entity_id=foreign_opo.id,
)
response = client.put(
    f"/api/custom-fields/values/opo/{foreign_opo.id}/{definition.id}",
    json={"value": "blocked"},
    headers=_auth(token),
)
assert response.status_code == 404
after = _cf_value_count(
    db_session,
    definition_id=definition.id,
    entity_id=foreign_opo.id,
)
assert after == before
```

- [ ] **Step 4: Run subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k custom_field_scope_isolation
```

---

### Task 6: Prove malformed RELATED configs fail closed

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

- [ ] **Step 1: Add exact malformed cases**

```python
MALFORMED_RELATED_CONFIGS = [
    {"organization_ids": ["not-a-uuid"]},
    {"organization_ids": [str(uuid.uuid4())], "extra": True},
    {"organization_ids": "not-a-list"},
    {"org_ids": [str(uuid.uuid4())]},
]
```

- [ ] **Step 2: Organizations list remains permitted but empty**

For each malformed config grant `organizations.view` through `RELATED`. Assert:

```python
response = client.get("/api/organizations", headers=_auth(token))
assert response.status_code == 200
assert response.json()["total"] == 0
assert response.json()["items"] == []
```

- [ ] **Step 3: Existing details return 404 using the correct requested permission**

For separate test instances/grants cover:

```text
organizations.view -> GET /api/organizations/{existing_id} -> 404
opo.view -> GET /api/opo/{existing_id} -> 404
technical_devices.view -> GET /api/technical-devices/{existing_id} -> 404
buildings.view -> GET /api/buildings/{existing_id} -> 404
custom_fields.manage -> GET /api/custom-fields/values/opo/{existing_id} -> 404
```

The permission exists, so these are not `403` cases.

- [ ] **Step 4: Run subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k malformed_related
```

---

### Task 7: Prove ASSIGNED and OWN deny domain access by default

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

- [ ] **Step 1: Parameterize scopes**

```python
@pytest.mark.parametrize("scope_type", [ScopeType.ASSIGNED, ScopeType.OWN])
```

- [ ] **Step 2: For each scope use the endpoint's real requested permission**

Assert existing objects return `404` for:

```text
organizations.view -> GET /api/organizations/{organization.id}
opo.view -> GET /api/opo/{opo.id}
technical_devices.view -> GET /api/technical-devices/{device.id}
buildings.view -> GET /api/buildings/{building.id}
```

Use `scope_config=None`. Do not invent owner/assignee semantics.

- [ ] **Step 3: Run subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k deny_by_default
```

---

### Task 8: Prove representative 401 and 403 matrices

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

- [ ] **Step 1: Define protected representative endpoints**

Create URLs at test runtime for:

```text
GET /api/organizations
GET /api/opo
GET /api/technical-devices
GET /api/buildings
GET /api/custom-fields/definitions
GET /api/custom-fields/values/opo/<random_uuid>
GET /api/reference/hazard-signs
GET /api/reference/technical-device-types
GET /api/reference/building-types
```

- [ ] **Step 2: Add unauthenticated matrix**

Call every endpoint without session/cookie/header and assert exactly `401`.

- [ ] **Step 3: Add missing-permission matrix using a concrete seeded unrelated permission**

Create one user with exactly:

```text
tasks.view + ALL
```

`tasks.view` is seeded by migration `0002_stage1_identity.py` and is unrelated to every endpoint in this matrix.

Authenticate and assert every endpoint above returns exactly `403`.

- [ ] **Step 4: Run subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k "unauthenticated_matrix or missing_permission_matrix"
```

---

### Task 9: Prove foreign-vs-absent non-enumeration

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`

- [ ] **Step 1: Grant only RELATED access to `allowed_org`**

Use the exact requested permission for each endpoint.

- [ ] **Step 2: Compare existing foreign ID to random absent ID**

Both statuses must be `404` for:

```text
GET /api/organizations/{id}
GET /api/opo/{id}
GET /api/technical-devices/{id}
GET /api/buildings/{id}
GET /api/custom-fields/values/opo/{id}
```

For OPO, foreign owner and operator must both be outside `allowed_org`. For TD/Building, foreign `organization_id` is authoritative even if an OPO link exists.

- [ ] **Step 3: Assert status only**

Do not require identical response text; status non-enumeration is the invariant.

- [ ] **Step 4: Run subset**

```powershell
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q -k non_enumeration
```

---

### Task 10: Execute the evidence-first RED/GREEN gate

**Files:**
- Test: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Possible production file: `app/modules/opo/reference_routes.py`

- [ ] **Step 1: Run complete new matrix before any production edit**

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5433/spravoshnik_test"
python -m pytest tests/integration/test_stage3_cp22f_authorization_matrix.py -q
```

Valid outcomes:

```text
GREEN immediately -> preferred closure outcome; no production edit.
RED only in reference permission behavior -> diagnose and minimally correct reference_routes.py.
RED anywhere else -> BLOCKED; do not widen CP2.2-F.
```

- [ ] **Step 2: If reference RED occurs, capture evidence before editing**

Record failing test, endpoint, requested permission, actual status/body, expected status, scope type, and root cause.

- [ ] **Step 3: Re-run matrix after any allowed reference fix**

Required: `0 failed`, `0 errors`, `0 skipped`.

---

### Task 11: Run authorization checkpoint regressions

**Files:**
- No production change expected.

- [ ] **Step 1: CP2.2-E**

```powershell
python -m pytest tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py -q
```

- [ ] **Step 2: CP2.2-D**

```powershell
python -m pytest tests/integration/test_stage3_cp22d_td_building_http_scope.py -q
```

- [ ] **Step 3: CP2.2-C**

```powershell
python -m pytest tests/integration/test_stage3_cp22c_org_opo_http_scope.py -q
```

- [ ] **Step 4: CP2.2-B**

```powershell
python -m pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
```

- [ ] **Step 5: CP2.2-A**

```powershell
python -m pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
```

- [ ] **Step 6: Legacy authorization API**

```powershell
python -m pytest tests/unit/test_authorization.py -q
```

Every integration invocation must show zero skipped tests.

---

### Task 12: Run full backend and static verification

**Files:**
- No additional change expected.

- [ ] **Step 1: PostgreSQL health**

```powershell
docker compose ps
```

Require both `postgres` and `postgres-test` healthy.

- [ ] **Step 2: Avoid concurrent pytest on the shared test DB**

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "pytest" } |
  Select-Object ProcessId, CommandLine
```

Only stop a stale pytest process when it is known to belong to this project.

- [ ] **Step 3: Full backend suite**

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5433/spravoshnik_test"
python -m pytest -q
```

Baseline was 319 tests; final count must be greater because CP2.2-F adds tests. Required: `0 failed`, `0 errors`, `0 skipped`.

- [ ] **Step 4: Ruff**

```powershell
ruff check tests/integration/test_stage3_cp22f_authorization_matrix.py
```

If `reference_routes.py` changed:

```powershell
ruff check app/modules/opo/reference_routes.py
```

- [ ] **Step 5: Alembic invariant**

```powershell
python -m alembic heads
python -m alembic current
```

Both must report `0010_stage3`.

- [ ] **Step 6: Diff hygiene**

```powershell
git diff --check
git status -sb
git diff --stat 1445d8a...HEAD
git diff 1445d8a...HEAD -- . ":(exclude)docs/superpowers/specs/**" ":(exclude)docs/superpowers/plans/**"
```

Expected implementation diff: the new test file only, plus `reference_routes.py` only if a proven reference RED required it. No frontend or migration diff.

- [ ] **Step 7: GitHub Actions evidence**

The push-triggered CI must show PASS for:

```text
ruff check app tests
alembic upgrade head
pytest
```

If CI fails, inspect the exact job/log before any production change.

---

### Task 13: Commit and hand off the exact implementation SHA

**Files:**
- Add: `tests/integration/test_stage3_cp22f_authorization_matrix.py`
- Add only if proven: `app/modules/opo/reference_routes.py`

- [ ] **Step 1: Test-only closure commit**

```powershell
git add tests/integration/test_stage3_cp22f_authorization_matrix.py
git commit -m "test(stage3 cp2.2-f): close authorization regression matrix"
```

- [ ] **Step 2: Alternative only if reference production fix was proven**

```powershell
git add app/modules/opo/reference_routes.py tests/integration/test_stage3_cp22f_authorization_matrix.py
git commit -m "fix(stage3 cp2.2-f): close authorization boundaries"
```

- [ ] **Step 3: Push only checkpoint branch**

```powershell
git push origin agent/stage3-cp22f-authorization-closure
```

- [ ] **Step 4: User fetches exact SHA**

```powershell
cd D:\Spravoshnik-EPB
git fetch origin --prune
git switch --track origin/agent/stage3-cp22f-authorization-closure
# if it already exists locally:
# git switch agent/stage3-cp22f-authorization-closure
# git pull --ff-only
git rev-parse --short HEAD
git status -sb
```

The local SHA must match the GitHub handoff SHA.

- [ ] **Step 5: Verification Agent report**

Required sections:

```text
Branch / HEAD
TEST_DATABASE_URL set
Docker health
CP2.2-F targeted
CP2.2-E/D/C/B/A regressions
legacy authorization unit
full pytest
Ruff
Alembic heads/current
git diff --check
blocking findings
verdict PASS/FAIL
```

The verifier does not silently edit production code.

- [ ] **Step 6: Security Auditor report**

Audit:

```text
401 before permission/scope
403 for missing requested permission
404 foreign vs absent
cross-role scope borrowing
malformed RELATED fail-closed
ASSIGNED/OWN deny-by-default
global reference permission-only boundary
custom-field parent scope
no schema/frontend/unrelated production changes
```

The auditor reports findings only.

---

## Completion Gate

CP2.2-F is `COMPLETE` only with evidence on the exact implementation SHA:

```text
CP2.2-F matrix              PASS, 0 skipped
CP2.2-E                     PASS, 0 skipped
CP2.2-D                     PASS, 0 skipped
CP2.2-C                     PASS, 0 skipped
CP2.2-B                     PASS, 0 skipped
CP2.2-A                     PASS, 0 skipped
legacy authorization unit   PASS
full PostgreSQL pytest       PASS, 0 failed/errors/skipped
Ruff                         PASS
GitHub Actions               PASS
Alembic heads/current        0010_stage3
frontend diff                none
migration diff               none
unrelated production diff    none
Verification Agent           PASS
Security Auditor             no blocking finding
```

When this gate is satisfied, CP2.2-F closes Stage 3 authorization and becomes the verified security baseline for subsequent product checkpoints.
