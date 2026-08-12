# Stage 5 — Tasks and Workflow

Date: 2026-08-12
Status: Approved design
Base checkpoint: Stage 4 CP4.2 (`7066e648543c1aaccbdcc85016a9340d9d304c70`)
Initial implementation branch: `agent/stage5-cp51-tasks-core`

## 1. Goal

Implement the Stage 5 task and workflow foundation for Spravoshnik EPB while preserving the modular-monolith boundaries established in Stages 0-4.

Stage 5 is deliberately split into three stacked checkpoints:

1. **CP5.1 — Tasks Core**: task persistence, assignees, supported business links, comments, computed overdue state, CRUD/status API, authorization and audit.
2. **CP5.2 — Workflow Engine**: versioned workflow templates, immutable published versions, task templates, business-function assignee resolution and atomic task instantiation.
3. **CP5.3 — Contract ↔ Tasks Integration**: actual-work start producer, contract suspension/resume deadline effects, termination cancellation and the real Tasks completion-readiness provider.

This decomposition is authoritative for Stage 5. Each checkpoint must pass its own migration, targeted tests, full regression, lint and review before the next checkpoint begins.

## 2. Source rules and architectural constraints

This design follows the current authoritative project documents:

- `docs/ARCHITECTURE.md`;
- `docs/DATA_MODEL.md`;
- `docs/BUSINESS_RULES.md`;
- `docs/PERMISSIONS.md`;
- `docs/UI_MAP.md`;
- `docs/DEVELOPMENT_PLAN.md`;
- Stage 4 CP4.2 contract lifecycle and readiness design.

Key inherited rules:

- tasks are universal working units;
- a task may have multiple assignees;
- personal tasks may exist without a business link;
- overdue is computed, not persisted as a main task status;
- workflow templates are data-driven rather than hard-coded in routes;
- published workflow versions must not mutate existing tasks;
- business-function roles are not authorization roles;
- contract completion remains manual and fail-closed;
- a signed contract starts actual work through an internal producer, not through a public arbitrary status write;
- backend authorization and anti-enumeration remain mandatory;
- no future-stage table may be referenced by a real FK before that table exists.

## 3. Selected approach

The selected approach is three stacked checkpoints.

Rejected alternatives:

1. **Tasks + Workflow in one checkpoint** — fewer pull requests, but combines two migrations, authorization, workflow publication rules and task mutation behavior into one review surface.
2. **All Stage 5 in one checkpoint** — shortest branch chain, but creates a large cross-module transaction change at the same time as the task and workflow foundations. This is harder to test, audit and revert safely.

The selected approach minimizes cross-module risk and matches the project rule that every checkpoint must have a bounded scope and independent acceptance criteria.

## 4. Stage 5 checkpoint graph

```text
Stage 4 CP4.2
  7066e648...
      |
      v
CP5.1 Tasks Core
      |
      v
CP5.2 Workflow Engine
      |
      v
CP5.3 Contract ↔ Tasks Integration
```

Each checkpoint is stacked on the exact verified HEAD of the previous checkpoint. No checkpoint is automatically merged into the integration branch.

---

# Part I — CP5.1 Tasks Core

## 5. CP5.1 scope

CP5.1 implements:

- `app/modules/tasks` module;
- task status and priority enums;
- `tasks` table;
- `task_assignees` table;
- task links to entities that already physically exist by Stage 5;
- task comments;
- task CRUD and soft delete/restore;
- assignee replacement;
- strict task status commands;
- manual due-date updates with reason-on-extension rule;
- computed `is_overdue`;
- list/filter/read API;
- ALL / ASSIGNED / RELATED / OWN authorization;
- `tasks.view_all` compatibility override;
- anti-enumeration for inaccessible tasks and linked resources;
- audit and rollback behavior;
- migration tests and full regression.

## 6. CP5.1 non-goals

CP5.1 does not implement:

- workflow templates or workflow-generated tasks;
- contract lifecycle side effects;
- contract readiness provider;
- task links to expertises because `expertises` does not exist before Stage 6;
- task file attachments because Documents does not exist before Stage 8;
- notification creation;
- @mention notifications;
- production calendar calculations;
- scheduler behavior;
- frontend task pages;
- recurring tasks;
- dependencies that block one task on another;
- generic event sourcing.

## 7. Task statuses

Persisted task statuses:

```text
new
in_progress
completed
cancelled
```

Allowed transitions in CP5.1:

```text
new -> in_progress
new -> cancelled
in_progress -> completed
in_progress -> cancelled
```

`completed` and `cancelled` are terminal in v1.

Direct arbitrary writes to `status` through a general PATCH are forbidden. Status changes go through a task status command service.

`overdue` is not a persisted task status.

## 8. Task priorities

Persisted priorities:

```text
low
normal
high
urgent
```

Default priority is `normal`.

## 9. Task model

The CP5.1 `tasks` table contains:

```text
id UUID PK
title VARCHAR NOT NULL
description TEXT NULL
creator_employee_id UUID FK employees NOT NULL
due_date DATE NULL
priority task_priority NOT NULL DEFAULT normal
status task_status NOT NULL DEFAULT new
is_personal BOOLEAN NOT NULL DEFAULT false
source_workflow_template_version_id UUID NULL
source_workflow_task_template_id UUID NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
completed_at TIMESTAMPTZ NULL
cancelled_at TIMESTAMPTZ NULL
deleted_at TIMESTAMPTZ NULL
version INTEGER NOT NULL DEFAULT 1
```

The two `source_workflow_*` columns are physically introduced in CP5.2 when the referenced workflow tables exist. The CP5.1 ORM may omit them until CP5.2 rather than creating invalid forward FKs.

Rules:

- `title` is required after trimming;
- `creator_employee_id` is the employee identity of the authenticated actor;
- `completed_at` is set exactly once when entering `completed`;
- `cancelled_at` is set exactly once when entering `cancelled`;
- terminal timestamps are not used as alternate status fields;
- soft deletion uses `deleted_at`;
- rejected mutations must not increment `version` and must not produce success audit events.

## 10. Multiple assignees

`task_assignees`:

```text
task_id UUID FK tasks ON DELETE CASCADE
employee_id UUID FK employees ON DELETE RESTRICT
PRIMARY KEY (task_id, employee_id)
```

Rules:

- zero or more assignees are structurally allowed for a generic task;
- manual tasks may be created before assignees are known;
- assigned employees must exist and must not be soft-deleted;
- duplicate assignee IDs are normalized;
- assignee replacement is atomic;
- a task with multiple assignees is visible under ASSIGNED scope to every assignee;
- workflow-specific assignee guarantees are introduced in CP5.2.

## 11. Supported task links in CP5.1

CP5.1 creates only links whose referenced tables already exist:

```text
task_organizations
task_contracts
task_contract_items
task_technical_devices
task_buildings
task_opos
```

Each table contains:

```text
task_id FK tasks
<entity>_id FK <entity table>
is_primary BOOLEAN NOT NULL DEFAULT false
PRIMARY KEY (task_id, <entity>_id)
```

The service enforces at most one `is_primary=true` row across all business-link tables for one task.

A non-personal task must have at least one supported business link.

A personal task may have no business links.

A personal task may still have a business link when the user intentionally wants a private responsibility related to a business entity; `is_personal` is therefore not treated as the logical negation of having links.

## 12. Deferred task links

`task_expertises` is not created in CP5.1 because the `expertises` table belongs to Stage 6 and does not yet exist.

Stage 6 adds:

```text
task_expertises
task_id FK tasks
expertise_id FK expertises
is_primary BOOLEAN DEFAULT false
PRIMARY KEY (task_id, expertise_id)
```

Task attachments are not modeled in CP5.1. Stage 8 Documents adds the task-document link after the Documents module exists.

## 13. Link validation and cross-resource security

Task create/update commands validate every linked entity before saving.

For a linked entity:

- the record must exist and be active according to the owning module's rules;
- the actor must have the corresponding view/reference access where the owning module exposes such a scope policy;
- inaccessible and foreign resources must not be distinguishable from absent resources through task mutation endpoints;
- contract-item links must belong to the referenced contract when both are present;
- nested relationships must not be silently rewritten to make an invalid request valid.

The service does not use polymorphic `entity_type + entity_id` storage for these business-critical links.

## 14. Task comments

CP5.1 implements the shared comment foundation only to the extent needed by tasks.

Tables:

```text
comments
comment_tasks
```

`comments`:

```text
id UUID PK
author_employee_id UUID FK employees NOT NULL
text TEXT NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
```

`comment_tasks`:

```text
comment_id UUID FK comments UNIQUE
task_id UUID FK tasks
```

CP5.1 API scope:

- list active comments for an accessible task;
- add a comment to an accessible task.

Editing/deleting comments, comment links to contracts/expertises and `comment_mentions` are not required for CP5.1.

Notifications for assignments/comments/@mentions belong to the Notifications stage and are not faked in Stage 5.

## 15. Due-date rules

A task may have `due_date = NULL`.

For a manual due-date edit:

- moving the due date earlier requires no reason;
- setting a previously absent due date requires no extension reason;
- moving the due date later requires a non-empty business reason;
- removing a due date from a task that previously had one is treated as an extension and requires a non-empty reason;
- the accepted mutation writes audit metadata with old date, new date and reason;
- a rejected extension writes no success audit event and leaves the task unchanged.

No separate `task_due_date_history` table is introduced in CP5.1. The immutable audit stream is the v1 history mechanism for manual due-date changes.

## 16. Overdue computation

Base CP5.1 rule:

```text
is_overdue =
    due_date IS NOT NULL
    AND due_date < current_date
    AND status NOT IN (completed, cancelled)
```

The value is computed at read/query time and is not persisted as a main status.

Contract-suspension suppression is added in CP5.3, because before that checkpoint Tasks Core does not own the cross-module lifecycle effect.

`is_due_soon` remains reserved for the Calendar/Notifications stage where the 30/14/5 policy and production calendar are implemented.

## 17. Task deletion and restore

CP5.1 manual tasks support soft delete and restore under `tasks.delete` and `tasks.restore`.

Rules:

- deleting sets `deleted_at` and increments version;
- restore clears `deleted_at` and increments version;
- deleted tasks do not appear in ordinary registries;
- task status history is preserved through audit;
- CP5.2 will prohibit soft deletion of workflow-generated tasks because cancellation, not deletion, is the correct historical operation for them.

## 18. CP5.1 authorization

Permission codes already seeded in Stage 1 are reused; Stage 5 does not silently create a second authorization system.

Authoritative Stage 5 task permissions:

```text
tasks.view
tasks.view_all
tasks.create
tasks.assign
tasks.edit
tasks.change_status
tasks.delete
tasks.restore
tasks.comment
```

The pre-seeded `tasks.complete` permission is reserved and unused by the Stage 5 API. Completing a task is a normal task state transition governed by `tasks.change_status`. This resolves the difference between the Stage 1 seed list and current `PERMISSIONS.md` without silently changing the approved permission model.

Exact permission isolation is mandatory:

- `tasks.edit` does not grant assign/status/comment/delete;
- `tasks.assign` does not grant edit/status;
- `tasks.change_status` does not grant edit/assign;
- `tasks.comment` does not grant edit;
- `tasks.view_all` is read-only.

## 19. Task scope semantics

`tasks.view` and task mutation permissions use the existing scope vocabulary:

### ALL

Access to every task permitted by the requested permission code.

### ASSIGNED

Access when `ctx.employee_id` is an active assignee of the task.

### OWN

Access when `ctx.employee_id == task.creator_employee_id`.

### RELATED

Access when at least one linked business entity resolves to an organization contained in `ctx.related_organization_ids`.

Organization resolution includes:

- direct `task_organizations.organization_id`;
- `task_contracts` through `contracts.customer_organization_id`;
- `task_contract_items` through its parent contract customer organization;
- technical devices through their owning organization;
- buildings through their owning organization;
- OPO through owner or operating organization.

Malformed RELATED scope remains fail-closed through the existing authorization context parser.

## 20. `tasks.view_all`

`tasks.view_all` is a compatibility/global-read override for manager-style task registries.

If the authenticated user has an active `tasks.view_all` permission grant, the user may read/list all non-deleted tasks regardless of task relation scope.

It does not grant any mutation permission.

Superuser retains the normal project-wide superuser bypass.

## 21. Task API

Planned CP5.1 backend API:

```text
GET    /api/tasks
POST   /api/tasks
GET    /api/tasks/{task_id}
PATCH  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
POST   /api/tasks/{task_id}/restore
PUT    /api/tasks/{task_id}/assignees
POST   /api/tasks/{task_id}/status
GET    /api/tasks/{task_id}/comments
POST   /api/tasks/{task_id}/comments
```

List filters include only fields available before Stage 6:

```text
assignee_id
creator_employee_id
status
priority
due_from
due_to
contract_id
organization_id
is_overdue
include_deleted (only where permission policy allows)
```

Expertise filtering is added in Stage 6 with `task_expertises`.

Task general PATCH cannot change:

- `status`;
- assignees;
- creator;
- workflow source fields.

Those fields are owned by dedicated commands or later workflow internals.

## 22. CP5.1 audit

Accepted mutations write audit events in the same transaction.

Representative actions:

```text
task.created
task.updated
task.deleted
task.restored
task.assignees_updated
task.status_changed
task.comment_added
```

Due-date changes include structured metadata:

```json
{
  "old_due_date": "YYYY-MM-DD or null",
  "new_due_date": "YYYY-MM-DD or null",
  "reason": "string or null"
}
```

Rejected commands do not write a success audit event.

---

# Part II — CP5.2 Workflow Engine

## 23. CP5.2 scope

CP5.2 adds:

- `workflow_templates`;
- `workflow_template_versions`;
- `workflow_task_templates`;
- task workflow-source columns/FKs;
- template/version CRUD needed for administration;
- version publication;
- immutable published versions;
- deterministic version numbering;
- business-function assignee resolution;
- atomic workflow instantiation;
- preservation of source workflow version/template on generated tasks;
- workflow permission enforcement using `workflows.manage`;
- migration and regression tests.

CP5.2 does not yet implement Expertise workflow production because Expertises belongs to Stage 6.

## 24. Workflow template

`workflow_templates`:

```text
id UUID PK
name VARCHAR NOT NULL
scope_type VARCHAR NOT NULL
is_active BOOLEAN NOT NULL DEFAULT true
description TEXT NULL
created_at TIMESTAMPTZ NOT NULL
created_by UUID FK users NOT NULL
```

Supported initial `scope_type` values are data values, not route branches:

```text
contract
expertise
opo_control
```

Stage 5 only produces contract-linked tasks directly in CP5.3. Expertise production is connected in Stage 6.

## 25. Workflow versions

`workflow_template_versions`:

```text
id UUID PK
workflow_template_id UUID FK workflow_templates
version_number INTEGER NOT NULL
is_active BOOLEAN NOT NULL DEFAULT false
created_at TIMESTAMPTZ NOT NULL
created_by UUID FK users NOT NULL
UNIQUE(workflow_template_id, version_number)
```

A partial unique index enforces at most one active version per workflow template:

```text
UNIQUE(workflow_template_id) WHERE is_active = true
```

Version semantics:

- a newly created version starts unpublished (`is_active=false`);
- task-template rows may be edited only while its version is unpublished;
- publishing the version sets it active and deactivates the prior active version atomically;
- a version that has ever been published is immutable even if a newer version later becomes active;
- publishing a new version does not modify existing tasks.

To make the last rule enforceable, the service must distinguish `never published` from `previously published`. The physical CP5.2 model therefore adds `published_at TIMESTAMPTZ NULL` to `workflow_template_versions` even though the older target sketch only listed `is_active`. `published_at IS NOT NULL` is the immutable-publication marker.

## 26. Workflow task templates

`workflow_task_templates`:

```text
id UUID PK
workflow_template_version_id UUID FK workflow_template_versions
title VARCHAR NOT NULL
description TEXT NULL
assignee_function_role_id UUID FK employee_function_roles NULL
relative_due_days INTEGER NULL
priority task_priority NOT NULL DEFAULT normal
sort_order INTEGER NOT NULL DEFAULT 0
is_required BOOLEAN NOT NULL DEFAULT true
```

No hard-coded workflow task names are introduced into Python routes.

## 27. Workflow source on tasks

CP5.2 adds to `tasks`:

```text
source_workflow_template_version_id UUID FK workflow_template_versions NULL
source_workflow_task_template_id UUID FK workflow_task_templates NULL
```

Rules:

- manual tasks have both source fields NULL;
- workflow-generated tasks have both fields non-NULL;
- source task template must belong to source version;
- source fields are immutable after task creation;
- generated tasks cannot be soft-deleted; they are cancelled when historically no longer applicable.

## 28. Relative due-date calculation

`relative_due_days` is interpreted relative to an anchor date supplied by the invoking business process:

```text
due_date = anchor_date + relative_due_days calendar days
```

Examples:

- `-5` means five calendar days before the anchor;
- `0` means the anchor date;
- `10` means ten calendar days after the anchor;
- NULL means no generated due date.

The workflow engine does not guess the anchor. The caller supplies it explicitly.

Full production-calendar adjustment is deferred to Stage 11. The Stage 5 API is designed so Stage 11 can replace the date policy without changing workflow template persistence.

## 29. Business-function assignee resolution

`assignee_function_role_id` points to an employee business/function role, never to an authorization role.

Eligible automatic candidates:

- have the requested function-role assignment;
- employee is not soft-deleted;
- function role is active.

Resolution rules:

1. If no function role is configured and no explicit override is supplied, create the task unassigned.
2. If exactly one eligible employee exists, assign that employee.
3. If zero eligible employees exist for a configured function role, workflow instantiation fails closed.
4. If multiple eligible employees exist, workflow instantiation fails unless the caller supplies an explicit assignee override that is one of the eligible employees.
5. The engine never silently assigns all matching experts/specialists.

Failure is atomic: no subset of workflow tasks is committed.

## 30. Workflow instantiation

Input:

```text
workflow_template_version_id
anchor_date
actor_id
business links
optional per-task assignee overrides
```

Output:

```text
ordered list of created tasks
```

Instantiation rules:

- version must exist and be published;
- version must belong to an active workflow template;
- task templates are read in deterministic `sort_order, id` order;
- every generated task stores both workflow source IDs;
- all generated task rows, assignees, links and audit events commit atomically;
- a resolution/validation failure rolls the whole instantiation back.

Stage 5 does not add a generic `workflow_run` or global event-idempotency table because it is not part of the approved v1 model. Producing business services must call instantiation once per intended business event. If repeated external event delivery is introduced later, that owning integration must add an explicit idempotency key rather than relying on heuristic deduplication.

## 31. Workflow management authorization

Workflow template/version administration requires:

```text
workflows.manage
```

Business-function membership does not grant this permission.

Task mutations on generated tasks still use the normal task permissions/scopes after creation.

---

# Part III — CP5.3 Contract ↔ Tasks Integration

## 32. CP5.3 scope

CP5.3 connects the established Tasks module to the already verified Stage 4 contract lifecycle.

It implements:

- task-start producer for signed contracts;
- contract suspension overdue suppression;
- contract resume due-date shifting;
- contract termination cancellation of unfinished linked tasks;
- real Tasks completion-readiness provider;
- shared transaction boundaries for contract/task effects;
- cross-module audit behavior;
- regression coverage for Stage 4 lifecycle invariants.

## 33. Contract actual-work start

Stage 4 exposes internal-only `signed -> in_progress` through `mark_work_started()`.

CP5.3 connects the task producer:

```text
linked task new -> in_progress
AND linked contract status == signed
=> contract becomes in_progress in the same transaction
```

Rules:

- only actual `new -> in_progress` triggers work start;
- merely creating a task does not start the contract;
- changing a task not linked to a contract does not affect contracts;
- if one task is linked to multiple contracts, each eligible signed linked contract is started deterministically in the same transaction;
- a contract already `in_progress` is left unchanged;
- suspended/completed/terminated/archived contracts are not force-transitioned by a task status command;
- rejected task status changes do not start contracts.

No public HTTP endpoint is added for arbitrary contract work start.

## 34. Contract suspension and overdue behavior

When a contract is `suspended`, linked unfinished tasks are considered deadline-paused.

During an open contract suspension:

```text
is_overdue = false
```

for tasks linked to that contract and not in `completed/cancelled`.

The physical `due_date` is not modified at suspension time.

If a task is linked to more than one contract and at least one linked contract has an open suspension, the task is treated as paused for overdue computation in v1.

Notification suppression/recalculation is deferred to Stage 11.

## 35. Resume due-date shift

On `suspended -> in_progress`, CP5.3 shifts each linked unfinished task's non-null `due_date` by the suspension duration expressed in whole calendar dates:

```text
pause_days = ended_at.date() - started_at.date()
new_due_date = old_due_date + pause_days
```

A same-calendar-day suspension produces a zero-day shift.

This calendar-day rule matches DATE task deadlines. Production-calendar adjustment belongs to Stage 11.

Rules:

- completed/cancelled tasks are not shifted;
- tasks with NULL due date are not changed;
- each closed suspension interval is applied once;
- repeated resume commands are already rejected by the Stage 4 contract state machine and therefore cannot double-shift;
- task versions and audit metadata record accepted due-date shifts.

## 36. Contract termination

On contract termination, every linked unfinished task is cancelled in the same transaction:

```text
new -> cancelled
in_progress -> cancelled
```

Completed and already-cancelled tasks remain unchanged.

This applies to both manual and workflow-generated tasks linked to the terminated contract.

Historical task rows are preserved; termination never hard-deletes tasks.

If a task is linked to multiple contracts, termination of one linked contract cancels the task in v1 because the task is considered part of that contract's unfinished work. A future need for shared multi-contract work items would require an explicit different model rather than silently changing this rule.

## 37. Shared transaction boundary

CP5.3 must not produce partial states such as:

```text
contract resumed, tasks not shifted
contract terminated, tasks still active
task started, signed contract still signed
```

The implementation must therefore coordinate contract and task mutations before the single transaction commit.

The exact refactor may use internal mutation primitives or injected cross-module effects, but these architectural requirements are fixed:

- `Contracts` remains owner of contract state-machine validation;
- `Tasks` remains owner of task status/deadline mutation rules;
- routes do not duplicate either domain's business rules;
- cross-module orchestration occurs in an application/service boundary;
- one DB transaction owns the combined mutation and audit records;
- failure rolls both domains back.

## 38. Tasks completion-readiness provider

CP5.3 replaces the Stage 4 `tasks_provider_unavailable` blocker with a real Tasks readiness provider.

A contract is task-ready when it has no unfinished **required workflow-generated tasks** linked to it.

Blocking tasks:

```text
source_workflow_task_template_id IS NOT NULL
AND source task template is_required = true
AND task.status NOT IN (completed, cancelled)
AND task.deleted_at IS NULL
```

Manual tasks do not block contract completion merely because they are linked to the contract.

Cancelled required workflow tasks count as non-blocking, matching the approved Stage 4 rule that mandatory tasks may be done or cancelled before completion.

The other readiness dimensions remain fail-closed until their owning stages:

```text
expertises_provider_unavailable
documents_provider_unavailable
conclusion_delivery_provider_unavailable
```

## 39. Contract deadline changes outside suspension

Stage 5 does not automatically reschedule tasks for every change of `contracts.end_date` in CP5.3.

In particular, signed addendum deadline recalculation is not inferred heuristically from task links. Workflow-generated tasks preserve their source template, so a later dedicated contract-deadline recalculation policy can deterministically recompute tasks when that behavior is explicitly activated.

This keeps CP5.3 focused on the already approved suspension/resume/termination effects and avoids changing due dates without a defined anchor policy.

---

# Part IV — Error Handling, Concurrency and Testing

## 40. Validation and error policy

Domain validation errors use the project's established 422-style business-error behavior.

Not-found/authorization behavior remains non-enumerating:

- absent task;
- inaccessible task;
- foreign nested task resource;
- inaccessible linked entity during mutation;

must not reveal sensitive existence differences where the existing module policy uses generic 404.

Database integrity errors that represent a business invariant should be translated into stable service/API errors where the project already follows that pattern.

## 41. Concurrency

Critical Stage 5 mutations use row locks or equivalent transaction-safe patterns where concurrent execution could violate invariants.

Required concurrency-sensitive operations include:

- status transition of the same task;
- assignee replacement versus task deletion;
- workflow version publication;
- deterministic workflow version numbering;
- workflow instantiation where shared contract state is started;
- resume due-date shifting;
- termination cancellation;
- cross-module task/contract status transitions.

Optimistic `version` fields remain part of stored entities, but Stage 5 does not invent a new HTTP concurrency protocol unless the existing project introduces one. DB locking protects the checkpoint's transactional invariants.

## 42. TDD strategy

Every implementation checkpoint follows RED -> GREEN -> regression.

Representative CP5.1 RED groups:

- migration/model shape;
- status/priority enum behavior;
- task CRUD and due-date extension reason;
- multiple assignees;
- supported links and primary-link invariant;
- comments;
- overdue computation;
- ALL/ASSIGNED/RELATED/OWN and `tasks.view_all`;
- exact permission isolation;
- generic 404 anti-enumeration;
- rollback/no-audit on rejected mutations;
- migration upgrade/downgrade/upgrade.

Representative CP5.2 RED groups:

- workflow schema;
- one active version per template;
- published version immutability;
- deterministic version numbering;
- task-template editing only on unpublished versions;
- assignee resolution 0/1/many;
- explicit override validation;
- atomic instantiation;
- source version/template preservation;
- generated-task delete prohibition;
- `workflows.manage` isolation.

Representative CP5.3 RED groups:

- first linked task start starts signed contract;
- task creation alone does not start contract;
- task transition rollback rolls back contract start;
- suspended contract suppresses linked-task overdue;
- resume shifts only unfinished non-null due dates exactly once;
- terminate cancels unfinished tasks atomically;
- completed tasks survive termination unchanged;
- Tasks readiness blocks on unfinished required generated tasks;
- manual tasks do not block completion;
- remaining readiness providers stay fail-closed;
- Stage 4 contract lifecycle regression remains green.

## 43. Migration plan

Revision IDs must remain within Alembic's effective `version_num` length used by this project.

Planned migration chain:

```text
0012_stage4_contract_lifecycle
  -> 0013_stage5_tasks
  -> 0014_stage5_workflows
  -> 0015_stage5_contract_tasks
```

Expected physical responsibilities:

### `0013_stage5_tasks`

- task enums;
- tasks;
- task_assignees;
- existing-entity task link tables;
- comments;
- comment_tasks;
- task indexes/constraints.

### `0014_stage5_workflows`

- workflow_templates;
- workflow_template_versions including `published_at`;
- workflow_task_templates;
- source workflow FKs on tasks;
- one-active-version partial unique index.

### `0015_stage5_contract_tasks`

Prefer no new business table unless implementation proves a DB constraint/index is required for the approved integration behavior. Cross-module integration should primarily reuse existing contract/task/suspension data rather than introduce duplicate state.

`task_expertises` is explicitly not part of these migrations; Stage 6 owns it.

## 44. Documentation updates

At checkpoint acceptance, update only authoritative documents affected by verified behavior:

- `PROJECT_STATUS.md` every checkpoint;
- `docs/DATA_MODEL.md` for actual schema refinements;
- `docs/BUSINESS_RULES.md` for confirmed task/workflow lifecycle rules;
- `docs/PERMISSIONS.md` for the explicit `tasks.complete` reserved/unused clarification and task scope semantics;
- `docs/ARCHITECTURE.md` only if the implemented service boundary materially refines the documented module boundary;
- `docs/UI_MAP.md` only when backend API behavior changes what the later frontend must present.

## 45. Acceptance criteria — CP5.1

CP5.1 is ready for review when:

1. migration head is `0013_stage5_tasks` with one Alembic head;
2. task CRUD, assignees, status commands, supported links and comments work through service/API tests;
3. late due-date changes require a reason and rejected attempts are atomic;
4. `is_overdue` is computed and terminal tasks are never overdue;
5. ALL/ASSIGNED/RELATED/OWN task access and `tasks.view_all` are covered;
6. exact task permission isolation is covered;
7. inaccessible task/link resources preserve anti-enumeration behavior;
8. full Ruff and Alembic verification pass;
9. full regression passes on exact final HEAD;
10. a stacked draft PR is opened against CP4.2 or the exact approved parent checkpoint;
11. no merge into integration is performed automatically.

## 46. Acceptance criteria — CP5.2

CP5.2 is ready for review when:

1. migration head is `0014_stage5_workflows`;
2. workflow templates and versions are persisted;
3. at most one active version exists per template;
4. published versions/task templates are immutable;
5. new versions do not mutate prior generated tasks;
6. 0/1/many business-function assignment cases are verified;
7. instantiation is atomic and source metadata is preserved;
8. generated tasks cannot be soft-deleted;
9. `workflows.manage` is enforced;
10. full regression is green on exact final HEAD;
11. no automatic integration merge occurs.

## 47. Acceptance criteria — CP5.3

CP5.3 is ready for review when:

1. a linked task entering `in_progress` starts an eligible signed contract atomically;
2. contract suspension suppresses overdue for linked unfinished tasks;
3. resume shifts deadlines once by the closed suspension interval;
4. termination atomically cancels unfinished linked tasks;
5. real Tasks readiness replaces only the Tasks unavailable blocker;
6. manual tasks do not unexpectedly block contract completion;
7. Stage 4 lifecycle tests remain green;
8. combined task/contract operations roll back fully on failure;
9. full regression and migration verification pass on exact final HEAD;
10. no automatic integration merge occurs.

## 48. Deferred ownership after Stage 5

Stage 5 deliberately leaves these responsibilities to their owning stages:

### Stage 6 Expertises

- `task_expertises` physical FK link;
- expertise workflow producer;
- expertise work-start producer;
- expertise completion-readiness provider.

### Stage 8 Documents

- task attachments/document links;
- document readiness provider;
- addendum document link.

### Stage 11 Calendar and Notifications

- production calendar;
- due-soon 30/14/5 policy;
- assignment notifications;
- overdue notifications;
- suspension-aware notification suppression/recalculation;
- @mention notifications and deduplication.

### Frontend stage

- `/tasks` registry and task card;
- workflow administration UI;
- contract task tab integration.

## 49. Git and review policy

Initial branch:

```text
agent/stage5-cp51-tasks-core
```

It starts from exact CP4.2 HEAD:

```text
7066e648543c1aaccbdcc85016a9340d9d304c70
```

CP5.2 and CP5.3 use fresh stacked branches from the verified predecessor HEAD.

Rules:

- no direct development in integration or main;
- no automatic merge of PR #5 or any Stage 5 PR;
- small TDD commits are preferred;
- rejected test-first commits may exist as auditable RED checkpoints;
- final review PRs remain draft unless the user explicitly chooses otherwise;
- Issue #3 remains the session handoff/source-of-truth log.

## 50. Definition of Done for Stage 5

Stage 5 is complete only after all three checkpoints are independently green and reviewed:

```text
CP5.1 Tasks Core          GREEN
CP5.2 Workflow Engine     GREEN
CP5.3 Contract Integration GREEN
```

At that point the application has a stable task domain, data-driven workflow foundation and real contract/task lifecycle integration without prematurely implementing Expertises, Documents, Calendar or Notifications.