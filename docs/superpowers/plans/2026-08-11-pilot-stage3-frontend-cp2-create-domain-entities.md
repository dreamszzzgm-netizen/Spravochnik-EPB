# Pilot Stage 3 Frontend CP2 — Create OPO, Technical Devices, and Buildings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) and superpowers:test-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Let a pilot user create OPO, Technical Devices, and Buildings directly from an Organization workspace using the existing backend APIs, while replacing raw backend enum values with Russian UI labels.

**Architecture:** Keep this checkpoint frontend-only. The three existing read-only organization tabs gain permission-gated “Добавить” actions that link to dedicated create pages nested under the organization. Forms use typed functions in `src/lib/api/resources.ts`, follow the existing Organization form pattern, and return to the Organization workspace after successful creation.

**Tech Stack:** Next.js 16, React 19, TypeScript, shadcn/Radix components, lucide-react, Vitest.

## Global Constraints

- Branch: `pilot/hermes-stage3-frontend`.
- Starting implementation base before this plan: `d726df0`.
- Frontend only: do not modify `app/**`, `alembic/**`, Python tests, backend schemas/routes/services/repositories, or database code.
- No new npm dependency.
- Backend remains the security boundary; UI permission gating is usability only.
- Do not invent backend endpoints or fields.
- This checkpoint implements CREATE only. Do not add edit/delete/restore/detail routes yet.
- Existing Contracts placeholder remains unchanged.

---

## Backend contracts to mirror

### OPO

`POST /api/opo`

```ts
export type HazardClass =
  | "hazard_class_1"
  | "hazard_class_2"
  | "hazard_class_3"
  | "hazard_class_4";

export interface OPOCreatePayload {
  name: string;
  registration_number: string;
  hazard_class: HazardClass;
  address: string;
  registration_date: string;
  owner_organization_id: string;
  operating_organization_id: string;
  hazard_sign_ids: string[];
  activity_type_ids: string[];
  comment: string | null;
}
```

Reference endpoints:

```text
GET /api/reference/hazard-signs
GET /api/reference/activity-types
```

Reference item shape:

```ts
export interface ReferenceItemResponse {
  id: string;
  code: string;
  name: string;
}
```

### Technical Device

Backend enum values:

```ts
export type TechnicalDeviceType =
  | "pressure_vessel"
  | "pipeline"
  | "lifting_mechanism"
  | "other";
```

Create payload:

```ts
export interface TechnicalDeviceCreatePayload {
  name: string;
  device_type: TechnicalDeviceType;
  serial_number: string | null;
  opo_id: string | null;
  organization_id: string;
}
```

### Building

Backend enum values:

```ts
export type BuildingType =
  | "industrial"
  | "warehouse"
  | "administrative"
  | "other";
```

Create payload:

```ts
export interface BuildingCreatePayload {
  name: string;
  building_type: BuildingType;
  opo_id: string | null;
  organization_id: string;
}
```

---

## File Map

**Modify**
- `frontend/src/lib/api/types.ts`
- `frontend/src/lib/api/resources.ts`
- `frontend/src/lib/api/view-models.ts`
- `frontend/src/app/organizations/[id]/_components/organization-opo-list.tsx`
- `frontend/src/app/organizations/[id]/_components/organization-device-list.tsx`
- `frontend/src/app/organizations/[id]/_components/organization-building-list.tsx`

**Create**
- `frontend/src/app/organizations/[id]/opo/new/page.tsx`
- `frontend/src/app/organizations/[id]/devices/new/page.tsx`
- `frontend/src/app/organizations/[id]/buildings/new/page.tsx`
- `frontend/src/app/organizations/[id]/create-domain-entities.test.ts`

No other files should change unless required solely for formatting by existing tooling; report any such change explicitly.

---

### Task 1: RED — source-level contract tests

Create `frontend/src/app/organizations/[id]/create-domain-entities.test.ts` following the existing source-analysis Vitest pattern.

Test at minimum:

- types export `HazardClass`, `TechnicalDeviceType`, `BuildingType` and the three create payloads;
- resources export `createOpo`, `createTechnicalDevice`, `createBuilding`, `getHazardSigns`, `getActivityTypes`;
- POST paths are exactly `/api/opo`, `/api/technical-devices`, `/api/buildings`;
- reference paths are exactly `/api/reference/hazard-signs` and `/api/reference/activity-types`;
- OPO list component has an `/organizations/${organizationId}/opo/new` link gated by `useCan("opo.create")`;
- device list has `/organizations/${organizationId}/devices/new` gated by `useCan("technical_devices.create")`;
- building list has `/organizations/${organizationId}/buildings/new` gated by `useCan("buildings.create")`;
- all three create pages exist and submit through the intended resource function;
- Contracts placeholder is not modified by this checkpoint.

Run the new test before production changes and record RED.

---

### Task 2: Typed API and Russian labels

In `types.ts` add the exact types/payloads above plus `ReferenceItemResponse`.

In `resources.ts` add:

```ts
export const createOpo = (payload: OPOCreatePayload) =>
  apiRequest<OPOResponse>("/api/opo", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const createTechnicalDevice = (payload: TechnicalDeviceCreatePayload) =>
  apiRequest<TechnicalDeviceResponse>("/api/technical-devices", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const createBuilding = (payload: BuildingCreatePayload) =>
  apiRequest<BuildingResponse>("/api/buildings", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getHazardSigns = (options: ResourceOptions = {}) =>
  apiRequest<ReferenceItemResponse[]>("/api/reference/hazard-signs", options);

export const getActivityTypes = (options: ResourceOptions = {}) =>
  apiRequest<ReferenceItemResponse[]>("/api/reference/activity-types", options);
```

Add label helpers in `view-models.ts`:

```ts
hazardClassLabel("hazard_class_1") => "I класс опасности"
hazardClassLabel("hazard_class_2") => "II класс опасности"
hazardClassLabel("hazard_class_3") => "III класс опасности"
hazardClassLabel("hazard_class_4") => "IV класс опасности"

technicalDeviceTypeLabel("pressure_vessel") => "Сосуд под давлением"
technicalDeviceTypeLabel("pipeline") => "Трубопровод"
technicalDeviceTypeLabel("lifting_mechanism") => "Подъёмное сооружение"
technicalDeviceTypeLabel("other") => "Другое"

buildingTypeLabel("industrial") => "Производственное"
buildingTypeLabel("warehouse") => "Складское"
buildingTypeLabel("administrative") => "Административное"
buildingTypeLabel("other") => "Другое"
```

Unknown values fall back to the raw value.

Update the three CP1 list components to display these Russian labels instead of raw enum values.

---

### Task 3: Permission-gated create buttons in organization tabs

In each list component:

- import `Link`, `Plus`, `Button`, and `useCan` as needed;
- OPO: `const canCreate = useCan("opo.create")`;
- TD: `const canCreate = useCan("technical_devices.create")`;
- Building: `const canCreate = useCan("buildings.create")`;
- render a small `Добавить` button in `CardHeader` only when `canCreate` is true;
- use these links exactly:

```text
/organizations/${organizationId}/opo/new
/organizations/${organizationId}/devices/new
/organizations/${organizationId}/buildings/new
```

Do not make existing rows clickable in this checkpoint.

---

### Task 4: OPO create page

Create `frontend/src/app/organizations/[id]/opo/new/page.tsx` using the existing Organization create-page conventions.

Required fields:

- `name` — required text;
- `registration_number` — required text;
- `hazard_class` — required Select, default `hazard_class_3`;
- `address` — required text;
- `registration_date` — required `type="date"` input;
- `owner_organization_id` — Select;
- `operating_organization_id` — Select;
- hazard signs — checkbox list from `getHazardSigns()`;
- activity types — checkbox list from `getActivityTypes()`;
- `comment` — optional Textarea.

On mount, load in parallel:

```ts
getOrganizations({ page: 1, page_size: 100 })
getHazardSigns()
getActivityTypes()
```

Default owner and operator to the current route organization id when it exists in the returned organization list. The form must still render a clear load error if supporting data cannot be loaded.

Submit with `createOpo`. On success:

```ts
router.replace(`/organizations/${organizationId}`)
```

Use `ApiError.detail` for backend errors; otherwise `Не удалось создать ОПО.`.

Cancel returns to `/organizations/${organizationId}`.

---

### Task 5: Technical Device create page

Create `frontend/src/app/organizations/[id]/devices/new/page.tsx`.

Fields:

- name required;
- device type Select using all four exact backend enum values;
- serial number optional;
- OPO optional Select.

Load OPO choices with:

```ts
getOpoList({
  organization_id: organizationId,
  page: 1,
  page_size: 100,
})
```

The OPO Select must include a clear `Без ОПО` option. Do not expose organization selection here: `organization_id` is always the current Organization route id.

Submit exact payload through `createTechnicalDevice`; success returns to the Organization workspace. Backend error fallback: `Не удалось создать техническое устройство.`.

---

### Task 6: Building create page

Create `frontend/src/app/organizations/[id]/buildings/new/page.tsx`.

Fields:

- name required;
- building type Select using all four exact backend enum values;
- OPO optional Select with `Без ОПО`.

Use the current Organization route id as `organization_id`, load OPO options via scoped `getOpoList`, submit through `createBuilding`, and return to the Organization workspace. Backend error fallback: `Не удалось создать здание или сооружение.`.

---

### Task 7: GREEN + frontend verification

Run from `frontend/`:

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

Then from repository root:

```powershell
git diff --check
git status
git diff --stat
git diff
```

Verify there are no implementation changes outside `frontend/**`.

---

### Task 8: Commit boundary

Commit only the frontend implementation files listed in the File Map.

Commit message:

```text
feat(pilot): add organization domain create flows
```

Push only to `origin/pilot/hermes-stage3-frontend` and stop for independent audit. Do not start edit/delete/detail CP3.