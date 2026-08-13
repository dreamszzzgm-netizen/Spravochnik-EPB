# Pilot — No Demo Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all fictional business data from the Pilot v0.1 frontend so a clean PostgreSQL database is represented truthfully, while preserving existing real API-backed areas and the current deployment/runtime.

**Architecture:** Enforce a production-source boundary that forbids `@/lib/mock-data` imports from `frontend/src/app` and `frontend/src/components`. Already API-backed screens remain untouched; not-yet-connected screens become deterministic empty/unavailable states, while shared shell elements use only real auth/navigation/runtime state. No database migration or backend-domain change is introduced.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Vitest, shadcn/ui, lucide-react, existing FastAPI backend and Docker Compose Pilot stack.

## Global Constraints

- Branch: `agent/stage5-cp59-pilot-deployment`.
- Preserve the clean Pilot PostgreSQL database, `admin`, storage, backups, Docker project `spravoshnik-epb-work`, port configuration, and smart desktop launcher.
- Do not add or modify Alembic migrations; schema head remains `0013_stage5_tasks_core`.
- Do not change backend business rules or API contracts in this patch.
- Existing API-backed Organizations/OPO/Technical Devices/Buildings flows remain real and must keep working.
- Production user-facing code under `frontend/src/app` and `frontend/src/components` must not import `@/lib/mock-data`.
- System/reference rows seeded by backend migrations are not demo data and must not be removed.
- Unsupported create/workflow actions must not look functional; hide them or replace them with truthful unavailable copy.
- No automatic merge into `codex/feat-gigastudio-frontend-integration`.

---

## File Structure

**Create**

- `frontend/src/no-demo-data.test.ts` — static production-boundary regression test.

**Modify**

- `frontend/src/components/app-shell.tsx` — remove global demo banner.
- `frontend/src/components/nav-sidebar.tsx` — remove hard-coded business counters.
- `frontend/src/components/notifications-popover.tsx` — real empty notification state, no mock records.
- `frontend/src/components/command-search.tsx` — navigation-only command palette until real global search exists.
- `frontend/src/components/dashboard/dashboard-header.tsx` — use real auth username and only working create navigation.
- `frontend/src/components/dashboard/status-badge.tsx` — remove mock-data type dependency.
- `frontend/src/components/dashboard/priority-badge.tsx` — remove mock-data type dependency.
- `frontend/src/app/page.tsx` — replace fabricated dashboard metrics/activity with truthful Pilot readiness/empty state.
- `frontend/src/app/tasks/page.tsx` — truthful Tasks unavailable/empty state.
- `frontend/src/app/contracts/page.tsx` — truthful Contracts frontend unavailable/empty state.
- `frontend/src/app/expertise/page.tsx` — truthful Stage 6 unavailable/empty state.
- `frontend/src/app/expertise/[id]/page.tsx` — no fictional detail record; unavailable state with back navigation.
- `frontend/src/app/npd/page.tsx` — remove embedded sample FNP/GOST list.
- `frontend/src/design-quality.test.ts` — remove regression assertion for retired mock task-list internals while preserving remaining accessibility/contrast checks.
- `docs/PILOT_DEPLOYMENT.md` — document that mock business rows are no longer shown; unconnected screens use empty states.
- `PROJECT_STATUS.md` — record exact verified no-demo checkpoint only after CI is GREEN.

**Delete after callers are removed**

- `frontend/src/components/demo-data-notice.tsx`
- `frontend/src/components/dashboard/document-status-chart.tsx`
- `frontend/src/components/dashboard/employee-load.tsx`
- `frontend/src/components/dashboard/expertise-donut.tsx`
- `frontend/src/components/dashboard/expertise-header.tsx`
- `frontend/src/components/dashboard/expertise-tabs.tsx`
- `frontend/src/components/dashboard/expiring-soon.tsx`
- `frontend/src/components/dashboard/my-tasks-list.tsx`
- `frontend/src/components/dashboard/recent-activity.tsx`

`frontend/src/lib/mock-data.ts` may remain as non-production legacy/test material, but no file under `src/app` or `src/components` may import it.

---

### Task 1: Add the No Demo Data production contract (RED)

**Files:**
- Create: `frontend/src/no-demo-data.test.ts`
- Test: `frontend/src/no-demo-data.test.ts`

**Interfaces:**
- Consumes: filesystem contents below `src/app` and `src/components`.
- Produces: a permanent guard that fails whenever production UI reintroduces `@/lib/mock-data`, known sample identifiers, or the global demo banner.

- [ ] **Step 1: Create the failing regression test**

Create `frontend/src/no-demo-data.test.ts` with this structure:

```ts
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = resolve(process.cwd(), "src");
const PRODUCTION_ROOTS = [resolve(ROOT, "app"), resolve(ROOT, "components")];

function sourceFiles(dir: string): string[] {
  const result: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      result.push(...sourceFiles(full));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(name) || /\.(test|spec)\.(ts|tsx)$/.test(name)) continue;
    result.push(full);
  }
  return result;
}

function read(path: string): string {
  return readFileSync(path, "utf8");
}

describe("Pilot production UI has no demo business data", () => {
  it("forbids mock-data imports from production app/components", () => {
    const offenders = PRODUCTION_ROOTS.flatMap(sourceFiles)
      .filter((path) => read(path).includes("@/lib/mock-data"))
      .map((path) => relative(process.cwd(), path));
    expect(offenders).toEqual([]);
  });

  it("does not expose known fictional sample identifiers", () => {
    const forbidden = [
      "ЭПБ-2026/2401",
      "ЭПБ-2026/2408",
      "npd-536",
      "npd-533",
      "gost-34347",
      "Демо-режим: содержимое этой страницы",
    ];
    const joined = PRODUCTION_ROOTS.flatMap(sourceFiles)
      .map((path) => read(path))
      .join("\n");
    for (const marker of forbidden) expect(joined).not.toContain(marker);
  });

  it("does not hard-code task/expertise sidebar badges", () => {
    const sidebar = read(resolve(ROOT, "components/nav-sidebar.tsx"));
    expect(sidebar).not.toContain('item.href === "/tasks"');
    expect(sidebar).not.toContain('item.href === "/expertise"');
  });

  it("keeps organizations API-backed", () => {
    const organizations = read(resolve(ROOT, "app/organizations/page.tsx"));
    expect(organizations).toContain('from "@/lib/api/resources"');
    expect(organizations).toContain("getOrganizations");
  });
});
```

- [ ] **Step 2: Run the RED test**

From `frontend/`:

```bash
npm test -- src/no-demo-data.test.ts
```

Expected: FAIL. The failure list must include current mock-dependent production files such as Tasks, Contracts, Expertise, dashboard components, notifications, command search, status/priority badges, and dashboard header.

- [ ] **Step 3: Commit only the RED test**

```bash
git add frontend/src/no-demo-data.test.ts
git commit -m "test(pilot): forbid demo data in production UI"
```

Review gate: the test must fail because real production source still contains mock dependencies/sample records, not because the test itself has a path/runtime error.

---

### Task 2: Clean the global shell and shared UI state

**Files:**
- Modify: `frontend/src/components/app-shell.tsx`
- Delete: `frontend/src/components/demo-data-notice.tsx`
- Modify: `frontend/src/components/nav-sidebar.tsx`
- Modify: `frontend/src/components/notifications-popover.tsx`
- Modify: `frontend/src/components/command-search.tsx`
- Modify: `frontend/src/components/dashboard/dashboard-header.tsx`
- Test: `frontend/src/no-demo-data.test.ts`
- Test: `frontend/src/design-quality.test.ts`

**Interfaces:**
- Consumes: `mainNav`, `settingsNav`, `useAuth()`, existing `BackendStatus`, existing command palette primitives.
- Produces: a shell that contains no fictional badge counts, notifications, search results, or fake user identity.

- [ ] **Step 1: Remove the global DemoDataNotice**

In `app-shell.tsx`, remove:

```ts
import { DemoDataNotice } from "@/components/demo-data-notice";
```

and remove:

```tsx
<DemoDataNotice />
```

Then delete `frontend/src/components/demo-data-notice.tsx`.

- [ ] **Step 2: Remove hard-coded sidebar counts**

In `nav-sidebar.tsx`, remove the `Badge` import and both conditional blocks that render literal `7` for `/tasks` and literal `4` for `/expertise`. Keep navigation labels/icons unchanged.

- [ ] **Step 3: Replace notifications with a deterministic empty state**

Replace `notifications-popover.tsx` with a component that imports only `Bell`, `Button`, `Popover*`, and `Separator`. Preserve the responsive content width required by design quality tests:

```tsx
"use client";

import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";

export function NotificationsPopover() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative h-9 w-9" aria-label="Уведомления">
          <Bell className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(380px,calc(100vw-2rem))] p-0">
        <div className="px-4 py-3">
          <h4 className="text-sm font-semibold">Уведомления</h4>
          <p className="text-xs text-muted-foreground">Новых уведомлений нет</p>
        </div>
        <Separator />
        <div className="px-4 py-8 text-center text-sm text-muted-foreground">
          Серверный модуль уведомлений будет подключён отдельным этапом.
        </div>
      </PopoverContent>
    </Popover>
  );
}
```

There is no unread badge and no “Прочитать все” action until a real notifications API exists.

- [ ] **Step 4: Convert command search to navigation-only commands**

Remove `searchIndex`/`SearchEntry` imports. Define a local navigation entry type and derive entries from `mainNav` + `settingsNav`, so the command palette contains only real routes, never fake business entities:

```ts
type NavigationEntry = {
  href: string;
  label: string;
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
};

const navigationEntries: NavigationEntry[] = [...mainNav, ...settingsNav].map((item) => ({
  href: item.href,
  label: item.label,
  description: item.description,
  icon: item.icon,
}));
```

Render one `CommandGroup heading="Разделы"`; on select call `router.push(item.href)`. Change the input placeholder to `Поиск по разделам…`. Keep `⌘K`/Ctrl+K behavior.

- [ ] **Step 5: Make DashboardHeader use real auth state**

Remove `currentUser` and unsupported quick-create actions. Import `useAuth` and keep only the real Organizations creation route:

```tsx
const { state } = useAuth();
const username = state.status === "authenticated" ? state.user.username : "пользователь";
```

The heading becomes:

```tsx
{greeting}, {username}
```

The only action button is:

```tsx
<Button size="sm" asChild>
  <Link href="/organizations/new">
    <Plus className="mr-1.5 h-4 w-4" />
    Новая организация
  </Link>
</Button>
```

Do not show “Новая задача”, “Договор”, or “Экспертизу” shortcuts in this checkpoint because those frontend create flows are not part of this patch.

- [ ] **Step 6: Run focused tests**

```bash
npm test -- src/no-demo-data.test.ts src/design-quality.test.ts
```

Expected: no-demo test still FAILS because registry/dashboard files are not cleaned yet; design-quality notification-width/theme/contrast tests PASS.

- [ ] **Step 7: Commit shared-shell cleanup**

```bash
git add frontend/src/components/app-shell.tsx frontend/src/components/nav-sidebar.tsx frontend/src/components/notifications-popover.tsx frontend/src/components/command-search.tsx frontend/src/components/dashboard/dashboard-header.tsx frontend/src/design-quality.test.ts frontend/src/no-demo-data.test.ts
git rm frontend/src/components/demo-data-notice.tsx
git commit -m "fix(pilot): remove demo state from shared shell"
```

---

### Task 3: Replace mock registries with truthful empty/unavailable states

**Files:**
- Modify: `frontend/src/app/tasks/page.tsx`
- Modify: `frontend/src/app/contracts/page.tsx`
- Modify: `frontend/src/app/expertise/page.tsx`
- Modify: `frontend/src/app/expertise/[id]/page.tsx`
- Modify: `frontend/src/app/npd/page.tsx`
- Test: `frontend/src/no-demo-data.test.ts`

**Interfaces:**
- Consumes: existing `EmptyState` component and lucide icons.
- Produces: deterministic user-facing pages containing no fake rows and no fake persistence actions.

- [ ] **Step 1: Replace Tasks registry**

`tasks/page.tsx` should import only `ListTodo` and `EmptyState`, preserve the page title/subtitle, and render:

```tsx
<EmptyState
  icon={ListTodo}
  title="Задач пока нет"
  description="Серверный модуль задач уже существует. Подключение этого списка к серверным данным выполняется отдельным этапом."
/>
```

Remove search, status/priority/deadline rendering, and “Новая задача” until the real frontend mutation flow is implemented.

- [ ] **Step 2: Replace Contracts registry**

`contracts/page.tsx` should render:

```tsx
<EmptyState
  icon={FileText}
  title="Договоры пока не отображаются"
  description="Серверный модуль договоров уже реализован. Подключение реального реестра договоров к Pilot-интерфейсу выполняется отдельным этапом."
/>
```

No mock rows, fake amounts, fake end dates, search, or “Новый договор” button.

- [ ] **Step 3: Replace Expertise registry**

`expertise/page.tsx` should render:

```tsx
<EmptyState
  icon={ShieldCheck}
  title="Экспертиз пока нет"
  description="Полноценный модуль экспертиз будет подключён после реализации Stage 6."
/>
```

No fake expertise rows and no “Новая экспертиза” button.

- [ ] **Step 4: Replace mock Expertise detail route**

`expertise/[id]/page.tsx` must not import `ExpertiseHeader` or `ExpertiseTabs`. Await `params` only to satisfy the route signature, then render:

```tsx
<EmptyState
  icon={ShieldCheck}
  title="Экспертиза недоступна"
  description="Эта карточка не представляет реальную запись. Реальные карточки экспертиз появятся после подключения Stage 6."
  actionLabel="К списку экспертиз"
  actionHref="/expertise"
/>
```

- [ ] **Step 5: Replace NPD sample list**

Remove the `sample` array, list/card/search/action UI, and render:

```tsx
<EmptyState
  icon={BookOpen}
  title="НПД пока не загружены"
  description="Реестр НПД, импорт и контроль актуальности будут подключены на соответствующем этапе."
/>
```

- [ ] **Step 6: Run focused no-demo test**

```bash
npm test -- src/no-demo-data.test.ts
```

Expected: FAIL only for remaining mock-dependent dashboard/shared component files, not for the five cleaned routes.

- [ ] **Step 7: Commit registry cleanup**

```bash
git add frontend/src/app/tasks/page.tsx frontend/src/app/contracts/page.tsx frontend/src/app/expertise/page.tsx frontend/src/app/expertise/[id]/page.tsx frontend/src/app/npd/page.tsx frontend/src/no-demo-data.test.ts
git commit -m "fix(pilot): replace demo registries with empty states"
```

---

### Task 4: Remove mock dashboard data and retire mock-only dashboard components

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/dashboard/status-badge.tsx`
- Modify: `frontend/src/components/dashboard/priority-badge.tsx`
- Modify: `frontend/src/design-quality.test.ts`
- Delete: `frontend/src/components/dashboard/document-status-chart.tsx`
- Delete: `frontend/src/components/dashboard/employee-load.tsx`
- Delete: `frontend/src/components/dashboard/expertise-donut.tsx`
- Delete: `frontend/src/components/dashboard/expertise-header.tsx`
- Delete: `frontend/src/components/dashboard/expertise-tabs.tsx`
- Delete: `frontend/src/components/dashboard/expiring-soon.tsx`
- Delete: `frontend/src/components/dashboard/my-tasks-list.tsx`
- Delete: `frontend/src/components/dashboard/recent-activity.tsx`
- Test: `frontend/src/no-demo-data.test.ts`
- Test: `frontend/src/design-quality.test.ts`

**Interfaces:**
- Consumes: real `DashboardHeader`, `EmptyState`, `Card`, real Organizations route.
- Produces: a useful but non-fictional Pilot home screen and zero production imports from `@/lib/mock-data`.

- [ ] **Step 1: Replace the fabricated dashboard**

Rewrite `app/page.tsx` to retain `DashboardHeader` and show Pilot readiness rather than invented analytics. Use one real navigation card for Organizations and neutral cards for unconnected modules. Example shape:

```tsx
import Link from "next/link";
import { Building2, FileText, ListTodo, ShieldCheck } from "lucide-react";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { Card, CardContent } from "@/components/ui/card";

const modules = [
  { title: "Организации", description: "Работа с реальными серверными данными", href: "/organizations", icon: Building2, available: true },
  { title: "Договоры", description: "Серверный модуль готов; интерфейс реестра будет подключён отдельно", href: "/contracts", icon: FileText, available: false },
  { title: "Задачи", description: "Серверный модуль готов; интерфейс реестра будет подключён отдельно", href: "/tasks", icon: ListTodo, available: false },
  { title: "Экспертизы", description: "Полноценный модуль появится после Stage 6", href: "/expertise", icon: ShieldCheck, available: false },
];
```

Each card may link to its route, but it must show text such as `Доступно` only for Organizations and `Будет подключено` for the others. Do not display numeric KPI values, money, task counts, RTN statuses, employee load, activity, or deadlines.

- [ ] **Step 2: Remove mock-only dashboard components**

After `page.tsx` and Expertise detail no longer reference them, delete the eight files listed above. They contain no real server source and keeping them would violate the production boundary or invite accidental reuse of fictional state.

- [ ] **Step 3: Preserve reusable badge components without mock-data types**

In `status-badge.tsx`, replace the type import with local exported unions:

```ts
export type ContractStatus = "Черновик" | "На согласовании" | "Подписан" | "В работе" | "Приостановлен" | "Завершён" | "Расторгнут" | "Архив";
export type ExpertiseStatus = "Подготовка" | "Сбор документов" | "Обследование" | "Подготовка заключения" | "Внутреннее согласование" | "Готово к регистрации" | "На рассмотрении в РТН" | "Отказ РТН / Требует доработки" | "Зарегистрировано" | "Получено заказчиком" | "Завершено";
export type TaskStatus = "Новая" | "В работе" | "Выполнена" | "Отменена";
```

Keep existing color maps and rendering behavior.

In `priority-badge.tsx`, replace the mock type import with:

```ts
export type TaskPriority = "низкий" | "обычный" | "высокий" | "срочный";
```

- [ ] **Step 4: Update design-quality regression test**

Remove only the obsolete test named `gives task checkboxes a compact visual with a 44px hit area`, because `my-tasks-list.tsx` is intentionally removed. Keep the notification narrow-viewport, localized theme, semantic-color, reduced-motion, and WCAG contrast tests unchanged.

- [ ] **Step 5: Run the no-demo and design tests**

```bash
npm test -- src/no-demo-data.test.ts src/design-quality.test.ts
```

Expected: PASS.

- [ ] **Step 6: Run grep-level verification**

From `frontend/`:

```bash
grep -R --line-number --include='*.ts' --include='*.tsx' '@/lib/mock-data' src/app src/components || true
```

Expected: no output.

Also:

```bash
grep -R --line-number --include='*.ts' --include='*.tsx' 'ЭПБ-2026/240\|npd-536\|gost-34347\|Демо-режим' src/app src/components || true
```

Expected: no output.

- [ ] **Step 7: Commit dashboard/mock retirement**

```bash
git add frontend/src/app/page.tsx frontend/src/components/dashboard/status-badge.tsx frontend/src/components/dashboard/priority-badge.tsx frontend/src/design-quality.test.ts frontend/src/no-demo-data.test.ts
git rm frontend/src/components/dashboard/document-status-chart.tsx frontend/src/components/dashboard/employee-load.tsx frontend/src/components/dashboard/expertise-donut.tsx frontend/src/components/dashboard/expertise-header.tsx frontend/src/components/dashboard/expertise-tabs.tsx frontend/src/components/dashboard/expiring-soon.tsx frontend/src/components/dashboard/my-tasks-list.tsx frontend/src/components/dashboard/recent-activity.tsx
git commit -m "fix(pilot): remove mock dashboard business data"
```

---

### Task 5: Full frontend quality gate and operator documentation

**Files:**
- Modify: `docs/PILOT_DEPLOYMENT.md`
- Modify: `PROJECT_STATUS.md` only after fresh CI evidence exists.
- Test: all frontend tests/build.

**Interfaces:**
- Consumes: cleaned frontend from Tasks 1–4.
- Produces: verified source/build evidence and operator-facing truth about the Pilot limitations.

- [ ] **Step 1: Run the complete frontend quality gate**

From `frontend/`:

```bash
npm ci
npm run lint
npm run typecheck
npm test
BACKEND_ORIGIN=http://backend:8000 npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 2: Update Pilot runbook limitation text**

In `docs/PILOT_DEPLOYMENT.md`, replace the statement that some Next.js screens “используют mock-data” with truthful wording:

```text
- фиктивные business/demo-записи в Pilot-интерфейсе не показываются;
- разделы, которые ещё не подключены к реальному backend API, показывают честное пустое/недоступное состояние;
- Organizations/OPO/TD/Buildings продолжают работать через реальные серверные API;
- Contracts/Tasks frontend integration, Stage 6 Expertises, NPD и Notifications остаются отдельными этапами.
```

Do not change the existing backup/TLS/LAN safety sections.

- [ ] **Step 3: Commit code + runbook state before status evidence**

```bash
git add docs/PILOT_DEPLOYMENT.md
git commit -m "docs(pilot): document no-demo frontend boundary"
```

- [ ] **Step 4: Wait for GitHub workflows on the exact code head**

Required checks:

```text
ci: Ruff PASS + Alembic upgrade head PASS + full pytest PASS
pilot-ci / frontend-quality: lint PASS + typecheck PASS + Vitest PASS + Next build PASS
pilot-ci / pilot-images-and-smoke: image build PASS + migrate PASS + health PASS + same-origin proxy PASS + backup PASS
```

Do not claim GREEN until these checks belong to the exact final code commit.

- [ ] **Step 5: Update PROJECT_STATUS.md with fresh evidence only**

Record:

```text
- no-demo cleanup final HEAD
- Alembic head remains 0013_stage5_tasks_core
- no schema migration
- frontend production boundary: no @/lib/mock-data imports under src/app/src/components
- exact frontend test count/results
- exact CI run IDs and statuses
- Pilot smoke result
```

Replace the old line `Frontend task/business screens that still use mock-data...` with a statement that unsupported screens now show truthful empty states and their real API migrations remain deferred.

- [ ] **Step 6: Commit status evidence**

```bash
git add PROJECT_STATUS.md
git commit -m "docs(pilot): record verified no-demo checkpoint"
```

Then require CI on this documentation head if workflow paths trigger; otherwise verify that the previous code head is the exact runtime content and the status-only commit changes documentation only.

---

### Task 6: Pilot image smoke and installed-Pilot update procedure

**Files:**
- No source changes unless verification discovers a defect.
- Runtime: `D:\Spravoshnik-EPB-Pilot` after GitHub checkpoint is GREEN.

**Interfaces:**
- Consumes: verified branch head, existing `.env.pilot`, Docker project `spravoshnik-epb-work`.
- Produces: installed Pilot showing no fictional business records, with the database untouched.

- [ ] **Step 1: Confirm no database reset is required**

Do not remove any Docker volume and do not clear `var/pilot/storage`. The current clean database remains the source of truth.

- [ ] **Step 2: Update the installed Pilot source**

On the Pilot workstation:

```powershell
cd D:\Spravoshnik-EPB-Pilot
git status --short
git pull --ff-only origin agent/stage5-cp59-pilot-deployment
```

Expected before pull: clean working tree except ignored `.env.pilot`/runtime data.

- [ ] **Step 3: Rebuild only the frontend image**

```powershell
docker compose `
  -p spravoshnik-epb-work `
  --env-file deploy/pilot/.env.pilot `
  -f docker-compose.pilot.yml `
  build frontend
```

Expected: successful Next.js standalone build.

- [ ] **Step 4: Recreate only frontend service**

```powershell
docker compose `
  -p spravoshnik-epb-work `
  --env-file deploy/pilot/.env.pilot `
  -f docker-compose.pilot.yml `
  up -d --no-deps frontend
```

- [ ] **Step 5: Verify frontend/backend health**

```powershell
(Invoke-WebRequest http://127.0.0.1:3100/backend/health/live).Content
```

Expected: successful health response.

- [ ] **Step 6: User acceptance through the smart shortcut**

Close the browser, launch `Spravoshnik EPB` from the desktop shortcut, and verify:

```text
/                no fake KPI/activity/employees/deadlines
/organizations   real API data; clean DB shows no organizations
/contracts       no fake contracts; truthful unavailable state
/tasks           no fake tasks; truthful unavailable state
/expertise       no fake expertise rows; truthful Stage 6 state
/npd             no sample FNP/GOST rows
notification bell no fake unread badge/records
sidebar          no literal 7 or 4 counters
global search    navigation only; no fake business entities
```

- [ ] **Step 7: Verify PostgreSQL business tables remain clean**

Use the previously established read-only count query for `organizations`, `contracts`, `tasks`, `opo`, `technical_devices`, and `buildings`. Expected: all remain `0` unless the user deliberately created real data during acceptance.

- [ ] **Step 8: Final review gate**

Confirm:

```text
No DB migration
No DB reset
No backup deletion
No mock business records visible
Real Organizations API still works
Desktop launcher still works
Pilot health remains GREEN
PR #8 remains draft/unmerged
```

If all hold, the `Pilot — No Demo Data` patch is complete.
