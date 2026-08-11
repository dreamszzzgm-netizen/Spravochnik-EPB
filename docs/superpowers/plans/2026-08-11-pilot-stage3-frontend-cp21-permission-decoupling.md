# Stage 3 Frontend CP2.1 Permission-Decoupling Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** Ensure OPO, Technical Device, and Building create forms remain usable when the user has the relevant `*.create` permission but lacks optional supporting-data `*.view` permissions, while aligning frontend field lengths with backend schemas.

**Architecture:** Keep backend as the security boundary and make supporting lookups optional in the frontend. `opo.view` controls whether OPO/reference lookup data is requested; `organizations.view` controls whether the OPO form can offer organization choices beyond the current organization. Failure to load optional supporting data must never disable creation of a valid current-organization / no-OPO payload.

**Tech Stack:** Next.js 16, React 19, TypeScript, existing `useCan`, existing API resources, Vitest source-analysis tests.

## Global Constraints

- Frontend-only hotfix: do not modify `app/**`, Alembic, backend tests, database, or backend permissions.
- Do not change backend endpoint contracts.
- Preserve backend as the authoritative authorization boundary.
- Do not begin CP3 edit/detail/delete work.
- No new npm dependencies.
- `registration_number` frontend max length must be 100 to match `OPOCreate`.
- Technical Device `serial_number` frontend max length must be 100 to match `TechnicalDeviceCreate`.

---

## Task 1: Add regression tests for permission-decoupled create forms

**Files:**
- Create: `frontend/src/app/organizations/[id]/create-domain-permissions.test.ts`

**Interfaces:**
- Consumes: existing `useCan(permission: string): boolean`.
- Produces: source-level regression expectations for conditional optional lookups and backend-aligned max lengths.

- [ ] **Step 1: Write failing tests**

Create tests that verify all of the following:

1. OPO create page imports and uses `useCan` for both `opo.view` and `organizations.view`.
2. OPO create page defaults both owner and operating organization IDs to the current route `organizationId` without waiting for `/api/organizations`.
3. OPO create page only calls `getHazardSigns()` / `getActivityTypes()` when `opo.view` is available.
4. OPO create page only calls `getOrganizations(...)` when `organizations.view` is available.
5. Optional lookup errors do not disable the OPO submit button.
6. TD and Building create pages import/use `useCan("opo.view")` and only call `getOpoList(...)` when that permission is available.
7. TD and Building submit buttons are not disabled merely because optional OPO lookup failed.
8. TD and Building always retain the `Без ОПО` option.
9. OPO registration-number input has `maxLength={100}`.
10. TD serial-number input has `maxLength={100}`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
cd D:\Spravoshnik-EPB-hermes\frontend
npm test -- create-domain-permissions.test.ts
```

Expected: FAIL because the current pages unconditionally fetch supporting data and use maxLength 128.

---

## Task 2: Make OPO supporting data optional

**Files:**
- Modify: `frontend/src/app/organizations/[id]/opo/new/page.tsx`

**Interfaces:**
- Consumes: `useCan("opo.view")`, `useCan("organizations.view")`, existing `getOrganizations`, `getHazardSigns`, `getActivityTypes`, `createOpo`.
- Produces: a create form whose required payload can be submitted using the current organization even without optional view permissions.

- [ ] **Step 1: Initialize required references from the route**

Set initial values directly from `organizationId` semantics rather than waiting for the organization list. Because `organizationId` is derived after hooks, use an effect whose only purpose is to set the two IDs when the route ID changes, or equivalent React-safe initialization.

Required behavior:

```text
owner_organization_id = current organizationId
operating_organization_id = current organizationId
```

The form must remain submittable with those values even if organization lookup is unavailable.

- [ ] **Step 2: Gate optional lookup requests by permissions**

Add:

```ts
const canViewOpo = useCan("opo.view");
const canViewOrganizations = useCan("organizations.view");
```

Do not call:

```ts
getHazardSigns()
getActivityTypes()
```

when `canViewOpo === false`.

Do not call:

```ts
getOrganizations(...)
```

when `canViewOrganizations === false`.

Do not use one `Promise.all` where one optional failure blocks all data.

- [ ] **Step 3: Treat optional lookup failures as warnings, not form blockers**

Keep separate optional loading/error states if useful, but the required fields and submit action must remain available.

If organization choices cannot be loaded, owner/operator stay fixed to the current organization. Render clear text such as:

```text
Текущая организация
```

instead of an unusable empty select.

If `opo.view` is unavailable or reference lookup fails, omit/disable only the optional hazard-sign/activity selectors and allow empty arrays:

```ts
hazard_sign_ids: []
activity_type_ids: []
```

Do not convert optional reference failure into a form-level fatal error.

- [ ] **Step 4: Align registration number length**

Change:

```tsx
maxLength={128}
```

to:

```tsx
maxLength={100}
```

for `registration_number`.

- [ ] **Step 5: Keep create errors authoritative**

Errors from `createOpo(payload)` remain form-level errors using existing `ApiError.detail` behavior.

---

## Task 3: Make TD OPO lookup optional

**Files:**
- Modify: `frontend/src/app/organizations/[id]/devices/new/page.tsx`

**Interfaces:**
- Consumes: `useCan("opo.view")`, `getOpoList`, `createTechnicalDevice`.
- Produces: TD creation that always supports `opo_id: null` without requiring OPO read permission.

- [ ] **Step 1: Gate OPO lookup**

Add:

```ts
const canViewOpo = useCan("opo.view");
```

Only call `getOpoList(...)` when `canViewOpo` is true.

If false, finish optional loading immediately and leave `opos=[]`.

- [ ] **Step 2: Do not block submission on optional lookup failure**

Keep:

```text
Без ОПО
```

always available.

An OPO lookup error may be displayed as a nonfatal warning, but must not disable the submit button.

The valid fallback payload is:

```ts
opo_id: null
organization_id: organizationId
```

- [ ] **Step 3: Align serial-number length**

Change TD serial-number input to:

```tsx
maxLength={100}
```

- [ ] **Step 4: Preserve create failure behavior**

`createTechnicalDevice()` errors remain authoritative form-level errors.

---

## Task 4: Make Building OPO lookup optional

**Files:**
- Modify: `frontend/src/app/organizations/[id]/buildings/new/page.tsx`

**Interfaces:**
- Consumes: `useCan("opo.view")`, `getOpoList`, `createBuilding`.
- Produces: Building creation that always supports `opo_id: null` without requiring OPO read permission.

- [ ] **Step 1: Gate OPO lookup**

Use:

```ts
const canViewOpo = useCan("opo.view");
```

Only fetch OPO options when true.

- [ ] **Step 2: Keep `Без ОПО` always usable**

Optional OPO lookup errors must not disable building creation. A valid fallback payload is:

```ts
opo_id: null
organization_id: organizationId
```

- [ ] **Step 3: Preserve create failure behavior**

`createBuilding()` errors remain authoritative form-level errors.

---

## Task 5: Full verification

**Files:** no new production files.

- [ ] **Step 1: Run targeted test**

```powershell
cd D:\Spravoshnik-EPB-hermes\frontend
npm test -- create-domain-permissions.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run full frontend verification fresh on final tree**

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

Expected: all PASS.

- [ ] **Step 3: Check repository diff**

```powershell
cd D:\Spravoshnik-EPB-hermes
git diff --check
git status
git diff --stat
git diff
```

Expected implementation changes only in:

```text
frontend/src/app/organizations/[id]/opo/new/page.tsx
frontend/src/app/organizations/[id]/devices/new/page.tsx
frontend/src/app/organizations/[id]/buildings/new/page.tsx
frontend/src/app/organizations/[id]/create-domain-permissions.test.ts
```

If `next build` rewrites `frontend/next-env.d.ts`, restore that generated artifact before commit unless it contains an intentional required source change.

- [ ] **Step 4: Commit**

```powershell
git add "frontend/src/app/organizations/[id]/opo/new/page.tsx"
git add "frontend/src/app/organizations/[id]/devices/new/page.tsx"
git add "frontend/src/app/organizations/[id]/buildings/new/page.tsx"
git add "frontend/src/app/organizations/[id]/create-domain-permissions.test.ts"

git commit -m "fix(pilot): decouple create forms from optional view permissions"
git push origin pilot/hermes-stage3-frontend
```

Do not start CP3.
