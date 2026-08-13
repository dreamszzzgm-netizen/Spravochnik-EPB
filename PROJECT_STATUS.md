# Project status

## Current verified development baseline

- Official integration GREEN baseline remains unchanged: `650008fc5a80eaf6165d2d0aba249041aae2a98d`.
- Stacked parent checkpoint: **Stage 5 / CP5.1 — Tasks Core backend**, HEAD `c7f6efbd16796f6ac207e5717045cc1bc3994d08`.
- Active checkpoint: **Stage 5 / CP5.2 — Workflow Engine backend**.
- Feature branch: `agent/stage5-cp52-workflow-engine`.
- Draft PR: `#11`, stacked on `agent/stage5-cp51-tasks-core`.
- Verified functional code head before final documentation/review commits: `e8f24bccf9c832041f8622303a85dd1b48494095`.
- Alembic head: `0014_stage5_workflow_engine`.
- Verification at that code head: GitHub Actions run `31693756568` (#420) — Ruff PASS, `alembic upgrade head` PASS, **562 passed / 289 warnings**.
- Follow-up code head `dc23aae6779f193cd9f36bdd11ec507907d2597b` only replaces the workflow API's deprecated 422 status constant; a new PR CI run was triggered for exact-head verification.

## Completed through CP5.2

- Stage 0 — application foundation.
- Stage 1 — identity, sessions, RBAC, permission scopes and audit foundation.
- Stage 2 — organizations and contacts.
- Stage 3 — OPO, technical devices, buildings, custom fields and scoped authorization closure.
- Stage 4 CP4.1 — Contracts Core backend.
- Stage 4 CP4.2 — Contract Lifecycle and Addenda backend.
- Stage 5 CP5.1 — Tasks Core backend.
- Stage 5 CP5.2 — Workflow Engine backend:
  - migration `0014_stage5_workflow_engine`;
  - logical workflow templates with stable unique codes;
  - numbered workflow template versions;
  - publication through `published_at`;
  - published versions and their task definitions are immutable by API/service contract;
  - ordered workflow task templates with title, description, business-function assignee, relative due days, priority and required flag;
  - generated tasks preserve exact `source_workflow_template_version_id` and `source_workflow_task_template_id` provenance;
  - source version/task-template provenance is protected by a composite FK and all-or-none CHECK constraint;
  - employee business-function assignment is separate from authorization roles;
  - automatic assignee resolution excludes soft-deleted employees and employees absent on the workflow anchor date;
  - missing eligible assignee fails closed before task creation;
  - workflow instantiation uses the latest published version only;
  - due-date calculation is injected through a resolver so CP5.2 does not invent a temporary production-calendar implementation;
  - workflow-generated work is created as ordinary CP5.1 tasks and keeps normal task validation/audit behavior;
  - `TaskService.create_task(..., commit=False)` allows a higher application service to own a transaction while preserving default standalone behavior;
  - whole workflow instantiation is atomic: any late failure rolls back all generated tasks;
  - management HTTP API for list/create/detail/version creation/version list/publish;
  - all workflow management endpoints require the exact backend permission `workflows.manage`;
  - audit events cover template creation, version creation, publication and instantiation;
  - migration, service, transaction, instantiation, authorization and API coverage added.

## Stage 5 boundary / deferred work

### CP5.3 — Contract ↔ Tasks integration

Deferred intentionally:

- first real linked work start driving internal contract `signed -> in_progress`;
- task deadline pause/shift on contract suspension/resume;
- unfinished task cancellation on contract termination;
- real Tasks completion-readiness provider for contracts.

### Later owning stages

- Stage 6 adds Expertise-triggered workflow instantiation and `task_expertises` after the physical `expertises` table exists.
- Stage 8 adds task document attachments and broader document/comment relations.
- Notifications/mentions remain later work.
- Frontend workflow management UI is not part of CP5.2.
- Production calendar behavior remains owned by `WorkingCalendarService`; CP5.2 only consumes an injected due-date resolver.

The exact CP5.2 implementation contract is recorded in:

`docs/superpowers/plans/2026-08-13-stage5-cp52-workflow-engine.md`.

Completion evidence is recorded in:

`docs/superpowers/reviews/2026-08-13-stage5-cp52-workflow-engine-completion.md`.

## Pilot deployment policy

Stage 5.9 — Pilot Deployment v0.1 remains an independent stacked operational branch. CP5.2 does not rebase, merge or modify the Pilot branch automatically.

The pilot deployment packages the existing modular monolith for a LAN server with PostgreSQL, backend, worker/scheduler, Next.js frontend, local storage, controlled migrations, administrator bootstrap, health checks and backup tooling.

The pilot is not a public-internet deployment. Remote access remains VPN/LAN oriented.

## Integration policy

CP5.2 is a stacked checkpoint on top of CP5.1 and is prepared for review as **draft PR #11** only. **Do not merge CP5.2 into `codex/feat-gigastudio-frontend-integration`, Pilot or another integration branch automatically.** Integration remains untouched until explicit user approval.
