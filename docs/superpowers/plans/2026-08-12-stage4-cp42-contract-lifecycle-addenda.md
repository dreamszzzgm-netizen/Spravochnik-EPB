# Stage 4 CP4.2 Contract Lifecycle and Addenda Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved CP4.2 contract lifecycle, suspension history, fail-closed completion readiness, post-signing immutability, and additional agreements without prematurely implementing Tasks, Expertises, Documents, or Notifications.

**Architecture:** Keep `app/modules/contracts` as the domain owner and preserve the existing CP4.1 CRUD/API contracts. Add focused lifecycle, commercial-calculation, readiness, and addenda services around the existing repository/service layer; persist suspensions and addenda in one Alembic migration. Future Tasks/Expertises/Documents integrations connect through the approved internal work-start command and readiness provider boundary instead of direct imports into Contracts.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x ORM, PostgreSQL, Alembic, Pydantic v2, pytest, existing identity authorization/audit infrastructure.

## Global Constraints

- Working branch: `agent/stage4-cp42-contract-lifecycle-addenda`, based on CP4.1 checkpoint `fa11c71726cea0fb92ed6f1df777456ab0ab830c`.
- Do not merge, rebase, or fast-forward `codex/feat-gigastudio-frontend-integration` during this checkpoint.
- New Alembic revision is the single child of `0011_stage4_contracts_core` and must leave exactly one migration head.
- `contracts.change_status` controls ordinary transitions; `contracts.terminate` controls termination; `contracts.complete` controls completion; `contracts.manage_addenda` controls addendum mutations.
- `signed -> in_progress` is internal `mark_work_started()` only; no public CP4.2 endpoint exposes that transition.
- Completion is manual and fail-closed. Missing Tasks/Expertises/Documents/conclusion-delivery providers are blockers, never success.
- Signed contract items and legally significant base terms are immutable; price/deadline changes after signing happen only through signed addenda.
- At most one open `contract_suspensions` row may exist per contract; enforce in service logic and PostgreSQL.
- Signed/cancelled addenda are immutable. Signed addenda cannot be retroactively cancelled or deleted.
- Effective amount is `active item total + active signed addendum deltas`; the result must never be negative.
- `original_end_date` is initialized once on signing and never changes; `end_date` is the current effective deadline.
- Rejected commands rollback completely, create no success audit event, and do not increment versions merely because validation was attempted.
- Preserve existing 404 anti-enumeration behavior for foreign, inaccessible, deleted, or nested out-of-scope resources.
- Do not add Tasks, Expertises, Documents, Notifications, a generic workflow engine, generic event sourcing, or frontend work in CP4.2.

---

## Planned File Structure

**Create:**
- `alembic/versions/0012_stage4_contract_lifecycle_addenda.py` — schema changes, addendum enum, suspension/addenda tables, partial unique index.
- `app/modules/contracts/commercial.py` — authoritative effective-amount calculation/recalculation.
- `app/modules/contracts/lifecycle.py` — transition map and lifecycle commands.
- `app/modules/contracts/readiness.py` — readiness result types, provider Protocol, unavailable providers, aggregation.
- `app/modules/contracts/addenda.py` — addendum CRUD/lifecycle and signed commercial effects.
- `tests/integration/test_stage4_cp42_migration.py` — migration/table/index/enum checks.
- `tests/integration/test_contract_lifecycle.py` — lifecycle, immutability, suspension, termination service tests.
- `tests/integration/test_contract_addenda.py` — addendum lifecycle/effects/rollback/idempotency tests.
- `tests/integration/test_contract_completion.py` — fail-closed readiness/manual completion tests.
- `tests/integration/test_contract_lifecycle_api.py` — API, dedicated permissions, anti-enumeration tests.

**Modify:**
- `app/modules/contracts/enums.py`
- `app/modules/contracts/models.py`
- `app/modules/contracts/repository.py`
- `app/modules/contracts/service.py`
- `app/modules/contracts/schemas.py`
- `app/modules/contracts/routes.py`
- `tests/integration/test_contracts_core.py`
- `PROJECT_STATUS.md`
- `docs/BUSINESS_RULES.md`
- `docs/DATA_MODEL.md`
- `docs/PERMISSIONS.md`

---

### Task 1: Persist the CP4.2 data model

**Files:**
- Create: `alembic/versions/0012_stage4_contract_lifecycle_addenda.py`
- Modify: `app/modules/contracts/enums.py`
- Modify: `app/modules/contracts/models.py`
- Create: `tests/integration/test_stage4_cp42_migration.py`

**Interfaces:**
- Produces `ContractAddendumStatus` with values `draft`, `approval`, `signed`, `cancelled`.
- Produces `Contract.original_end_date`.
- Produces ORM classes `ContractSuspension` and `ContractAddendum`.
- Produces DB enum `contract_addendum_status`, tables `contract_suspensions`, `contract_addenda`, and partial unique index `uq_contract_suspensions_one_open`.

- [ ] **Step 1: Write the failing model/migration tests**

Create this initial test file:

```python
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus
from app.modules.contracts.models import Contract, ContractAddendum, ContractSuspension


def test_cp42_models_expose_expected_contract_fields() -> None:
    assert hasattr(Contract, "original_end_date")
    assert ContractSuspension.__tablename__ == "contract_suspensions"
    assert ContractAddendum.__tablename__ == "contract_addenda"
    assert [status.value for status in ContractAddendumStatus] == [
        "draft",
        "approval",
        "signed",
        "cancelled",
    ]


def test_cp42_database_objects_exist(db_session: Session) -> None:
    inspector = sa.inspect(db_session.get_bind())
    assert "contract_suspensions" in inspector.get_table_names()
    assert "contract_addenda" in inspector.get_table_names()
    index_names = {
        index["name"] for index in inspector.get_indexes("contract_suspensions")
    }
    assert "uq_contract_suspensions_one_open" in index_names
```

- [ ] **Step 2: Run the focused test and verify RED**

```powershell
python -m pytest -q tests/integration/test_stage4_cp42_migration.py
```

Expected: import/assertion failure because CP4.2 enum/models do not exist yet.

- [ ] **Step 3: Add the enum and exact ORM fields**

In `enums.py` add:

```python
class ContractAddendumStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVAL = "approval"
    SIGNED = "signed"
    CANCELLED = "cancelled"
```

In `models.py`, add this field to `Contract`:

```python
original_end_date: Mapped[date | None] = mapped_column(Date)
```

Add `ContractSuspension` with columns `id`, `contract_id`, `started_at`, `ended_at`, `reason`, `created_by`, `created_at`.

Add `ContractAddendum` with columns `id`, `contract_id`, `number`, `addendum_date`, `status`, `amount_delta`, `currency`, `new_end_date`, `description`, `signed_at`, `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`, `version`.

Use the existing project enum helper:

```python
status: Mapped[ContractAddendumStatus] = mapped_column(
    Enum(
        ContractAddendumStatus,
        name="contract_addendum_status",
        values_callable=enum_values,
    ),
    nullable=False,
    default=ContractAddendumStatus.DRAFT,
    index=True,
)
```

- [ ] **Step 4: Create Alembic revision `0012_stage4_contract_lifecycle_addenda`**

Use this exact revision linkage:

```python
revision: str = "0012_stage4_contract_lifecycle_addenda"
down_revision: str | Sequence[str] | None = "0011_stage4_contracts_core"
```

The migration must:
1. create PostgreSQL enum `contract_addendum_status`;
2. add nullable `contracts.original_end_date`;
3. backfill `original_end_date = end_date` for existing statuses `signed`, `in_progress`, `suspended`, `completed`, `terminated`, `archived`;
4. create `contract_suspensions` with FKs to `contracts` and `users`;
5. create this partial unique index:

```python
op.create_index(
    "uq_contract_suspensions_one_open",
    "contract_suspensions",
    ["contract_id"],
    unique=True,
    postgresql_where=sa.text("ended_at IS NULL"),
)
```

6. create `contract_addenda` with FKs to `contracts` and `users` and indexes for `contract_id`, `status`, `deleted_at`;
7. downgrade in reverse order and drop the addendum enum after dropping its table.

- [ ] **Step 5: Verify migration GREEN and single head**

```powershell
python -m pytest -q tests/integration/test_stage4_cp42_migration.py tests/integration/test_migration.py
alembic heads
alembic upgrade head
```

Expected: tests PASS; `alembic heads` prints only `0012_stage4_contract_lifecycle_addenda`.

- [ ] **Step 6: Commit Task 1**

```powershell
git add alembic/versions/0012_stage4_contract_lifecycle_addenda.py app/modules/contracts/enums.py app/modules/contracts/models.py tests/integration/test_stage4_cp42_migration.py
git commit -m "feat: add contract lifecycle and addenda data model"
```

---

### Task 2: Centralize commercial calculation and enforce post-signing CRUD guards

**Files:**
- Create: `app/modules/contracts/commercial.py`
- Modify: `app/modules/contracts/service.py`
- Modify: `app/modules/contracts/repository.py`
- Modify: `tests/integration/test_contracts_core.py`
- Create: `tests/integration/test_contract_lifecycle.py`

**Interfaces:**
- Produces `calculate_effective_amount(db, contract_id, pending_delta=Decimal("0.00")) -> Decimal`.
- Produces `recalculate_effective_amount(db, contract) -> Decimal`.
- Produces repository helpers `count_active_contract_items()` and `count_contract_responsibles()`.
- Existing CP4.1 `ContractService` public method signatures remain unchanged.

- [ ] **Step 1: Write RED guard tests**

Create `test_contract_lifecycle.py` using the existing CP4.1 fixture style. Add these named tests:
- `test_signed_contract_rejects_item_create_update_delete`;
- `test_signed_contract_rejects_legal_term_changes_but_allows_comment_change`;
- `test_contract_delete_allowed_only_draft_or_approval`;
- `test_responsibles_frozen_only_in_terminal_statuses`.

For the item guard, use a valid existing item and assert the service rejects the mutation before audit/state change:

```python
before_version = item.version
before_amount = contract.amount
before_audit = _audit_count(db_session, "contract_item.updated")
contract.status = ContractStatus.SIGNED
db_session.commit()

with pytest.raises(ContractValidationError):
    service.update_item(
        db_session,
        actor_id=actor_id,
        contract=contract,
        item=item,
        name=item.name,
        expertise_type_id=item.expertise_type_id,
        price=Decimal("200.00"),
        technical_device_ids=[device.id],
        building_ids=[],
        comment=item.comment,
    )

db_session.refresh(item)
db_session.refresh(contract)
assert item.version == before_version
assert contract.amount == before_amount
assert _audit_count(db_session, "contract_item.updated") == before_audit
```

- [ ] **Step 2: Run RED guard tests**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py tests/integration/test_contracts_core.py
```

Expected: new guard tests fail because CP4.1 only checks deletion state.

- [ ] **Step 3: Implement the shared commercial calculator**

Create `commercial.py` with this implementation shape:

```python
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus
from app.modules.contracts.models import Contract, ContractAddendum, ContractItem

MONEY_QUANTUM = Decimal("0.01")


def calculate_effective_amount(
    db: Session,
    contract_id: uuid.UUID,
    *,
    pending_delta: Decimal = Decimal("0.00"),
) -> Decimal:
    item_total = db.scalar(
        sa.select(
            sa.func.coalesce(sa.func.sum(ContractItem.price), Decimal("0.00"))
        ).where(
            ContractItem.contract_id == contract_id,
            ContractItem.deleted_at.is_(None),
        )
    )
    signed_delta_total = db.scalar(
        sa.select(
            sa.func.coalesce(
                sa.func.sum(ContractAddendum.amount_delta),
                Decimal("0.00"),
            )
        ).where(
            ContractAddendum.contract_id == contract_id,
            ContractAddendum.deleted_at.is_(None),
            ContractAddendum.status == ContractAddendumStatus.SIGNED,
        )
    )
    return (
        Decimal(item_total or 0)
        + Decimal(signed_delta_total or 0)
        + pending_delta
    ).quantize(MONEY_QUANTUM)


def recalculate_effective_amount(db: Session, contract: Contract) -> Decimal:
    amount = calculate_effective_amount(db, contract.id)
    contract.amount = amount
    db.flush()
    return amount
```

- [ ] **Step 4: Replace the CP4.1 private amount summation**

In `ContractService.create_item`, `update_item`, and `delete_item`, replace calls to `_recalculate_amount()` with `recalculate_effective_amount()`. Remove `_recalculate_amount()` after all call sites are replaced.

- [ ] **Step 5: Add exact service lifecycle guards**

Implement helper predicates/constants in `service.py`:

```python
EDITABLE_TERM_STATUSES = {ContractStatus.DRAFT, ContractStatus.APPROVAL}
RESPONSIBLE_EDITABLE_STATUSES = {
    ContractStatus.DRAFT,
    ContractStatus.APPROVAL,
    ContractStatus.SIGNED,
    ContractStatus.IN_PROGRESS,
    ContractStatus.SUSPENDED,
}
```

Rules enforced in service methods:
- `update_contract`: full legal-field changes only for `draft/approval`; for `signed/in_progress/suspended`, reject if any legal field differs and allow only `comment` difference; reject all changes in terminal statuses except no-op reads never reach the service;
- `create_item/update_item/delete_item`: only `draft/approval`;
- `delete_contract`: only `draft/approval`;
- `replace_responsibles`: only statuses in `RESPONSIBLE_EDITABLE_STATUSES`.

- [ ] **Step 6: Add repository count helpers**

Use exact side-effect-free queries:

```python
def count_active_contract_items(db: Session, contract_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(ContractItem).where(
                ContractItem.contract_id == contract_id,
                ContractItem.deleted_at.is_(None),
            )
        )
        or 0
    )


def count_contract_responsibles(db: Session, contract_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).select_from(ContractResponsible).where(
                ContractResponsible.contract_id == contract_id
            )
        )
        or 0
    )
```

- [ ] **Step 7: Verify GREEN and CP4.1 regression**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py tests/integration/test_contracts_core.py tests/integration/test_contracts_api_mutations.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

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
- Produces `ContractLifecycleService.change_status()`.
- Produces internal `ContractLifecycleService.mark_work_started()`.
- Ordinary transition set is exactly `draft->approval`, `approval->signed`, `completed->archived`, `terminated->archived`.

- [ ] **Step 1: Write RED transition tests**

Add these named tests:
- `test_ordinary_transition_matrix_accepts_only_approved_pairs`;
- `test_signing_requires_start_date`;
- `test_signing_requires_end_date`;
- `test_signing_requires_active_item`;
- `test_signing_requires_responsible`;
- `test_signing_sets_original_end_date_once`;
- `test_manual_status_change_cannot_start_signed_contract`;
- `test_mark_work_started_accepts_only_signed_contract`.

Use this transition matrix in the first test:

```python
allowed = {
    (ContractStatus.DRAFT, ContractStatus.APPROVAL),
    (ContractStatus.APPROVAL, ContractStatus.SIGNED),
    (ContractStatus.COMPLETED, ContractStatus.ARCHIVED),
    (ContractStatus.TERMINATED, ContractStatus.ARCHIVED),
}
```

Explicit rejected pairs are `draft->signed`, `approval->in_progress`, `signed->in_progress` through `change_status`, and `archived->draft`.

- [ ] **Step 2: Run transition tests and verify RED**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py -k "transition or signing or work_started"
```

Expected: import failure for `ContractLifecycleService` or failing assertions.

- [ ] **Step 3: Implement transition map and service signatures**

Create `lifecycle.py` with:

```python
ORDINARY_TRANSITIONS: dict[ContractStatus, set[ContractStatus]] = {
    ContractStatus.DRAFT: {ContractStatus.APPROVAL},
    ContractStatus.APPROVAL: {ContractStatus.SIGNED},
    ContractStatus.COMPLETED: {ContractStatus.ARCHIVED},
    ContractStatus.TERMINATED: {ContractStatus.ARCHIVED},
}
```

`ContractLifecycleService.change_status()` must:
1. reject deleted contracts;
2. verify `(current, target)` is allowed;
3. for `approval->signed`, require non-null start/end dates, at least one active item, at least one responsible, and non-negative effective amount;
4. set `original_end_date = end_date` only when entering `signed` and only when currently null;
5. increment `contract.version` once;
6. write `contract.status_changed` with metadata `{"from": old.value, "to": target.value}`;
7. commit/refresh atomically; rollback on exception.

`mark_work_started()` must accept only `signed`, set `in_progress`, increment version, audit `contract.work_started`, and commit atomically.

- [ ] **Step 4: Add row locking for lifecycle mutation lookup**

Add repository helper:

```python
def get_contract_for_update(
    db: Session,
    contract_id: uuid.UUID,
) -> Contract | None:
    return db.scalar(
        sa.select(Contract)
        .where(
            Contract.id == contract_id,
            Contract.deleted_at.is_(None),
        )
        .with_for_update()
    )
```

Lifecycle commands invoked by the API must reload/lock the contract immediately before mutating it. Service-level tests may pass the locked row returned by this helper.

- [ ] **Step 5: Verify GREEN**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py -k "transition or signing or work_started"
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```powershell
git add app/modules/contracts/lifecycle.py app/modules/contracts/repository.py tests/integration/test_contract_lifecycle.py
git commit -m "feat: add contract lifecycle state machine"
```

---

### Task 4: Implement suspension, resume, and termination

**Files:**
- Modify: `app/modules/contracts/lifecycle.py`
- Modify: `app/modules/contracts/repository.py`
- Modify: `tests/integration/test_contract_lifecycle.py`

**Interfaces:**
- Produces `suspend(db, actor_id, contract, reason) -> ContractSuspension`.
- Produces `resume(db, actor_id, contract) -> ContractSuspension` returning the closed interval.
- Produces `terminate(db, actor_id, contract, reason) -> Contract`.
- Produces `get_open_contract_suspension()` and `list_contract_suspensions()`.

- [ ] **Step 1: Write RED suspension/termination tests**

Add these named tests:
- `test_suspend_requires_in_progress_and_reason`;
- `test_suspend_creates_one_open_interval`;
- `test_second_open_suspension_is_rejected_by_service`;
- `test_second_open_suspension_is_rejected_by_database`;
- `test_resume_requires_suspended_and_open_interval`;
- `test_resume_closes_interval_and_restores_in_progress`;
- `test_terminate_requires_dedicated_domain_command_and_reason`;
- `test_terminate_from_suspended_closes_open_interval`.

Each rejected-command test captures status/version/audit count before the call and verifies they are unchanged after `db_session.refresh()`.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py -k "suspend or resume or terminate"
```

Expected: failing assertions because the commands are absent.

- [ ] **Step 3: Add suspension repository helpers**

Implement:

```python
def get_open_contract_suspension(
    db: Session,
    contract_id: uuid.UUID,
) -> ContractSuspension | None:
    return db.scalar(
        sa.select(ContractSuspension).where(
            ContractSuspension.contract_id == contract_id,
            ContractSuspension.ended_at.is_(None),
        )
    )


def list_contract_suspensions(
    db: Session,
    contract_id: uuid.UUID,
) -> list[ContractSuspension]:
    return list(
        db.scalars(
            sa.select(ContractSuspension)
            .where(ContractSuspension.contract_id == contract_id)
            .order_by(
                ContractSuspension.started_at.asc(),
                ContractSuspension.id.asc(),
            )
        ).all()
    )
```

- [ ] **Step 4: Implement `suspend()`**

Behavior is exact:
- clean `reason.strip()` and reject empty;
- require status `in_progress`;
- reject if open suspension exists;
- create `ContractSuspension(started_at=datetime.now(UTC), reason=clean_reason, created_by=actor_id)`;
- set status `suspended`, increment version;
- audit action `contract.suspended` with metadata `{"reason": clean_reason}`;
- flush, commit, refresh contract and suspension; rollback on exception.

- [ ] **Step 5: Implement `resume()` and `terminate()`**

`resume()` requires `suspended` plus one open interval, sets `ended_at=datetime.now(UTC)`, status `in_progress`, increments version, and audits `contract.resumed`.

`terminate()` requires status in `{signed, in_progress, suspended}`, a non-empty reason, closes the open suspension when current status is `suspended`, sets `terminated`, increments version, and audits `contract.terminated` with metadata `{"reason": clean_reason}`.

- [ ] **Step 6: Prove the partial unique index independently**

In `test_second_open_suspension_is_rejected_by_database`, insert two open rows for one contract directly with ORM, flush, assert `sqlalchemy.exc.IntegrityError`, then rollback.

- [ ] **Step 7: Verify GREEN**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

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
- Produces `CompletionBlocker`, `CompletionCheck`, `CompletionReadiness`.
- Produces `CompletionReadinessProvider` Protocol.
- Produces `default_readiness_providers()` with four explicit unavailable providers.
- `ContractLifecycleService` accepts an injected provider registry for deterministic tests.

- [ ] **Step 1: Write RED readiness tests**

Create these tests:
- `test_default_readiness_fails_closed_with_four_provider_blockers`;
- `test_readiness_passes_with_four_satisfied_injected_providers`;
- `test_complete_rechecks_readiness_and_rejects_blockers`;
- `test_complete_allows_in_progress_with_satisfied_providers`;
- `test_complete_rejects_non_in_progress_contract`.

Use this concrete test provider:

```python
class SatisfiedProvider:
    def __init__(self, key: str) -> None:
        self.key = key

    def check(self, db: Session, contract: Contract) -> CompletionCheck:
        return CompletionCheck(key=self.key, passed=True, blockers=())
```

- [ ] **Step 2: Run readiness tests and verify RED**

```powershell
python -m pytest -q tests/integration/test_contract_completion.py
```

Expected: import failure because readiness types do not exist.

- [ ] **Step 3: Implement readiness result types and Protocol**

Create `readiness.py`:

```python
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.modules.contracts.models import Contract


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


class CompletionReadinessProvider(Protocol):
    key: str

    def check(self, db: Session, contract: Contract) -> CompletionCheck:
        raise NotImplementedError
```

The Protocol body may use `raise NotImplementedError` because it is an interface contract, not a deferred implementation.

- [ ] **Step 4: Implement explicit unavailable providers**

Required keys and blocker codes:

```python
UNAVAILABLE_CODES = {
    "tasks": "tasks_provider_unavailable",
    "expertises": "expertises_provider_unavailable",
    "documents": "documents_provider_unavailable",
    "conclusion_delivery": "conclusion_delivery_provider_unavailable",
}
```

`default_readiness_providers()` returns one unavailable provider for every key above. Each returns `passed=False` and exactly one blocker with the matching code.

- [ ] **Step 5: Implement aggregation and completion**

`ContractLifecycleService.get_completion_readiness()` must iterate required keys in this deterministic order: `tasks`, `expertises`, `documents`, `conclusion_delivery`, aggregate checks/blockers, and set `ready_to_complete = not blockers`.

`complete()` must:
1. require status `in_progress`;
2. call readiness again inside the command;
3. reject if any blocker exists;
4. set status `completed`;
5. increment version;
6. audit `contract.completed`;
7. commit/refresh atomically.

- [ ] **Step 6: Verify GREEN**

```powershell
python -m pytest -q tests/integration/test_contract_completion.py tests/integration/test_contract_lifecycle.py
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```powershell
git add app/modules/contracts/readiness.py app/modules/contracts/lifecycle.py tests/integration/test_contract_completion.py
git commit -m "feat: add fail-closed contract completion readiness"
```

---

### Task 6: Implement additional agreements and signed commercial effects

**Files:**
- Create: `app/modules/contracts/addenda.py`
- Modify: `app/modules/contracts/repository.py`
- Modify: `app/modules/contracts/commercial.py`
- Create: `tests/integration/test_contract_addenda.py`

**Interfaces:**
- Produces `ContractAddendumService.create_addendum()`.
- Produces `update_addendum()`, `delete_addendum()`, `change_status()`.
- Produces nested repository helpers `get_contract_addendum()` and `list_contract_addenda()`.

- [ ] **Step 1: Write RED addendum lifecycle tests**

Create these tests:
- `test_addendum_create_allowed_only_for_signed_active_parent_statuses`;
- `test_addendum_creation_copies_parent_currency`;
- `test_addendum_edit_delete_allowed_only_draft_or_approval`;
- `test_addendum_transition_matrix`;
- `test_signed_and_cancelled_addenda_are_immutable`;
- `test_addendum_cannot_sign_after_parent_becomes_terminal`;
- `test_addendum_without_effect_cannot_sign`.

Allowed transition pairs are exactly:

```python
allowed = {
    (ContractAddendumStatus.DRAFT, ContractAddendumStatus.APPROVAL),
    (ContractAddendumStatus.APPROVAL, ContractAddendumStatus.SIGNED),
    (ContractAddendumStatus.DRAFT, ContractAddendumStatus.CANCELLED),
    (ContractAddendumStatus.APPROVAL, ContractAddendumStatus.CANCELLED),
}
```

- [ ] **Step 2: Write RED commercial-effect tests**

Add:
- `test_signed_addenda_recalculate_amount_and_effective_deadline`;
- `test_negative_projected_effective_amount_is_rejected_atomically`;
- `test_currency_mismatch_is_rejected_before_signing`;
- `test_deadline_extension_requires_description_reason`;
- `test_deadline_shortening_does_not_require_extension_reason`;
- `test_signing_retry_does_not_double_apply_effect`;
- `test_signed_addenda_history_has_deterministic_order`.

The main scenario is:

```python
assert contract.amount == Decimal("100000.00")
assert contract.original_end_date == date(2026, 9, 30)

# After signed +25,000 agreement
assert contract.amount == Decimal("125000.00")

# After signed -10,000 agreement with new 2026-12-31 deadline
assert contract.amount == Decimal("115000.00")
assert contract.original_end_date == date(2026, 9, 30)
assert contract.end_date == date(2026, 12, 31)
```

- [ ] **Step 3: Run addendum tests and verify RED**

```powershell
python -m pytest -q tests/integration/test_contract_addenda.py
```

Expected: import failure because `ContractAddendumService` does not exist.

- [ ] **Step 4: Add nested repository helpers**

Implement exact lookup semantics:

```python
def get_contract_addendum(
    db: Session,
    contract_id: uuid.UUID,
    addendum_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> ContractAddendum | None:
    stmt = sa.select(ContractAddendum).where(
        ContractAddendum.id == addendum_id,
        ContractAddendum.contract_id == contract_id,
    )
    if not include_deleted:
        stmt = stmt.where(ContractAddendum.deleted_at.is_(None))
    return db.scalar(stmt)
```

`list_contract_addenda()` filters deleted rows and orders by `addendum_date`, `created_at`, `id`.

- [ ] **Step 5: Implement addendum creation/update/delete guards**

Parent statuses allowed for creation/edit/sign are exactly `{signed, in_progress, suspended}`.

`create_addendum()` accepts `actor_id`, `contract`, `number`, `addendum_date`, `amount_delta`, `new_end_date`, `description`; it copies `contract.currency` and sets `created_by=updated_by=actor_id`.

Normalize non-null `amount_delta` with `Decimal(value).quantize(Decimal("0.01"))`; both positive and negative values are allowed.

`update_addendum()` and `delete_addendum()` reject signed/cancelled rows and terminal parent contracts.

- [ ] **Step 6: Implement addendum status changes atomically**

For `approval->signed`:
1. lock/reload parent and addendum;
2. require parent status in `{signed, in_progress, suspended}`;
3. require either non-zero delta or `new_end_date`;
4. require `addendum.currency == contract.currency`;
5. if `new_end_date` is later than current `end_date`, require non-empty `description`;
6. if `start_date` exists, reject `new_end_date < start_date`;
7. compute `projected = calculate_effective_amount(db, contract.id, pending_delta=amount_delta_or_zero)` and reject `projected < 0`;
8. set `signed_at=datetime.now(UTC)` once and status `signed`;
9. apply `new_end_date` to `contract.end_date` when present;
10. call `recalculate_effective_amount()` after the row status becomes signed;
11. increment addendum and contract versions once;
12. audit `contract_addendum.signed` with amount/deadline metadata;
13. commit/refresh atomically.

For cancellation, set `cancelled`, increment addendum version, audit `contract_addendum.cancelled`, and do not alter contract amount/end date.

For `draft->approval`, audit `contract_addendum.status_changed` with `from/to` metadata.

- [ ] **Step 7: Verify GREEN and CP4.1 amount regression**

```powershell
python -m pytest -q tests/integration/test_contract_addenda.py tests/integration/test_contracts_core.py
```

Expected: PASS; contracts with no signed addenda still equal active item total.

- [ ] **Step 8: Commit Task 6**

```powershell
git add app/modules/contracts/addenda.py app/modules/contracts/repository.py app/modules/contracts/commercial.py tests/integration/test_contract_addenda.py
git commit -m "feat: add contract additional agreements"
```

---

### Task 7: Expose lifecycle/readiness/addenda through permission-safe API commands

**Files:**
- Modify: `app/modules/contracts/schemas.py`
- Modify: `app/modules/contracts/routes.py`
- Create: `tests/integration/test_contract_lifecycle_api.py`

**Interfaces:**
- `GET completion-readiness` requires `contracts.view`.
- `POST complete` requires `contracts.complete`.
- `POST terminate` requires `contracts.terminate`.
- `/status`, `/suspend`, `/resume` require `contracts.change_status`.
- Addenda reads require `contracts.view`; addenda mutations require `contracts.manage_addenda`.
- Ordinary PATCH never accepts a status field.

- [ ] **Step 1: Add explicit Pydantic schemas**

Add these concrete schemas:

```python
class ContractStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ContractStatus


class ContractReasonCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1)


class ContractAddendumCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: str = Field(min_length=1, max_length=120)
    addendum_date: date
    amount_delta: Decimal | None = None
    new_end_date: date | None = None
    description: str | None = None


class ContractAddendumUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: str | None = Field(default=None, max_length=120)
    addendum_date: date | None = None
    amount_delta: Decimal | None = None
    new_end_date: date | None = None
    description: str | None = None


class ContractAddendumStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ContractAddendumStatus
```

Add response models mirroring the approved fields and readiness dataclasses. Add `original_end_date: date | None` to `ContractResponse`. Do not add `status` to `ContractUpdate` or `ContractAddendumUpdate`.

- [ ] **Step 2: Write RED API tests**

Create these named tests:
- `test_status_endpoint_requires_change_status_permission`;
- `test_terminate_endpoint_requires_terminate_permission_only`;
- `test_complete_endpoint_requires_complete_permission_only`;
- `test_dedicated_permissions_do_not_grant_each_other`;
- `test_patch_contract_rejects_status_field`;
- `test_no_public_command_starts_signed_contract_manually`;
- `test_completion_readiness_returns_fail_closed_blockers`;
- `test_addenda_read_uses_view_permission`;
- `test_addenda_mutation_uses_manage_addenda_permission`;
- `test_foreign_nested_addendum_returns_same_404_as_unknown_id`.

- [ ] **Step 3: Run API tests and verify RED**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle_api.py
```

Expected: 404/405/schema failures because routes are not registered.

- [ ] **Step 4: Add contract command routes**

Register exactly:

```text
POST /api/contracts/{contract_id}/status
POST /api/contracts/{contract_id}/suspend
POST /api/contracts/{contract_id}/resume
POST /api/contracts/{contract_id}/terminate
GET  /api/contracts/{contract_id}/completion-readiness
POST /api/contracts/{contract_id}/complete
```

Each route obtains the command-specific `AuthorizationContext` from `require_scoped_permission()`, uses `_contract_or_404()` with that context, reloads/locks before mutation when required, calls the corresponding lifecycle service method, and maps `ContractValidationError` to `_unprocessable(str(exc))`.

- [ ] **Step 5: Add nested addenda routes**

Register exactly:

```text
GET    /api/contracts/{contract_id}/addenda
POST   /api/contracts/{contract_id}/addenda
GET    /api/contracts/{contract_id}/addenda/{addendum_id}
PATCH  /api/contracts/{contract_id}/addenda/{addendum_id}
DELETE /api/contracts/{contract_id}/addenda/{addendum_id}
POST   /api/contracts/{contract_id}/addenda/{addendum_id}/status
```

Nested resource lookup always uses both `contract_id` and `addendum_id`. Reads use `contracts.view`; mutations use `contracts.manage_addenda`. Parent scope denial and unknown nested ID both return 404.

- [ ] **Step 6: Keep signed work-start internal**

Do not create a route for `mark_work_started()`. Add a test that posts `{"status": "in_progress"}` to `/status` for a signed contract and receives 422 without changing the contract.

- [ ] **Step 7: Verify GREEN and CP4.1 API regression**

```powershell
python -m pytest -q tests/integration/test_contract_lifecycle_api.py tests/integration/test_contracts_api.py tests/integration/test_contracts_api_mutations.py tests/integration/test_contracts_api_queries.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 7**

```powershell
git add app/modules/contracts/schemas.py app/modules/contracts/routes.py tests/integration/test_contract_lifecycle_api.py
git commit -m "feat: expose contract lifecycle and addenda API"
```

---

### Task 8: Close atomicity, audit, migration, and authorization edge cases

**Files:**
- Modify: `tests/integration/test_contract_lifecycle.py`
- Modify: `tests/integration/test_contract_addenda.py`
- Modify: `tests/integration/test_contract_completion.py`
- Modify: `tests/integration/test_contract_lifecycle_api.py`
- Modify production files only when a new failing test proves a defect.

**Interfaces:**
- No new public interfaces.
- Produces explicit proof of rollback, audit cleanliness, one-head migration behavior, and exact scope isolation.

- [ ] **Step 1: Add rejected-command audit assertions**

For each audit action `contract.status_changed`, `contract.suspended`, `contract.resumed`, `contract.terminated`, `contract.completed`, `contract_addendum.signed`, capture the action count before an invalid command and assert the count is unchanged afterward.

Use the concrete structure:

```python
before = _audit_count(db_session, "contract.suspended")
with pytest.raises(ContractValidationError):
    lifecycle.suspend(
        db_session,
        actor_id=actor_id,
        contract=contract,
        reason="   ",
    )
assert _audit_count(db_session, "contract.suspended") == before
```

- [ ] **Step 2: Add rollback/version assertions**

For every rejected mutation, record the relevant `version`, `status`, `amount`, `end_date`, `signed_at`, or `deleted_at`; call `db_session.refresh()` after the exception; assert every recorded value is unchanged.

- [ ] **Step 3: Add `0012 -> 0011 -> 0012` migration smoke test**

Follow the repository's existing Alembic integration-test execution approach. The test must downgrade only to `0011_stage4_contracts_core`, assert `contract_addenda` and `contract_suspensions` disappear, upgrade to head, then assert both tables and `uq_contract_suspensions_one_open` exist again.

- [ ] **Step 4: Add ALL/RELATED/ASSIGNED/OWN API scope cases**

Use existing identity grant fixtures to test one `/status` mutation and one addendum mutation under each scope. Each authorized scope returns the command's normal business result; a non-matching scope returns 404. Run dedicated-permission isolation independently from scope matching.

- [ ] **Step 5: Run the complete Stage 4 focused suite**

```powershell
python -m pytest -q tests/integration/test_contracts_core.py tests/integration/test_contracts_api.py tests/integration/test_contracts_api_mutations.py tests/integration/test_contracts_api_queries.py tests/integration/test_contract_lifecycle.py tests/integration/test_contract_addenda.py tests/integration/test_contract_completion.py tests/integration/test_contract_lifecycle_api.py tests/integration/test_stage4_cp42_migration.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 8**

```powershell
git add app/modules/contracts tests/integration
git commit -m "test: close CP4.2 lifecycle edge cases"
```

If no production file changed, stage only the test files that changed.

---

### Task 9: Reconcile docs, run full verification, and prepare the review checkpoint

**Files:**
- Modify: `PROJECT_STATUS.md`
- Modify: `docs/BUSINESS_RULES.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/PERMISSIONS.md`
- Keep: `docs/superpowers/specs/2026-08-12-stage4-cp42-contract-lifecycle-addenda-design.md`
- Keep: `docs/superpowers/plans/2026-08-12-stage4-cp42-contract-lifecycle-addenda.md`

**Interfaces:**
- Produces a documented, reviewable CP4.2 checkpoint.
- Does not merge into integration.

- [ ] **Step 1: Reconcile authoritative docs with the approved design**

Make these exact corrections:
- completion requires `contracts.complete`, not `contracts.change_status`;
- termination requires `contracts.terminate`;
- Tasks/Expertises/Documents/Notifications side effects stay deferred to their owning stages;
- document `original_end_date`, `contract_suspensions`, `contract_addenda`, addendum terminal statuses, effective amount formula, and fail-closed readiness;
- document that addendum `document_id` remains deferred to Stage 8.

- [ ] **Step 2: Run static and migration verification before status claims**

```powershell
python -m ruff check .
alembic heads
alembic upgrade head
```

Expected: Ruff PASS; one head named `0012_stage4_contract_lifecycle_addenda`; upgrade succeeds.

- [ ] **Step 3: Run the full test suite**

```powershell
python -m pytest -q
```

Expected: all tests PASS. Record the exact pass and warning counts from this run; do not predict them.

- [ ] **Step 4: Verify stacked ancestry and integration isolation**

```powershell
git merge-base --is-ancestor fa11c71726cea0fb92ed6f1df777456ab0ab830c HEAD
git log --oneline --decorate fa11c71726cea0fb92ed6f1df777456ab0ab830c..HEAD
```

Expected: ancestry command exits 0. Do not merge/rebase the integration branch.

- [ ] **Step 5: Update `PROJECT_STATUS.md` with verified facts only**

Record:
- branch name;
- final implementation commit;
- migration head `0012_stage4_contract_lifecycle_addenda`;
- implemented lifecycle/addenda/readiness scope;
- deferred Stage 5/6/8 integrations;
- exact pytest/Ruff/Alembic results from Steps 2–3.

- [ ] **Step 6: Commit documentation/status**

```powershell
git add PROJECT_STATUS.md docs/BUSINESS_RULES.md docs/DATA_MODEL.md docs/PERMISSIONS.md
git commit -m "docs: record CP4.2 contract lifecycle checkpoint"
```

- [ ] **Step 7: Push and create a stacked draft PR**

Target base branch `agent/stage4-cp41-contracts-core` so the PR contains CP4.2 only. The PR body must state CP4.1 dependency, exact final HEAD, migration head, exact verification results, deferred Tasks/Expertises/Documents integrations, and the sentence **DO NOT MERGE into integration automatically**.

- [ ] **Step 8: Verify CI on the exact final HEAD**

Check Ruff, Alembic, and pytest jobs for the exact pushed commit. If a job fails, invoke systematic debugging, reproduce locally or in a focused test, fix only the proven defect, rerun full verification, push the corrected HEAD, and update the PR/checkpoint facts.

---

## Final Acceptance Checklist

- [ ] `0012_stage4_contract_lifecycle_addenda` is the only Alembic head.
- [ ] Signing requires start date, end date, at least one active item, and at least one responsible.
- [ ] `original_end_date` is captured once and remains immutable.
- [ ] Public ordinary transitions match the approved state machine exactly.
- [ ] No public endpoint exposes manual `signed -> in_progress`.
- [ ] Signed legal terms/items are immutable; responsibles remain editable only until terminal status; comment remains editable until archive.
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
