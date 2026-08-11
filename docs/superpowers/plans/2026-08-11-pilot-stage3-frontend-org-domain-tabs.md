# Pilot Stage 3 Frontend — Organization Domain Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the OPO / Technical Devices / Buildings placeholders in the Organization workspace with real API-backed read-only lists, without modifying backend code.

**Architecture:** Extend the existing typed frontend API layer with OPO, TechnicalDevice, and Building response/list types plus list functions filtered by `organization_id`. Add three focused client components under the organization workspace; each component loads only its own resource, handles loading/error/empty states, and renders compact cards consistent with the existing design system. The organization page keeps its current tabs and swaps only the three placeholders for the new components.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, existing Tailwind/shadcn UI, Vitest.

## Global Constraints

- Base commit: `d599ab2b0f4aeb398517e86d70108310046a8bb5`.
- Branch: `pilot/hermes-stage3-frontend`.
- FRONTEND ONLY. Never modify `app/`, `alembic/`, backend `tests/`, Python files, backend routes/services/repositories, or database migrations.
- Keep the existing Next.js 16 / React 19 / shadcn design system. No new dependencies.
- This checkpoint is read-only integration. Do not create new create/edit/detail routes yet and do not render links to routes that do not exist.
- Preserve existing Organization general/contacts behavior.
- No force push, rebase, or reset of published history.

---

### Task 1: Extend typed API contracts

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/api/resources.ts`

**Interfaces:**
- Produces: `OPOResponse`, `OPOPaginatedResponse`, `TechnicalDeviceResponse`, `TechnicalDevicePaginatedResponse`, `BuildingResponse`, `BuildingPaginatedResponse` and resource list functions.

- [ ] Add these TypeScript interfaces matching the current FastAPI schemas exactly:

```ts
export interface OPOResponse {
  id: string;
  name: string;
  registration_number: string;
  hazard_class: string;
  address: string;
  registration_date: string;
  owner_organization_id: string;
  operating_organization_id: string;
  deleted_at: string | null;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface OPOPaginatedResponse {
  items: OPOResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface TechnicalDeviceResponse {
  id: string;
  name: string;
  device_type: string;
  serial_number: string | null;
  opo_id: string | null;
  organization_id: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TechnicalDevicePaginatedResponse {
  items: TechnicalDeviceResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface BuildingResponse {
  id: string;
  name: string;
  building_type: string;
  opo_id: string | null;
  organization_id: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BuildingPaginatedResponse {
  items: BuildingResponse[];
  total: number;
  page: number;
  page_size: number;
}
```

- [ ] Import those types into `resources.ts` and add these functions:

```ts
export const getOpoList = (
  params: {
    organization_id: string;
    q?: string;
    page?: number;
    page_size?: number;
    signal?: AbortSignal;
  },
) => {
  const searchParams = new URLSearchParams();
  searchParams.set("organization_id", params.organization_id);
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  return apiRequest<OPOPaginatedResponse>(`/api/opo?${searchParams.toString()}`, {
    signal: params.signal,
  });
};

export const getTechnicalDevices = (
  params: {
    organization_id: string;
    q?: string;
    page?: number;
    page_size?: number;
    signal?: AbortSignal;
  },
) => {
  const searchParams = new URLSearchParams();
  searchParams.set("organization_id", params.organization_id);
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  return apiRequest<TechnicalDevicePaginatedResponse>(
    `/api/technical-devices?${searchParams.toString()}`,
    { signal: params.signal },
  );
};

export const getBuildings = (
  params: {
    organization_id: string;
    q?: string;
    page?: number;
    page_size?: number;
    signal?: AbortSignal;
  },
) => {
  const searchParams = new URLSearchParams();
  searchParams.set("organization_id", params.organization_id);
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  return apiRequest<BuildingPaginatedResponse>(`/api/buildings?${searchParams.toString()}`, {
    signal: params.signal,
  });
};
```

---

### Task 2: Add three API-backed tab components

**Files:**
- Create: `frontend/src/app/organizations/[id]/_components/organization-opo-list.tsx`
- Create: `frontend/src/app/organizations/[id]/_components/organization-device-list.tsx`
- Create: `frontend/src/app/organizations/[id]/_components/organization-building-list.tsx`

**Interfaces:**
- Each component accepts exactly `{ organizationId: string }`.
- Each component loads at most 100 rows with its resource function and `page: 1, page_size: 100`.

- [ ] Each component must be `"use client"`, create an `AbortController` in `useEffect`, abort on unmount, and keep `items`, `total`, `loading`, `error` state.
- [ ] Loading state: centered `Loader2` spinner inside a bordered Card.
- [ ] Error state: Card with `ApiError.detail` when available, otherwise `Ошибка загрузки`.
- [ ] Empty state copy:
  - OPO: `ОПО для этой организации пока не добавлены.`
  - TD: `Технические устройства для этой организации пока не добавлены.`
  - Buildings: `Здания и сооружения для этой организации пока не добавлены.`
- [ ] Non-empty state: Card header with section title and count; rows separated with `divide-y` and no links.
- [ ] OPO row shows `name`, registration number, hazard class, address; use `ShieldCheck` icon.
- [ ] Technical device row shows `name`, `device_type`, optional `serial_number`, and whether it is linked to OPO (`ОПО привязано` / `Без ОПО`); use `Wrench` icon.
- [ ] Building row shows `name`, `building_type`, and whether it is linked to OPO; use `Warehouse` icon.
- [ ] Use only existing semantic classes (`bg-primary/10`, `text-primary`, `text-muted-foreground`, `border-border`, `hover:bg-muted/40` only if appropriate). Do not introduce hardcoded new palette values.

---

### Task 3: Replace workspace placeholders

**Files:**
- Modify: `frontend/src/app/organizations/[id]/page.tsx`

- [ ] Import the three new components.
- [ ] Replace only the `opo`, `devices`, and `buildings` placeholder TabsContent blocks with:

```tsx
<TabsContent value="opo" className="mt-4">
  <OrganizationOpoList organizationId={id} />
</TabsContent>

<TabsContent value="devices" className="mt-4">
  <OrganizationDeviceList organizationId={id} />
</TabsContent>

<TabsContent value="buildings" className="mt-4">
  <OrganizationBuildingList organizationId={id} />
</TabsContent>
```

- [ ] Keep the Contracts placeholder unchanged for now.
- [ ] Do not change General, Contacts, Edit button, or Organization header behavior.

---

### Task 4: Add regression tests and verify

**Files:**
- Create: `frontend/src/app/organizations/[id]/domain-tabs.test.ts`

- [ ] Write source-level Vitest assertions proving:
  - the old shared placeholder loop no longer covers `opo`, `devices`, or `buildings`;
  - `OrganizationOpoList`, `OrganizationDeviceList`, and `OrganizationBuildingList` are imported and rendered with `organizationId={id}`;
  - Contracts placeholder remains;
  - `resources.ts` contains all three filtered endpoints and sends `organization_id`.
- [ ] Run the test before implementation and record the RED evidence.
- [ ] After implementation run:

```powershell
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

- [ ] Require all four commands to succeed with zero errors/warnings allowed by existing scripts.
- [ ] From repository root run `git diff --check` and `git status`.
- [ ] Confirm all changed implementation files are under `frontend/` plus this plan document already present on the branch. No backend file may change.
- [ ] Commit:

```powershell
git add frontend/src/lib/api/types.ts frontend/src/lib/api/resources.ts frontend/src/app/organizations/[id]/page.tsx frontend/src/app/organizations/[id]/_components/organization-opo-list.tsx frontend/src/app/organizations/[id]/_components/organization-device-list.tsx frontend/src/app/organizations/[id]/_components/organization-building-list.tsx frontend/src/app/organizations/[id]/domain-tabs.test.ts
git commit -m "feat(pilot): connect organization domain tabs"
git push origin pilot/hermes-stage3-frontend
```

- [ ] Return commit SHA, exact changed files, RED evidence, `npm test`, typecheck, lint, build, `git diff --check`, and clean `git status`.
