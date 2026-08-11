# Stage 3 CP2.2-C Organizations + OPO HTTP Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the approved scoped authorization model at all Organizations and OPO HTTP endpoints while preserving 401/403/404 semantics and CP2.2-B SQL-scoped lists.

**Architecture:** Replace permission-only dependencies in the Organizations and OPO routers with `require_scoped_permission()`. Lists pass the resulting `AuthorizationContext` into the CP2.2-B repositories. Object endpoints fetch normally, then apply the pure policy functions before any mutation; inaccessible objects and inaccessible referenced organization UUIDs return 404. Organization collection create remains ALL-only and returns 403 for a user who has `organizations.create` but lacks ALL scope.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Pydantic v2, pytest.

## Global Constraints

- Base commit: `d599ab2b0f4aeb398517e86d70108310046a8bb5`.
- Branch: `pilot/opencode-cp22c`.
- Modify only `app/modules/organizations/routes.py`, `app/modules/opo/routes.py`, and the new CP2.2-C integration test unless a genuine blocker is reported before editing another file.
- Do not modify repositories, services, schemas, identity core, Alembic, frontend, or old tests.
- No force push, rebase, or reset of published history.
- No HTTP mutation may happen before scope checks on the current object and any newly referenced organization IDs.
- 401 = missing/invalid authentication; 403 = requested permission absent; 404 = object/reference exists outside requested permission scope or object is absent.

---

### Task 1: Add HTTP scope regression tests

**Files:**
- Create: `tests/integration/test_stage3_cp22c_org_opo_http_scope.py`

**Interfaces:**
- Consumes: `require_scoped_permission`, `AuthorizationContext`, existing `/api/organizations` and `/api/opo` routes.
- Produces: regression coverage proving scoped list/detail/create/update/delete/restore and nested Organization resources.

- [ ] Create helper functions that create a normal user, one role, requested permission codes, and one `UserRoleAssignment` with an exact `ScopeType` and `scope_config={"organization_ids": [...]}`.
- [ ] Cover Organizations: RELATED list excludes foreign and scopes `total`; detail foreign -> 404; create with RELATED -> 403; update/delete/restore foreign -> 404; foreign parent_id on an allowed organization update -> 404 and leaves parent unchanged; contacts and identifiers cannot bypass parent organization scope.
- [ ] Cover OPO: RELATED list includes allowed owner OR allowed operator and excludes fully foreign; detail foreign -> 404; create requires both owner and operator referenced organizations in scope; update of an allowed OPO rejects a newly supplied foreign owner/operator UUID with 404 and leaves row unchanged; delete/restore foreign -> 404.
- [ ] Run the new file before production changes and record the representative RED failures.

Run:
```powershell
pytest tests/integration/test_stage3_cp22c_org_opo_http_scope.py -q
```

Expected before implementation: failures showing lists/details are still permission-only and/or routes do not pass `AuthorizationContext`.

---

### Task 2: Scope all Organization HTTP endpoints

**Files:**
- Modify: `app/modules/organizations/routes.py`

**Interfaces:**
- Consumes: `AuthorizationContext`, `can_access_organization`, `can_create_organization`, `can_reference_organizations`, `require_scoped_permission`.
- Produces: Organizations router with scope enforcement for list/detail/create/update/delete/restore/contacts/identifiers.

- [ ] Replace `require_permission`/`User` route dependencies with permission-specific `AuthorizationContext` dependencies from `require_scoped_permission()`.
- [ ] Change `_organization_or_404` to receive an `AuthorizationContext` and return 404 when the row is absent or `can_access_organization()` is false.
- [ ] Pass the `organizations.view` context to `list_organizations_paginated(..., authorization=authorization)`.
- [ ] For `POST /api/organizations`, require `organizations.create`; if `can_create_organization()` is false, raise 403 `Permission denied`; use `authorization.user_id` as `actor_id`.
- [ ] For PATCH, check current object scope first. If `parent_id` is explicitly present and non-null, require `can_reference_organizations(authorization, parent_id)` or return 404. Preserve the existing parent when the field is omitted by passing `organization.parent_id` instead of an implicit `None`.
- [ ] Apply `organizations.manage_contacts` context to contact create/update/delete/set-primary; apply `organizations.manage_identifiers` to identifier create/delete; apply `organizations.view` to nested reads.

Required PATCH parent handling:
```python
parent_id = (
    payload.parent_id
    if "parent_id" in payload.model_fields_set
    else organization.parent_id
)
if (
    "parent_id" in payload.model_fields_set
    and payload.parent_id is not None
    and not can_reference_organizations(authorization, payload.parent_id)
):
    raise HTTPException(status_code=404, detail="Organization not found")
```

---

### Task 3: Scope all OPO HTTP endpoints

**Files:**
- Modify: `app/modules/opo/routes.py`

**Interfaces:**
- Consumes: `AuthorizationContext`, `can_access_opo`, `can_reference_organizations`, `require_scoped_permission`.
- Produces: OPO router with scope enforcement for list/detail/create/update/delete/restore.

- [ ] Replace permission-only dependencies with `require_scoped_permission()` contexts for `opo.view`, `opo.create`, `opo.edit`, `opo.delete`, and `opo.restore`.
- [ ] Change `_opo_or_404` to receive an `AuthorizationContext`; absent or out-of-scope returns 404.
- [ ] Pass `authorization` into `list_opo_paginated` so CP2.2-B SQL scoping is active at HTTP level.
- [ ] On create, before calling the service, require BOTH `owner_organization_id` and `operating_organization_id` through `can_reference_organizations`; otherwise return 404 `Organization not found`.
- [ ] On update, check current OPO scope first. Only organization IDs explicitly supplied by the PATCH need a reference-scope check. Do not require an already-existing foreign owner/operator counterpart to be in scope when that field is not being changed.

Required update checks:
```python
if (
    payload.owner_organization_id is not None
    and not can_reference_organizations(
        authorization,
        payload.owner_organization_id,
    )
):
    raise HTTPException(status_code=404, detail="Organization not found")

if (
    payload.operating_organization_id is not None
    and not can_reference_organizations(
        authorization,
        payload.operating_organization_id,
    )
):
    raise HTTPException(status_code=404, detail="Organization not found")
```

- [ ] Use `authorization.user_id` for audit actor IDs.

---

### Task 4: Verify and publish

- [ ] Run:
```powershell
pytest tests/integration/test_stage3_cp22c_org_opo_http_scope.py -q
pytest tests/integration/test_stage3_cp22b_scoped_repositories.py -q
pytest tests/integration/test_stage3_cp22a_authorization_core.py -q
pytest tests/unit/test_authorization.py -q
pytest tests/integration/test_stage3_cp21_http_api.py -q
pytest
ruff check app/modules/organizations/routes.py app/modules/opo/routes.py tests/integration/test_stage3_cp22c_org_opo_http_scope.py
git diff --check
alembic heads
```
- [ ] Require 0 pytest failures/errors, Ruff clean, and a single Alembic head `0010_stage3`.
- [ ] Confirm diff contains only the two routers plus the new CP2.2-C test.
- [ ] Commit:
```powershell
git add app/modules/organizations/routes.py app/modules/opo/routes.py tests/integration/test_stage3_cp22c_org_opo_http_scope.py
git commit -m "feat(stage3 cp2.2-c): enforce organization and opo HTTP scope"
git push origin pilot/opencode-cp22c
```
- [ ] Return commit SHA, exact changed files, RED evidence, targeted/full test outputs, Ruff, Alembic head, and `git status`.
