# Stage 3 CP2.2-D Technical Devices + Buildings HTTP Scope and Atomic PATCH Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) and superpowers:test-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Enforce scoped HTTP authorization for Technical Devices and Buildings and refactor relation PATCH handling so all authorization/domain validation happens before ORM mutation, audit, flush, or commit.

**Architecture:** Routes obtain one `AuthorizationContext` for the requested action using `require_scoped_permission`. Lists pass it into the CP2.2-B scoped repositories; object endpoints mask out-of-scope entities as 404. Create/PATCH explicitly authorize organization and OPO references with the same action context. Services compute the proposed final relation state, validate referenced rows and organization↔OPO consistency, and only then mutate ORM fields.

**Tech Stack:** FastAPI, SQLAlchemy 2.x ORM, PostgreSQL, pytest, Ruff.

## Global Constraints

- Branch: `pilot/opencode-cp22c`.
- Starting implementation base before this plan: `3c56374`.
- No Alembic migration.
- Preserve permission codes exactly: `technical_devices.view/create/edit/delete/restore`, `buildings.view/create/edit/delete/restore`.
- 401 unauthenticated; 403 permission absent; 404 object/reference outside action scope or absent.
- TD/Building object scope is based only on their own `organization_id`, never inferred from their OPO.
- Legacy `organization_id IS NULL` remains visible only to ALL/superuser and invisible to RELATED lists/objects.
- `organization_id` explicitly set to null on PATCH remains 422.
- If `opo_id` is supplied and non-null on create/PATCH, that OPO must itself be accessible under the same action context.
- A relation-changing PATCH must validate the proposed final `organization_id + opo_id` before mutating ORM state.
- A PATCH that does not change `organization_id` or `opo_id` must not newly fail because of an unrelated legacy relation inconsistency.
- No audit event, flush, or commit before all relation validation succeeds.

---

## File Map

**Modify**
- `app/modules/technical_devices/routes.py` — scoped HTTP dependency, object masking, reference authorization.
- `app/modules/buildings/routes.py` — same for Buildings.
- `app/modules/technical_devices/service.py` — proposed-state relation validation before mutation.
- `app/modules/buildings/service.py` — proposed-state relation validation before mutation.

**Create**
- `tests/integration/test_stage3_cp22d_td_building_http_scope.py` — HTTP scope + atomicity regression matrix.

Do not modify repositories, schemas, identity authorization/dependencies, Alembic, frontend, or existing tests.

---

### Task 1: RED — scoped HTTP regression matrix

- [ ] Create `tests/integration/test_stage3_cp22d_td_building_http_scope.py` using the existing Stage 3 integration fixtures and helper style.
- [ ] Cover Technical Devices:
  - RELATED list returns only rows whose own `organization_id` is allowed; scoped `total` is not leaked.
  - A device whose `organization_id` is foreign remains hidden even if its OPO is accessible through an allowed owner/operator organization.
  - foreign detail/update/delete/restore => 404.
  - create with foreign `organization_id` => 404.
  - create with allowed organization + foreign/non-accessible OPO => 404.
  - create with allowed organization + accessible matching OPO => 201.
  - PATCH explicit `organization_id: null` => 422.
  - PATCH move to foreign organization => 404 and DB unchanged.
  - PATCH link to foreign/non-accessible OPO => 404 and DB unchanged.
  - PATCH relation combination that is scope-allowed but domain-invalid (`OPO does not belong to final organization`) => 404 and DB unchanged, including unrelated scalar fields supplied in the same request.
  - PATCH scalar-only field on an accessible record does not re-authorize unchanged relation references.
- [ ] Cover Buildings with the same security/atomicity cases.
- [ ] Run only the new test file and record the expected RED failures caused by current `require_permission` routes / missing scoped context / mutation-before-validation behavior.

Expected RED command:

```powershell
pytest tests/integration/test_stage3_cp22d_td_building_http_scope.py -q
```

---

### Task 2: Technical Device HTTP scope

- [ ] In `technical_devices/routes.py` import:

```python
from app.modules.identity.authorization import (
    AuthorizationContext,
    can_access_opo,
    can_access_technical_device,
    can_reference_organizations,
)
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.opo.repository import get_opo
```

- [ ] Replace action dependencies with reusable scoped dependencies for view/create/edit/delete/restore.
- [ ] Change `_device_or_404` to accept `AuthorizationContext`; after fetching, return 404 when `can_access_technical_device(ctx, device)` is false.
- [ ] LIST passes `authorization=authorization` to `list_technical_devices_paginated` before user filters/count/pagination are applied by the repository.
- [ ] CREATE:
  - if `can_reference_organizations(ctx, payload.organization_id)` is false => 404 before service call;
  - if `payload.opo_id` is non-null, fetch active OPO with `get_opo`; missing/deleted or `not can_access_opo(ctx, opo)` => 404 before service call;
  - call service with `actor_id=authorization.user_id`.
- [ ] PATCH:
  - scoped-fetch current device first;
  - preserve current 422 for explicit null `organization_id`;
  - if new organization is explicitly supplied and not action-scope-accessible => 404;
  - if new non-null OPO is explicitly supplied, require an existing active OPO and `can_access_opo` under the same edit context, else 404;
  - perform all route authorization checks before calling service.
- [ ] DELETE/RESTORE use scoped fetch and `authorization.user_id`.

---

### Task 3: Building HTTP scope

Apply the same pattern in `buildings/routes.py` using:

```python
AuthorizationContext
can_access_building
can_access_opo
can_reference_organizations
require_scoped_permission
get_opo
```

- [ ] LIST passes scoped context to `list_buildings_paginated`.
- [ ] CREATE authorizes organization and optional OPO references before service.
- [ ] PATCH scoped-fetches current Building, preserves explicit-null organization 422, authorizes newly supplied organization and OPO references before service.
- [ ] DELETE/RESTORE mask foreign object as 404.

---

### Task 4: Technical Device proposed-state validation before mutation

Refactor `TechnicalDeviceService.update_technical_device` without changing its public signature.

- [ ] Compute relation flags and proposed values first:

```python
relation_changed = organization_id_provided or opo_id_provided
final_organization_id = (
    organization_id if organization_id_provided else device.organization_id
)
final_opo_id = opo_id if opo_id_provided else device.opo_id
```

- [ ] Before assigning any field on `device`:
  - when `organization_id_provided`, reject null, then require existing active Organization;
  - when `opo_id_provided and final_opo_id is not None`, require existing active OPO;
  - only when `relation_changed and final_opo_id is not None and final_organization_id is not None`, load final OPO if not already loaded and require final organization to equal its owner or operator.
- [ ] Do not call `db.flush()` before these checks.
- [ ] Only after all validations pass, calculate `changed` and assign name/type/serial/relation fields.
- [ ] Write audit and commit only if `changed` is non-empty.
- [ ] Scalar-only PATCH (`relation_changed == False`) must preserve previous behavior and must not newly validate unchanged OPO relation.

---

### Task 5: Building proposed-state validation before mutation

Refactor `BuildingService.update_building` with the same pipeline:

```text
CURRENT + PATCH
→ proposed final organization/OPO
→ validate explicit refs
→ validate final organization↔OPO only when a relation field changes
→ mutate fields
→ audit
→ commit
```

Preserve the current public signature and current 422 semantics at the route for explicit null organization.

---

### Task 6: GREEN + regressions

Run:

```powershell
pytest tests/integration/test_stage3_cp22d_td_building_http_scope.py -q
pytest tests/integration/test_stage3_cp22c_org_opo_http_scope.py -q
pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
pytest tests/unit/test_authorization.py -q
pytest tests/integration/test_stage3_cp21_http_api.py -q
pytest
```

Then:

```powershell
ruff check app/modules/technical_devices/routes.py app/modules/buildings/routes.py app/modules/technical_devices/service.py app/modules/buildings/service.py tests/integration/test_stage3_cp22d_td_building_http_scope.py
git diff --check
alembic heads
```

Expected Alembic head remains exactly `0010_stage3`.

---

### Task 7: Commit boundary

Only these implementation files may be committed after this plan:

```text
app/modules/technical_devices/routes.py
app/modules/buildings/routes.py
app/modules/technical_devices/service.py
app/modules/buildings/service.py
tests/integration/test_stage3_cp22d_td_building_http_scope.py
```

Commit message:

```text
feat(stage3 cp2.2-d): secure device and building mutations
```

Push only to `origin/pilot/opencode-cp22c` and stop for independent audit. Do not start CP2.2-E.