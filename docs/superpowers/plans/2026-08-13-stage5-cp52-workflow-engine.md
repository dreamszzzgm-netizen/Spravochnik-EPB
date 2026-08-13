# Stage 5 CP5.2 Workflow Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a versioned backend workflow engine that creates ordinary CP5.1 tasks atomically from immutable published templates and resolves assignees by employee business function.

**Architecture:** Add a focused `workflows` module, an Alembic `0014` migration, workflow provenance columns on Tasks, and a backwards-compatible transactional hook in `TaskService.create_task`. Workflow configuration is managed through `workflows.manage`; instantiation remains an application-service API for CP5.3/Stage 6 callers.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, Pydantic, pytest, Ruff.

## Global Constraints

- Base branch: `agent/stage5-cp51-tasks-core` at `c7f6efbd16796f6ac207e5717045cc1bc3994d08`.
- Feature branch: `agent/stage5-cp52-workflow-engine`.
- Preserve modular-monolith/service-layer architecture.
- Never use authorization roles for workflow assignee resolution; use employee function roles only.
- Published workflow versions and their task definitions are immutable.
- Generated tasks preserve exact source workflow version/task-template identifiers.
- Workflow instantiation is atomic.
- Do not implement CP5.3 contract lifecycle effects, Stage 6 expertise integration, frontend workflow UI, notifications, or a temporary Russian production-calendar approximation.
- No merge into integration or Pilot branches automatically.

---

### Task 1: RED migration and model contract

**Files:**
- Create: `tests/integration/test_stage5_cp52_workflow_migration.py`
- Create later in GREEN: `alembic/versions/0014_stage5_workflow_engine.py`
- Create later in GREEN: `app/modules/workflows/models.py`
- Modify later in GREEN: `app/modules/tasks/models.py`

**Interfaces:**
- Produces tables `workflow_templates`, `workflow_template_versions`, `workflow_task_templates`.
- Produces task columns `source_workflow_template_version_id` and `source_workflow_task_template_id`.

- [ ] Write migration tests that expect all three tables, version/task constraints, provenance columns and composite provenance FK.
- [ ] Commit RED tests only.
- [ ] Let GitHub Actions confirm RED because `0014` and workflow models do not yet exist.
- [ ] Add `0014_stage5_workflow_engine.py` and ORM models matching the design.
- [ ] Add provenance columns/constraints to `Task` ORM.
- [ ] Run CI and require migration + pytest GREEN.
- [ ] Add downgrade/upgrade round-trip assertion (`0014 -> 0013 -> 0014`).

### Task 2: RED workflow configuration service

**Files:**
- Create: `tests/integration/test_workflow_service.py`
- Create later in GREEN: `app/modules/workflows/repository.py`
- Create later in GREEN: `app/modules/workflows/service.py`
- Create: `app/modules/workflows/__init__.py`

**Interfaces:**
- `WorkflowService.create_template(...) -> WorkflowTemplate`
- `WorkflowService.create_version(..., task_templates: Iterable[WorkflowTaskTemplateInput]) -> WorkflowTemplateVersion`
- `WorkflowService.publish_version(...) -> WorkflowTemplateVersion`
- `WorkflowService.latest_published_version(...) -> WorkflowTemplateVersion`

- [ ] Write RED tests for normalized unique template code/name, sequential version numbers, non-empty versions, unique `sort_order`, active function-role validation and explicit one-way publication.
- [ ] Commit RED tests and confirm the expected import/service failures in CI.
- [ ] Implement repository/service minimally.
- [ ] Verify version snapshots are never mutated by publishing a later version.
- [ ] Verify audit events `workflow.template_created`, `workflow.version_created`, `workflow.version_published`.
- [ ] Run targeted and full backend CI GREEN.

### Task 3: RED transactional TaskService hook

**Files:**
- Modify: `tests/integration/test_tasks_core.py` (or the closest existing Tasks service test file)
- Modify later in GREEN: `app/modules/tasks/service.py`

**Interfaces:**
- Extend `TaskService.create_task(..., commit: bool = True) -> Task`.

- [ ] Write a RED regression proving `commit=False` leaves the transaction open while creating/validating the task and audit row.
- [ ] Confirm RED because the parameter is not accepted.
- [ ] Implement the backwards-compatible flag; keep default behavior identical for all existing callers.
- [ ] Verify existing task creation tests still pass unchanged.

### Task 4: RED workflow instantiation and business-function resolution

**Files:**
- Extend: `tests/integration/test_workflow_service.py`
- Modify later in GREEN: `app/modules/workflows/repository.py`
- Modify later in GREEN: `app/modules/workflows/service.py`

**Interfaces:**
- `WorkflowService.instantiate(db, *, actor_user_id, creator_employee_id, template_id, anchor_date, links, due_date_resolver) -> list[Task]`.
- `due_date_resolver(anchor_date: date, relative_due_days: int) -> date`.

- [ ] RED: published version with two task templates creates two normal Tasks in `sort_order`.
- [ ] RED: generated tasks carry matching source version/task-template IDs.
- [ ] RED: employees are selected only through `EmployeeFunctionRoleAssignment`.
- [ ] RED: deleted employees and employees absent on `anchor_date` are excluded.
- [ ] RED: no eligible employee fails closed with zero persisted generated tasks.
- [ ] RED: a failure in any generated task rolls back the whole workflow instance.
- [ ] Commit RED tests and confirm failure.
- [ ] Implement pre-resolution, injected due-date calculation and atomic TaskService calls with `commit=False`.
- [ ] Write `workflow.instantiated` audit with template/version/task count metadata.
- [ ] Run targeted and full backend CI GREEN.

### Task 5: RED management HTTP API

**Files:**
- Create: `tests/integration/test_workflows_api.py`
- Create later in GREEN: `app/modules/workflows/schemas.py`
- Create later in GREEN: `app/modules/workflows/routes.py`
- Modify later in GREEN: `app/main.py`

**Interfaces:**
- `GET /api/workflows`
- `POST /api/workflows`
- `GET /api/workflows/{template_id}`
- `GET /api/workflows/{template_id}/versions`
- `POST /api/workflows/{template_id}/versions`
- `POST /api/workflows/{template_id}/versions/{version_id}/publish`

- [ ] Write RED HTTP tests for unauthenticated 401, missing `workflows.manage` 403 and allowed superuser/permission holder behavior.
- [ ] Write RED business-validation tests for empty versions, duplicate sort order and double publication.
- [ ] Commit RED tests and confirm missing routes.
- [ ] Implement schemas/routes using existing identity dependencies and workflow service.
- [ ] Register router in `app/main.py`.
- [ ] Run targeted and full backend CI GREEN.

### Task 6: Documentation synchronization and final verification

**Files:**
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/BUSINESS_RULES.md`
- Modify: `docs/PERMISSIONS.md` only if implementation semantics need clarification; permission code itself already exists.
- Modify: `PROJECT_STATUS.md`
- Create: `docs/superpowers/reviews/2026-08-13-stage5-cp52-workflow-engine-completion.md`

**Interfaces:**
- Record final Alembic head `0014_stage5_workflow_engine`.
- Record exact verified commit SHA and GitHub Actions evidence.

- [ ] Synchronize physical workflow tables/provenance rules with `DATA_MODEL.md`.
- [ ] Synchronize versioning/assignee-resolution/atomicity rules with `BUSINESS_RULES.md`.
- [ ] Advance `PROJECT_STATUS.md` to CP5.2 and leave CP5.3/Stage 6 as deferred owners.
- [ ] Run Ruff, Alembic upgrade and the full pytest suite through GitHub Actions on exact final code head.
- [ ] Run `git diff --check` equivalent by inspecting patches for whitespace errors.
- [ ] Create a draft stacked PR targeting `agent/stage5-cp51-tasks-core`.
- [ ] Do not merge.
