# Stage 5 CP5.1 Tasks Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Stage 5 CP5.1 backend task foundation: persistence, assignees, supported FK-backed links, shared task comments, due-date rules, strict status commands, scoped authorization, registry API, audit, migrations and regression coverage.

**Architecture:** Add a focused `app/modules/tasks` bounded module plus a minimal shared `app/modules/comments` persistence module. Task API accepts a normalized list of typed links, while persistence uses only real FK-backed link tables. CP5.1 deliberately excludes workflow templates, expertise links, document attachments, notifications and contract lifecycle side effects.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, PostgreSQL 17, Alembic, Pydantic, pytest, existing identity/RBAC/audit infrastructure.

## Global Constraints

- Base checkpoint: Stage 4 CP4.2 HEAD `7066e648543c1aaccbdcc85016a9340d9d304c70`.
- Working branch: `agent/stage5-cp51-tasks-core`.
- Never merge or modify integration automatically.
- Alembic parent: `0012_stage4_contract_lifecycle`; new revision: `0013_stage5_tasks_core`.
- Task statuses: `new`, `in_progress`, `completed`, `cancelled`.
- Priorities: `low`, `normal`, `high`, `urgent`; default `normal`.
- `overdue` is computed, never persisted as a task status.
- General PATCH cannot change status, assignees, creator or future workflow-source fields.
- Manual task may have zero assignees.
- Non-personal task requires at least one supported business link; personal task may have none.
- CP5.1 links only organizations, contracts, contract items, technical devices, buildings and OPO.
- Do not create `task_expertises` before Stage 6 or task-document links before Stage 8.
- Moving a due date later or clearing an existing due date requires a non-empty business reason.
- Exact task permissions: `tasks.view`, `tasks.view_all`, `tasks.create`, `tasks.assign`, `tasks.edit`, `tasks.change_status`, `tasks.delete`, `tasks.restore`, `tasks.comment`.
- `tasks.complete` remains reserved and unused.
- Scopes: ALL=all, ASSIGNED=assignee, OWN=creator employee, RELATED=linked business entity resolves to an allowed organization.
- Inaccessible tasks and linked resources use non-enumerating 404 behavior.
- Accepted multi-row mutations and audit commit atomically; rejected commands do not increment version and do not write success audit.
- No frontend changes.

## File Map

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
- `comments/models.py`: generic comment persistence plus task link model; no task authorization.
- `tasks/enums.py`: `TaskStatus`, `TaskPriority`, `TaskLinkKind`.
- `tasks/models.py`: task, assignee and six supported FK link models.
- `tasks/repository.py`: task/list/filter queries and relation-resolution helpers.
- `tasks/service.py`: business commands, validation, audit, lifecycle and due-date rules.
- `tasks/schemas.py`: API request/response models and paginated envelope.
- `tasks/routes.py`: HTTP mapping and permission/scope enforcement only.
- `identity/authorization.py`: task access decision using precomputed assignees and related organization ids.

---

### Task 1: Migration and ORM foundation

**Files:** create comment/task models and migration; modify `alembic/env.py`, `tests/conftest.py`; create `tests/integration/test_stage5_tasks_migration.py`.

**Interfaces:** produce `TaskStatus`, `TaskPriority`, `TaskLinkKind`, `Task`, `TaskAssignee`, `TaskOrganization`, `TaskContract`, `TaskContractItem`, `TaskTechnicalDevice`, `TaskBuilding`, `TaskOPO`, `Comment`, `CommentTask`.

- [ ] **Step 1: Write RED tests**

```python
from app.modules.comments.models import Comment, CommentTask
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task


def test_task_enums_are_exact():
    assert [item.value for item in TaskStatus] == ["new", "in_progress", "completed", "cancelled"]
    assert [item.value for item in TaskPriority] == ["low", "normal", "high", "urgent"]


def test_task_models_use_expected_tables():
    assert Task.__tablename__ == "tasks"
    assert Comment.__tablename__ == "comments"
    assert CommentTask.__tablename__ == "comment_tasks"
```

Add PostgreSQL assertions for `tasks`, `task_assignees`, `task_organizations`, `task_contracts`, `task_contract_items`, `task_technical_devices`, `task_buildings`, `task_opos`, `comments`, `comment_tasks`, exact enum values, FK targets, indexes, and migration round trip `0013 -> 0012 -> 0013`.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_stage5_tasks_migration.py -q
```

Expected: import/revision failures because Stage 5 persistence does not exist.

- [ ] **Step 3: Implement enums and ORM**

`TaskStatus`/`TaskPriority` are `enum.StrEnum`. `TaskLinkKind` values are `organization`, `contract`, `contract_item`, `technical_device`, `building`, `opo`.

`Task` fields: UUID id, required title, optional description/due date, required creator employee FK, priority/status enums, `is_personal`, timestamps, `completed_at`, `cancelled_at`, `deleted_at`, integer version. Do not add workflow-source columns.

Indexes: creator, status, due date, deleted_at, assignee employee id, and each business entity FK in link tables.

- [ ] **Step 4: Implement migration**

Create `task_status` and `task_priority`, parent/child tables with real FKs, shared comments, and indexes. Downgrade drops links/comments/tasks before enums.

- [ ] **Step 5: Register metadata and test cleanup**

Import comment/task models in `alembic/env.py`. Add new child tables to `tests/conftest.py` TRUNCATE before their parent business tables.

- [ ] **Step 6: Run GREEN**

```bash
python -m pytest tests/integration/test_stage5_tasks_migration.py -q
python -m alembic heads
```

Expected single head `0013_stage5_tasks_core`.

- [ ] **Step 7: Commit**

```bash
git add app/modules/comments app/modules/tasks/enums.py app/modules/tasks/models.py alembic/versions/0013_stage5_tasks_core.py alembic/env.py tests/conftest.py tests/integration/test_stage5_tasks_migration.py
git commit -m "feat(tasks): add CP5.1 task persistence foundation"
```

---

### Task 2: Task CRUD, assignees and FK-backed links

**Files:** create `app/modules/tasks/repository.py`, `app/modules/tasks/service.py`, `tests/integration/test_tasks_core.py`.

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class TaskLinkInput:
    kind: TaskLinkKind
    entity_id: uuid.UUID
    is_primary: bool = False
```

Repository exports `get_task`, `get_task_for_update`, `get_task_assignee_ids`, `get_task_links`, `get_task_related_organization_ids`. Service exports `TaskNotFoundError`, `TaskValidationError`, `TaskService`.

- [ ] **Step 1: Write RED service tests with concrete calls**

```python
created = TaskService().create_task(
    db_session,
    actor_user_id=actor.id,
    creator_employee_id=actor.employee_id,
    title="  Inspect vessel  ",
    description="Check shell condition",
    due_date=date(2026, 8, 20),
    priority=TaskPriority.NORMAL,
    is_personal=True,
    assignee_ids=[employee_a.id, employee_b.id, employee_a.id],
    links=[],
)
assert created.title == "Inspect vessel"

assigned = TaskService().replace_assignees(
    db_session,
    actor_user_id=actor.id,
    task=created,
    employee_ids=[employee_b.id, employee_a.id, employee_b.id],
)
assert assigned == sorted({employee_a.id, employee_b.id}, key=str)

updated = TaskService().update_task(
    db_session,
    actor_user_id=actor.id,
    task=created,
    title="Inspect vessel shell",
    description="Updated description",
    due_date=date(2026, 8, 19),
    priority=TaskPriority.HIGH,
    is_personal=True,
    links=[],
    due_date_change_reason=None,
)
assert updated.priority == TaskPriority.HIGH
```

Also test non-personal without links, soft-deleted assignee, duplicate links, two primary links, mismatched contract item/contract, delete/restore, and rejected mutation audit/version invariants.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_core.py -q
```

- [ ] **Step 3: Implement repository helpers**

Use SQLAlchemy `select()`. `get_task_for_update` uses `.with_for_update()`. Resolve RELATED organizations through direct organization; contract customer; contract-item parent contract customer; technical device owner organization; building owner organization; OPO owner and operator.

- [ ] **Step 4: Implement service methods**

```python
create_task(db, *, actor_user_id, creator_employee_id, title, description, due_date, priority, is_personal, assignee_ids, links) -> Task
update_task(db, *, actor_user_id, task, title, description, due_date, priority, is_personal, links, due_date_change_reason) -> Task
delete_task(db, *, actor_user_id, task) -> None
restore_task(db, *, actor_user_id, task) -> None
replace_assignees(db, *, actor_user_id, task, employee_ids) -> list[uuid.UUID]
```

Validate before mutation, flush, write existing audit row, commit, refresh. Roll back on exceptions.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest tests/integration/test_tasks_core.py -q
```

- [ ] **Step 6: Commit**

```bash
git add app/modules/tasks/repository.py app/modules/tasks/service.py tests/integration/test_tasks_core.py
git commit -m "feat(tasks): add task CRUD assignees and business links"
```

---

### Task 3: Status machine and due-date rule

**Files:** modify service; create `tests/integration/test_tasks_status_due_date.py`.

**Interfaces:** add `TaskService.change_status(db, *, actor_user_id, task, target_status) -> Task` and `is_task_overdue(task, *, today: date) -> bool`.

- [ ] **Step 1: RED tests**

Verify only `new -> in_progress`, `new -> cancelled`, `in_progress -> completed`, `in_progress -> cancelled`. Reject `new -> completed`, same-status and terminal transitions. Verify terminal timestamps.

Concrete due-date assertions: `2026-08-20 -> 2026-08-19` no reason; `NULL -> 2026-08-20` no reason; `2026-08-20 -> 2026-08-21` requires reason; `2026-08-20 -> NULL` requires reason. Audit metadata uses `old_due_date`, `new_due_date`, `reason`.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_status_due_date.py -q
```

- [ ] **Step 3: Implement transition map and timestamps**

Status command increments version once and writes `task.status_changed`. `completed_at`/`cancelled_at` are set only on terminal entry.

- [ ] **Step 4: Implement extension guard and overdue helper**

`is_task_overdue` is true only for non-terminal task with non-null `due_date < today`.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest tests/integration/test_tasks_status_due_date.py -q
git add app/modules/tasks/service.py tests/integration/test_tasks_status_due_date.py
git commit -m "feat(tasks): enforce task lifecycle and due date rules"
```

---

### Task 4: Scoped task authorization

**Files:** modify `app/modules/identity/authorization.py`, task repository; create `tests/integration/test_tasks_authorization.py`.

**Interfaces:**

```python
class TaskLike(Protocol):
    creator_employee_id: uuid.UUID


def can_access_task(
    ctx: AuthorizationContext,
    task: TaskLike,
    *,
    assignee_employee_ids: set[uuid.UUID],
    related_organization_ids: set[uuid.UUID],
) -> bool:
    if ctx.has_all_scope:
        return True
    return (
        ScopeType.ASSIGNED in ctx.active_scope_types
        and ctx.employee_id in assignee_employee_ids
    ) or (
        ScopeType.OWN in ctx.active_scope_types
        and ctx.employee_id == task.creator_employee_id
    ) or (
        ScopeType.RELATED in ctx.active_scope_types
        and bool(ctx.related_organization_ids & related_organization_ids)
    )
```

- [ ] **Step 1: Write RED matrix**

Test ALL/ASSIGNED/OWN/RELATED for each requested permission, deny cases, malformed RELATED fail-closed, multiple assignees, OPO owner/operator, contract-item relation and exact permission isolation. Verify `tasks.view_all` is read-only.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_authorization.py -q
```

- [ ] **Step 3: Implement helper/relation queries**

Do not use business-function roles for authorization.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m pytest tests/integration/test_tasks_authorization.py -q
git add app/modules/identity/authorization.py app/modules/tasks/repository.py tests/integration/test_tasks_authorization.py
git commit -m "feat(tasks): add scoped task authorization"
```

---

### Task 5: API schemas, registry and CRUD commands

**Files:** create `schemas.py`, `routes.py`; modify `app/main.py`; create `tests/integration/test_tasks_api.py`.

**Interfaces:**

```python
class TaskLinkRequest(BaseModel):
    kind: TaskLinkKind
    entity_id: uuid.UUID
    is_primary: bool = False
```

Paginated list response is `{items, total, page, page_size}`. Mutation models use `extra="forbid"`.

- [ ] **Step 1: Write RED HTTP tests**

Routes:

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

Assert 401, permission 403, inaccessible 404, exact mutation permissions, protected PATCH fields rejected, scope-filtered registry, `tasks.view_all`, filters for assignee/creator/status/priority/due range/contract/organization/overdue, deleted exclusion, and response assignees/links/overdue.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_tasks_api.py -q
```

- [ ] **Step 3: Implement schemas/routes**

Use `require_scoped_permission`. `_task_or_404` loads assignees and related organizations then calls `can_access_task`. Read path may use `tasks.view_all` fallback; mutation paths never do. Validate linked-resource reference access using owning-module helpers before service call. Map validation errors to 422 and hidden resource failures to 404.

- [ ] **Step 4: Register router, run GREEN, commit**

```bash
python -m pytest tests/integration/test_tasks_api.py -q
git add app/modules/tasks/schemas.py app/modules/tasks/routes.py app/main.py tests/integration/test_tasks_api.py
git commit -m "feat(tasks): expose scoped task API"
```

---

### Task 6: Shared task comments

**Files:** modify task repository/service/schemas/routes; create `tests/integration/test_task_comments.py`.

**Interfaces:** `TaskService.add_comment(db, *, actor_user_id, author_employee_id, task, text) -> Comment`; repository `list_task_comments(db, task_id) -> list[Comment]`.

- [ ] **Step 1: RED tests**

Test GET/POST comments, blank text, actor-bound author, `tasks.comment` POST permission, view/view_all GET access, inaccessible task 404, oldest-first order and `task.comment_added` audit.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_task_comments.py -q
```

- [ ] **Step 3: Implement atomically**

Create `Comment`, flush, create `CommentTask`, audit, commit. No edit/delete/mentions.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m pytest tests/integration/test_task_comments.py -q
git add app/modules/tasks tests/integration/test_task_comments.py
git commit -m "feat(tasks): add shared task comments"
```

---

### Task 7: Query, locking and transaction hardening

**Files:** modify task repository/service; extend core/API/authorization tests.

- [ ] **Step 1: Add RED edge tests**

Test row-lock command path, duplicate-link normalization, multi-primary rejection before replacement, rollback preserving old links, no registry duplicates with multiple relations, correct overdue totals, deleted linked target rejection, terminal readability, terminal transition rejection and restore preserving status/timestamps.

- [ ] **Step 2: Run focused tests**

```bash
python -m pytest tests/integration/test_tasks_core.py tests/integration/test_tasks_api.py tests/integration/test_tasks_authorization.py -q
```

- [ ] **Step 3: Apply only proven fixes**

Prefer `EXISTS` for relation filters. Use `get_task_for_update` for mutating HTTP commands. Preserve rollback/audit invariants.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m pytest tests/integration/test_tasks_core.py tests/integration/test_tasks_api.py tests/integration/test_tasks_authorization.py -q
git add app/modules/tasks tests/integration/test_tasks_core.py tests/integration/test_tasks_api.py tests/integration/test_tasks_authorization.py
git commit -m "test(tasks): harden task queries and transaction invariants"
```

---

### Task 8: Authoritative docs and status

**Files:** `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, `docs/PERMISSIONS.md`, `PROJECT_STATUS.md`.

- [ ] **Step 1:** document task states, assignees, personal/non-personal link rule, extension reason, computed overdue, delete/restore.
- [ ] **Step 2:** document actual CP5.1 physical schema and explicitly defer workflow source FKs, expertise/document links and mentions.
- [ ] **Step 3:** document exact permissions/scopes, read-only `tasks.view_all`, reserved `tasks.complete`.
- [ ] **Step 4:** update project status only with proven exact HEAD/revision/test counts.
- [ ] **Step 5: Commit**

```bash
git add docs/BUSINESS_RULES.md docs/DATA_MODEL.md docs/PERMISSIONS.md PROJECT_STATUS.md
git commit -m "docs(stage5): document CP5.1 tasks core"
```

---

### Task 9: Full regression, whole-branch review and stacked draft PR

**Base for review:** `7066e648543c1aaccbdcc85016a9340d9d304c70`.

- [ ] **Step 1: Full verification**

```bash
python -m ruff check app tests alembic
python -m alembic heads
python -m alembic upgrade head
python -m pytest -q
```

Require Ruff PASS, one head `0013_stage5_tasks_core`, upgrade PASS, full pytest PASS.

- [ ] **Step 2:** rerun migration round-trip test and confirm final DB head `0013_stage5_tasks_core`.
- [ ] **Step 3:** whole-branch diff review: no frontend, workflow engine, expertise/document tables, notifications or contract lifecycle effects.
- [ ] **Step 4:** security review: permission isolation, all scopes, malformed RELATED fail-closed, read-only `view_all`, anti-enumeration, unforgeable creator/comment author, protected PATCH, rejected-command audit invariant.
- [ ] **Step 5:** after any review fix, rerun exact-HEAD full verification.
- [ ] **Step 6:** create draft PR `agent/stage5-cp51-tasks-core` -> `agent/stage4-cp42-contract-lifecycle-addenda` titled `Stage 5 CP5.1: Tasks Core backend`; include exact HEAD, parent, migration, test results, deferrals and `DO NOT MERGE into integration automatically`.
- [ ] **Step 7:** require PR merge-ref Ruff/Alembic/pytest GREEN.
- [ ] **Step 8:** update Issue #3 with final handoff and next checkpoint CP5.2.

## Acceptance Matrix

```text
A. Scope        Tasks Core only
B. Database     0013 single head, real FK links, round trip
C. Backend      CRUD, assignees, links, status, due date, comments, registry
D. UI           no frontend changes
E. Tests        targeted RED/GREEN plus full regression
F. Invariants   computed overdue, terminal states, extension reason, one primary link
G. Security     exact permissions, ALL/ASSIGNED/RELATED/OWN, anti-enumeration
H. Regression   Stage 0-4 remain GREEN
I. Verdict      stacked draft PR only, integration untouched
```

## Deferred Work

```text
CP5.2  workflow templates, versions, task templates, assignee resolution, atomic instantiation
CP5.3  contract work-start, suspension/resume deadline shift, termination cancellation, Tasks readiness provider
Stage 6 task_expertises and expertise workflow integration
Stage 8 task document attachments
Stage 11 due-soon calendar, 30/14/5 reminders, notifications and dedup
```
