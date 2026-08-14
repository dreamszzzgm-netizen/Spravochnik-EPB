# PR6 Tasks API Workspace — Design

## Context

This checkpoint implements the first user-facing increment of the approved `DEVELOPMENT_PLAN v2.0` section **PR6 — Workflow & Tasks 2.0**.

The backend Tasks Core is already real and supports paginated reads, status/priority/overdue filters, scoped authorization, assignees, business links, comments, soft delete/restore and workflow provenance. The frontend `/tasks` route still renders `myTasks` from `mock-data`, which makes the current UI diverge from the verified backend state.

Expertise development is paused. This checkpoint must not add or change Expertise behavior.

## Goal

Replace the mocked `/tasks` registry with a real API-backed task registry while preserving the current Spravoshnik EPB design system and permission model.

## Scope

### Included

- Add a typed frontend API module for Tasks.
- Load `GET /api/tasks` from `/tasks`.
- Support backend-native filters:
  - status;
  - priority;
  - overdue only.
- Support pagination with backend `page` / `page_size`.
- Display real task fields:
  - title;
  - status;
  - priority;
  - due date;
  - overdue state;
  - assignee count;
  - business-link count.
- Provide loading, error and empty states.
- Remove `myTasks` dependency from `/tasks`.
- Keep task search visibly unavailable until the backend supports a real search parameter; do not implement fake client-only search over one page.

### Deferred to the next PR6 checkpoints

- task creation/edit form;
- assignee picker;
- task detail page;
- checklist CRUD;
- workflow management UI;
- task attachments;
- notifications;
- Expertise-triggered workflows.

## Frontend API contract

`frontend/src/lib/api/tasks.ts` owns frontend Task types and transport functions.

Status values follow backend enums exactly:

- `new`
- `in_progress`
- `completed`
- `cancelled`

Priority values follow backend enums exactly:

- `low`
- `normal`
- `high`
- `urgent`

The API client exposes Russian labels separately so transport values never leak into presentation copy.

## Page behavior

`/tasks` becomes a client component.

On page/filter changes it:

1. aborts any previous request;
2. enters loading state;
3. calls `getTasks()`;
4. updates `items` and `total` on success;
5. renders normalized API errors on failure;
6. ignores expected abort errors.

Changing a filter resets pagination to page 1.

The registry uses the existing `StatusBadge`, `PriorityBadge`, `DeadlineChip`, Card and Button patterns. No new UI dependency is added.

## Authorization

Read authorization remains server-owned. The page does not duplicate authorization scope logic. A backend `403` is rendered through the existing `ApiError` normalization.

The current “Новая задача” action is not wired to a nonexistent route in this checkpoint. Creation belongs to the next checkpoint.

## Error handling

- `401`/session behavior remains owned by the existing app/auth layer.
- `403`, `404`, `422`, `500` responses use `ApiError.detail`.
- Network/unknown failures show a safe Russian fallback.
- Aborted requests do not surface an error.

## Testing

TDD order:

1. API tests first for query serialization and backend transport values.
2. Page behavior test first for real API rendering and removal of mock-data dependency.
3. Implement minimal production code.
4. Run frontend lint, typecheck, tests and production build through CI.

## Acceptance

- `/tasks` contains no `myTasks`/`mock-data` import.
- Real backend tasks render from `GET /api/tasks`.
- Status, priority and overdue filters generate the correct API query.
- Pagination uses backend totals.
- Loading, error and empty states are present.
- No Expertise code changes.
- Frontend lint, typecheck, tests and production build pass.
