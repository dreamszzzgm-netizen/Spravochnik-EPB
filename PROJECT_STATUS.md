# Project status

## Current verified development baseline

- Official integration GREEN baseline remains unchanged: `650008fc5a80eaf6165d2d0aba249041aae2a98d`.
- Stacked parent checkpoint: **Stage 5 / CP5.1 — Tasks Core backend**, HEAD `c7f6efbd16796f6ac207e5717045cc1bc3994d08`.
- Active checkpoint: **Stage 5 / CP5.2 — Workflow Engine backend**.
- Feature branch: `agent/stage5-cp52-workflow-engine`.
- Draft PR: `#11`, stacked on `agent/stage5-cp51-tasks-core`.
- Functional code head: `dc23aae6779f193cd9f36bdd11ec507907d2597b`.
- Documentation-complete verified head before this status-only synchronization: `7e4c49535f6fb6efb18670a1841f6f3c8b17299b`.
- Alembic head: `0014_stage5_workflow_engine`.
- Final verification: GitHub Actions run `31694161900` (#442) — Ruff PASS, `alembic upgrade head` PASS, pytest PASS. The immediately preceding full evidence run `31693756568` (#420) reported **562 passed / 289 warnings**; run #442 passed the same complete suite after the warning-cleanup and documentation commits.

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

## Organization Smart Import — base + hardening integrated

Integration branch: `agent/integration-cp52-smart-import-hardening` (local merge of CP5.2 + Smart Import base + Smart Import hardening; merge commit `3415cf2`).

- CP5.2 Workflow Engine: **complete** (`agent/stage5-cp52-workflow-engine`).
- Organization Smart Import base: **integrated** — migration re-chained as `0015_org_legal_form_fields`.
- Organization Smart Import hardening: **integrated** (`agent/parallel-org-smart-import-hardening`, PR #13) — legal-form-aware fields, server-side legal-form rules, read-only import preview pipeline, local OCR adapter, hardened create/edit routes served through a Next.js proxy while user URLs stay `/organizations/new` and `/organizations/[id]/edit`.
- Alembic: **single head** `0015_org_legal_form_fields`; linear chain `0013_stage5_tasks_core -> 0014_stage5_workflow_engine -> 0015_org_legal_form_fields`.
- Backend regression on disposable test PostgreSQL (port `5433`): **579 passed / 0 skipped / 0 failed**; `ruff check app tests` PASS.
- Frontend: lint PASS, typecheck PASS, tests **80 passed**, production build PASS.
- OCR runtime: local Tesseract **not installed** (`OCR_RUNTIME_AVAILABLE = NO`); OCR code is green via mocks/stubs, `TESSERACT_CMD`/`TESSERACT_LANG` documented in `.env.example`.
- Reports/Documents source (`agent/reports-document-control-ready`): integrated into the new branch described below.

## Reports and Organization Documents — MERGED

Source branch `agent/integration-reports-documents` (PR #16) merged into the canonical integration branch `agent/integration-cp52-smart-import-hardening` via merge commit `7426cb2`. Independent review passed with no P0/P1/P2 findings; only non-blocking P3 backlog items recorded.

- Reports: **COMPLETE**; `/api/reports/management` uses live organization, contract, task and document data and remains superuser-only.
- Organization Documents: **COMPLETE**; organization-scoped list/upload/download/soft-delete uses `LocalFileStorage` and `STORAGE_ROOT`.
- Document Completeness: **COMPLETE**; administrator-managed requirements support `all` and `has_opo`, and missing documents are derived only from active required applicable rules.
- Documents workspace: `/organizations/[id]/documents`, linked directly from the organization card; no global Documents navigation item was added.
- Alembic: **single head** `0016_documents`; linear chain `0013_stage5_tasks_core -> 0014_stage5_workflow_engine -> 0015_org_legal_form_fields -> 0016_documents`.
- Migration round-trip on disposable PostgreSQL port `5433`: `0016_documents -> 0015_org_legal_form_fields -> 0016_documents` PASS; `document_requirements` and `organization_documents` verified.
- Backend regression (post-merge, disposable PostgreSQL): **594 passed / 0 skipped / 0 failed**; Ruff PASS.
- Frontend (post-merge): lint PASS, typecheck PASS, tests **84 passed**, production build PASS.
- CI on PR #16: 4/4 checks success; auto-merge was off; `main` untouched.

### Canonical integration baseline

- Canonical branch: `agent/integration-cp52-smart-import-hardening` (HEAD `7426cb2888771551797e66f137531ff8029e6d6f`).
- Contains: CP5.2 Workflow Engine, Organization Smart Import (+ hardening), Reports, Organization Documents, Document Completeness.
- Current Alembic head: `0016_documents`.

## Stage 6 CP6.1 — Expertise Core — MERGED

Source branch `agent/stage6-cp61-expertise-core` (PR #17) merged into the canonical integration branch `agent/integration-cp52-smart-import-hardening` via merge commit `b722b41`. Independent final review passed with no P0/P1/P2 findings.

- Domain invariant **1 expertise = 1 expertise subject** enforced at DB level (`expertise_subjects.expertise_id UNIQUE` + CHECK `technical_device_id` XOR `building_id`) and at the service layer.
- `expertises` / `expertise_subjects` / `expertise_contract_items` / `expertise_status_history` tables; FK RESTRICT for historically meaningful references (contract, expertise type, employee, TD, building); soft-delete only, no cascade destroying history.
- Status machine `preparation -> … -> completed` with `rtn_review -> {registered, rtn_rework}` and `rtn_rework -> ready_for_registration`; unconfirmed transitions fail closed; `completed` terminal.
- Append-only `expertise_status_history` with `from_status`/`to_status`/`changed_by`/`reason`.
- Optimistic locking via `version` + expected-version check → `409 Conflict` on mismatch (both PATCH and status mutation).
- Scoped authorization via existing `expertises.view/create/edit/change_status` permission codes; list filtering applied before count/offset/limit; foreign expertise/contract/item/TD/building fail closed with 404.
- Alembic: **single head** `0017_expertises`; linear chain `… -> 0016_documents -> 0017_expertises`.
- Migration round-trip on disposable PostgreSQL port `5433`: `0017_expertises -> 0016_documents -> 0017_expertises` PASS.
- Backend regression (pre-merge, disposable PostgreSQL): **617 passed / 0 skipped / 0 failed**; Ruff PASS.
- Backend regression (post-merge, canonical branch): **618 passed / 0 skipped / 0 failed**; Ruff PASS; `alembic heads` single head `0017_expertises`.
- Frontend: `/expertise` (real paginated list), `/expertise/[id]` (real card + status history), `/expertise/new` (create); mock-data no longer backs the Expertise routes. lint PASS, typecheck PASS, tests **88 passed**, production build PASS (pre- and post-merge).
- CI on PR #17: 4/4 checks success; auto-merge off; `main` untouched.

### Canonical integration baseline

- Canonical branch: `agent/integration-cp52-smart-import-hardening` (HEAD `b722b41`).
- Contains: CP5.2 Workflow Engine, Organization Smart Import (+ hardening), Reports, Organization Documents, Document Completeness, Expertise Core.
- Current Alembic head: `0017_expertises`.


## Stage 6 CP6.2 — Expertise Collaboration + Workflow Bridge

Feature branch: `agent/stage6-cp62-expertise-collaboration` (worktree `D:\Spravoshnik-EPB-Expertise-CP62`), based on the canonical integration branch.

- **Responsible-expert selector**: `GET /api/employees` (`employees.view`) returns active employees; `/expertise/new` now offers a real responsible-expert selector instead of hardcoding the current user. `expertises.responsible_expert_id` remains the single source of truth.
- **Participants**: `expertise_participants` (expertise_id FK CASCADE, employee_id FK RESTRICT, `participation_role` enum `expert|specialist`, UNIQUE `(expertise_id, employee_id, participation_role)`). API: list/add/remove participants (`expertises.view` / `expertises.assign_experts`). Responsible expert is NOT duplicated — read from `expertises.responsible_expert_id`.
- **Task ↔ Expertise**: `task_expertises` FK-backed link table (task FK CASCADE, expertise FK RESTRICT, `is_primary`), driven by the new `TaskLinkKind.EXPERTISE`. Task link access is scope-checked via `expertises.view` (fail closed on foreign expertise); `task_expertises` participates in task scope/related-organization resolution.
- **Workflow bridge**: manual `POST /api/expertises/{id}/workflow/start` (`expertises.edit`) reuses CP5.2 `WorkflowService.instantiate`, linking generated tasks to the expertise with `TaskLinkInput(kind=EXPERTISE, is_primary=True)`. `GET /api/expertises/workflow-templates` lists templates with a published version. No second workflow engine, no generic `entity_type/entity_id`, no auto-start on create (docs only say a template *can* be applied, `BUSINESS_RULES.md §24`).
- **Internal number**: format not confirmed in docs → **deferred**; `internal_number` stays a free-text field, no numbering service invented in CP6.2.
- Alembic: **single head** `0018_expertise_collaboration`; linear chain `… -> 0017_expertises -> 0018_expertise_collaboration`.
- Migration round-trip on disposable PostgreSQL port `5433`: `0018 -> 0017 -> 0018` PASS.
- Backend regression (disposable PostgreSQL): **633 passed / 0 skipped / 0 failed**; Ruff PASS.
- Frontend: `/expertise/new` real responsible-expert selector; `/expertise/[id]` gains Участники / Связанные задачи / Процесс blocks (permission-gated, real API, no mock-data). lint PASS, typecheck PASS, tests **88 passed**, production build PASS.

### Deferred (next CPs)

Inspection, NDT, defects, photos, calculations, conclusion, RTN attempts, DOCX generation, AI, expertise documents, expert attestation subsystem, numbering format.



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
