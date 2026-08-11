# Stage 3 CP2.2-E — Custom Fields Parent Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Custom Fields IDOR by enforcing the scoped `custom_fields.manage` authorization context against the concrete OPO / Technical Device / Building parent before reading, setting, or clearing values.

**Architecture:** Keep custom field definitions global and permission-only. For value endpoints, build `AuthorizationContext` from `custom_fields.manage`, resolve the parent using existing Stage 3 repositories, and apply the existing `can_access_opo`, `can_access_technical_device`, and `can_access_building` policies before the service is called. Unknown entity types remain validation errors (422); absent, deleted, or foreign parents are masked as 404.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, PostgreSQL 17, pytest, existing Stage 3 identity authorization helpers.

## Global Constraints

- Working branch: `pilot/opencode-cp22c`.
- Expected base before implementation: `0f970fa` plus this plan commit.
- Backend only. Do not touch `frontend/`.
- No Alembic/schema/model changes.
- Do not change identity authorization semantics.
- Do not require separate `opo.view`, `technical_devices.view`, `buildings.view`, or `organizations.view` permissions for custom field operations.
- `GET /api/custom-fields/definitions` remains global permission-only via `require_permission("custom_fields.manage")`.
- `GET/PUT/DELETE /api/custom-fields/values/...` use `require_scoped_permission("custom_fields.manage")`.
- Stage 3 parent scope semantics are reused exactly: OPO owner OR operator; TD/Building own `organization_id`; null-organization legacy TD/Building is invisible to RELATED; ALL/superuser is unrestricted.
- Foreign/absent/deleted parent => 404.
- Unknown `entity_type` => 422 on read/set/clear.
- No mutation, audit success event, flush, or commit may occur for an out-of-scope parent.
- PostgreSQL integration tests must execute, not skip.

---

### Task 1: Add failing Custom Fields parent-scope integration tests

**Files:**
- Create: `tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py`

**Interfaces:**
- Consumes: `require_scoped_permission("custom_fields.manage")`, existing Stage 3 entities and authorization scope fixtures/patterns.
- Produces: regression contract for OPO/TD/Building parent scope and mutation safety.

- [ ] **Step 1: Create helpers for scoped users and parent entities**

Use the same patterns as CP2.2-C/D tests: create users, roles, permission grants, RELATED/ALL scope assignments, organizations, OPOs, technical devices, buildings, and session tokens. Seed or create a `CustomFieldDefinition` directly in the DB so the test focuses on value authorization.

- [ ] **Step 2: Write failing OPO tests**

Cover:

```text
RELATED owner organization -> GET values 200
RELATED operating organization -> GET values 200
fully foreign OPO -> GET 404
fully foreign OPO -> PUT 404 and no value inserted
fully foreign OPO with pre-existing value -> DELETE 404 and value remains
```

- [ ] **Step 3: Write failing Technical Device tests**

Cover:

```text
TD organization allowed -> GET/PUT/DELETE works
TD organization foreign -> GET 404
TD organization foreign but linked OPO is accessible -> still 404
foreign PUT -> no value inserted
foreign DELETE -> pre-existing value remains
```

- [ ] **Step 4: Write failing Building tests**

Cover the same own-organization rule as TD, including the case where a linked OPO is accessible but the building's own `organization_id` is foreign.

- [ ] **Step 5: Write boundary tests**

Cover:

```text
RELATED empty organization_ids -> known parent 404
ALL scope -> known parents accessible
superuser -> known parents accessible
deleted OPO/TD/Building -> 404
unknown entity_type -> 422 for GET
unknown entity_type -> 422 for PUT
unknown entity_type -> 422 for DELETE
no custom_fields.manage permission -> 403
no authentication -> 401
```

- [ ] **Step 6: Run RED**

Run:

```powershell
pytest tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py -q
```

Expected: tests for foreign/unknown parent behavior fail because current value routes only check permission presence and do not resolve scoped parents consistently.

---

### Task 2: Add a route-level scoped parent resolver

**Files:**
- Modify: `app/modules/custom_fields/routes.py`
- Test: `tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py`

**Interfaces:**
- Consumes:
  - `AuthorizationContext`
  - `can_access_opo`
  - `can_access_technical_device`
  - `can_access_building`
  - `get_opo`
  - `get_technical_device`
  - `get_building`
- Produces: one private route helper that validates entity type, existence/deleted state, and scope before any value service call.

- [ ] **Step 1: Import existing authorization and repository helpers**

Use the existing Stage 3 helpers only; do not add authorization functions in `identity/authorization.py`.

- [ ] **Step 2: Add strict entity-type validation**

The helper must recognize exactly:

```python
{"opo", "technical_device", "building"}
```

For any other value, raise:

```python
HTTPException(status_code=422, detail="Unsupported entity type ...")
```

The exact detail may reuse the current service wording, but all three value endpoints must consistently return 422 instead of 500 or silently querying arbitrary custom-field rows.

- [ ] **Step 3: Resolve and authorize known parents**

Implement equivalent behavior to:

```python
def _parent_or_404(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    authorization: AuthorizationContext,
) -> object:
    if entity_type == "opo":
        entity = get_opo(db, entity_id)
        allowed = entity is not None and can_access_opo(authorization, entity)
    elif entity_type == "technical_device":
        entity = get_technical_device(db, entity_id)
        allowed = entity is not None and can_access_technical_device(authorization, entity)
    elif entity_type == "building":
        entity = get_building(db, entity_id)
        allowed = entity is not None and can_access_building(authorization, entity)
    else:
        raise HTTPException(status_code=422, detail=...)

    if not allowed:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity
```

Repository defaults must exclude soft-deleted parents. Do not use `include_deleted=True` for normal custom-field value operations.

- [ ] **Step 4: Convert value endpoints to scoped dependency**

For `read_values`, `set_value`, and `clear_value`, replace `require_permission("custom_fields.manage")` with:

```python
require_scoped_permission("custom_fields.manage")
```

Use `AuthorizationContext` as the dependency result. Call `_parent_or_404(...)` before `service.get_values`, `service.set_value`, or `service.clear_value`.

- [ ] **Step 5: Preserve definition endpoint semantics**

Do not change `GET /definitions`: it remains `require_permission("custom_fields.manage")` and is not organization-scoped.

- [ ] **Step 6: Preserve actor ID**

For set/clear audit calls use:

```python
actor_id=authorization.user_id
```

No service/API schema change is required.

---

### Task 3: Verify mutation safety and regressions

**Files:**
- Modify only if a failing test proves necessary: `app/modules/custom_fields/routes.py`
- Test: `tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py`

**Interfaces:**
- Consumes: Task 1 tests and Task 2 resolver.
- Produces: verified 401/403/404/422 behavior and no foreign-parent mutation.

- [ ] **Step 1: Run the CP2.2-E suite**

```powershell
pytest tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py -q
```

Expected: all tests pass, none skipped.

- [ ] **Step 2: Verify foreign PUT and DELETE do not mutate**

The tests must explicitly refresh/query `CustomFieldValue` after the 404 and prove:

```text
foreign PUT -> row absent
foreign DELETE -> row still present with same typed value
```

- [ ] **Step 3: Run Stage 3 regressions**

```powershell
pytest tests/integration/test_stage3_cp22d_td_building_http_scope.py -q
pytest tests/integration/test_stage3_cp22c_org_opo_http_scope.py -q
pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
pytest tests/integration/test_stage3_cp21_http_api.py -q
pytest tests/integration/test_stage3_cp211_service_regressions.py -q
pytest tests/unit/test_authorization.py -q
```

- [ ] **Step 4: Run the full suite**

```powershell
pytest
```

Required: zero failures/errors; integration tests execute against `postgres-test`.

- [ ] **Step 5: Static verification**

```powershell
ruff check app/modules/custom_fields/routes.py tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py
git diff --check
alembic heads
git status
git diff --stat
git diff
```

Required Alembic head: `0010_stage3`.

---

### Task 4: Commit and push the isolated checkpoint

**Files:**
- `app/modules/custom_fields/routes.py`
- `tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py`

- [ ] **Step 1: Confirm scope**

Implementation diff must contain only the two files above. If service, repository, identity, migrations, or frontend changes appear, stop and explain why before committing.

- [ ] **Step 2: Commit**

```powershell
git add app/modules/custom_fields/routes.py tests/integration/test_stage3_cp22e_custom_fields_parent_scope.py
git commit -m "feat(stage3 cp2.2-e): scope custom fields to parent entities"
```

- [ ] **Step 3: Push**

```powershell
git push origin pilot/opencode-cp22c
```

Do not merge, rebase, force-push, or start CP2.2-F.

## Self-review

- Spec coverage: definitions remain global; all value operations scope parent first; OPO/TD/Building semantics match CP2.2-A/B/C/D; unknown type 422; foreign mutations prevented.
- Placeholder scan: no TODO/TBD placeholders.
- Type consistency: uses existing `AuthorizationContext` and existing repository/policy function names.
- Scope: exactly one route file plus one new integration-test file unless a proven blocker requires otherwise.
