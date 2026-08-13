# Organization Smart Import Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete local file-based organization smart import and enforce legal-form-specific organization data on both create and edit flows.

**Architecture:** Keep recognition read-only and reuse the existing deterministic requisites parser. Add a local extraction/OCR boundary plus a reusable preview builder; legal-form rules live in a focused domain helper and are enforced by the service/API, while the frontend mirrors the same applicability for usability.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Python stdlib ZIP/XML, pypdf, pypdfium2, local Tesseract CLI, Next.js 16, React 19, TypeScript, Vitest.

## Global Constraints

- No external AI/network processing of organization documents.
- Recognition never writes directly to organization tables.
- Preview must require explicit apply, and final persistence remains a normal create/update action.
- Do not modify CP5.2 Workflow Engine internals or migrations.
- Upload limit is 5 MiB; Office expanded ZIP limit is 20 MiB; PDF limit is 20 pages; OCR timeout is 30 seconds per page.

---

### Task 1: Backend legal-form rules

**Files:**
- Create: `app/modules/organizations/legal_form.py`
- Modify: `app/modules/organizations/service.py`
- Modify: `app/modules/organizations/routes.py`
- Test: `tests/unit/test_organization_legal_form.py`
- Test: `tests/integration/test_organizations.py`

**Interfaces:**
- Produces: `validate_organization_legal_form(...) -> None`, `OrganizationLegalFormError`.
- Service create/update call validation before persistence; update clears fields that become inapplicable after a legal-form switch.

- [ ] Write tests proving IP rejects legal-only fields/identifiers and legal entity rejects IP-only fields/OGRNIP.
- [ ] Run focused tests and confirm RED because the helper/behavior is missing.
- [ ] Implement the helper and service integration.
- [ ] Run focused tests and full backend regression.
- [ ] Commit.

### Task 2: Local file extraction boundary

**Files:**
- Create: `app/modules/organizations/import_files.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/test_organization_import_files.py`

**Interfaces:**
- Produces: `extract_local_import_text(filename: str, content_type: str | None, raw: bytes) -> str`.
- Errors: `UnsupportedImportFormatError`, `InvalidImportFileError`, `LocalOcrUnavailableError`.

- [ ] Write failing tests for TXT, DOCX, XLSX, PDF text, image OCR adapter and safety limits.
- [ ] Confirm RED.
- [ ] Implement stdlib Office extraction, local PDF extraction and local Tesseract OCR fallback.
- [ ] Run focused tests and Ruff.
- [ ] Commit.

### Task 3: Multipart import-preview API

**Files:**
- Modify: `app/modules/organizations/routes.py`
- Test: `tests/integration/test_organizations.py`

**Interfaces:**
- Adds: `POST /api/organizations/import-file-preview` multipart `file` returning the existing `OrganizationImportPreviewResponse`.
- Reuses one private preview builder so pasted-text and file preview use identical duplicate checks.

- [ ] Write failing endpoint tests for valid file, oversized file, corrupt/unsupported format, read-only behavior and OCR-unavailable failure.
- [ ] Confirm RED.
- [ ] Implement endpoint and shared preview builder.
- [ ] Run focused and full backend tests.
- [ ] Commit.

### Task 4: Legal-form-aware edit form

**Files:**
- Modify: `frontend/src/app/organizations/[id]/edit/page.tsx`
- Test: `frontend/src/app/organizations/[id]/edit/smart-form.test.ts`

**Interfaces:**
- Edit form uses `[inn, ogrnip]` for IP and `[inn, kpp, ogrn]` for legal entity/branch.
- IP submits `residence_address`/`passport_details` and nulls legal-only fields; legal forms do the inverse.

- [ ] Write failing source-contract tests for legal-form-specific edit fields.
- [ ] Confirm RED.
- [ ] Implement dynamic edit UI and payload filtering.
- [ ] Run Vitest/typecheck.
- [ ] Commit.

### Task 5: File upload UI on create and edit

**Files:**
- Modify: `frontend/src/lib/api/resources.ts`
- Modify: `frontend/src/app/organizations/new/page.tsx`
- Modify: `frontend/src/app/organizations/[id]/edit/page.tsx`
- Test: focused frontend tests.

**Interfaces:**
- Adds: `previewOrganizationImportFile(file: File, options?)` using `FormData` and the new endpoint.
- File recognition only populates preview; `Применить к форме` remains explicit.

- [ ] Write failing API/UI tests.
- [ ] Confirm RED.
- [ ] Add file-preview API client and UI controls.
- [ ] Run lint/typecheck/Vitest/build.
- [ ] Commit.

### Task 6: Final verification and review checkpoint

- [ ] Run/inspect backend GitHub Actions: Ruff, Alembic, full pytest.
- [ ] Run/inspect frontend GitHub Actions: npm ci, lint, typecheck, Vitest, production build.
- [ ] Compare hardening branch against `agent/parallel-org-smart-import` and verify no Workflow Engine paths changed.
- [ ] Open a draft PR targeting `agent/parallel-org-smart-import` with exact CI evidence and no-auto-merge guardrail.