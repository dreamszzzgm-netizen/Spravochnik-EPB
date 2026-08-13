# Organization Smart Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить безопасный многошаговый импорт реквизитов организации и динамическую форму для юридического лица/ИП с поддержкой ОГРНИП, места жительства и структурированных паспортных данных.

**Architecture:** Импорт остаётся отдельным application/service flow: parse/normalize/validate → preview candidate → explicit confirmation → transactional domain save. Recognition/AI не пишет в рабочие таблицы напрямую. Динамические поля организации хранятся как core fields и identifiers, а паспортные данные ИП — в отдельной структурированной сущности, чтобы не смешивать их с общими реквизитами и не отправлять во внешний AI.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic, Next.js 16 App Router, React 19, TypeScript, shadcn/ui, pytest.

## Global Constraints

- Ветка: `agent/parallel-organization-smart-import`; не переносить незавершённые изменения из `agent/stage5-cp52-workflow-engine`.
- Импорт всегда многошаговый: parse → normalize → validate → duplicate detection → preview → user confirmation → transactional save.
- Recognition/AI не записывает рабочие данные напрямую.
- Персональные данные не передаются внешнему ИИ без безопасной обработки и подтверждения; паспортные данные ИП не отправлять внешнему AI.
- Критичные изменения сохраняются только после явного подтверждения пользователя.
- Бизнес-логика не размещается в HTTP routes.
- Все изменения схемы только через Alembic.
- UI использует существующий стек и дизайн-токены; не заменять Next.js/React/shadcn/Tailwind.

---

### Task 1: Organization type rules and IP profile data

**Files:**
- Create: `alembic/versions/0014_organization_ip_profile.py`
- Modify: `app/modules/organizations/models.py`
- Modify: `app/modules/organizations/schemas.py`
- Modify: `app/modules/organizations/service.py`
- Test: `tests/integration/test_organization_ip_profile.py`

**Interfaces:**
- Produces: `IndividualEntrepreneurProfile` model with `organization_id`, `residence_address`, `passport_series`, `passport_number`, `passport_issued_by`, `passport_issue_date`, `passport_department_code`.
- Produces: `IndividualEntrepreneurProfileUpsert` Pydantic schema.
- Rule: profile may exist only for `OrganizationType.INDIVIDUAL_ENTREPRENEUR`.

- [ ] **Step 1: Write failing integration tests** for creating/updating an ИП profile and rejecting profile data for a legal entity.
- [ ] **Step 2: Run** `python -m pytest tests/integration/test_organization_ip_profile.py -q` and confirm failure because the model/service does not exist.
- [ ] **Step 3: Add Alembic migration** creating `individual_entrepreneur_profiles` with one-to-one FK to `organizations.id`, unique `organization_id`, nullable structured passport fields, timestamps, and cascade delete.
- [ ] **Step 4: Add model/schema/service methods** with explicit organization type validation.
- [ ] **Step 5: Re-run targeted tests** and confirm PASS.
- [ ] **Step 6: Commit** `feat(organizations): add individual entrepreneur profile`.

### Task 2: Dynamic identifiers and form contract by organization type

**Files:**
- Modify: `app/modules/organizations/service.py`
- Modify: `frontend/src/app/organizations/new/page.tsx`
- Modify: `frontend/src/app/organizations/[id]/edit/page.tsx`
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/api/resources.ts`
- Test: `tests/unit/test_organizations.py`
- Test: `frontend/src/app/organizations/organization-type-fields.test.ts`

**Interfaces:**
- Legal entity fields: INN, KPP, OGRN, legal/actual address, director, contact fields.
- Individual entrepreneur fields: INN, OGRNIP, residence address, structured passport fields; hide KPP/OGRN UI.
- Branch keeps INN/KPP/OGRN plus parent organization behavior already supported by backend.

- [ ] **Step 1: Write failing backend/frontend tests** describing the exact visible fields per `organization_type` and server-side rejection of contradictory identifier combinations where applicable.
- [ ] **Step 2: Run targeted tests** and confirm RED.
- [ ] **Step 3: Extract a small frontend field-definition helper** so new/edit pages use the same organization-type rules.
- [ ] **Step 4: Wire IP profile payload into create/update API resources** without changing unrelated organization endpoints.
- [ ] **Step 5: Run targeted tests** and confirm GREEN.
- [ ] **Step 6: Commit** `feat(organizations): switch fields by organization type`.

### Task 3: Smart import candidate parser

**Files:**
- Create: `app/services/imports/__init__.py`
- Create: `app/services/imports/organization_candidate.py`
- Create: `app/services/imports/organization_parser.py`
- Test: `tests/unit/test_organization_import_parser.py`

**Interfaces:**
- Produces: `OrganizationImportCandidate` with normalized organization fields, identifiers, optional IP profile, `warnings`, `errors`, `source_fields`, and per-field confidence when available.
- Consumes plain text/key-value input initially; OCR/provider-specific extraction remains outside this parser.

- [ ] **Step 1: Write failing parser tests** for common Russian labels (`ИНН`, `КПП`, `ОГРН`, `ОГРНИП`, addresses, director, phone, email, passport labels).
- [ ] **Step 2: Run** `python -m pytest tests/unit/test_organization_import_parser.py -q` and confirm RED.
- [ ] **Step 3: Implement deterministic normalization/parsing** without network calls or AI dependency.
- [ ] **Step 4: Add validation** for identifier length/shape and organization-type inference only when evidence is unambiguous; otherwise return a warning requiring user choice.
- [ ] **Step 5: Run targeted tests** and confirm GREEN.
- [ ] **Step 6: Commit** `feat(import): parse organization candidate data`.

### Task 4: Duplicate detection and preview API

**Files:**
- Create: `app/services/imports/organization_import_service.py`
- Modify: `app/modules/organizations/repository.py`
- Modify: `app/modules/organizations/routes.py`
- Test: `tests/integration/test_organization_import_api.py`

**Interfaces:**
- `POST /api/organizations/import/preview` accepts candidate source data and returns normalized candidate plus duplicate matches.
- Duplicate detection checks unique identifiers first (INN/OGRN/OGRNIP), then returns soft name matches as warnings only.
- Preview endpoint never writes organization data.

- [ ] **Step 1: Write failing API tests** proving preview creates no rows and returns duplicates/warnings.
- [ ] **Step 2: Run targeted tests** and confirm RED.
- [ ] **Step 3: Implement repository lookup helpers and import preview service**.
- [ ] **Step 4: Add thin HTTP route** delegating to the service layer.
- [ ] **Step 5: Re-run tests** and confirm GREEN.
- [ ] **Step 6: Commit** `feat(import): add organization import preview`.

### Task 5: Explicit confirmation and transactional save

**Files:**
- Modify: `app/services/imports/organization_import_service.py`
- Modify: `app/modules/organizations/routes.py`
- Test: `tests/integration/test_organization_import_api.py`

**Interfaces:**
- `POST /api/organizations/import/confirm` accepts a user-reviewed candidate plus explicit duplicate resolution.
- Save uses existing organization application/service methods and one DB transaction.
- No save if candidate contains unresolved validation errors or duplicate conflict requiring user decision.

- [ ] **Step 1: Add failing tests** for successful confirm, rollback on invalid IP profile, and duplicate conflict without explicit resolution.
- [ ] **Step 2: Run targeted tests** and confirm RED.
- [ ] **Step 3: Implement confirm flow** revalidating all fields server-side before save.
- [ ] **Step 4: Run targeted tests** and confirm GREEN.
- [ ] **Step 5: Commit** `feat(import): confirm organization import transactionally`.

### Task 6: Smart import UI with review before save

**Files:**
- Create: `frontend/src/app/organizations/new/_components/smart-import.tsx`
- Modify: `frontend/src/app/organizations/new/page.tsx`
- Modify: `frontend/src/lib/api/resources.ts`
- Modify: `frontend/src/lib/api/types.ts`
- Test: `frontend/src/app/organizations/new/smart-import.test.ts`

**Interfaces:**
- UI flow: paste/upload supported source → “Распознать данные” → preview form with warnings/duplicates → user edits → explicit “Применить данные” to populate the create form.
- Final organization creation remains the existing explicit “Создать организацию” action.
- Passport fields are visually marked as local/confidential data and never sent to an external AI endpoint by this feature.

- [ ] **Step 1: Write failing component/contract tests** for preview-only behavior and explicit apply action.
- [ ] **Step 2: Run frontend targeted tests** and confirm RED.
- [ ] **Step 3: Implement compact import card** using existing shadcn components and design tokens.
- [ ] **Step 4: Ensure switching organization type after import updates visible fields without silently deleting candidate data before final submit; hidden incompatible identifiers are excluded from payload.
- [ ] **Step 5: Run frontend tests, typecheck and lint**.
- [ ] **Step 6: Commit** `feat(frontend): add smart organization import review flow`.

### Task 7: Regression and branch verification

**Files:**
- No production changes unless failures require a scoped fix.

- [ ] **Step 1: Run backend unit/integration suite** with the configured PostgreSQL test database.
- [ ] **Step 2: Run `ruff check .`**.
- [ ] **Step 3: Run frontend tests/typecheck/lint/build**.
- [ ] **Step 4: Compare branch against `agent/stage5-cp51-tasks-core`** and confirm no Workflow Engine files from CP5.2 were imported.
- [ ] **Step 5: Create a completion review document** under `docs/superpowers/reviews/` with evidence and remaining limitations.
