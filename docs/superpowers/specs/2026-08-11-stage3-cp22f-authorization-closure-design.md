# Stage 3 CP2.2-F Authorization Closure — Design

## Status

Approved for implementation planning.

## Baseline

- Repository: `dreamszzzgm-netizen/Spravochnik-EPB`
- Baseline branch: `codex/feat-gigastudio-frontend-integration`
- Baseline commit: `1445d8a2f9364c47a590a52e64e429bdd953cf75`
- Alembic head/current: `0010_stage3`
- Backend baseline: `319 passed`, `0 failed`, `0 skipped`
- Frontend baseline: `75 passed`, typecheck PASS, lint PASS, production build PASS
- PostgreSQL main/test containers: healthy

CP2.2-F starts from this verified baseline and must not depend on unmerged work from `pilot/opencode-cp22c` or other pilot branches.

## Goal

Close Stage 3 authorization by adding a final cross-module integration regression matrix that proves the security invariants established by CP2.2-A through CP2.2-E.

This is primarily a verification checkpoint, not a feature checkpoint. The intended successful outcome is that the new matrix passes against the existing production code. Production code may change only when a new failing test demonstrates a real authorization defect within the explicitly allowed scope.

## Non-goals

CP2.2-F does not:

- add business functionality;
- add or change database tables, columns, constraints, or migrations;
- change frontend behavior;
- add new permission codes or scope types;
- invent semantics for `ASSIGNED` or `OWN` on Stage 3 organization-owned domain entities;
- change the meaning of existing `RELATED` scope configuration;
- begin Contracts, CP2.3, or any next product feature;
- merge or cherry-pick the old `pilot/opencode-cp22c` branch.

## Authorization model being proven

### Authentication and permission boundary

Representative protected routes must preserve the following boundary:

- unauthenticated or invalid session -> `401`;
- authenticated user without the requested permission -> `403`;
- authenticated user with the requested permission but outside the object's usable scope -> `404`;
- absent or deleted scoped domain object -> `404`.

For scoped domain objects, foreign and absent identifiers must not become distinguishable through status codes.

### Requested-permission isolation

Authorization scope is computed from role assignments that grant the permission requested by the current action. A broader scope attached to another permission must not widen access.

Examples:

- `organizations.view + RELATED(org A)` must not become `ALL` because another role grants `organizations.update + ALL`;
- `opo.edit + RELATED(org A)` must not become `ALL` because another role grants `opo.view + ALL`;
- `custom_fields.manage + RELATED(org A)` must not be widened by `opo.view + ALL`.

This invariant applies independently to Organizations, OPO, Technical Devices, Buildings, and parent-scoped custom-field values.

### RELATED scope

`RELATED` remains strict and fail-closed.

Only a scope config with exactly the supported `organization_ids` list and valid UUID strings contributes usable organization IDs. Malformed, extra-key, wrong-key, wrong-type, or invalid-UUID configs grant the permission but contribute an empty usable organization set.

Consequences:

- list operations return an empty scoped result rather than broadening access;
- existing domain detail operations return `404`;
- custom-field values on inaccessible parents return `404`.

### ASSIGNED and OWN

For the Stage 3 entities covered by this checkpoint, `ASSIGNED` and `OWN` have no implemented ownership/assignment semantics. They therefore remain deny-by-default for scoped domain access.

The checkpoint must prove this behavior instead of inventing new ownership rules.

### Domain ownership rules

- Organization access is based on `organization.id`.
- OPO access is allowed when either owner organization or operating organization is in the usable related organization set.
- Technical Device access is based only on `technical_devices.organization_id`; linked OPO access must not widen device scope.
- Building access is based only on `buildings.organization_id`; linked OPO access must not widen building scope.
- Custom-field values are authorized through their existing parent entity before values are read, written, or cleared.

### Global reference resources

Reference data remains global and permission-only, not organization-scoped.

Expected permissions:

- hazard signs / activity types -> `opo.view`;
- technical-device types -> `technical_devices.view`;
- building types -> `buildings.view`.

Once the matching permission exists, the user's scope type does not filter reference rows. `RELATED` with an empty organization set, `ASSIGNED`, and `OWN` still allow the global reference endpoint because those endpoints intentionally use permission-only authorization.

Create permission alone does not imply the matching view permission. Frontend CP2.1 already decouples optional lookup loading so create forms remain usable when these global reference lookups return `403`.

Custom-field definitions likewise remain global and permission-only. Custom-field values remain parent-scoped.

## Implementation boundary

### Required new test file

Create:

`tests/integration/test_stage3_cp22f_authorization_matrix.py`

The file should reuse established fixture patterns from CP2.2-C/D/E but keep its own focused setup helpers so the final matrix is readable and independently understandable.

### Production changes

No production change is expected.

A production change is allowed only when a newly added CP2.2-F test first demonstrates a real defect and the defect is confined to the existing global reference permission behavior in:

`app/modules/opo/reference_routes.py`

If a failing matrix test exposes a defect in Organizations, OPO, Technical Devices, Buildings, Custom Fields, Identity, repository scope, or another production module, CP2.2-F must stop and report the blocker instead of silently widening scope.

## Test matrix

The final integration matrix must cover five groups.

### 1. Global reference permission boundaries

For each relevant reference endpoint prove:

- no authentication -> `401`;
- wrong/unrelated permission -> `403`;
- matching view permission -> `200`;
- matching view permission with `RELATED` empty set -> `200`;
- matching view permission with `ASSIGNED` -> `200`;
- matching view permission with `OWN` -> `200`;
- superuser -> `200`.

Also prove that create permission without the matching view permission still returns `403` for the reference endpoint.

### 2. Cross-role requested-permission isolation

For Organizations, OPO, Technical Devices, and Buildings prove both directions:

- unrelated `ALL` permission cannot widen a requested scoped VIEW;
- an `ALL` VIEW grant cannot widen a requested scoped EDIT.

For custom-field values prove that an unrelated broader OPO permission cannot widen `custom_fields.manage`.

Mutation tests must verify that denied foreign operations leave the database unchanged.

### 3. Fail-closed scope behavior

Prove malformed `RELATED` configs remain permission-bearing but contribute no usable organization IDs.

At minimum cover:

- invalid UUID;
- extra key;
- `organization_ids` not a list;
- wrong key name.

Prove `ASSIGNED` and `OWN` deny domain detail access by default.

### 4. 401 / 403 matrix

Parameterize representative protected endpoints from:

- Organizations;
- OPO;
- Technical Devices;
- Buildings;
- custom-field definitions;
- custom-field values;
- OPO reference data;
- Technical Device reference data;
- Building reference data.

Authentication must be evaluated before permission/object scope, and missing requested permission must produce `403` before object existence is used for authorization.

### 5. Foreign-vs-absent non-enumeration

For scoped GET operations compare an existing foreign UUID with a random absent UUID. Both must produce `404` for:

- Organization;
- OPO;
- Technical Device;
- Building;
- custom-field values on an OPO parent.

Status equivalence is required; identical response text is not required unless an existing route contract already guarantees it.

## Verification strategy

CP2.2-F uses evidence-first RED/GREEN discipline.

1. Add the completed matrix without modifying production code.
2. Run the matrix with a real PostgreSQL test database and `TEST_DATABASE_URL` set.
3. Immediate GREEN is a valid and preferred outcome for this closure checkpoint.
4. If RED occurs, record the exact failing invariant and root cause before any production edit.
5. Only the explicitly allowed reference-route file may be changed inside CP2.2-F; other defects become blockers/new focused fixes.
6. Re-run CP2.2-F targeted tests.
7. Re-run CP2.2-A through CP2.2-E authorization regressions and authorization unit tests.
8. Run the full PostgreSQL pytest suite exactly once with no skipped integration tests.
9. Run Ruff on the new test file and any allowed production file changed.
10. Verify `git diff --check`, Alembic remains `0010_stage3`, and the branch contains no frontend or migration changes.

## Acceptance criteria

CP2.2-F is COMPLETE only when all of the following are true:

- final authorization matrix: `0 failed`, `0 errors`, `0 skipped`;
- CP2.2-A/B/C/D/E regression suites: PASS with no skipped integration tests;
- authorization unit tests: PASS;
- full backend PostgreSQL suite: `0 failed`, `0 errors`, `0 skipped`;
- Ruff: PASS for checkpoint files;
- Alembic remains exactly `0010_stage3`;
- no frontend changes;
- no schema/migration changes;
- no unrelated production changes;
- branch diff is limited to the checkpoint scope;
- independent local Verification Agent reports PASS;
- independent Security Auditor reports no blocking finding.

## Handoff model

Primary development happens on GitHub branch:

`agent/stage3-cp22f-authorization-closure`

The user fetches the exact resulting commit into `D:\Spravoshnik-EPB` and verifies the SHA before running local agents.

Local agents do not silently repair production code. They return structured findings. Any repair is made deliberately in the GitHub checkpoint branch, producing a new commit that is then re-verified.

When all gates pass, CP2.2-F closes Stage 3 authorization and becomes the verified security baseline for subsequent product checkpoints.
