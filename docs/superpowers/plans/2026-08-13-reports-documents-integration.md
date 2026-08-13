# Reports and Organization Documents Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the prepared Reports/Documents work into the verified CP5.2 + Smart Import hardening baseline and deliver a single migrated, tested document-completeness workflow.

**Architecture:** Preserve the canonical CP5.2 and Smart Import architecture, merge the prepared domain/UI history, then add one linear Alembic revision after `0015_org_legal_form_fields`. Keep document status calculation in the backend domain service, persist files through the existing `LocalFileStorage`, expose organization-scoped document endpoints and admin-only requirement endpoints, and have Reports and the organization workspace consume those APIs.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, pytest, Next.js, TypeScript, Vitest, Tailwind.

## Global Constraints

- Base branch and SHA: `agent/integration-cp52-smart-import-hardening` at `68f88ce239a4ee73ad4f93077da11a7dfcf035b7`.
- Source branch: `agent/reports-document-control-ready` at `c1cb1fba26c79367cca759dda4ca66ab7714026d`.
- Do not use superseded Reports branches or merge PR #14 directly.
- Maintain exactly one Alembic head: `0016_documents`, down revision `0015_org_legal_form_fields`.
- Never create document tables at runtime and never alter applied migrations.
- Missing documents are derived only from active, required, applicable requirements.
- Initial applicability values are exactly `all` and `has_opo`; `has_opo` uses owner or operator OPO relationships.
- Use existing identity permissions when suitable; otherwise restrict requirement administration and Reports to superuser/admin.
- Use existing `LocalFileStorage` and `STORAGE_ROOT`; no cloud storage or parallel file-storage implementation.
- Test database is disposable PostgreSQL `127.0.0.1:5433/spravoshnik_test`, never pilot/working data.
- Do not merge to `main`, enable auto-merge, delete historical branches, or start the Expertise module.

---

### Task 1: Merge prepared Reports/Documents history

**Files:** Prepared source delta under `app/modules/analytics/`, `app/modules/documents/`, `frontend/src/app/reports/`, `frontend/src/app/organizations/`, `frontend/src/lib/api/`, `tests/unit/`, and `app/main.py`.

**Interfaces:** Consumes the canonical application routers and authorization dependencies. Produces the prepared models, service, API, report, and workspace as the integration starting point.

- [ ] Merge `origin/agent/reports-document-control-ready` with history preserved.
- [ ] Resolve conflicts in favor of the canonical CP5.2/Smart Import architecture.
- [ ] Run existing source tests and record every failure before changing implementation.

### Task 2: Add the linear Documents migration

**Files:** Create `alembic/versions/0016_documents.py`; test migration structure and PostgreSQL round-trip under `tests/integration/`.

**Interfaces:** Produces `document_requirements` and `organization_documents` matching the SQLAlchemy models, including requirement uniqueness and organization FK.

- [ ] Add a failing test asserting revision/down-revision, columns, constraints, indexes, upgrade, downgrade, and re-upgrade.
- [ ] Verify the test fails because revision `0016_documents` is absent.
- [ ] Implement only the two tables and their model-required constraints/indexes.
- [ ] Verify one head, then run the migration test against disposable PostgreSQL.

### Task 3: Complete document status and requirement administration

**Files:** Modify `app/modules/documents/control.py`, `repository.py`, `schemas.py`, `routes.py`; add focused unit/integration tests.

**Interfaces:** Produces one status classifier (`expired`, `expiring_14`, `expiring_40`, `valid`, `missing`, `no_expiry`), applicability filtering, and GET/POST/PATCH/disable requirement APIs.

- [ ] Add failing boundary and applicability tests, including inactive/non-required rules and owner/operator OPO links.
- [ ] Add failing authorization and CRUD API tests with explicit test requirements.
- [ ] Implement minimal shared status/applicability logic and admin-restricted CRUD.
- [ ] Re-run focused tests and Ruff.

### Task 4: Harden organization document storage and API

**Files:** Modify `app/modules/documents/service.py`, `repository.py`, `routes.py`, `schemas.py`; add storage and API acceptance tests.

**Interfaces:** Produces list/upload/download/soft-delete organization-scoped endpoints using `LocalFileStorage`, safe keys, SHA-256, atomic writes, rollback cleanup, and deleted-row filtering.

- [ ] Add failing tests for byte-identical download, metadata/hash/size, traversal rejection, authorization, rollback cleanup, and soft-delete visibility.
- [ ] Implement only the missing behavior while retaining the existing storage abstraction.
- [ ] Re-run focused storage/API tests and Ruff.

### Task 5: Complete Documents workspace and organization-card entry

**Files:** Modify `frontend/src/app/organizations/[id]/documents/page.tsx`, its component, `frontend/src/app/organizations/[id]/page.tsx`, and `frontend/src/lib/api/documents.ts`; add Vitest tests.

**Interfaces:** Consumes the Documents API and backend-provided status. Produces organization-local Documents navigation, list, upload, download, delete, loading, empty, and error states.

- [ ] Add failing tests for the card link, workspace states, upload fields, and actions.
- [ ] Implement minimal UI without a global Documents navigation item or duplicated status calculation.
- [ ] Re-run focused frontend tests, lint, and typecheck.

### Task 6: Complete management Reports and access control

**Files:** Modify `app/modules/analytics/`, `frontend/src/app/reports/page.tsx`, API client, dashboard/nav entry, and tests.

**Interfaces:** Produces real database counts and issue rows with organization/document identity and deep links; exposes `/reports` only to authorized users.

- [ ] Add failing backend acceptance tests for all six document statuses, source availability, and real counts.
- [ ] Add failing authorization and UI deep-link/visibility tests.
- [ ] Implement backend aggregation through the shared status service and guarded frontend entry.
- [ ] Re-run focused backend/frontend tests.

### Task 7: Full acceptance and regression verification

**Files:** Add or extend acceptance tests only where coverage is missing.

**Interfaces:** Verifies organizations with and without OPO, explicit requirements, all status boundaries, file lifecycle, report data, CP5.2, and Smart Import formats.

- [ ] Run migration upgrade/downgrade/upgrade on disposable PostgreSQL and inspect tables/current revision.
- [ ] Run `python -m ruff check app tests`, `python -m alembic heads`, and full `python -m pytest -q` with `TEST_DATABASE_URL` set.
- [ ] Run frontend `npm ci`, lint, typecheck, all tests, and production build.
- [ ] Run focused CP5.2 Workflow/Tasks/Identity/Organizations and Smart Import TXT/DOCX/XLSX/PDF regressions.

### Task 8: Review, status, and publication

**Files:** Modify `PROJECT_STATUS.md` only for capabilities proven by fresh verification; inspect the complete branch diff.

**Interfaces:** Produces a clean pushed branch and a new Draft PR based on the canonical hardening branch.

- [ ] Request an independent code review for the full base-to-head diff and resolve all Critical/Important findings with test-first fixes.
- [ ] Repeat all affected verification and run `git diff --check` plus secret/artifact hygiene checks.
- [ ] Update project status only for proven completion, commit intentional files, and push `agent/integration-reports-documents`.
- [ ] Create a Draft PR referencing source branch, Issue #15, Alembic chain, round-trip, test evidence, and storage policy; keep auto-merge off.
- [ ] Update Issue #15 and close it only if every listed acceptance and CI gate is green.

## Self-review

- Spec coverage: migration, CRUD, storage/API, shared statuses, workspace, report, authorization, PostgreSQL round-trip, backend/frontend/CP5.2/Smart Import regressions, project status, push, PR, and Issue #15 are mapped above.
- Placeholder scan: no deferred implementation placeholders remain; detailed assertions will follow the actual established test helpers discovered during each TDD task.
- Type consistency: the plan retains source model names `OrganizationDocument`, `DocumentRequirement`, `DocumentStatus`, existing `LocalFileStorage`, and existing organization/identity boundaries.
