# Project status

## Current verified development baseline

- Official integration GREEN baseline remains unchanged: `650008fc5a80eaf6165d2d0aba249041aae2a98d`.
- Stacked parent checkpoint: **Stage 4 / CP4.2 — Contract Lifecycle and Addenda backend**, HEAD `7066e648543c1aaccbdcc85016a9340d9d304c70`.
- Active checkpoint: **Stage 5 / CP5.1 — Tasks Core backend**.
- Feature branch: `agent/stage5-cp51-tasks-core`.
- Verified code head before final documentation/review commits: `3683d7add747365d5af6ce2792579c5e13c3c35b`.
- Alembic head: `0013_stage5_tasks_core`.
- Verification at that code head: GitHub Actions run `31602992297` (#194) — Ruff PASS, `alembic upgrade head` PASS, **548 passed / 280 warnings**.

## Completed through CP5.1

- Stage 0 — application foundation.
- Stage 1 — identity, sessions, RBAC, permission scopes and audit foundation.
- Stage 2 — organizations and contacts.
- Stage 3 — OPO, technical devices, buildings, custom fields and scoped authorization closure.
- Stage 4 CP4.1 — Contracts Core backend.
- Stage 4 CP4.2 — Contract Lifecycle and Addenda backend.
- Stage 5 CP5.1 — Tasks Core backend:
  - migration `0013_stage5_tasks_core`;
  - task statuses `new/in_progress/completed/cancelled` and priorities `low/normal/high/urgent`;
  - manual task CRUD with soft delete/restore and optimistic version field;
  - multiple active employee assignees;
  - FK-backed links to organizations, contracts, contract items, technical devices, buildings and OPO;
  - personal tasks may be unlinked; non-personal tasks require at least one business link;
  - at most one primary business link;
  - manual due-date extension or clearing requires a business reason;
  - computed overdue state rather than an `overdue` status;
  - status machine `new -> in_progress/cancelled`, `in_progress -> completed/cancelled`;
  - terminal timestamps preserved through soft delete/restore;
  - scoped ALL/ASSIGNED/RELATED/OWN authorization with non-enumerating 404 behavior;
  - `tasks.view_all` as a read-only global override;
  - exact mutation permissions for create/edit/assign/status/delete/restore/comment;
  - SQL-scoped task registry with count/pagination and task filters;
  - cross-resource reference authorization through the owning module's exact view permission before linked-resource mutation;
  - shared task comments through `comments` + `comment_tasks`, with server-bound author and audit;
  - HTTP API for registry/detail/create/update/delete/restore/assignees/status/comments;
  - rollback, deduplication, deleted visibility and authorization hardening coverage.

## Stage 5 boundary / deferred work

### CP5.2 — Workflow Engine

Deferred intentionally:

- workflow templates;
- immutable published workflow versions;
- workflow task templates;
- source workflow/version fields on generated tasks;
- business-function assignee resolution;
- workflow instantiation.

### CP5.3 — Contract ↔ Tasks integration

Deferred intentionally:

- first real linked work start driving internal contract `signed -> in_progress`;
- task deadline pause/shift on contract suspension/resume;
- unfinished task cancellation on contract termination;
- real Tasks completion-readiness provider for contracts.

### Later owning stages

- Stage 6 adds `task_expertises` after the physical `expertises` table exists.
- Stage 8 adds task document attachments and broader document/comment relations.
- Notifications/mentions remain later work.
- Frontend task pages are not migrated from mock data in CP5.1.

The exact CP5.1 physical/data/API amendment is recorded in:

`docs/superpowers/reviews/2026-08-12-stage5-cp51-tasks-core-completion.md`.

## Pilot deployment policy

After CP5.1 is finalized as a stacked draft review checkpoint, the next operational branch is **Stage 5.9 — Pilot Deployment v0.1**, stacked on the final CP5.1 head.

The pilot deployment will package the existing modular monolith for a LAN server with:

- PostgreSQL persistent storage;
- backend web process;
- worker;
- scheduler;
- Next.js frontend;
- local file storage volume;
- controlled Alembic migration step;
- administrator bootstrap workflow;
- health checks;
- backup tooling;
- production environment template and LAN installation/update instructions.

The pilot is not a public-internet deployment. Remote access remains VPN/LAN oriented.

## Integration policy

CP5.1 is a stacked checkpoint on top of CP4.2 and is prepared for review as a **draft** pull request only. **Do not merge CP5.1 into `codex/feat-gigastudio-frontend-integration` automatically.** Integration remains untouched until explicit user approval.
