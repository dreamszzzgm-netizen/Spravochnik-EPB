# Organization Smart Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add correct legal-form-specific organization data and a local, preview-first smart requisites import.

**Architecture:** Extend Organizations through one Alembic migration and existing model/schema/service/routes. Keep deterministic requisites extraction in a focused module with a read-only preview service. Frontend uses existing API client and applies preview values to local form state only after explicit user action.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Pydantic, Alembic, pytest, Next.js 16, React 19, TypeScript, Vitest.

## Global Constraints
- Branch from CP5.1 only; do not merge/rebase CP5.2.
- No external AI/network calls for import.
- Import preview performs no business-table writes.
- Schema changes only through Alembic.
- Backend business logic stays out of routes.
- TDD: failing test commit before production implementation.

---

### Task 1: Domain candidate parser and legal-form schema
**Files:** create `app/modules/organizations/importer.py`; modify `app/modules/organizations/schemas.py`; test `tests/unit/test_organization_smart_import.py`.

- [ ] Add RED tests proving IP fields exist and requisites text extracts legal form/identifiers/addresses without persistence.
- [ ] Verify RED in GitHub Actions.
- [ ] Implement deterministic parser and preview schemas.
- [ ] Verify unit tests GREEN.

### Task 2: Persistent IP fields
**Files:** create `alembic/versions/0014_organization_legal_form_fields.py`; modify `app/modules/organizations/models.py`, `service.py`, `routes.py`; extend integration tests.

- [ ] Add RED migration/API round-trip tests for `residence_address` and `passport_details`.
- [ ] Add migration and service plumbing.
- [ ] Verify Alembic + backend suite GREEN.

### Task 3: Read-only import preview endpoint
**Files:** modify `app/modules/organizations/repository.py`, `routes.py`; test preview endpoint.

- [ ] Add RED tests for no-write behavior and duplicate identifier warnings.
- [ ] Implement lookup-only duplicate detection and preview response.
- [ ] Verify tests GREEN.

### Task 4: Frontend legal-form behavior and smart import
**Files:** modify `frontend/src/lib/api/types.ts`, `resources.ts`, `frontend/src/app/organizations/new/page.tsx`; add focused Vitest tests.

- [ ] Add RED tests for legal-form identifier selection and candidate application.
- [ ] Extract pure form helpers where needed.
- [ ] Implement IP-specific fields and smart-import preview/apply card following existing design system.
- [ ] Verify lint, typecheck, tests, build GREEN.

### Task 5: Full verification and review checkpoint
- [ ] Run backend Ruff, Alembic, pytest via GitHub Actions.
- [ ] Run frontend lint/typecheck/test/build via feature workflow.
- [ ] Update project checkpoint note without changing official integration baseline.
- [ ] Open draft PR targeting `agent/stage5-cp51-tasks-core`; do not merge automatically.