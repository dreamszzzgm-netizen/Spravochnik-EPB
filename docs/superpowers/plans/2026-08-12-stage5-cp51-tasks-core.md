# Stage 5 CP5.1 Tasks Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Stage 5 CP5.1 backend task foundation: persistence, assignees, supported FK-backed links, shared task comments, due-date rules, strict status commands, scoped authorization, registry API, audit, migrations and regression coverage.

**Architecture:** Add a focused `app/modules/tasks` bounded module plus a minimal shared `app/modules/comments` persistence module. Task API accepts a normalized list of typed links, while persistence uses only real FK-backed link tables. CP5.1 deliberately does not implement workflow templates, expertise links, document attachments, notifications or contract lifecycle side effects.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, PostgreSQL 17, Alembic, Pydantic, pytest, existing identity/RBAC/audit infrastructure.

## Global Constraints

- Base checkpoint is exact Stage 4 CP4.2 HEAD `7066e648543c1aaccbdcc85016a9340d9d304c70`.
- Working branch is `agent/stage5-cp51-tasks-core`; do not merge or modify integration automatically.
- Alembic parent is `0012_stage4_contract_lifecycle`; new revision id is `0013_stage5_tasks_core`.
- Persisted task statuses are exactly `new`, `in_progress`, `completed`, `cancelled`.
- Persisted priorities are exactly `low`, `normal`, `high`, `urgent`; default is `normal`.
- `overdue` is computed, never persisted as a main task status.
- General PATCH must not mutate task status, assignees, creator or future workflow-source fields.
- A manual task may have zero assignees; workflow assignee guarantees belong to CP5.2.
- A non-personal task must have at least one supported business link; a personal task may have none.
- CP5.1 supports links only to organizations, contracts, contract items, technical devices, buildings and OPO.
- Do not create `task_expertises` before Stage 6 or task-document links before Stage 8.
- Moving a due date later, or clearing an existing due date, requires a non-empty business reason; earlier/new due dates do not.
- Use exact permission isolation for `tasks.view`, `tasks.view_all`, `tasks.create`, `tasks.assign`, `tasks.edit`, `tasks.change_status`, `tasks.delete`, `tasks.restore`, `tasks.comment`.
- `tasks.complete` stays reserved and unused in CP5.1.
- Task scopes: ALL=all, ASSIGNED=active assignee, OWN=creator employee, RELATED=linked business entity resolves to an allowed organization.
- Inaccessible/foreign tasks and linked resources must preserve non-enumerating 404 behavior.
- Accepted multi-row mutations and their audit row commit atomically; rejected commands do not increment version and do not write a success audit event.
- No frontend changes in CP5.1.

---

## File Structure

Create:

```text
app/modules/comments/__init__.py
app/modules/comments/models.py
app/modules/tasks/__init__.py
app/modules/tasks/enums.py
app/modules/tasks/models.py
app/modules/tasks/repository.py
app/modules/tasks/service.py
app/modules/tasks/schemas.py
app/modules/tasks/routes.py
alembic/versions/0013_stage5_tasks_core.py
tests/integration/test_stage5_tasks_migration.py
tests/integration/test_tasks_core.py
tests/integration/test_tasks_status_due_date.py
tests/integration/test_tasks_authorization.py
tests/integration/test_tasks_api.py
tests/integration/test_task_comments.py
```

Modify:

```text
alembic/env.py
app/main.py
app/modules/identity/authorization.py
tests/conftest.py
docs/BUSINESS_RULES.md
docs/DATA_MODEL.md
docs/PERMISSIONS.md
PROJECT_STATUS.md
```

Responsibilities:

- `comments/models.py`: generic `Comment` plus task link model only; no task authorization logic.
- `tasks/enums.py`: `TaskStatus`, `TaskPriority`, `TaskLinkKind`.
- `tasks/models.py`: task, assignee and six supported link ORM models.
- `tasks/repository.py`: task retrieval/list/filter queries, assignee/link read helpers, typed link organization resolution.
- `tasks/service.py`: all task business commands, validation, audit and status/due-date rules.
- `tasks/schemas.py`: API request/response models and paginated envelope.
- `tasks/routes.py`: HTTP mapping only; permission/scope resolution, anti-enumeration, service calls.
- `identity/authorization.py`: add task protocol/access helper using precomputed assignee and related organization ids.

---

### Task 1: Migration and ORM foundation

**Files:**
- Create: `app/modules/comments/__init__.py`
- Create: `app/modules/comments/models.py`
- Create: `app/modules/tasks/__init__.py`
- Create: `app/modules/tasks/enums.py`
- Create: `app/modules/tasks/models.py`
- Create: `alembic/versions/0013_stage5_tasks_core.py`
- Modify: `alembic/env.py`
- Modify: `tests/conftest.py`
- Create: `tests/integration/test_stage5_tasks_migration.py`

**Interfaces:**
- Produces `TaskStatus`, `TaskPriority`, `TaskLinkKind`.
- Produces ORM types `Task`, `TaskAssignee`, `TaskOrganization`, `TaskContract`, `TaskContractItem`, `TaskTechnicalDevice`, `TaskBuilding`, `TaskOPO`, `Comment`, `CommentTask`.
- Later tasks import these exact names.

- [ ] **Step 1: Write migration/model RED tests**

Test exact enum values and table constraints:

```python
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task
from app.modules.comments.models import Comment, CommentTask


def test_task_enums_are_exact():
    assert [item.value for item in TaskStatus] == ["new", "in_progress", "completed", "cancelled"]
    assert [item.value for item in TaskPriority] == ["low", "normal", "high", "urgent"]


def test_task_models_use_expected_tables():
    assert Task.__tablename__ == "tasks"
    assert Comment.__tablename__ == "comments"
    assert CommentTask.__tablename__ == "comment_tasks"
```

Add PostgreSQL introspection assertions that `tasks`, `task_assignees`, all six link tables, `comments`, and `comment_tasks` exist after `upgrade head`, that `task_status` and `task_priority` have exact values, and that `0013 -> 0012 -> 0013` works.

- [ ] **Step 2: Run RED**

Run:

```bash
python -m pytest tests/integration/test_stage5_tasks_migration.py -q
```

Expected: FAIL because task/comment enums, models and revision `0013_stage5_tasks_core` do not exist.

- [ ] **Step 3: Implement enums and ORM**

`TaskStatus` and `TaskPriority` are `enum.StrEnum`. `TaskLinkKind` contains `organization`, `contract`, `contract_item`, `technical_device`, `building`, `opo`.

`Task` fields in CP5.1:

```python
id: UUID
title: str
description: str | None
creator_employee_id: UUID
due_date: date | None
priority: TaskPriority
status: TaskStatus
is_personal: bool
created_at: datetime
updated_at: datetime
completed_at: datetime | None
cancelled_at: datetime | None
deleted_at: datetime | None
version: int
```

Do not add workflow-source columns yet.

Create indexes at minimum on `tasks.creator_employee_id`, `tasks.status`, `tasks.due_date`, `tasks.deleted_at`, `task_assignees.employee_id`, and each link table's business entity id.

- [ ] **Step 4: Implement migration `0013_stage5_tasks_core`**

Migration creates both PostgreSQL enums, all CP5.1 tables and indexes with real FKs. `comments` is shared persistence; `comment_tasks.comment_id` is UNIQUE and both FKs use cascading link cleanup. Downgrade drops child links/tables before parent tables and drops enums last.

- [ ] **Step 5: Register metadata and clean test DB**

In `alembic/env.py` import task/comment models for metadata. In `tests/conftest.py`, add new task/comment tables to the TRUNCATE list before their referenced parents.

- [ ] **Step 6: Run GREEN and migration checks**

```bash
python -m pytest tests/integration/test_stage5_tasks_migration.py -q
python -m alembic heads
```

Expected: tests PASS and single head `0013_stage5_tasks_core`.

- [ ] **Step 7: Commit**

```bash
git add app/modules/comments app/modules/tasks/enums.py app/modules/tasks/models.py alembic/versions/0013_stage5_tasks_core.py alembic/env.py tests/conftest.py tests/integration/test_stage5_tasks_migration.py
git commit -m "feat(tasks): add CP5.1 task persistence foundation"
```

---

### Task 2: Task service CRUD, assignees and FK-backed links

**Files:**
- Create: `app/modules/tasks/repository.py`
- Create: `app/modules/tasks/service.py`
- Test: `tests/integration/test_tasks_core.py`

**Interfaces:**
- Produces `TaskNotFoundError`, `TaskValidationError`, `TaskService`.
- Produces normalized input dataclass `TaskLinkInput(kind: TaskLinkKind, entity_id: UUID, is_primary: bool = False)` in `service.py`.
- Repository produces `get_task`, `get_task_for_update`, `get_task_assignee_ids`, `get_task_links`, `get_task_related_organization_ids`.

- [ ] **Step 1: Write RED service tests**

Cover:

```python
service.create_task(... title="  Inspect vessel  ", is_personal=True, links=[])
service.replace_assignees(... employee_ids=[employee_a.id, employee_b.id, employee_a.id])
service.update_task(... due_date=old_date, due_date_change_reason=None, links=[...])
service.delete_task(...)
service.restore_task(...)
```

Assertions:
- title trims;
- new task starts `new`/`normal`/version 1;
- duplicate assignees normalize;
- soft-deleted employees cannot be assigned;
- non-personal task without links is rejected;
- no more than one primary link is accepted across all kinds;
- foreign `contract_item` plus mismatching explicit contract link is rejected;
- deleted task disappears from ordinary `get_task` but can be loaded with `include_deleted=True`;
- rejected mutations leave version/audit unchanged.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_core.py -q
```

Expected: FAIL because repository/service do not exist.

- [ ] **Step 3: Implement repository helpers**

Use SQLAlchemy 2.x `select()` and explicit link table queries. `get_task_for_update()` uses `.with_for_update()`. Related organization resolution must include:

```text
direct organization
contract.customer_organization_id
contract_item -> contract.customer_organization_id
technical_device.organization_id
building.organization_id
opo.owner_organization_id and opo.operating_organization_id
```

- [ ] **Step 4: Implement TaskService minimal business commands**

Exact public methods:

```python
create_task(db, *, actor_user_id, creator_employee_id, title, description, due_date, priority, is_personal, assignee_ids, links) -> Task
update_task(db, *, actor_user_id, task, title, description, due_date, priority, is_personal, links, due_date_change_reason) -> Task
delete_task(db, *, actor_user_id, task) -> None
restore_task(db, *, actor_user_id, task) -> None
replace_assignees(db, *, actor_user_id, task, employee_ids) -> list[UUID]
```

Each accepted command flushes, writes existing `write_audit()`, commits, refreshes. Validation occurs before mutation where practical; any exception rolls back.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest tests/integration/test_tasks_core.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/modules/tasks/repository.py app/modules/tasks/service.py tests/integration/test_tasks_core.py
git commit -m "feat(tasks): add task CRUD assignees and business links"
```

---

### Task 3: Strict task status machine and due-date extension rule

**Files:**
- Modify: `app/modules/tasks/service.py`
- Test: `tests/integration/test_tasks_status_due_date.py`

**Interfaces:**
- Adds `TaskService.change_status(db, *, actor_user_id, task, target_status) -> Task`.
- Adds pure helper `is_task_overdue(task, *, today: date) -> bool`.

- [ ] **Step 1: Write RED tests**

Verify exactly:

```text
new -> in_progress
new -> cancelled
in_progress -> completed
in_progress -> cancelled
```

Reject `new -> completed`, any terminal transition, and same-status writes. Assert `completed_at`/`cancelled_at` are set exactly on terminal entry. Assert `is_task_overdue` is true only when `due_date < today` and status is not terminal.

Due-date tests:
- old 20 Aug -> new 19 Aug: accepted without reason;
- old NULL -> new 20 Aug: accepted without reason;
- old 20 Aug -> new 21 Aug: rejected without reason, accepted with trimmed non-empty reason;
- old 20 Aug -> NULL: rejected without reason;
- audit metadata contains old/new/reason for accepted change.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_status_due_date.py -q
```

Expected: FAIL because status command/overdue helper are absent or due-date guard is incomplete.

- [ ] **Step 3: Implement status machine and overdue helper**

Use a constant transition map. General update stays unable to alter status. Set terminal timestamp once and increment version once per accepted transition.

- [ ] **Step 4: Implement exact extension guard**

Treat clearing a non-null due date as an extension. Clean reason with `.strip()` and include structured metadata keys `old_due_date`, `new_due_date`, `reason` in `task.updated` audit when due date changes.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest tests/integration/test_tasks_status_due_date.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/modules/tasks/service.py tests/integration/test_tasks_status_due_date.py
git commit -m "feat(tasks): enforce task lifecycle and due date rules"
```

---

### Task 4: Task authorization and scope semantics

**Files:**
- Modify: `app/modules/identity/authorization.py`
- Modify: `app/modules/tasks/repository.py`
- Test: `tests/integration/test_tasks_authorization.py`

**Interfaces:**
- Add protocol `TaskLike` with `creator_employee_id`.
- Add `can_access_task(ctx, task, *, assignee_employee_ids: set[UUID], related_organization_ids: set[UUID]) -> bool`.

- [ ] **Step 1: Write RED authorization tests**

For each requested permission code independently test ALL/ASSIGNED/OWN/RELATED. Include deny cases, malformed RELATED config fail-closed, multiple assignees, OPO owner/operator relation, contract-item relation, and exact permission isolation.

Also test `tasks.view_all` read override does not authorize `tasks.edit`, `tasks.assign`, `tasks.change_status`, `tasks.comment`, delete or restore.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_authorization.py -q
```

Expected: FAIL because `can_access_task` and task relation query helpers are absent.

- [ ] **Step 3: Implement task access helper**

Logic:

```python
if ctx.has_all_scope:
    return True
return (
    ScopeType.ASSIGNED in ctx.active_scope_types and ctx.employee_id in assignee_employee_ids
    or ScopeType.OWN in ctx.active_scope_types and ctx.employee_id == task.creator_employee_id
    or ScopeType.RELATED in ctx.active_scope_types and bool(ctx.related_organization_ids & related_organization_ids)
)
```

Do not reinterpret business-function roles as authorization roles.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/integration/test_tasks_authorization.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/identity/authorization.py app/modules/tasks/repository.py tests/integration/test_tasks_authorization.py
git commit -m "feat(tasks): add scoped task authorization"
```

---

### Task 5: API schemas and task registry/CRUD routes

**Files:**
- Create: `app/modules/tasks/schemas.py`
- Create: `app/modules/tasks/routes.py`
- Modify: `app/main.py`
- Test: `tests/integration/test_tasks_api.py`

**Interfaces:**
- Request link shape:

```python
class TaskLinkRequest(BaseModel):
    kind: TaskLinkKind
    entity_id: UUID
    is_primary: bool = False
```

- Paginated list response uses `{items, total, page, page_size}`.

- [ ] **Step 1: Write RED HTTP tests**

Cover routes:

```text
GET    /api/tasks
POST   /api/tasks
GET    /api/tasks/{task_id}
PATCH  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
POST   /api/tasks/{task_id}/restore
PUT    /api/tasks/{task_id}/assignees
POST   /api/tasks/{task_id}/status
```

Assert:
- 401 unauthenticated;
- 403 when permission missing;
- 404 for inaccessible task and inaccessible linked entity;
- PATCH rejects `status`, `assignee_ids`, creator fields as extra/forbidden request data;
- mutation permissions are exact;
- registry respects scopes and `tasks.view_all`;
- filters `assignee_id`, `creator_employee_id`, `status`, `priority`, `due_from`, `due_to`, `contract_id`, `organization_id`, `is_overdue`;
- list default excludes deleted rows;
- responses include assignees, normalized links and computed `is_overdue`.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_api.py -q
```

Expected: FAIL because schemas/router are absent.

- [ ] **Step 3: Implement schemas**

Use Pydantic `extra="forbid"` on mutation payloads so protected fields cannot be silently ignored. `TaskResponse` includes task scalar fields, `assignee_ids`, `links`, `is_overdue`.

- [ ] **Step 4: Implement routes**

Use existing `require_scoped_permission()` for requested task permission. Build a task-specific `_task_or_404()` that preloads assignee ids + related organization ids and calls `can_access_task`. For read/list, allow `tasks.view_all` as an alternate read context only; do not use it for mutations.

Cross-resource write validation must verify the actor can reference every requested linked resource using existing owning-module view/access helpers before calling `TaskService`.

Map `TaskValidationError` to HTTP 422 and generic inaccessible records to non-enumerating 404.

- [ ] **Step 5: Register router and run GREEN**

```bash
python -m pytest tests/integration/test_tasks_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/modules/tasks/schemas.py app/modules/tasks/routes.py app/main.py tests/integration/test_tasks_api.py
git commit -m "feat(tasks): expose scoped task API"
```

---

### Task 6: Shared task comments API

**Files:**
- Modify: `app/modules/tasks/repository.py`
- Modify: `app/modules/tasks/service.py`
- Modify: `app/modules/tasks/schemas.py`
- Modify: `app/modules/tasks/routes.py`
- Test: `tests/integration/test_task_comments.py`

**Interfaces:**
- Adds `TaskService.add_comment(db, *, actor_user_id, author_employee_id, task, text) -> Comment`.
- Adds repository `list_task_comments(db, task_id) -> list[Comment]`.

- [ ] **Step 1: Write RED tests**

Routes:

```text
GET  /api/tasks/{task_id}/comments
POST /api/tasks/{task_id}/comments
```

Assert blank text rejected, author always authenticated actor's employee, `tasks.comment` required for POST, `tasks.view`/`tasks.view_all` sufficient for GET according to task scope, foreign task 404, comments returned oldest-first, and accepted add writes `task.comment_added` audit.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_task_comments.py -q
```

Expected: FAIL because comment service/routes are absent.

- [ ] **Step 3: Implement comment service/query/routes**

Create `Comment`, flush to obtain id, create `CommentTask`, write audit, commit atomically. No edit/delete/@mention support in CP5.1.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/integration/test_task_comments.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/tasks tests/integration/test_task_comments.py
git commit -m "feat(tasks): add shared task comments"
```

---

### Task 7: Query correctness, locking and edge-case hardening

**Files:**
- Modify: `app/modules/tasks/repository.py`
- Modify: `app/modules/tasks/service.py`
- Extend: `tests/integration/test_tasks_core.py`
- Extend: `tests/integration/test_tasks_api.py`
- Extend: `tests/integration/test_tasks_authorization.py`

**Interfaces:**
- No new public API; hardens existing contract.

- [ ] **Step 1: Add RED edge tests**

Cover:
- same task mutated through stale version/reloaded row does not silently overwrite protected state;
- `get_task_for_update()` is used for status/assignee/update/delete/restore HTTP commands;
- duplicate links normalize per `(kind, entity_id)`;
- two primary links are rejected before any link replacement;
- link replacement rollback leaves old links intact when one requested target is invalid;
- filtered registry does not duplicate a task because it has multiple assignees/links;
- `is_overdue=true/false` pagination total is correct;
- deleted linked business resource cannot be newly referenced;
- terminal task remains readable but status cannot change;
- restoring a task does not rewrite status or terminal timestamps.

- [ ] **Step 2: Run focused RED**

```bash
python -m pytest tests/integration/test_tasks_core.py tests/integration/test_tasks_api.py tests/integration/test_tasks_authorization.py -q
```

- [ ] **Step 3: Apply only proven fixes**

Prefer `EXISTS` subqueries for registry relation filters to avoid duplicate rows. Use row locking at HTTP command boundary/repository helper where the existing project follows this convention. Preserve service rollback semantics.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/integration/test_tasks_core.py tests/integration/test_tasks_api.py tests/integration/test_tasks_authorization.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/tasks tests/integration/test_tasks_core.py tests/integration/test_tasks_api.py tests/integration/test_tasks_authorization.py
git commit -m "test(tasks): harden task queries and transaction invariants"
```

---

### Task 8: Authoritative docs and project status

**Files:**
- Modify: `docs/BUSINESS_RULES.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/PERMISSIONS.md`
- Modify: `PROJECT_STATUS.md`

**Interfaces:**
- Documentation must describe actual CP5.1 behavior only, not CP5.2/CP5.3 as already implemented.

- [ ] **Step 1: Update business rules**

Record task states, multiple assignees, personal/non-personal link rule, manual due-date extension reason, computed overdue, and CP5.1 deletion/restore behavior.

- [ ] **Step 2: Update data model**

Replace target-only Stage 5 task section with actual CP5.1 physical schema. Explicitly mark workflow source FKs, `task_expertises`, document links and mentions as deferred.

- [ ] **Step 3: Update permissions**

Document exact task permission isolation, scope semantics, `tasks.view_all` read override, and reserved-unused `tasks.complete`.

- [ ] **Step 4: Update project status**

Set CP5.1 to verification state with exact branch, head, Alembic revision and latest proven test numbers only after verification commands have actually run.

- [ ] **Step 5: Commit**

```bash
git add docs/BUSINESS_RULES.md docs/DATA_MODEL.md docs/PERMISSIONS.md PROJECT_STATUS.md
git commit -m "docs(stage5): document CP5.1 tasks core"
```

---

### Task 9: Full regression, whole-branch review and stacked draft PR

**Files:**
- Review all CP5.1 changes relative to `7066e648543c1aaccbdcc85016a9340d9d304c70`.
- Update `PROJECT_STATUS.md` only if final exact HEAD/test numbers differ from Task 8.

**Interfaces:**
- Produces final review checkpoint only; no integration merge.

- [ ] **Step 1: Run full backend verification**

```bash
python -m ruff check app tests alembic
python -m alembic heads
python -m alembic upgrade head
python -m pytest -q
```

Expected:
- Ruff PASS;
- exactly one Alembic head `0013_stage5_tasks_core`;
- upgrade PASS;
- full pytest PASS.

- [ ] **Step 2: Verify migration round trip on PostgreSQL**

Run the Stage 5 migration test that performs `0013 -> 0012 -> 0013`; verify the test DB is returned to `0013_stage5_tasks_core`.

- [ ] **Step 3: Whole-branch diff review**

Compare CP4.2 base to CP5.1 HEAD. Confirm no frontend, workflow engine, expertise tables, document tables, notifications, contract lifecycle effects or integration-branch changes slipped into the checkpoint.

- [ ] **Step 4: Security review checklist**

Verify:
- exact permission isolation;
- ALL/ASSIGNED/RELATED/OWN;
- malformed RELATED fail-closed;
- `tasks.view_all` read-only;
- linked-resource anti-enumeration;
- actor cannot forge creator/comment author;
- protected status/assignee fields cannot be PATCHed;
- rejected commands leave no success audit.

- [ ] **Step 5: Commit any review-only fixes and rerun exact-HEAD verification**

Do not report GREEN from an earlier commit after changing code/docs.

- [ ] **Step 6: Create stacked draft PR**

PR head:

```text
agent/stage5-cp51-tasks-core
```

PR base:

```text
agent/stage4-cp42-contract-lifecycle-addenda
```

PR title:

```text
Stage 5 CP5.1: Tasks Core backend
```

PR body must include exact final HEAD, parent CP4.2, Alembic head, verification results, implemented scope, CP5.2/CP5.3 deferrals, and `DO NOT MERGE into integration automatically`.

- [ ] **Step 7: Verify PR-triggered merge-ref CI**

Require Ruff, Alembic and full pytest GREEN on the stacked PR merge ref.

- [ ] **Step 8: Update Issue #3 handoff**

Post final branch/HEAD/revision/PR/CI numbers and the next checkpoint `CP5.2 Workflow Engine`.

---

## Acceptance Matrix

CP5.1 is complete only when all are true:

```text
A. Scope        — Tasks Core only; future stages not pulled in
B. Database     — 0013 single head; real FK task links; round-trip verified
C. Backend      — CRUD, assignees, links, status, due date, comments, registry
D. UI           — no frontend changes in CP5.1
E. Tests        — targeted RED/GREEN evidence + full regression GREEN
F. Invariants   — computed overdue, terminal states, due extension reason, one primary link
G. Security     — exact permissions + ALL/ASSIGNED/RELATED/OWN + anti-enumeration
H. Regression   — Stage 0-4 tests remain GREEN
I. Verdict      — draft stacked PR only; integration untouched
```

## Deferred to CP5.2 / CP5.3 / Later Stages

```text
CP5.2: workflow templates, versions, task templates, assignee resolution, atomic instantiation
CP5.3: contract work-start producer, suspension/resume deadline shift, termination cancellation, Tasks readiness provider
Stage 6: task_expertises and expertise-triggered workflow integration
Stage 8: task document attachments
Stage 11: due-soon calendar, 30/14/5 reminders, notifications and dedup
```
