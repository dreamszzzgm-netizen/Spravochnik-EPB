# Pilot — No Demo Data design

Date: 2026-08-13
Branch: `agent/stage5-cp59-pilot-deployment`

## 1. Goal

Remove all fake business information from the user-facing Pilot v0.1 frontend so an empty PostgreSQL database is represented as an empty system rather than as a populated demo system.

The patch is intentionally limited to presentation/data-source cleanup. It does not change database schema, business rules, backend domain services, authentication, deployment topology, or existing real API integrations.

## 2. Problem

The current Pilot database can be fully clean while the frontend still shows fictional tasks, expertises, contracts, dashboard metrics, notifications, NPD records, and sidebar counters.

This happens because a number of frontend screens and components still import `@/lib/mock-data` or embed sample values directly in production UI code.

Confirmed examples include:

- `/tasks` using `myTasks`;
- `/expertise` using `expertiseList`;
- `/expertise/[id]` using mock expertise detail components;
- `/contracts` using mock contracts;
- dashboard `/` using mock KPI/contracts/expertises and related dashboard components;
- notifications popover using mock notifications;
- sidebar hard-coded counters for tasks and expertises;
- `/npd` embedding sample regulatory documents directly in the page.

The Organizations area is already API-backed and must remain unchanged except for any shared-shell cleanup required to remove fake counters/notifications.

## 3. Chosen approach

Use a strict **No Demo Data production boundary**:

1. Production user-facing code under `frontend/src/app` and `frontend/src/components` must not import `@/lib/mock-data`.
2. Screens already backed by real API remain API-backed.
3. Screens not yet backed by a real API display an honest empty/not-yet-connected state instead of fictional records.
4. Hard-coded business counters and notification counts are removed unless they come from a real API.
5. Demo banners that describe mock content are removed from cleaned screens because no mock content remains.
6. Buttons for unsupported create/workflow actions must not imply that a working persistence flow exists. They are hidden or disabled with clear wording until their real flow is implemented.
7. System/reference seed data created by backend migrations is not considered demo data and is not removed.

This patch deliberately does **not** migrate every remaining screen to backend APIs. API migration belongs to the owning feature stages.

## 4. User-visible behavior

### 4.1 Tasks

If the backend task UI is not yet wired in this Pilot frontend, `/tasks` shows a normal empty/availability state and no fictional EPB tasks.

The sidebar does not show a hard-coded task count.

### 4.2 Expertises

`/expertise` shows no fictional expertises. Until the Stage 6 frontend/backend flow is available, it shows a neutral state explaining that expertises will appear after the module is connected.

Direct mock expertise detail pages must not expose fictional expertise data. A non-real detail route should present an unavailable/not-found style state and a route back to the expertise registry.

The sidebar does not show a hard-coded expertise count.

### 4.3 Contracts

`/contracts` must not render fictional contracts. Until the current backend Contracts API is wired into this frontend screen, it shows a neutral empty/not-yet-connected state rather than mock rows.

### 4.4 NPD

`/npd` must not embed sample FNP/GOST records. Until the NPD backend stage is connected, it shows an empty/not-yet-connected state.

### 4.5 Notifications

The notification bell must not display fictional notifications or a fake unread badge. Until a real notification source exists, the popover shows an empty state such as “Новых уведомлений нет”.

### 4.6 Dashboard

The dashboard must not display fabricated KPI counts, financial totals, activity history, employee load, deadlines, RTN states, task lists, or charts.

Where no real data source exists, the dashboard uses zero/empty values or an explicit neutral placeholder. It must never present a fictional business record as if it were production data.

The authenticated real user identity remains sourced from the real auth layer; no fake person should be shown as the current user.

## 5. Empty-state UX

Use the existing design system and `EmptyState` component where practical.

Empty states must:

- state what is currently empty or unavailable;
- avoid the word “demo” once mock rows are removed;
- avoid pretending an unsupported operation is functional;
- provide navigation to a real working area when useful;
- preserve the current visual system from `DESIGN.md`.

Examples:

- `Задач пока нет` / `Интерфейс задач будет подключён к серверным данным в следующем этапе.`
- `Экспертиз пока нет` / `Модуль экспертиз будет подключён после реализации Stage 6.`
- `Договоры не отображаются в этом Pilot-интерфейсе` / `Серверный модуль договоров уже существует; подключение списка выполняется отдельным этапом.`
- `НПД пока не загружены`.

Exact wording may be adjusted during implementation for concise UX, but it must remain truthful.

## 6. Data boundaries

### Keep

- PostgreSQL Pilot database and schema;
- `admin` and other real users;
- API-backed Organizations/OPO/Technical Devices/Buildings functionality;
- backend reference seeds such as hazard signs/activity types;
- authentication/session state;
- backup, launcher, Docker and Pilot deployment configuration.

### Remove from production UI

- imports from `@/lib/mock-data`;
- embedded sample business arrays/objects;
- hard-coded task/expertise badge counts;
- fictional notification records/counts;
- fictional dashboard values;
- demo-mode warnings that only existed to explain mock content.

`frontend/src/lib/mock-data.ts` may remain temporarily for tests/development only if no production `app` or user-facing `components` code imports it. Deleting it is optional and should only be done if no test still legitimately depends on it.

## 7. Error handling

This cleanup must not convert unavailable real APIs into fake success states.

- Existing API-backed pages retain their current loading/error/empty handling.
- Non-connected pages render deterministic empty states and do not perform fake persistence.
- Unsupported detail routes return or render a truthful unavailable/not-found presentation instead of mock detail content.

## 8. Testing strategy

Implement with TDD.

Add regression coverage that proves:

1. production code under `frontend/src/app` and relevant user-facing `frontend/src/components` does not import `@/lib/mock-data`;
2. sidebar contains no hard-coded `7` task badge or `4` expertise badge as business counters;
3. notification popover has no dependency on mock notifications;
4. `/npd` has no embedded sample list such as `npd-536`, `npd-533`, or `gost-34347`;
5. tasks/contracts/expertise registry pages contain truthful empty-state behavior instead of iterating mock collections;
6. mock expertise detail is no longer exposed;
7. frontend lint, typecheck, tests, and production build remain GREEN;
8. Pilot Docker image rebuild and same-origin health smoke remain GREEN.

## 9. Deployment/update behavior

No database migration is introduced.

To apply the patch to the installed Pilot:

1. keep the current clean database and backup untouched;
2. pull the verified Pilot branch update;
3. rebuild the frontend image (or the normal verified Pilot build path if CI/runbook requires it);
4. recreate/restart the frontend through Compose;
5. launch through the existing smart desktop shortcut;
6. verify empty screens and absence of fictional counters/notifications.

No database reset is required after this patch.

## 10. Out of scope

This patch does not implement:

- Tasks frontend API migration;
- Contracts frontend API migration;
- Stage 6 Expertises backend/frontend;
- NPD persistence/API;
- Notifications backend;
- real dashboard analytics;
- new database migrations;
- workflow engine CP5.2/CP5.3;
- redesign of the established visual system.

## 11. Acceptance criteria

The patch is accepted when all of the following are true:

1. A clean Pilot DB displays no fictional organizations, contracts, expertises, tasks, NPD entries, notifications, dashboard events, or employee activity.
2. Organizations and other already API-backed areas still work against real backend data.
3. Sidebar task/expertise counters are not fabricated.
4. No user-facing production source imports `@/lib/mock-data`.
5. Unsupported screens show truthful empty/unavailable states.
6. Existing `admin` login, Pilot storage, backups, launcher, and Docker topology are unchanged.
7. Frontend lint/typecheck/tests/build pass.
8. Pilot smoke/health checks pass on the exact final commit.
9. The patch remains on the stacked Pilot draft branch and is not automatically merged into integration.
