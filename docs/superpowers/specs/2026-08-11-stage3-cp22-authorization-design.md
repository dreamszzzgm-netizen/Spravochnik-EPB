# Stage 3 CP2.2 — Authorization & API Hardening Design

Date: 2026-08-11

## Scope

CP2.2 hardens backend authorization for the Stage 3 domain only:

- Organizations
- OPO
- Technical Devices
- Buildings
- Custom Field values attached to Stage 3 entities
- Reference data remains permission-gated but not organization-scoped

Out of scope:

- Stage 3 frontend
- Contracts / Expertise / Tasks authorization
- new domain features
- ASSIGNED/OWN business semantics for Stage 3 entities
- unrelated refactors

## Security semantics

HTTP behavior is fixed as follows:

- unauthenticated / invalid / expired session -> 401
- authenticated but missing required permission -> 403
- authenticated with permission, but the operation itself is not allowed by the caller's scope and there is no foreign object identifier to conceal (for example RELATED creating a new Organization) -> 403
- object exists but is outside the caller's authorized scope -> 404
- object does not exist -> 404
- deleted object through normal endpoint -> 404
- deleted object through restore endpoint but outside scope -> 404

This deliberately makes foreign-object UUIDs indistinguishable from nonexistent UUIDs while preserving 403 for scope-level operation denial where no object existence is disclosed.

## Scope model

Existing `ScopeType` values remain:

- `ALL`
- `RELATED`
- `ASSIGNED`
- `OWN`

Stage 3 semantics:

### ALL

Unrestricted access for the requested permission.

### RELATED

`scope_config` uses exactly:

```json
{
  "organization_ids": ["uuid", "uuid"]
}
```

The allowed organization set is the union of valid `organization_ids` across all active role assignments that grant the requested permission.

### ASSIGNED / OWN

Deny-by-default for Stage 3 objects because current OPO / TechnicalDevice / Building models do not contain an authoritative employee assignment/ownership relation.

No business meaning is inferred.

### Malformed scope_config

Fail closed without causing HTTP 500.

Examples that grant no RELATED access:

- `null`
- missing `organization_ids`
- `organization_ids` not a list
- invalid UUID data in the assignment
- unsupported keys such as `organizations`, `org_ids`, `all`

An empty list grants access to zero organizations.

### Multiple grants

Authorization is additive:

- `RELATED + RELATED` -> union of allowed organization ids
- any active `ALL` grant -> unrestricted
- `RELATED + ASSIGNED` -> RELATED access only
- `ASSIGNED + OWN` -> no Stage 3 object access

There is no deny-role model in CP2.2.

Superuser is treated as unrestricted.

## Authorization architecture

Add a dedicated policy layer under identity, conceptually:

```text
app/modules/identity/
  dependencies.py
  repository.py
  authorization.py   # new
```

`dependencies.py` remains responsible for authentication and permission presence.

`authorization.py` is responsible for object/list scope policy and must not depend on FastAPI HTTP status codes.

### AuthorizationContext

The scoped permission dependency returns a context containing at least:

```text
user_id
employee_id
permission_code
is_superuser
has_all_scope
related_organization_ids: set[UUID]
active_scope_types: set[ScopeType]
```

A new repository query loads active role assignments for one user + one permission, including `scope_type` and `scope_config`.

Only assignments satisfying all of the following participate:

- assignment belongs to current user
- assignment is not revoked
- assignment role grants requested permission

If there is no qualifying grant -> 403.

### Dependencies

Existing `require_permission(permission_code)` remains available for permission-only endpoints.

Add a scoped dependency factory, conceptually:

```python
require_scoped_permission("opo.view")
```

It performs:

1. session authentication
2. permission presence
3. AuthorizationContext construction

Routes receive the context; they do not parse roles or `scope_config` themselves.

## Object policies

Policy functions are pure business/security checks, e.g.:

```text
can_access_organization(ctx, organization)
can_access_opo(ctx, opo)
can_access_technical_device(ctx, device)
can_access_building(ctx, building)
```

### Organization

RELATED access requires:

```text
organization.id in ctx.related_organization_ids
```

### OPO

RELATED access requires at least one of:

```text
opo.owner_organization_id in allowed organizations
opo.operating_organization_id in allowed organizations
```

### Technical Device / Building

RELATED access uses the entity's own `organization_id` only:

```text
entity.organization_id in allowed organizations
```

Do not infer the entity's organization from OPO owner/operator.

Legacy Stage 3 rows with `organization_id IS NULL` are visible to ALL/superuser but not RELATED.

## Operation policy

### Organizations

LIST:

- ALL -> all non-deleted organizations
- RELATED -> allowed organization ids only
- ASSIGNED/OWN-only -> empty list

DETAIL / UPDATE / DELETE / RESTORE:

- ALL -> allowed
- RELATED -> only allowed organizations
- foreign -> 404

CREATE:

- ALL only
- RELATED / ASSIGNED / OWN -> 403

Creation requires ALL because creating a new organization would otherwise let a scoped user create data outside the administrator-controlled organization set.

### OPO

LIST:

- ALL -> all non-deleted OPO
- RELATED -> OPO where owner OR operator is in allowed organization ids

DETAIL / UPDATE / DELETE / RESTORE:

- current OPO must be in scope or 404

CREATE:

- ALL -> normal domain validation
- RELATED -> both owner and operator organizations must be in scope
- any foreign organization reference -> 404
- ASSIGNED/OWN-only -> references are outside the effective Stage 3 scope and therefore resolve as inaccessible (404)

UPDATE:

- current OPO must be in scope
- proposed final owner and operator must both be in scope for RELATED
- failure must not partially mutate the ORM object

### Technical Devices / Buildings

LIST:

- ALL -> all non-deleted rows
- RELATED -> row.organization_id in allowed organization ids

DETAIL / DELETE / RESTORE:

- current row must be in scope or 404

CREATE:

- organization_id must be in scope for RELATED
- if opo_id is supplied, that OPO must also be in scope
- foreign/inaccessible organization or OPO reference -> 404
- existing domain invariant remains: row organization must match OPO owner OR operator

UPDATE:

- current row must be in scope
- proposed new organization_id must be in scope
- proposed new opo_id must be in scope
- existing OPO/organization domain consistency still applies

A RELATED caller may move a TD/Building only between organizations already present in the caller's allowed organization set.

## List filtering

Scope filtering must happen in SQL before count, offset and limit.

Never fetch an unrestricted page and filter it in Python.

Security scope is always combined with user-supplied filters using AND semantics:

```text
security scope
AND endpoint query filters
AND search filters
AND deleted_at IS NULL
```

User-supplied query parameters may narrow scope but must never expand it.

`total` is counted after scope filtering, preventing foreign-record count leakage.

If RELATED has an empty allowed organization set, the SQL query must return zero rows and `total=0`.

## IDOR hardening

For detail/update/delete/restore:

1. authenticate
2. require permission
3. load object
4. nonexistent/deleted -> 404 as appropriate
5. evaluate scope
6. foreign -> 404
7. execute domain operation

For CREATE and PATCH, all security-sensitive foreign keys must be scope-checked before mutation.

Foreign UUIDs and nonexistent UUIDs intentionally return the same 404 behavior once the caller has the relevant permission.

## Validation-before-mutation

Security-sensitive updates use a proposed-state model:

```text
current state + PATCH payload
-> proposed final state
-> authorization validation
-> domain validation
-> mutate ORM object
-> audit
-> commit
```

No partial ORM mutation, success audit entry, or commit may occur after a failed authorization/domain check.

This particularly applies to:

- organization_id
- opo_id
- OPO owner_organization_id
- OPO operating_organization_id
- OPO N:M hazard/activity relations when their update participates in the same operation

## Custom Fields

Definitions remain permission-only management data.

Custom Field values inherit the parent entity's scope.

Stage 3 scoped entity types:

- `opo`
- `technical_device`
- `building`

Before get/set/clear value:

1. require `custom_fields.manage`
2. load the parent entity
3. evaluate parent scope
4. foreign -> 404
5. perform custom field operation

Unknown entity types follow existing domain validation semantics and must never bypass authorization by falling through to an unrestricted lookup.

## Reference Data

Hazard signs, activity types, technical-device types and building types are global reference data, not organization-owned.

They remain permission-gated but do not receive organization scope filtering in CP2.2.

## Regression test matrix

Required negative and positive coverage:

### Authentication / permission

- no session -> 401
- invalid/expired session -> 401
- authenticated without required permission -> 403
- RELATED/ASSIGNED/OWN creating Organization -> 403

### ALL

- list
- detail
- create
- update
- delete
- restore

### RELATED object access

- allowed organization -> accessible
- foreign organization -> 404
- OPO owner allowed -> accessible
- OPO operator allowed -> accessible
- fully foreign OPO -> 404
- allowed TD -> accessible
- foreign TD -> 404
- allowed Building -> accessible
- foreign Building -> 404

### Lists

- foreign rows absent
- total excludes foreign rows
- pagination occurs after security filtering
- user query filters cannot broaden security scope

### Create

- OPO owner+operator allowed -> success
- foreign OPO owner -> 404
- foreign OPO operator -> 404
- TD/Building allowed org -> success
- TD/Building foreign org -> 404
- TD/Building foreign OPO UUID -> 404

### Patch

- current foreign object -> 404
- move allowed -> foreign org -> 404
- change to foreign OPO -> 404
- failed PATCH leaves persisted state unchanged

### Delete / Restore

- foreign object -> 404
- no unauthorized mutation

### Custom Fields

- allowed parent get/set/clear -> allowed
- foreign parent get/set/clear -> 404

### Scope composition

- RELATED union across roles
- ALL overrides RELATED
- malformed config -> deny
- empty allowed set -> deny
- ASSIGNED-only -> deny Stage 3 objects
- OWN-only -> deny Stage 3 objects
- superuser -> unrestricted

## Delivery checkpoints

CP2.2 is delivered as small auditable checkpoints:

1. **CP2.2-A** — AuthorizationContext, scope parser, policy tests
2. **CP2.2-B** — scoped repositories and LIST security
3. **CP2.2-C** — Organization and OPO route authorization
4. **CP2.2-D** — TechnicalDevice / Building authorization and atomic updates
5. **CP2.2-E** — Custom Fields IDOR hardening
6. **CP2.2-F** — full negative security audit and cleanup

After every checkpoint:

- targeted tests
- full relevant test suite
- lint on changed files
- commit and normal push
- independent diff review before proceeding

## Acceptance

CP2.2 is complete only when:

- 401/403/404 semantics above are enforced
- permission-only access cannot bypass scope
- RELATED is constrained strictly by `scope_config.organization_ids`
- malformed scope config fails closed
- ASSIGNED/OWN do not fabricate semantics
- lists are SQL-scoped and totals do not leak foreign counts
- create/update foreign-key IDOR paths are blocked
- failed security-sensitive updates are atomic
- Custom Field values inherit parent scope
- superuser/ALL behavior remains correct
- full regression suite is green
- no unrelated frontend or domain feature work is included
