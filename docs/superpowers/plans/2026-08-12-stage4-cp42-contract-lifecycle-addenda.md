# Stage 4 CP4.2 Contract Lifecycle and Addenda Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved CP4.2 contract lifecycle, suspension history, fail-closed completion readiness, post-signing immutability, and additional agreements without prematurely implementing Tasks, Expertises, Documents, or Notifications.

**Architecture:** Keep `app/modules/contracts` as the domain owner and preserve the existing CP4.1 CRUD/API contracts. Add focused lifecycle, commercial calculation, and readiness modules around the existing repository/service layer; persist suspensions and addenda in one Alembic migration. Cross-module completion checks use explicit fail-closed providers, while future work-start producers call an internal contracts command rather than a public manual endpoint.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x ORM, PostgreSQL, Alembic, Pydantic v2, pytest, existing identity authorization/audit infrastructure.

## Global Constraints

- Working branch: `agent/stage4-cp42-contract-lifecycle-addenda`, based on CP4.1 checkpoint `fa11c71726cea0fb92ed6f1df777456ab0ab830c`.
- Do not merge, rebase, or fast-forward `codex/feat-gigastudio-frontend-integration` during this checkpoint.
- New Alembic revision must be the single child of `0011_stage4_contracts_core` and leave exactly one migration head.
- `contracts.change_status` controls ordinary transitions; `contracts.terminate` controls termination; `contracts.complete` controls completion; `contracts.manage_addenda` controls addendum mutations.
- `signed -> in_progress` is internal `mark_work_started()` only; no CP4.2 public manual endpoint may expose this transition.
- Completion is manual and fail-closed. Missing Tasks/Expertises/Documents/conclusion-delivery providers are blockers, never success.
- Signed contract items and legally significant base terms are immutable; price/deadline changes after signing happen only through signed addenda.
- At most one open `contract_suspensions` row may exist per contract; enforce in service logic and PostgreSQL.
- Signed/cancelled addenda are immutable. Signed addenda cannot be retroactively cancelled or deleted.
- Effective amount is `active item total + active signed addendum deltas`; resulting amount must never be negative.
- `original_end_date` is initialized once on signing and never changes; `end_date` is the current effective deadline.
- Rejected business commands must rollback completely, create no success audit event, and not increment versions merely because an invalid command was attempted.
- Preserve existing 404 anti-enumeration behavior for foreign, inaccessible, deleted, or nested out-of-scope resources.
- Do not add Tasks, Expertises, Documents, Notifications, generic workflow engine, generic event sourcing, or frontend work in CP4.2.

---

## Planned File Structure

**Create:**
- `alembic/versions/0012_stage4_contract_lifecycle_addenda.py` — schema changes, addendum enum, suspension/addenda tables, open-suspension partial unique index.
- `app/modules/contracts/commercial.py` — one authoritative effective-amount calculation/recalculation path shared by item CRUD and addendum signing.
- `app/modules/contracts/lifecycle.py` — ordinary transition map plus `ContractLifecycleService` for signing, work-start, suspension/resume, termination, readiness, and completion.
- `app/modules/contracts/readiness.py` — readiness result types, provider Protocol, explicit unavailable providers, and registry/aggregation helpers.
- `app/modules/contracts/addenda.py` — `ContractAddendumService` for addendum CRUD/lifecycle and atomic signed effects.
- `tests/integration/test_stage4_cp42_migration.py` — migration/table/index/enum assertions.
- `tests/integration/test_contract_lifecycle.py` — service-level signing, transition, immutability, suspension, termination tests.
- `tests/integration/test_contract_addenda.py` — service-level addendum lifecycle/effects/rollback/idempotency tests.
- `tests/integration/test_contract_completion.py` — readiness aggregation/fail-closed/manual completion tests.
- `tests/integration/test_contract_lifecycle_api.py` — API commands, dedicated permissions, anti-enumeration, status PATCH rejection.

**Modify:**
- `app/modules/contracts/enums.py` — add `ContractAddendumStatus`.
- `app/modules/contracts/models.py` — add `original_end_date`, `ContractSuspension`, `ContractAddendum`.
- `app/modules/contracts/repository.py` — add locking/query/count helpers for lifecycle/addenda/readiness.
- `app/modules/contracts/service.py` — keep CP4.1 CRUD signatures; add lifecycle guards and use shared commercial recalculation.
- `app/modules/contracts/schemas.py` — add lifecycle/readiness/addendum request/response schemas and `original_end_date` to contract response.
- `app/modules/contracts/routes.py` — command routes and nested addenda routes using existing scope checks.
- `tests/integration/test_contracts_core.py` — preserve CP4.1 regression coverage and adapt only assertions affected by `original_end_date`/shared amount helper.
- `PROJECT_STATUS.md` — mark CP4.2 complete only after full verification.
- `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, `docs/PERMISSIONS.md` — resolve CP4.2 implementation details to match the approved spec where current wording conflicts.

---

### Task 1: Persist CP4.2 lifecycle and addenda data model

**Files:**
- Create: `alembic/versions/0012_stage4_contract_lifecycle_addenda.py`
- Modify: `app/modules/contracts/enums.py`
- Modify: `app/modules/contracts/models.py`
- Create: `tests/integration/test_stage4_cp42_migration.py`

**Interfaces:**
- Produces: `ContractAddendumStatus`, `Contract.original_end_date`, `ContractSuspension`, `ContractAddendum`.
- Produces DB enum `contract_addendum_status`, tables `contract_suspensions`, `contract_addenda`, and unique partial index `uq_contract_suspensions_one_open`.
- Consumed by Tasks 3–7.

- [ ] **Step 1: Write failing migration/model tests**

Create `tests/integration/test_stage4_cp42_migration.py` with concrete checks:

```python
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus
from app.modules.contracts.models import Contract, ContractAddendum, ContractSuspension


def test_cp42_models_expose_expected_fields() -> None:
    assert hasattr(Contract, "original_end_date")
    assert ContractSuspension.__tablename__ == "contract_suspensions"
    assert ContractAddendum.__tablename__ == "contract_addenda"
    assert [status.value for status in ContractAddendumStatus] == [
        "draft", "approval", "signed", "cancelled"
    ]


def test_cp42_database_objects_exist(db_session: Session) -> None:
    inspector = sa.inspect(db_session.get_bind())
    assert "contract_suspensions" in inspector.get_table_names()
    assert "contract_addenda" in inspector.get_table_names()
    suspension_indexes = {row["name"] for row in inspector.get_indexes("contract_suspensions")}
    assert "uq_contract_suspensions_one_open" in suspension_indexes
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest -q tests/integration/test_stage4_cp42_migration.py
```

Expected: collection/import or assertion failure because CP4.2 enum/models/migration do not exist yet.

- [ ] **Step 3: Add enum and ORM models**

In `app/modules/contracts/enums.py` add:

```python
class ContractAddendumStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVAL = "approval"
    SIGNED = "signed"
    CANCELLED = "cancelled"
```

In `app/modules/contracts/models.py` add `original_end_date: Mapped[date | None]` to `Contract` and implement the two approved models with UUID PKs, timestamps, actor FKs, soft delete/version on addenda, and `Enum(ContractAddendumStatus, name="contract_addendum_status", values_callable=enum_values)`.

- [ ] **Step 4: Add Alembic revision `0012_stage4_contract_lifecycle_addenda`**

The migration must have:

```python
revision = "0012_stage4_contract_lifecycle_addenda"
down_revision = "0011_stage4_contracts_core"
```

Create `contract_addendum_status`, add `contracts.original_end_date`, create both tables, and create:

```python
op.create_index(
    "uq_contract_suspensions_one_open",
    "contract_suspensions",
    ["contract_id"],
    unique=True,
    postgresql_where=sa.text("ended_at IS NULL"),
)
```

Backfill `original_end_date = end_date` only for rows already in `signed`, `in_progress`, `suspended`, `completed`, `terminated`, or `archived`; draft/approval rows remain null.

- [ ] **Step 5: Verify migration/model GREEN**

Run:

```powershell
python -m pytest -q tests/integration/test_stage4_cp42_migration.py tests/integration/test_migration.py
alembic heads
alembic upgrade head
```

Expected: tests PASS and exactly one head: `0012_stage4_contract_lifecycle_addenda`.

- [ ] **Step 6: Commit the data-model slice**

```powershell
git add alembic/versions/0012_stage4_contract_lifecycle_addenda.py app/modules/contracts/enums.py app/modules/contracts/models.py tests/integration/test_stage4_cp42_migration.py
git commit -m "feat: add contract lifecycle and addenda data model"
```

---

### Task 2: Centralize effective contract amount and post-signing CRUD guards

**Files:**
- Create: `app/modules/contracts/commercial.py`
- Modify: `app/modules/contracts/service.py`
- Modify: `app/modules/contracts/repository.py`
- Modify: `tests/integration/test_contracts_core.py`
- Create: `tests/integration/test_contract_lifecycle.py`

**Interfaces:**
- Produces: `calculate_effective_amount(db: Session, contract_id: UUID, *, pending_delta: Decimal = Decimal("0.00")) -> Decimal`.
- Produces: `recalculate_effective_amount(db: Session, contract: Contract) -> Decimal`.
- Produces repository helpers `count_active_contract_items()` and `count_contract_responsibles()`.
- Existing `ContractService.create_contract/update_contract/delete_contract/restore_contract/replace_responsibles/create_item/update_item/delete_item` signatures remain unchanged.

- [ ] **Step 1: Add RED tests for lifecycle guards and shared amount calculation**

Add service tests proving:

```python
contract.status = ContractStatus.SIGNED
with pytest.raises(ContractValidationError, match="подписан"):
    service.create_item(...)
with pytest.raises(ContractValidationError, match="подписан"):
    service.update_item(...)
with pytest.raises(ContractValidationError, match="подписан"):
    service.delete_item(...)
with pytest.raises(ContractValidationError, match="нельзя удалить"):
    service.delete_contract(db_session, actor_id=actor_id, contract=contract)
```

Also prove `replace_responsibles()` succeeds for `SIGNED/IN_PROGRESS/SUSPENDED` and fails for `COMPLETED/TERMINATED/ARCHIVED`.

- [ ] **Step 2: Run focused RED tests**

```powershell
python -m pytest -q tests/integration/test_contracts_core.py tests/integration/test_contract_lifecycle.py
```

Expected: new lifecycle assertions fail because CP4.1 only checks soft deletion.

- [ ] **Step 3: Implement `commercial.py`**

Use one query path:

```python
def calculate_effective_amount(
    db: Session,
    contract_id: uuid.UUID,
    *,
    pending_delta: Decimal = Decimal("0.00"),
) -> Decimal:
    item_total = db.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(ContractItem.price), Decimal("0.00"))).where(
            ContractItem.contract_id == contract_id,
            ContractItem.deleted_at.is_(None),
        )
    )
    signed_delta_total = db.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(ContractAddendum.amount_delta), Decimal("0.00"))).where(
            ContractAddendum.contract_id == contract_id,
            ContractAddendum.deleted_at.is_(None),
            ContractAddendum.status == ContractAddendumStatus.SIGNED,
        )
    )
    return (Decimal(item_total or 0) + Decimal(signed_delta_total or 0) + pending_delta).quantize(MONEY_QUANTUM)


def recalculate_effective_amount(db: Session, contract: Contract) -> Decimal:
    amount = calculate_effective_amount(db, contract.id)
    contract.amount = amount
    db.flush()
    return amount
```

- [ ] **Step 4: Apply exact lifecycle guards to CP4.1 mutations**

Rules:
- full contract term edits only in `draft` or `approval`;
- in `signed/in_progress/suspended`, `update_contract()` may change only `comment`; routes will pass existing legal fields unchanged and service will reject any actual legal-field difference;
- item create/update/delete only in `draft` or `approval`;
- contract soft-delete only in `draft` or `approval`;
- responsibles mutable through `signed/in_progress/suspended`, frozen in terminal statuses.

Replace the private CP4.1 amount summation with `recalculate_effective_amount()`.

- [ ] **Step 5: Add repository count helpers used by signing**

```python
def count_active_contract_items(db: Session, contract_id: uuid.UUID) -> int: ...
def count_contract_responsibles(db: Session, contract_id: uuid.UUID) -> int: ...
```

Both use `SELECT count(*)` and no side effects.

- [ ] **Step 6: Verify GREEN and CP4.1 regression**

```powershell
python -m pytest -q tests/integration/test_contracts_core.py tests/integration/test_contracts_api_mutations.py tests/integration/test_contract_lifecycle.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/modules/contracts/commercial.py app/modules/contracts/service.py app/modules/contracts/repository.py tests/integration/test_contracts_core.py tests/integration/test_contract_lifecycle.py
git commit -m "feat: enforce signed contract immutability"
```

---

### Task 3: Implement signing and the primary contract state machine

**Files:**
- Create: `app/modules/contracts/lifecycle.py`
- Modify: `app/modules/contracts/repository.py`
- Modify: `tests/integration/test_contract_lifecycle.py`

**Interfaces:**
- Produces `ContractLifecycleService.change_status(db, *, actor_id, contract, target_status) -> Contract`.
- Produces `ContractLifecycleService.mark_work_started(db, *, actor_id, contract) -> Contract`.
- Ordinary public transition set is exactly `draft->approval`, `approval->signed`, `completed->archived`, `terminated->archived`.

- [ ] **Step 1: Write RED tests for signing prerequisites and transition matrix**

Tests must cover:

```python
@pytest.mark.parametrize(
    ("source", "target"),
    [
        (ContractStatus.DRAFT, ContractStatus.APPROVAL),
        (ContractStatus.APPROVAL, ContractStatus.SIGNED),
        (ContractStatus.COMPLETED, ContractStatus.ARCHIVED),
        (ContractStatus.TERMINATED, ContractStatus.ARCHIVED),
    ],
)
def test_allowed_ordinary_transitions(...): ...
```

And reject examples `draft->signed`, `approval->in_progress`, `signed->in_progress` through `change_status`, `archived->draft`.

Signing tests must independently reject missing `start_date`, missing `end_date`, zero active items, and zero responsibles with no audit/status/version mutation. A valid signing must set `original_end_date == end_date` exactly once.

- [ ] **Step 2: Run RED tests**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py -k "transition or signing or work_started"
```

Expected: FAIL because lifecycle service does not exist.

- [ ] **Step 3: Implement transition constants and service**

In `lifecycle.py`:

```python
ORDINARY_TRANSITIONS = {
    ContractStatus.DRAFT: {ContractStatus.APPROVAL},
    ContractStatus.APPROVAL: {ContractStatus.SIGNED},
    ContractStatus.COMPLETED: {ContractStatus.ARCHIVED},
    ContractStatus.TERMINATED: {ContractStatus.ARCHIVED},
}

class ContractLifecycleService:
    def change_status(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
        target_status: ContractStatus,
    ) -> Contract: ...

    def mark_work_started(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        contract: Contract,
    ) -> Contract: ...
```

For `approval->signed`, check start/end dates, active items, responsibles, current effective amount, then set `original_end_date` only when null. Audit accepted transitions with `contract.status_changed`; audit internal start with `contract.work_started`.

- [ ] **Step 4: Make transaction semantics explicit**

Every lifecycle command follows:

```python
try:
    # validate first
    # mutate
    db.flush()
    write_audit(...)
    db.commit()
    db.refresh(contract)
except Exception:
    db.rollback()
    raise
```

Validation failures occur before persistent mutation wherever possible.

- [ ] **Step 5: Verify GREEN**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py -k "transition or signing or work_started"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/modules/contracts/lifecycle.py app/modules/contracts/repository.py tests/integration/test_contract_lifecycle.py
git commit -m "feat: add contract lifecycle state machine"
```

---

### Task 4: Implement suspension, resume, and termination atomically

**Files:**
- Modify: `app/modules/contracts/lifecycle.py`
- Modify: `app/modules/contracts/repository.py`
- Modify: `tests/integration/test_contract_lifecycle.py`

**Interfaces:**
- Produces `suspend(db, *, actor_id, contract, reason) -> ContractSuspension`.
- Produces `resume(db, *, actor_id, contract) -> ContractSuspension` returning the now-closed row.
- Produces `terminate(db, *, actor_id, contract, reason) -> Contract`.
- Repository helpers: `get_open_contract_suspension()` and `list_contract_suspensions()`.

- [ ] **Step 1: Add RED tests**

Cover:
- suspend only from `in_progress`;
- mandatory non-blank reason;
- exactly one open suspension;
- resume only from `suspended` and requires an open row;
- resume closes `ended_at` and status becomes `in_progress`;
- termination only from `signed/in_progress/suspended`;
- termination reason mandatory;
- termination from suspended closes the open suspension;
- invalid duplicate/transition attempts preserve status, rows, versions, and audit counts.

- [ ] **Step 2: Run RED tests**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py -k "suspend or resume or terminate"
```

Expected: FAIL because commands are absent.

- [ ] **Step 3: Implement repository helpers**

```python
def get_open_contract_suspension(db: Session, contract_id: uuid.UUID) -> ContractSuspension | None: ...
def list_contract_suspensions(db: Session, contract_id: uuid.UUID) -> list[ContractSuspension]: ...
```

Order history by `started_at`, then `id`.

- [ ] **Step 4: Implement lifecycle commands**

Use `datetime.now(UTC)`. Audit actions:
- `contract.suspended`;
- `contract.resumed`;
- `contract.terminated`.

Persist the reason in the audit summary/metadata convention already supported by `write_audit`; do not add a generic contract reason column.

- [ ] **Step 5: Prove the DB invariant independently**

Add a test that manually attempts to flush a second open `ContractSuspension` and expects `sqlalchemy.exc.IntegrityError`; rollback afterwards. This confirms the partial unique index is not only service-level logic.

- [ ] **Step 6: Verify GREEN**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/modules/contracts/lifecycle.py app/modules/contracts/repository.py tests/integration/test_contract_lifecycle.py
git commit -m "feat: add contract suspension and termination lifecycle"
```

---

### Task 5: Add fail-closed completion readiness and manual completion

**Files:**
- Create: `app/modules/contracts/readiness.py`
- Modify: `app/modules/contracts/lifecycle.py`
- Create: `tests/integration/test_contract_completion.py`

**Interfaces:**
- Produces immutable result types `CompletionCheck`, `CompletionBlocker`, `CompletionReadiness`.
- Produces `CompletionReadinessProvider` Protocol with `key: str` and `check(db, contract) -> CompletionCheck`.
- Produces `default_readiness_providers() -> dict[str, CompletionReadinessProvider]` with four unavailable providers.
- `ContractLifecycleService(...providers...)` accepts an injectable registry for deterministic tests.
- Produces `get_completion_readiness()` and `complete()`.

- [ ] **Step 1: Write RED readiness tests**

Define a satisfied test provider:

```python
class SatisfiedProvider:
    def __init__(self, key: str) -> None:
        self.key = key

    def check(self, db: Session, contract: Contract) -> CompletionCheck:
        return CompletionCheck(key=self.key, passed=True, blockers=[])
```

Test default blockers are exactly:
- `tasks_provider_unavailable`;
- `expertises_provider_unavailable`;
- `documents_provider_unavailable`;
- `conclusion_delivery_provider_unavailable`.

Test all-satisfied injected providers produce `ready_to_complete=True`.

- [ ] **Step 2: Run RED tests**

```powershell
python -m pytest -q tests/integration/test_contract_completion.py
```

Expected: FAIL because readiness types/services do not exist.

- [ ] **Step 3: Implement `readiness.py`**

Use frozen dataclasses or equivalent explicit types:

```python
@dataclass(frozen=True)
class CompletionBlocker:
    code: str
    detail: str

@dataclass(frozen=True)
class CompletionCheck:
    key: str
    passed: bool
    blockers: tuple[CompletionBlocker, ...]

@dataclass(frozen=True)
class CompletionReadiness:
    ready_to_complete: bool
    checks: tuple[CompletionCheck, ...]
    blockers: tuple[CompletionBlocker, ...]
```

Required provider keys are exactly `tasks`, `expertises`, `documents`, `conclusion_delivery`.

- [ ] **Step 4: Implement lifecycle aggregation and completion**

`get_completion_readiness()` aggregates all four required checks on every call. `complete()`:
- requires contract status `in_progress` at domain level;
- recalculates readiness inside the command;
- raises `ContractValidationError` if any blocker exists;
- sets status `completed`, increments version, audits `contract.completed`, commits atomically.

- [ ] **Step 5: Test fail-closed completion and successful injected completion**

Add assertions that default CP4.2 completion is rejected with no audit/status mutation, while four satisfied injected providers allow `in_progress -> completed`.

- [ ] **Step 6: Verify GREEN**

```powershell
python -m pytest -q tests/integration/test_contract_completion.py tests/integration/test_contract_lifecycle.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/modules/contracts/readiness.py app/modules/contracts/lifecycle.py tests/integration/test_contract_completion.py
git commit -m "feat: add fail-closed contract completion readiness"
```

---

### Task 6: Implement additional agreements and atomic commercial effects

**Files:**
- Create: `app/modules/contracts/addenda.py`
- Modify: `app/modules/contracts/repository.py`
- Modify: `app/modules/contracts/commercial.py`
- Create: `tests/integration/test_contract_addenda.py`

**Interfaces:**
- Produces `ContractAddendumService.create_addendum(...) -> ContractAddendum`.
- Produces `update_addendum(...) -> ContractAddendum`, `delete_addendum(...) -> None`, `change_status(...) -> ContractAddendum`.
- Repository helpers `get_contract_addendum()`, `list_contract_addenda()`.
- Addendum signing calls shared `calculate_effective_amount(..., pending_delta=...)` before mutation and `recalculate_effective_amount()` after status becomes signed.

- [ ] **Step 1: Write RED CRUD/lifecycle tests**

Cover:
- create only when parent is `signed/in_progress/suspended`;
- default addendum currency copies parent contract currency;
- edit/delete only `draft/approval` with allowed parent status;
- `draft->approval`, `approval->signed`, `draft|approval->cancelled` only;
- signed/cancelled immutable;
- cannot sign after parent becomes terminal;
- addendum with neither non-zero delta nor `new_end_date` cannot sign.

- [ ] **Step 2: Write RED commercial-effect tests**

Concrete scenario:

```python
# signed base items = 100_000.00
# addendum A: +25_000.00, no date change
# addendum B: -10_000.00, new_end_date=2026-12-31
assert contract.amount == Decimal("115000.00")
assert contract.original_end_date == date(2026, 9, 30)
assert contract.end_date == date(2026, 12, 31)
```

Also test:
- negative projected amount is rejected atomically;
- currency mismatch rejected;
- extending current end date requires non-blank description;
- shortening deadline does not require an extension reason;
- signing retry cannot double-apply delta;
- signed chain is ordered by `signed_at`, then UUID for reconstruction.

- [ ] **Step 3: Run RED tests**

```powershell
python -m pytest -q tests/integration/test_contract_addenda.py
```

Expected: FAIL because service/repository helpers do not exist.

- [ ] **Step 4: Implement repository helpers**

```python
def get_contract_addendum(
    db: Session,
    contract_id: uuid.UUID,
    addendum_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> ContractAddendum | None: ...


def list_contract_addenda(db: Session, contract_id: uuid.UUID) -> list[ContractAddendum]: ...
```

Nested lookup must always include `contract_id` in the predicate.

- [ ] **Step 5: Implement `ContractAddendumService`**

Creation signature:

```python
def create_addendum(
    self,
    db: Session,
    *,
    actor_id: uuid.UUID,
    contract: Contract,
    number: str,
    addendum_date: date,
    amount_delta: Decimal | None,
    new_end_date: date | None,
    description: str | None,
) -> ContractAddendum: ...
```

Normalize money to two decimals; allow positive/negative delta; treat `0.00` as no financial effect. On signing, validate projected amount with `pending_delta`, then atomically set `signed_at`, status, effective end date, recalculated amount, versions, and audit.

Audit actions:
- `contract_addendum.created`;
- `contract_addendum.updated`;
- `contract_addendum.deleted`;
- `contract_addendum.status_changed` for approval;
- `contract_addendum.signed`;
- `contract_addendum.cancelled`.

- [ ] **Step 6: Verify GREEN and CP4.1 amount regression**

```powershell
python -m pytest -q tests/integration/test_contract_addenda.py tests/integration/test_contracts_core.py
```

Expected: PASS; contracts without signed addenda still equal the active item sum.

- [ ] **Step 7: Commit**

```powershell
git add app/modules/contracts/addenda.py app/modules/contracts/repository.py app/modules/contracts/commercial.py tests/integration/test_contract_addenda.py
git commit -m "feat: add contract additional agreements"
```

---

### Task 7: Expose lifecycle, readiness, and addenda through permission-safe API commands

**Files:**
- Modify: `app/modules/contracts/schemas.py`
- Modify: `app/modules/contracts/routes.py`
- Create: `tests/integration/test_contract_lifecycle_api.py`

**Interfaces:**
- Public lifecycle commands use dedicated endpoints; `status` is never writable through ordinary `PATCH /api/contracts/{id}`.
- `GET completion-readiness` requires `contracts.view` in scope.
- `POST complete` requires `contracts.complete`.
- `POST terminate` requires `contracts.terminate`.
- Ordinary `/status`, `/suspend`, `/resume` require `contracts.change_status`.
- Addenda GET uses `contracts.view`; addenda mutations use `contracts.manage_addenda`.

- [ ] **Step 1: Add request/response schemas**

In `schemas.py` add explicit models:

```python
class ContractStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ContractStatus

class ContractReasonCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1)

class ContractAddendumCreate(BaseModel): ...
class ContractAddendumUpdate(BaseModel): ...
class ContractAddendumStatusChange(BaseModel): ...
class ContractAddendumResponse(BaseModel): ...
class CompletionBlockerResponse(BaseModel): ...
class CompletionCheckResponse(BaseModel): ...
class ContractCompletionReadinessResponse(BaseModel): ...
```

Add `original_end_date: date | None` to `ContractResponse`. Do not add `status` to `ContractUpdate` or `ContractAddendumUpdate`.

- [ ] **Step 2: Write RED API tests before routes**

Test route presence and permission isolation:
- a user with only `contracts.change_status` cannot terminate or complete;
- a user with only `contracts.terminate` cannot call ordinary `/status`;
- a user with only `contracts.complete` cannot call `/terminate`;
- a user with `contracts.manage_addenda` but no access scope to the parent receives the same 404 as a foreign ID;
- `PATCH /api/contracts/{id}` with `{"status": "signed"}` is rejected by Pydantic extra-forbid;
- no endpoint permits manual `signed -> in_progress`.

- [ ] **Step 3: Run RED API tests**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle_api.py
```

Expected: route/schema failures.

- [ ] **Step 4: Add contract command routes**

Implement exactly:

```text
POST /api/contracts/{id}/status
POST /api/contracts/{id}/suspend
POST /api/contracts/{id}/resume
POST /api/contracts/{id}/terminate
GET  /api/contracts/{id}/completion-readiness
POST /api/contracts/{id}/complete
```

Reuse `_contract_or_404()` with the command-specific `AuthorizationContext` returned by `require_scoped_permission(...)`.

- [ ] **Step 5: Add nested addenda routes**

Implement:

```text
GET    /api/contracts/{id}/addenda
POST   /api/contracts/{id}/addenda
GET    /api/contracts/{id}/addenda/{addendum_id}
PATCH  /api/contracts/{id}/addenda/{addendum_id}
DELETE /api/contracts/{id}/addenda/{addendum_id}
POST   /api/contracts/{id}/addenda/{addendum_id}/status
```

Use nested lookup `(contract_id, addendum_id)` and the same contract-level 404 anti-enumeration rule.

- [ ] **Step 6: Map domain validation consistently**

All `ContractValidationError` failures become existing `422 Unprocessable Entity` through `_unprocessable(str(exc))`. Missing/out-of-scope resources stay 404. Permission dependency behavior stays unchanged.

- [ ] **Step 7: Verify GREEN**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle_api.py tests/integration/test_contracts_api.py tests/integration/test_contracts_api_mutations.py tests/integration/test_contracts_api_queries.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add app/modules/contracts/schemas.py app/modules/contracts/routes.py tests/integration/test_contract_lifecycle_api.py
git commit -m "feat: expose contract lifecycle and addenda API"
```

---

### Task 8: Close rollback, audit, migration, and authorization edge cases

**Files:**
- Modify: `tests/integration/test_contract_lifecycle.py`
- Modify: `tests/integration/test_contract_addenda.py`
- Modify: `tests/integration/test_contract_completion.py`
- Modify: `tests/integration/test_contract_lifecycle_api.py`
- Modify production files only when a failing test proves a gap.

**Interfaces:**
- No new public API is introduced in this task.
- Produces proof that CP4.2 satisfies atomicity and exact permission isolation rather than only happy-path behavior.

- [ ] **Step 1: Add explicit audit-count helpers and rejected-command assertions**

For every command family, capture audit count before rejection and assert it remains unchanged afterward:

```python
before = _audit_count(db_session, "contract.suspended")
with pytest.raises(ContractValidationError):
    lifecycle.suspend(..., reason="   ")
assert _audit_count(db_session, "contract.suspended") == before
```

Repeat for invalid status, resume, terminate, complete, addendum signing, and post-sign item mutation.

- [ ] **Step 2: Add version/state rollback assertions**

After each rejected command call `db_session.refresh(entity)` and assert status/version/amount/end_date/signed_at/deleted_at are unchanged.

- [ ] **Step 3: Add migration downgrade/upgrade smoke coverage**

Use the existing migration-test pattern to prove `0012 -> 0011 -> 0012` works on the test database and leaves enum/table/index state correct. Do not downgrade below CP4.1 in this test.

- [ ] **Step 4: Add exact RBAC scope cases**

Cover ALL/RELATED/ASSIGNED/OWN for at least one lifecycle mutation and one addendum mutation, reusing existing authorization fixture patterns. Verify permission-name isolation separately from scope matching.

- [ ] **Step 5: Run all Stage 4 focused tests**

```powershell
python -m pytest -q tests/integration/test_contracts_core.py tests/integration/test_contracts_api.py tests/integration/test_contracts_api_mutations.py tests/integration/test_contracts_api_queries.py tests/integration/test_contract_lifecycle.py tests/integration/test_contract_addenda.py tests/integration/test_contract_completion.py tests/integration/test_contract_lifecycle_api.py tests/integration/test_stage4_cp42_migration.py
```

Expected: PASS.

- [ ] **Step 6: Commit any edge-case fixes and tests**

```powershell
git add app/modules/contracts tests/integration
git commit -m "test: close CP4.2 lifecycle edge cases"
```

If Step 5 required no production changes, commit only the new/strengthened tests.

---

### Task 9: Reconcile docs, run full verification, and prepare review checkpoint

**Files:**
- Modify: `PROJECT_STATUS.md`
- Modify: `docs/BUSINESS_RULES.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/PERMISSIONS.md`
- Keep: `docs/superpowers/specs/2026-08-12-stage4-cp42-contract-lifecycle-addenda-design.md`
- Keep: `docs/superpowers/plans/2026-08-12-stage4-cp42-contract-lifecycle-addenda.md`

**Interfaces:**
- Produces a documented, reviewable CP4.2 checkpoint; no integration merge.

- [ ] **Step 1: Update authoritative docs to the approved permission/lifecycle semantics**

Make these exact reconciliations:
- completion uses `contracts.complete`, not `contracts.change_status`;
- termination uses `contracts.terminate`;
- Tasks/Expertises/Documents side effects are explicitly deferred to owning stages;
- `original_end_date`, `contract_suspensions`, `contract_addenda`, addendum terminal statuses, and fail-closed readiness are reflected in the data/business rules;
- addendum document FK remains deferred to Stage 8.

- [ ] **Step 2: Update `PROJECT_STATUS.md` only after tests are green**

Record:
- CP4.2 branch and final implementation commit;
- migration head `0012_stage4_contract_lifecycle_addenda`;
- implemented lifecycle/addenda/readiness scope;
- deferred Stage 5/6/8 integrations;
- final test count from the actual verification run.

- [ ] **Step 3: Run static and migration verification**

```powershell
python -m ruff check .
alembic heads
alembic upgrade head
```

Expected: Ruff PASS; exactly one Alembic head `0012_stage4_contract_lifecycle_addenda`; upgrade succeeds.

- [ ] **Step 4: Run the complete test suite**

```powershell
python -m pytest -q
```

Expected: all tests PASS. Record the exact pass/warning counts; do not predict or hard-code them before the run.

- [ ] **Step 5: Verify stacked ancestry and integration isolation**

```powershell
git merge-base --is-ancestor fa11c71726cea0fb92ed6f1df777456ab0ab830c HEAD
git log --oneline --decorate fa11c71726cea0fb92ed6f1df777456ab0ab830c..HEAD
```

Expected: first command exits 0. Compare the integration branch separately; do not merge it.

- [ ] **Step 6: Commit documentation/status update**

```powershell
git add PROJECT_STATUS.md docs/BUSINESS_RULES.md docs/DATA_MODEL.md docs/PERMISSIONS.md
git commit -m "docs: record CP4.2 contract lifecycle checkpoint"
```

- [ ] **Step 7: Push the stacked branch and create/update a draft review PR**

The review PR should target `agent/stage4-cp41-contracts-core` so the CP4.2 diff is isolated from CP4.1. Its body must state:
- CP4.2 depends on CP4.1;
- exact final commit and migration head;
- exact test/CI results;
- Tasks/Expertises/Documents integrations remain deferred;
- **DO NOT MERGE into integration automatically**.

- [ ] **Step 8: Verify CI on the exact final HEAD**

Check Ruff, Alembic, and pytest jobs. If any job fails, use systematic debugging, add a reproducing test when applicable, fix on the CP4.2 branch, rerun full verification, and update the review checkpoint with the new exact HEAD.

---

## Final Acceptance Checklist

Before CP4.2 is declared complete, all of the following must be true:

- [ ] `0012_stage4_contract_lifecycle_addenda` is the only Alembic head.
- [ ] Contract signing requires start date, end date, at least one active item, and at least one responsible.
- [ ] `original_end_date` is captured once and remains immutable.
- [ ] Public ordinary transitions match the approved state machine exactly.
- [ ] No public endpoint exposes manual `signed -> in_progress`.
- [ ] Signed legal terms/items are immutable; responsibles remain editable only until terminal status; comment is editable until archive.
- [ ] Contract deletion is limited to draft/approval.
- [ ] Suspension has a mandatory reason and exactly one open row maximum.
- [ ] Resume closes the authoritative suspension interval.
- [ ] Termination requires `contracts.terminate` and closes an open suspension.
- [ ] Default completion readiness fails closed with four explicit unavailable-provider blockers.
- [ ] Completion requires `contracts.complete` and fresh server-side readiness.
- [ ] Addenda can exist only for signed/in-progress/suspended parents.
- [ ] Signed/cancelled addenda are immutable and signed addenda cannot be cancelled retroactively.
- [ ] Addendum signing is atomic and idempotent with respect to amount/deadline effects.
- [ ] Effective amount equals active item total plus active signed addendum deltas and never becomes negative.
- [ ] Deadline extensions require a non-blank business reason.
- [ ] Wrong dedicated permission never grants another command.
- [ ] Foreign/out-of-scope nested resources preserve anti-enumeration 404 behavior.
- [ ] Rejected commands create no success audit event and leave persisted state/version unchanged.
- [ ] CP4.1 contract tests remain green.
- [ ] Full `python -m pytest -q`, Ruff, and Alembic verification are green on the exact final HEAD.
- [ ] Integration branch remains untouched and review PR remains draft until explicit user approval.
