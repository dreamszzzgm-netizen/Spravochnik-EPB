# Stage 5 / CP5.2 — Workflow Engine completion review

Date: 2026-08-13

## Checkpoint

- Parent checkpoint: `agent/stage5-cp51-tasks-core`
- Parent SHA: `c7f6efbd16796f6ac207e5717045cc1bc3994d08`
- Feature branch: `agent/stage5-cp52-workflow-engine`
- Draft PR: #11
- Alembic head: `0014_stage5_workflow_engine`

This checkpoint is intentionally stacked and must not be merged into the integration or Pilot branches automatically.

## Implemented scope

### Versioned workflow configuration

CP5.2 adds three physical workflow entities:

- `workflow_templates` — logical workflow identity and stable code;
- `workflow_template_versions` — numbered revisions with explicit `published_at`;
- `workflow_task_templates` — ordered task definitions bound to a specific version.

A task template stores:

- title;
- optional description;
- employee business-function role;
- relative due days;
- task priority;
- sort order;
- required flag.

Published version content is not edited in place. A change is represented by a new version, so generated work can always point back to the exact configuration snapshot used at creation time.

### Task provenance

`tasks` now has nullable provenance columns:

- `source_workflow_template_version_id`;
- `source_workflow_task_template_id`.

Database constraints require the pair to be both NULL or both populated. A composite FK binds the source task template to the same source workflow version, preventing cross-version provenance corruption.

Manual tasks keep both columns NULL.

### Business-function assignee resolution

Workflow templates reference `employee_function_roles`, not authorization roles.

Instantiation resolves active employees assigned to each required business function and excludes:

- soft-deleted employees;
- employees with an absence covering the workflow anchor date.

If a required business function has no eligible employee, instantiation fails closed before creating workflow tasks.

### Atomic workflow instantiation

`WorkflowService.instantiate()`:

1. validates the active logical template;
2. selects the latest published version;
3. loads ordered task templates;
4. resolves eligible employees for every referenced business function;
5. creates ordinary CP5.1 tasks;
6. records exact workflow version/task-template provenance;
7. writes workflow-level audit evidence;
8. commits once for the whole operation.

Any failure rolls back all generated tasks.

To support this without duplicating Tasks business rules, `TaskService.create_task()` now accepts `commit: bool = True`. Existing callers retain the previous standalone commit behavior. Workflow instantiation uses `commit=False` and owns the outer transaction.

### Due dates

CP5.2 does not embed an approximate Russian production calendar.

The instantiation service receives a due-date resolver:

`(anchor_date, relative_due_days) -> due_date`

This keeps the workflow engine independent from the later `WorkingCalendarService` implementation while preserving the final architectural dependency direction.

### Management HTTP API

Added `/api/workflows` management endpoints for:

- listing templates;
- creating a template;
- reading template detail;
- listing versions;
- creating a version with ordered task definitions;
- publishing a version.

Every endpoint requires exact backend permission `workflows.manage`.

The API does not expose an edit operation for published versions/task definitions.

## Verification evidence

### GitHub Actions run #420

Run ID: `31693756568`

Verified head: `e8f24bccf9c832041f8622303a85dd1b48494095`

Results:

- `ruff check app tests` — PASS;
- `alembic upgrade head` — PASS, including `0013_stage5_tasks_core -> 0014_stage5_workflow_engine`;
- `pytest` — **562 passed / 289 warnings**.

The workflow-specific suites passed:

- `test_stage5_cp52_workflow_migration.py`;
- `test_task_service_transactions.py`;
- `test_workflow_instantiation.py`;
- `test_workflow_service.py`;
- `test_workflows_api.py`.

### Warning cleanup

After run #420, `dc23aae6779f193cd9f36bdd11ec507907d2597b` replaced the new Workflow API use of FastAPI's deprecated `HTTP_422_UNPROCESSABLE_ENTITY` constant with `HTTP_422_UNPROCESSABLE_CONTENT`.

This is behavior-preserving warning cleanup. A fresh PR CI run was triggered on the updated branch; final PR status is the source of truth for exact-head CI.

Existing warnings outside the CP5.2 scope remain technical debt and were not mixed into this checkpoint.

## Acceptance matrix

| Requirement | Result |
| --- | --- |
| Versioned workflow templates | PASS |
| Published snapshot provenance | PASS |
| Ordered task templates | PASS |
| Business-function assignee resolution | PASS |
| Deleted/absent employee exclusion | PASS |
| Fail closed without eligible assignee | PASS |
| Ordinary CP5.1 task reuse | PASS |
| Atomic multi-task instantiation | PASS |
| Exact source version/task-template IDs | PASS |
| Backend permission enforcement | PASS |
| Audit coverage | PASS |
| Migration from clean DB to head | PASS |
| Full regression suite | PASS |

## Deliberately deferred

The following are not CP5.2 gaps; they belong to later checkpoints:

- CP5.3 Contract ↔ Tasks lifecycle effects;
- Expertise-triggered workflow instantiation in Stage 6;
- `task_expertises` until the Expertise table exists;
- frontend workflow management UI;
- task notifications/mentions;
- production-calendar implementation;
- document attachments.

## Conclusion

CP5.2 establishes the reusable backend Workflow Engine required by later Contract and Expertise automation without hard-coding workflow steps in routes or coupling business-function assignment to RBAC roles.

The checkpoint remains a stacked draft PR for review and must not be merged automatically.
