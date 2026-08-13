# Stage 6 CP6.1 — Expertise Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:test-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the stable Expertise domain foundation: `1 expertise = 1 expertise subject`, contract scoping, responsible expert invariant, status machine + history, optimistic locking, scoped authorization, and a real-data frontend list/detail/create.

**Architecture:** New module `app/modules/expertises/` following the existing modular-monolith layering (HTTP → Service → Repository → DB) and the established contracts/tasks patterns. Physical `expertises`/`expertise_subjects`/`expertise_contract_items`/`expertise_status_history` tables via hand-written Alembic migration `0017_expertises` (down_revision `0016_documents`), with DB-level FK/UNIQUE/CHECK/indexes — never runtime DDL.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (PostgreSQL) + Alembic; Next.js 16 (Turbopack) frontend.

## Global Constraints

- Branch: `agent/stage6-cp61-expertise-core`; worktree `D:\Spravoshnik-EPB-Expertise`.
- Canonical base: `agent/integration-cp52-smart-import-hardening` (`a69b9ae`). Do NOT touch `main`.
- Do NOT commit/delete local `docker-compose.yml` / `run.bat` env edits in the main worktree.
- Python 3.13 (`.venv`); ruff target py312, line-length 100, select `E,F,I,B,UP,SIM`.
- Alembic head after this CP must be exactly one: `0017_expertises`.
- Backend baseline 594 passed / 0 skipped; frontend 84 passed. No `skip` additions.
- Test PostgreSQL: `127.0.0.1:5433/spravoshnik_test` only. Never production/pilot (5434).
- Enum machine values (confirmed by BUSINESS_RULES §11 + DATA_MODEL): `preparation`, `document_collection`, `inspection`, `conclusion_preparation`, `internal_approval`, `ready_for_registration`, `rtn_review`, `rtn_rework`, `registered`, `received_by_customer`, `completed`.
- Permission codes (PERMISSIONS.md §9): `expertises.view`, `expertises.create`, `expertises.edit`, `expertises.change_status` (+ reserved `expertises.delete/restore/assign_experts/...` NOT implemented in CP6.1).
- No workflow auto-instantiation, no documents linking, no inspection/RTN/conclusion/AI.

## Data model (confirmed from DATA_MODEL.md §20–§23, §31.2)

- `expertises`: `id`, `contract_id FK contracts RESTRICT`, `expertise_type_id FK expertise_types RESTRICT`, `status`, `internal_number NULL`, `responsible_expert_id FK employees RESTRICT`, `comment NULL`, `created_by FK users RESTRICT`, `created_at`, `updated_at`, `deleted_at`, `version`.
- `expertise_subjects`: `id`, `expertise_id FK expertises UNIQUE`, `technical_device_id FK technical_devices NULL`, `building_id FK buildings NULL`, CHECK exactly-one-of-two NOT NULL.
- `expertise_contract_items`: `expertise_id FK expertises`, `contract_item_id FK contract_items`, PK `(expertise_id, contract_item_id)`.
- `expertise_status_history`: `id`, `expertise_id FK expertises`, `from_status NULL`, `to_status`, `changed_at TIMESTAMPTZ`, `changed_by FK users`, `reason NULL`. Append-only.

Deferred columns (conclusion stage): `conclusion_date`, `safe_operation_until`, `expertise_participants`.

## Status transitions (BUSINESS_RULES §11.1–11.2)

```
preparation -> document_collection
document_collection -> inspection
inspection -> conclusion_preparation
conclusion_preparation -> internal_approval
internal_approval -> ready_for_registration
ready_for_registration -> rtn_review
rtn_review -> registered | rtn_rework
rtn_rework -> ready_for_registration
registered -> received_by_customer
received_by_customer -> completed
```
Initial `preparation`; terminal `completed` (no outgoing). Unconfirmed transitions fail closed.

---

### Task 1: Migration `0017_expertises`

**Files:** Create `alembic/versions/0017_expertises.py`; Modify `alembic/env.py` (import expertise models).

- [ ] Create tables `expertises`, `expertise_subjects`, `expertise_contract_items`, `expertise_status_history` with FK/UNIQUE/CHECK/indexes; downgrade drops them in reverse.
- [ ] `python -m alembic heads` == `0017_expertises`.

### Task 2: Models + enum

**Files:** Create `app/modules/expertises/__init__.py`, `enums.py`, `models.py`.

- [ ] `ExpertiseStatus` StrEnum (11 values). `Expertise`, `ExpertiseSubject`, `ExpertiseContractItem`, `ExpertiseStatusHistory` mapped models mirroring the migration exactly.

### Task 3: Domain rules

**Files:** Create `app/modules/expertises/domain.py` (or fold into `service.py`).

- [ ] `EXPERTISE_TRANSITIONS` dict. `can_transition(from, to)`. Helper to validate subject XOR (service-level, DB CHECK is the authority).

### Task 4: Repository

**Files:** Create `app/modules/expertises/repository.py`.

- [ ] `get_expertise`, `get_expertise_for_update` (with_for_update), `list_expertises_paginated` (scope filter applied BEFORE count/offset/limit; filters `contract_id`, `status`, `q`), subject/link/history readers. `_apply_expertise_scope` joins `Contract`.

### Task 5: Service

**Files:** Create `app/modules/expertises/service.py`.

- [ ] `create_expertise` (atomic: validate contract/type/items/subject/expert → create expertise + subject + contract-item links + initial history → commit/rollback), `update_expertise` (version check → 409 on mismatch → `version += 1`), `change_status` (transition check → status + history row + audit), `ExpertiseVersionConflictError`.

### Task 6: Schemas + Authorization helper

**Files:** Create `app/modules/expertises/schemas.py`; Modify `app/modules/identity/authorization.py` (add `can_access_expertise`).

- [ ] Pydantic request/response models (create/update/status-change/list paginated). `can_access_expertise(ctx, customer_organization_id, responsible_employee_id)`.

### Task 7: Routes + register

**Files:** Create `app/modules/expertises/routes.py`; Modify `app/main.py`.

- [ ] `GET /api/expertises`, `GET /api/expertises/{id}`, `POST /api/expertises`, `PATCH /api/expertises/{id}`, `POST /api/expertises/{id}/status`. Scoped deps `expertises.*`. IDOR fail-closed (foreign contract/item/TD/building → 404).

### Task 8: Tests (TDD, written before each piece of production code)

**Files:** Create `tests/unit/test_expertise_domain.py`, `tests/unit/test_expertise_models.py`, `tests/integration/test_expertise_api.py`, `tests/integration/test_expertise_migration.py`; Modify `tests/conftest.py` (add expertise tables to TRUNCATE list).

- [ ] RED tests for all 12 mandatory invariants + acceptance A–F + IDOR + version 409 + pagination scope + migration round-trip.

### Task 9: Frontend real-data slice

**Files:** Create `frontend/src/lib/api/expertises.ts`; Modify `frontend/src/app/expertise/page.tsx`, `frontend/src/app/expertise/[id]/page.tsx`; add `/expertise/new`.

- [ ] Replace `@/lib/mock-data` `expertiseList` with real paginated list; real detail card; create form. Keep loading/empty/error/forbidden states. No production mock-data dependency for `/expertise*`.

### Task 10: Regression + report

- [ ] Full backend (ruff + alembic heads + pytest), full frontend (lint/typecheck/test/build), migration round-trip, update `PROJECT_STATUS.md`, push, Draft PR.
