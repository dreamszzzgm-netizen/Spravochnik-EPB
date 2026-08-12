# Stage 5 CP5.1 — Tasks Core completion amendment

Date: 2026-08-12

## Verified implementation

CP5.1 implements the backend Tasks Core on top of CP4.2.

### Schema / migration

Alembic head: `0013_stage5_tasks_core`.

Physical CP5.1 tables:

- `tasks`
- `task_assignees`
- `task_organizations`
- `task_contracts`
- `task_contract_items`
- `task_technical_devices`
- `task_buildings`
- `task_opos`
- `comments`
- `comment_tasks`

`task_expertises` is intentionally **not** physical in CP5.1 because `expertises` belongs to Stage 6. It will be added by a later migration after the owning table exists.

Workflow source columns/tables belong to CP5.2 Workflow Engine and are not part of the CP5.1 physical `tasks` table.

Comment links to contracts/expertises and comment mentions are also deferred until the owning stages exist. CP5.1 physically supports task comments through `comments` + `comment_tasks`.

## Task business rules implemented

Statuses:

- `new`
- `in_progress`
- `completed`
- `cancelled`

Allowed transitions:

- `new -> in_progress`
- `new -> cancelled`
- `in_progress -> completed`
- `in_progress -> cancelled`

`completed` and `cancelled` are terminal in CP5.1.

Overdue is computed, not stored as a status:

```text
due_date < today
AND status NOT IN (completed, cancelled)
```

A manual due-date extension, or clearing an existing due date, requires a nonblank business reason. Shortening a due date does not require a reason.

A personal task may have no business link. A non-personal task requires at least one FK-backed business link. A task may have multiple assignees and at most one primary business link.

## Authorization

Task authorization uses the existing scoped model:

- `ALL`
- `ASSIGNED`
- `RELATED`
- `OWN`

`OWN` means the current employee is `creator_employee_id`.
`ASSIGNED` means the current employee is in `task_assignees`.
`RELATED` is derived from linked organizations and ownership/customer relations of linked contract/items, OPO, technical devices and buildings.

`tasks.view_all` is a global read-only override. It does not imply mutation permissions.

Mutation permissions remain isolated:

- `tasks.create`
- `tasks.edit`
- `tasks.assign`
- `tasks.change_status`
- `tasks.delete`
- `tasks.restore`
- `tasks.comment`

A user cannot create or replace task links to a business resource that the same user cannot reference through the owning module's exact `*.view` permission. Inaccessible/foreign resources are intentionally indistinguishable from absent resources through task mutation endpoints (`404`).

## HTTP API

Implemented:

- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/{id}`
- `PATCH /api/tasks/{id}`
- `DELETE /api/tasks/{id}`
- `POST /api/tasks/{id}/restore`
- `PUT /api/tasks/{id}/assignees`
- `POST /api/tasks/{id}/status`
- `GET /api/tasks/{id}/comments`
- `POST /api/tasks/{id}/comments`

Generic PATCH cannot write protected fields such as task status or creator. Task creator and comment author are bound server-side to the authenticated employee.

The task registry applies scope and filters in SQL before count/pagination. Supported CP5.1 filters include assignee, creator, status, priority, due-date range, contract, organization and computed overdue state.

## Comments

Task comments use the shared `comments` entity with `comment_tasks` FK link.

CP5.1 supports list/add only. Comment edit/delete/mentions are intentionally not introduced here.

Adding a comment:

- trims text;
- rejects blank text;
- binds author to the authenticated employee;
- requires exact `tasks.comment` permission and applicable task scope;
- writes audit action `task.comment_added` atomically.

## Deferred Stage 5 work

CP5.2 owns:

- `workflow_templates`
- immutable published workflow versions
- workflow task templates
- source workflow/version fields on generated tasks
- business-function assignee resolution
- workflow instantiation.

CP5.3 owns:

- `signed -> in_progress` from first real linked work start
- task deadline pause/shift on contract suspend/resume
- unfinished task cancellation on contract termination
- real Tasks completion-readiness provider for contracts.

Stage 6 owns `task_expertises`.
Stage 8 owns task document attachments.

## Verification

Exact code head before this documentation commit:

`3683d7add747365d5af6ce2792579c5e13c3c35b`

GitHub Actions run #194 (`31602992297`):

- Ruff: PASS
- `alembic upgrade head`: PASS through `0013_stage5_tasks_core`
- pytest: **548 passed / 280 warnings**
- duration: 123.53 s

No integration merge is performed by this checkpoint.
