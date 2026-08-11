# Stage 4 CP4.1 Contracts Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first secure, transactional Contracts backend vertical slice from GREEN baseline `650008fc5a80eaf6165d2d0aba249041aae2a98d`.

**Architecture:** Add a focused `app/modules/contracts` module following the existing Stage 3 `models/repository/service/routes/schemas` layering. PostgreSQL owns referential and scalar integrity; the service layer owns cross-table invariants, aggregate amount recalculation, and atomic audit; the route layer adapts FastAPI requests and enforces permission/scope policies without embedding business logic.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 17, Alembic, Pydantic v2, pytest, Ruff.

## Global Constraints

- Base all work on exact commit `650008fc5a80eaf6165d2d0aba249041aae2a98d`.
- Work only on `agent/stage4-cp41-contracts-core`; do not merge into integration.
- Architecture remains a modular monolith with service-layer business rules.
- Backend permission checks are mandatory; hidden UI is never authorization.
- Foreign-scope and absent UUIDs return the same 404 for scoped entities.
- `1 contract item` must reference at least one concrete TD/building subject.
- Contract `amount` is server-owned and equals the sum of active item prices.
- CP4.1 creates contracts only in `draft`; lifecycle transitions are CP4.2+.
- No Tasks, Expertises, Documents, Addenda, suspension, termination, or completion implementation in this checkpoint.
- TDD is mandatory: observable RED before production implementation.

---

## File structure

**Create**
- `app/modules/contracts/__init__.py` — module marker.
- `app/modules/contracts/enums.py` — `ContractStatus`.
- `app/modules/contracts/models.py` — Stage 4 ORM entities.
- `app/modules/contracts/repository.py` — scoped queries and aggregate reads.
- `app/modules/contracts/schemas.py` — API request/response models.
- `app/modules/contracts/service.py` — transactions and business invariants.
- `app/modules/contracts/routes.py` — FastAPI adapter/authorization.
- `alembic/versions/0011_stage4_contracts_core.py` — schema and seed migration.
- `tests/integration/test_contracts_core.py` — service/domain/integration behavior.
- `tests/integration/test_contracts_api.py` — HTTP and authorization behavior.
- `tests/integration/test_stage4_migration.py` — schema/check/seed migration assertions.

**Modify**
- `alembic/env.py` — register contracts metadata.
- `app/main.py` — include Contracts router.
- `app/modules/identity/authorization.py` — contract scope policy only.
- `tests/conftest.py` — Stage 4 truncate list and migration guard.

---

### Task 1: RED — Stage 4 database contract

**Files:**
- Create: `tests/integration/test_stage4_migration.py`
- Modify: `tests/conftest.py` only where required to allow the test database to reach the new expected revision after implementation; do not add production schema here.

**Produces:** tests that require Alembic head `0011_stage4_contracts_core`, contract tables, FK/check constraints, `contract_status`, and deterministic `expertise_types` seeds.

- [ ] **Step 1: Write failing migration assertions**

Tests must assert at minimum:

```python
def test_stage4_tables_exist(db_session: Session) -> None:
    names = set(inspect(db_session.bind).get_table_names())
    assert {
        "contracts",
        "contract_responsibles",
        "expertise_types",
        "contract_items",
        "contract_item_technical_devices",
        "contract_item_buildings",
    } <= names


def test_expertise_type_seed_is_deterministic(db_session: Session) -> None:
    rows = db_session.execute(
        text("SELECT code FROM expertise_types ORDER BY code")
    ).scalars().all()
    assert rows == ["building_epb", "technical_device_epb"]
```

Also inspect/check that `contract_items.price >= 0`, contract date ordering is protected by a DB CHECK when both dates exist, and junction tables have real FKs.

- [ ] **Step 2: Commit tests only**

Commit message:

```text
test(stage4 cp4.1): define contracts database contract
```

- [ ] **Step 3: Push and verify RED in GitHub Actions**

Expected: CI fails because `0011_stage4_contracts_core` / Stage 4 tables do not exist. A syntax/import failure is not an acceptable RED reason.

---

### Task 2: GREEN — Migration and ORM foundation

**Files:**
- Create: `alembic/versions/0011_stage4_contracts_core.py`
- Create: `app/modules/contracts/__init__.py`
- Create: `app/modules/contracts/enums.py`
- Create: `app/modules/contracts/models.py`
- Modify: `alembic/env.py`
- Modify: `tests/conftest.py`

**Produces:** ORM classes `Contract`, `ContractResponsible`, `ExpertiseType`, `ContractItem`, `ContractItemTechnicalDevice`, `ContractItemBuilding` and enum `ContractStatus`.

- [ ] **Step 1: Define enum**

```python
class ContractStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVAL = "approval"
    SIGNED = "signed"
    IN_PROGRESS = "in_progress"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    ARCHIVED = "archived"
```

- [ ] **Step 2: Implement migration**

Use revision/down revision exactly:

```python
revision = "0011_stage4_contracts_core"
down_revision = "0010_stage3"
```

Schema rules:

```text
contracts.customer_organization_id -> organizations.id RESTRICT
contracts.customer_contact_id -> organization_contacts.id RESTRICT NULL
contracts.created_by -> users.id RESTRICT
contract_responsibles.employee_id -> employees.id RESTRICT
contract_items.contract_id -> contracts.id CASCADE
contract_items.expertise_type_id -> expertise_types.id RESTRICT
item-subject junction -> item CASCADE, subject RESTRICT
CHECK amount >= 0
CHECK price >= 0
CHECK start_date/end_date ordering
```

Seed stable UUIDs (hard-coded constants in migration) for `technical_device_epb` and `building_epb`; never use `uuid.uuid4()` for these reference rows.

- [ ] **Step 3: Align ORM models with migration**

Use `Numeric(14, 2)`, timezone-aware timestamps, `deleted_at`, and `version` where specified by the design. Do not add ORM cascades that bypass DB RESTRICT behavior.

- [ ] **Step 4: Register metadata and test cleanup**

`alembic/env.py` imports `app.modules.contracts.models`. `tests/conftest.py` truncates Stage 4 tables child-first through CASCADE and migration guard recognizes/upgrades the new head.

- [ ] **Step 5: Run/push GREEN for migration tests**

Expected commands in CI:

```bash
ruff check app tests
alembic upgrade head
pytest tests/integration/test_stage4_migration.py -q
```

- [ ] **Step 6: Commit**

```text
feat(stage4 cp4.1): add contracts database foundation
```

---

### Task 3: RED — Contract service behavior

**Files:**
- Create: `tests/integration/test_contracts_core.py`

**Consumes:** ORM entities from Task 2.

**Produces:** executable contract for `ContractService`.

- [ ] **Step 1: Write failing tests for create/update validation**

Tests call the intended service API:

```python
service.create_contract(
    db,
    actor_id=actor.id,
    customer_organization_id=org.id,
    customer_contact_id=contact.id,
    number=" 42/2026 ",
    contract_date=date(2026, 8, 11),
    start_date=date(2026, 8, 12),
    end_date=date(2026, 9, 30),
    comment=None,
)
```

Assert stripped number, `draft`, `Decimal("0.00")`, `RUB`, `created_by`, and one `contract.created` audit event.

Write separate tests that reject:
- deleted/missing customer;
- contact of another organization;
- deleted contact;
- `start_date > end_date`;
- blank number.

- [ ] **Step 2: Write failing responsible replacement tests**

Intended API:

```python
service.replace_responsibles(
    db,
    actor_id=actor.id,
    contract=contract,
    employee_ids=[employee_a.id, employee_b.id, employee_a.id],
)
```

Assert active employees only, duplicate normalization, atomic replacement, audit.

- [ ] **Step 3: Write failing item/amount tests**

Intended API:

```python
service.create_item(
    db,
    actor_id=actor.id,
    contract=contract,
    name="ЭПБ сосудов",
    expertise_type_id=expertise_type.id,
    price=Decimal("125000.00"),
    technical_device_ids=[device.id],
    building_ids=[],
    comment=None,
)
```

Assert:
- zero subjects rejected;
- missing/deleted subject rejected;
- amount becomes `125000.00`;
- second item adds to amount;
- update replaces price/subjects and recalculates amount;
- item soft delete removes its price from amount;
- mutation rollback leaves both amount and audit unchanged on failure.

- [ ] **Step 4: Commit and verify RED**

```text
test(stage4 cp4.1): define contracts service behavior
```

Expected RED: missing `contracts.service` / service methods, not malformed tests.

---

### Task 4: GREEN — Repository and ContractService

**Files:**
- Create: `app/modules/contracts/repository.py`
- Create: `app/modules/contracts/service.py`

**Interfaces produced:**

```python
get_contract(db, contract_id, *, include_deleted=False) -> Contract | None
get_contract_responsible_ids(db, contract_id) -> set[UUID]
list_contracts_paginated(db, *, q, page, page_size, customer_organization_id, status, authorization) -> tuple[list[Contract], int]
list_contract_items(db, contract_id, *, include_deleted=False) -> list[ContractItem]

ContractService.create_contract(...) -> Contract
ContractService.update_contract(...) -> Contract
ContractService.delete_contract(...) -> None
ContractService.restore_contract(...) -> None
ContractService.replace_responsibles(...) -> list[UUID]
ContractService.create_item(...) -> ContractItem
ContractService.update_item(...) -> ContractItem
ContractService.delete_item(...) -> None
```

- [ ] **Step 1: Implement validation helpers**

Use explicit exceptions:

```python
class ContractNotFoundError(Exception): ...
class ContractValidationError(Exception): ...
class ContractItemNotFoundError(Exception): ...
```

Centralize customer/contact/date validation and subject loading. Do not catch DB integrity errors as business validation when the service can validate first.

- [ ] **Step 2: Implement transactional create/update/delete/restore**

Write audit before one final `db.commit()`. On any service exception, callers/tests must be able to observe no partial persistent mutation.

- [ ] **Step 3: Implement responsible replacement**

Delete current rows and insert normalized active employee set within the same transaction; commit once.

- [ ] **Step 4: Implement item mutation and amount recalculation**

Use a helper equivalent to:

```python
def _recalculate_amount(db: Session, contract: Contract) -> None:
    total = db.scalar(
        select(func.coalesce(func.sum(ContractItem.price), 0)).where(
            ContractItem.contract_id == contract.id,
            ContractItem.deleted_at.is_(None),
        )
    )
    contract.amount = Decimal(total).quantize(Decimal("0.01"))
```

Subject arrays are full replacement on update when supplied. Validate final combined subject count before deleting existing junction rows.

- [ ] **Step 5: Verify targeted service tests GREEN, then full regression**

- [ ] **Step 6: Commit**

```text
feat(stage4 cp4.1): implement contracts domain service
```

---

### Task 5: RED — Scoped HTTP/API contract

**Files:**
- Create: `tests/integration/test_contracts_api.py`

**Produces:** HTTP behavior and authorization regression matrix.

- [ ] **Step 1: Add authentication/permission matrix**

For each scoped endpoint test:
- unauthenticated → 401;
- authenticated without exact permission → 403;
- absent UUID → 404;
- existing foreign-scope UUID → same 404 body;
- `ALL` → allowed;
- `RELATED` → allowed only for configured customer org;
- `ASSIGNED` → allowed only after employee is responsible;
- `OWN` → allowed only when `created_by` is actor.

No permission may borrow `ALL` or RELATED scope from a different permission code.

- [ ] **Step 2: Add create/list/detail/update/delete/restore tests**

Expected API payload excludes writable `amount`, `status`, `currency`.

List response:

```json
{"items": [], "total": 0, "page": 1, "page_size": 20}
```

- [ ] **Step 3: Add responsible endpoint tests**

`PUT /api/contracts/{id}/responsibles` requires `contracts.manage_responsibles` and contract scope.

- [ ] **Step 4: Add item security tests**

`POST/PATCH/DELETE .../items` requires `contracts.manage_items`. Linking a TD additionally requires effective `technical_devices.view` scope for that TD; linking a building additionally requires effective `buildings.view` scope. Missing permission, foreign scope, deleted entity, and absent UUID all produce the same subject-not-found 404 from the public API.

- [ ] **Step 5: Commit and verify RED**

```text
test(stage4 cp4.1): define contracts authorization API
```

Expected RED: routes/schemas/policy are missing.

---

### Task 6: GREEN — Authorization, schemas, routes

**Files:**
- Modify: `app/modules/identity/authorization.py`
- Create: `app/modules/contracts/schemas.py`
- Create: `app/modules/contracts/routes.py`
- Modify: `app/main.py`

**Produces:** secured FastAPI API defined in the design.

- [ ] **Step 1: Add contract authorization policy**

Add protocol/policy helpers with signatures:

```python
def can_access_contract(
    ctx: AuthorizationContext,
    contract: ContractLike,
    *,
    responsible_employee_ids: set[uuid.UUID],
) -> bool: ...
```

Rules are exactly ALL/RELATED/ASSIGNED/OWN from the design.

- [ ] **Step 2: Add Pydantic schemas**

Use `Decimal` for money and `ConfigDict(from_attributes=True)` for ORM responses. `ContractResponse.amount` and item price serialize exactly without float conversion.

- [ ] **Step 3: Implement route 404 helpers**

One `_contract_or_404` helper obtains the contract and applies the exact permission context. Foreign/absent behavior must not diverge.

- [ ] **Step 4: Implement cross-resource subject authorization**

Load the actor’s active scope grants for `technical_devices.view` / `buildings.view` separately from `contracts.manage_items`, build permission-specific authorization contexts, and apply existing `can_access_technical_device` / `can_access_building`. Never reuse the Contracts context as an implicit subject-view grant.

- [ ] **Step 5: Include router in `app/main.py`**

- [ ] **Step 6: Run targeted API tests, full pytest, Ruff**

- [ ] **Step 7: Commit**

```text
feat(stage4 cp4.1): expose scoped contracts API
```

---

### Task 7: Regression hardening and documentation

**Files:**
- Modify tests only for any newly discovered missing regression case.
- Modify `docs/superpowers/specs/2026-08-11-stage4-cp41-contracts-core-design.md` only if verified implementation intentionally differs.
- Modify `PROJECT_STATUS.md` only to remove stale Stage 1 status and record verified CP4.1 state after tests pass.

- [ ] **Step 1: Run full CI on exact branch HEAD**

Required GitHub Actions steps:

```text
pip install -e ".[dev]" — PASS
ruff check app tests — PASS
alembic upgrade head — PASS
pytest — PASS
```

- [ ] **Step 2: Verify Alembic topology**

Single expected head: `0011_stage4_contracts_core`.

- [ ] **Step 3: Compare exact baseline to HEAD**

No unrelated frontend, workflow, Stage 3 behavior, Tasks, Expertise, Documents, or Addenda changes.

- [ ] **Step 4: Independent review**

Review authorization, transaction boundaries, FK/delete behavior, money precision, item minimum-subject invariant, and audit rollback behavior. Any blocker returns checkpoint to RE-VERIFICATION.

- [ ] **Step 5: Final documentation commit if required**

```text
docs(stage4 cp4.1): record verified contracts checkpoint
```

---

### Task 8: Publish review boundary without merge

- [ ] **Step 1: Open a draft PR**

Base: `codex/feat-gigastudio-frontend-integration`  
Head: `agent/stage4-cp41-contracts-core`

PR must state:
- exact baseline;
- exact verified HEAD;
- RED evidence commit/run;
- final CI run/result;
- migrations/head;
- targeted/full test counts;
- changed-file scope;
- explicit `DO NOT MERGE — user requested integration remains untouched` until user chooses otherwise.

- [ ] **Step 2: Do not enable auto-merge and do not call merge**

The task is complete when the branch is verified and the draft PR is ready for human review, with integration unchanged.

---

## Self-review

- Spec coverage: contract core, responsibles, items, subjects, amount, soft delete, authorization, audit, migration and API are mapped to tasks.
- Deferred requirements are explicitly lifecycle-dependent and are not hidden placeholders: status transitions, suspension/resume, termination, completion, addenda, Tasks/Expertises/Documents, frontend integration are separate future checkpoints.
- Type consistency: UUID for identities, `Decimal`/NUMERIC(14,2) for money, `ContractStatus` enum for status, `AuthorizationContext` for scoped access.
- No production code is scheduled before observable RED tests.
