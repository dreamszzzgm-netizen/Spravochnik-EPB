# Stage 6 CP6.2 — Expertise Collaboration + Workflow Bridge

## Objective

Add the next Expertise foundation slice without reworking the CP6.1 schema:

1. real responsible-expert selector from existing `Employee` records;
2. expertise participants (additional experts + specialists);
3. `Task ↔ Expertise` association via FK-backed link table;
4. Expertise ↔ CP5.2 Workflow Engine bridge (manual, reusing existing `WorkflowService.instantiate`).

## Architecture decisions (from B1 read-only review)

- **Employee/User**: `Employee` (id, full_name, position, phone, email, employment_type `staff|external_expert`, deleted_at, version) ↔ `User.employee_id` (unique). No new employee model.
- **Business functions** (`EmployeeFunctionRole`: `expert`, `specialist`, `accountant`, `contract_responsible`) are separate from authorization roles. `responsible_expert_id` in `expertises` is the single source of truth for the responsible expert; participants do NOT duplicate it.
- **Task links** are FK-backed tables (`task_organizations`, `task_contracts`, …) driven by `TaskLinkKind` enum + `TaskLinkInput`. `task_expertises` is confirmed by `DATA_MODEL.md §35.6`.
- **Workflow**: CP5.2 has no "workflow instance" entity — `WorkflowService.instantiate` creates ordinary tasks with `source_workflow_*` provenance and FK-backed links. The bridge is `instantiate(... links=[TaskLinkInput(kind=EXPERTISE, entity_id=expertise_id, is_primary=True)])`. No second workflow engine, no generic `entity_type/entity_id`.
- **Auto workflow start**: NOT confirmed by docs (`BUSINESS_RULES.md §24` says a template *can* be applied; `§6.2` says creating an expertise in `preparation` does not start the contract). Decision: **manual** "start workflow" endpoint, no auto-start on create.
- **Internal number**: exact format NOT confirmed anywhere. Decision: **defer** `internal_number`; do not invent a format or numbering service in CP6.2.
- **Participants roles**: docs confirm `expert` and `specialist` (`BUSINESS_RULES.md §10`). `responsible_expert` stays in `expertises.responsible_expert_id` only.

## Migration

`0018_expertise_collaboration` (down_revision `0017_expertises`):

- `expertise_participants`: id, expertise_id FK(RESTRICT/CASCADE — see below), employee_id FK(RESTRICT), participation_role enum(`expert`,`specialist`), created_at; UNIQUE (expertise_id, employee_id, participation_role).
- `task_expertises`: task_id FK(CASCADE), expertise_id FK(RESTRICT), is_primary bool; PK (task_id, expertise_id).

FK delete behavior: participant rows are child data of expertise → `CASCADE` on expertise; `RESTRICT` on employee (history must not vanish when an employee is deleted). `task_expertises` mirrors the existing `task_*` link tables: `CASCADE` on task, `RESTRICT` on expertise.

## API

- `GET /api/employees` — active employees selector (`employees.view`).
- `GET /api/expertises/{id}/participants` — list (`expertises.view`).
- `POST /api/expertises/{id}/participants` — add (`expertises.assign_experts`), body `{employee_id, participation_role}`.
- `DELETE /api/expertises/{id}/participants/{employee_id}` — remove (`expertises.assign_experts`).
- `GET /api/expertises/{id}/tasks` — linked tasks (`expertises.view`).
- `POST /api/expertises/{id}/workflow/start` — manual workflow bridge (`expertises.edit`), body `{workflow_template_id}`.

All expertise endpoints are scoped by the existing `_apply_expertise_scope` (RELATED/ASSIGNED), fail closed with 404 for foreign expertise.

## Non-goals (deferred)

Inspection, NDT, defects, photos, calculations, conclusion, RTN attempts, DOCX generation, AI, expertise documents, expert attestation subsystem, numbering format.

## Verification

- TDD RED tests first (participants duplicate/IDOR, responsible source-of-truth, task link, workflow IDOR, employee selector leak, CP6.1 optimistic locking intact).
- `ruff check app tests`, `alembic heads` == `0018_expertise_collaboration`, backend `> 617 passed`, frontend `>= 88 passed`.
- Migration round-trip `0018 → 0017 → 0018` on disposable PostgreSQL `5433`.
