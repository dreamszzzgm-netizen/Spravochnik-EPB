# Stage 5 / CP5.2 — Workflow Engine Design

## Goal

Implement the reusable backend workflow engine that sits between Tasks Core (CP5.1) and the later business integrations. The engine must store configurable workflow templates, preserve immutable historical versions, resolve assignees by employee business function, and instantiate ordinary Tasks with traceable workflow provenance.

## Scope

CP5.2 includes:

- logical `WorkflowTemplate` records managed with the existing global `workflows.manage` permission;
- immutable `WorkflowTemplateVersion` snapshots;
- ordered `WorkflowTaskTemplate` rows containing title, description, assignee business-function role, relative deadline, priority and required flag;
- publishing a version without changing previously published versions;
- selecting the latest published version for new instantiations;
- business-function assignee resolution against `employee_function_roles` / assignments;
- exclusion of deleted employees and employees absent on the workflow anchor date;
- atomic creation of generated tasks through Tasks Core;
- generated-task provenance using source workflow version + source workflow task-template identifiers;
- audit events for template creation, version creation, publication and instantiation;
- backend management API for templates/versions/publication;
- integration tests and Alembic migration coverage.

CP5.2 explicitly does **not** include:

- contract status start/pause/resume/termination effects (CP5.3);
- contract completion readiness provider (CP5.3);
- expertise-triggered workflow application (Stage 6);
- `task_expertises` (Stage 6);
- frontend Tasks/Workflow screens;
- Russian production-calendar implementation (Stage 11);
- notification scheduling.

## Architecture

A new `app.modules.workflows` module owns workflow configuration and instantiation. It does not duplicate Task lifecycle rules. Generated work items are normal `Task` entities and are created through `TaskService` so task validation, links, assignees and audit behavior remain centralized.

`TaskService.create_task()` gains a backwards-compatible `commit: bool = True` argument. Workflow instantiation calls it with `commit=False` for every generated task and performs one final commit, so either the complete workflow instance is created or no generated task is persisted.

The workflow service accepts a due-date resolver callable when instantiating. CP5.2 therefore stores relative-day offsets but does not hard-code a temporary calendar implementation that would conflict with the future `WorkingCalendarService`. Stage 6/11 can inject the correct working-calendar calculation without changing workflow persistence.

## Data model

### workflow_templates

- `id UUID PK`
- `code VARCHAR(80) UNIQUE NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `is_active BOOLEAN NOT NULL DEFAULT true`
- `created_by UUID FK users`
- `created_at`, `updated_at`
- `deleted_at NULL`
- `version INTEGER NOT NULL DEFAULT 1`

A logical template is mutable only for administrative metadata. Business steps are never edited in place.

### workflow_template_versions

- `id UUID PK`
- `workflow_template_id UUID FK workflow_templates`
- `version_number INTEGER NOT NULL`
- `created_by UUID FK users`
- `created_at`
- `published_at NULL`
- unique `(workflow_template_id, version_number)`
- check `version_number > 0`

A version is a snapshot. The API provides no mutation endpoint for its task definitions. Publishing only sets `published_at` once.

### workflow_task_templates

- `id UUID PK`
- `workflow_template_version_id UUID FK workflow_template_versions`
- `title VARCHAR(255) NOT NULL`
- `description TEXT NULL`
- `assignee_function_role_id UUID FK employee_function_roles`
- `relative_due_days INTEGER NOT NULL`
- `priority task_priority NOT NULL`
- `sort_order INTEGER NOT NULL`
- `is_required BOOLEAN NOT NULL DEFAULT true`
- unique `(workflow_template_version_id, sort_order)`
- check `relative_due_days >= 0`
- check `sort_order >= 0`

### tasks provenance

Add nullable:

- `source_workflow_template_version_id`
- `source_workflow_task_template_id`

Both are either NULL together or populated together. A composite FK guarantees that the source task-template actually belongs to the recorded workflow version.

## Version rules

1. Creating a version always creates a new immutable snapshot and increments `version_number` for the logical template.
2. A version contains at least one task template.
3. `sort_order` is unique inside a version.
4. Every assignee function role must exist and be active when the version is created.
5. Publishing is explicit and one-way.
6. Existing generated tasks retain their source identifiers forever; publishing a newer version never rewrites them.
7. New instantiations use the highest published `version_number` for the template.

## Assignee resolution

For each workflow task-template:

1. load active employees assigned to the referenced business-function role;
2. exclude employees with `deleted_at IS NOT NULL`;
3. exclude employees whose `employee_absences` interval contains the workflow anchor date;
4. assign all remaining eligible employees, leveraging Tasks Core multiple-assignee support;
5. if no eligible employee exists, fail the whole instantiation before any task is committed.

Authorization roles are never used for assignee resolution.

## Instantiation flow

```text
WorkflowService.instantiate()
  -> load logical template
  -> choose latest published version
  -> load ordered task templates
  -> pre-resolve all function-role assignees
  -> resolve each relative deadline through injected due_date_resolver
  -> create each Task via TaskService(commit=False)
  -> set source workflow/version metadata
  -> write workflow.instantiated audit
  -> one transaction commit
```

The caller supplies the normal Tasks Core business links. CP5.2 does not invent a polymorphic workflow target table.

## API

All endpoints require `workflows.manage` (superuser bypass remains unchanged):

- `GET /api/workflows`
- `POST /api/workflows`
- `GET /api/workflows/{template_id}`
- `POST /api/workflows/{template_id}/versions`
- `GET /api/workflows/{template_id}/versions`
- `POST /api/workflows/{template_id}/versions/{version_id}/publish`

Instantiation is an application-service operation in CP5.2. Stage 6 and CP5.3 call it from their owning business transactions. A generic public "instantiate anything" HTTP endpoint is intentionally not exposed.

## Error handling

Validation failures raise a workflow-specific validation error and leave the transaction unchanged. Examples:

- duplicate/blank template code;
- inactive/deleted workflow template;
- empty version;
- duplicate sort order;
- inactive/missing function role;
- no published version;
- no eligible employee for a required task template;
- double publication.

Management endpoints return 422 for business validation and 404 for absent/deleted workflow resources.

## Testing

TDD checkpoints cover:

- `0014` schema and `0014 -> 0013 -> 0014` round-trip;
- template/version numbering and publication;
- published snapshot immutability across later versions;
- latest-published-version selection;
- business-function assignee resolution with absence exclusion;
- no-candidate fail-closed behavior;
- atomic multi-task instantiation;
- task source provenance;
- existing TaskService callers unchanged with default commit behavior;
- `workflows.manage` HTTP permission enforcement;
- audit events;
- full backend regression suite and Ruff.

## Integration boundary

CP5.2 is stacked directly on final CP5.1 (`c7f6efbd16796f6ac207e5717045cc1bc3994d08`). It is a review checkpoint only. It must not merge the Pilot deployment branch or the integration branch automatically.
