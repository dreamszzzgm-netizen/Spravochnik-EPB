# Stage 5 Design — Self-Review Clarifications

Date: 2026-08-12
Status: Authoritative clarification to `2026-08-12-stage5-tasks-workflow-design.md`

This note records two clarifications discovered during the required design self-review. They do not change the approved Stage 5 architecture or checkpoint decomposition; they remove two implementation ambiguities.

## 1. Shared Comment ownership

The generic `Comment` persistence model must not live inside `app/modules/tasks`, because contracts and expertises will also use comments later and must not depend on the Tasks module.

CP5.1 therefore introduces a minimal shared comments foundation:

```text
app/modules/comments/
  __init__.py
  models.py
```

The shared module owns only generic comment persistence needed by the approved data model (`Comment` and link-model definitions as they are introduced). Task-specific comment access rules, task link validation, API routes and authorization remain owned by `app/modules/tasks`.

CP5.1 physically creates only `comments` and `comment_tasks`. Contract/expertise comment links are still deferred to their owning checkpoints.

## 2. Workflow-generated tasks must have an assignee

The approved business requirement for automatically generated tasks is stricter than generic manual tasks: an automatically generated workflow task must not be committed without a responsible assignee.

Therefore CP5.2 assignee resolution is authoritative as follows:

1. An explicit per-task assignee override may be supplied.
2. If `assignee_function_role_id` is configured and exactly one eligible employee exists, that employee is assigned automatically.
3. If zero eligible employees exist for the configured function role, instantiation fails closed.
4. If multiple eligible employees exist, instantiation fails unless an explicit override selects exactly one eligible employee.
5. If no function role is configured, an explicit assignee override is mandatory.
6. The engine never silently creates an unassigned workflow-generated task and never silently assigns all matching employees.
7. The whole workflow instantiation remains atomic: assignee resolution failure creates no subset of tasks.

Generic/manual CP5.1 tasks may still have zero assignees. This clarification applies only to workflow-generated tasks.

## 3. Self-review result

Placeholder scan: no `TODO` or `TBD` remains in the main Stage 5 design.

The main design plus this clarification note form the approved written Stage 5 specification for implementation planning.