# Stage 4 CP4.2 — Contract Lifecycle, Suspensions, Completion Readiness and Addenda

Date: 2026-08-12
Status: Approved design
Base checkpoint: CP4.1 Contracts Core (`fa11c71726cea0fb92ed6f1df777456ab0ab830c`)
Target working branch: `agent/stage4-cp42-contract-lifecycle-addenda`

## 1. Goal

Complete the Stage 4 contract-domain lifecycle that can be implemented safely before Tasks, Expertises and Documents are available. CP4.2 adds the contract state machine, suspension/resume records, termination/completion commands, completion readiness infrastructure, additional agreements, legal-term immutability after signing, effective amount/deadline application, authorization and audit behavior.

The design intentionally avoids fake cross-module behavior. Effects that require future Tasks, Expertises, Documents or Notifications integrations are represented by narrow fail-closed integration boundaries and are completed in their owning stages.

## 2. Scope

CP4.2 includes:

- strict contract status transition rules;
- explicit permission separation for ordinary status changes, termination and completion;
- signing-time freezing of legally significant contract terms;
- one-open-suspension invariant and suspension history;
- resume closing the current suspension;
- termination with preserved history;
- completion-readiness aggregation that fails closed while required providers are unavailable;
- manual completion only after readiness succeeds;
- additional agreements with their own lifecycle;
- atomic application of signed addendum amount and end-date changes;
- preservation of original contract deadline;
- recalculation of effective contract amount from active contract items plus signed addendum deltas;
- authorization/scope enforcement using the existing contracts access policy;
- audit entries for accepted business commands and no audit entries for rejected commands;
- migration, API schemas/routes, service/repository changes and tests.

## 3. Non-goals

CP4.2 does not implement:

- Tasks module models, routes, deadlines or task cancellation;
- Expertise module models or automatic work-start triggers;
- Documents module or addendum document storage;
- Notifications or recalculation of notification schedules;
- frontend contract workspace migration;
- automatic contract completion;
- a generic workflow engine;
- generic event sourcing.

Future stages must integrate through the domain boundaries defined here rather than by importing future modules into Contracts prematurely.

## 4. Architectural approach

Use the existing modular-monolith contracts module and service/repository layering.

`app/modules/contracts` remains the owner of:

- contract statuses and transition validation;
- contract signing rules;
- suspension records;
- addenda;
- effective contract amount and deadline;
- completion-readiness orchestration;
- contract audit commands.

Contracts must not directly import future Tasks, Expertises or Documents modules in CP4.2. Readiness and future lifecycle side effects use narrow integration ports/hooks whose unavailable state is explicit and fail-closed.

This approach was chosen over two rejected alternatives:

1. Deferring most lifecycle behavior until Stage 5, which would leave Stage 4 materially incomplete.
2. Temporary success stubs for missing dependencies, which could allow invalid completion and create unsafe production behavior.

## 5. Permission model

The approved permission split is authoritative for CP4.2:

- `contracts.change_status` — ordinary lifecycle transitions only;
- `contracts.terminate` — termination only;
- `contracts.complete` — completion only;
- `contracts.manage_addenda` — addendum CRUD/status actions;
- existing `contracts.edit`, `contracts.delete`, `contracts.restore`, `contracts.manage_items`, `contracts.manage_responsibles` keep their current meanings subject to lifecycle restrictions below.

Scope semantics remain ALL / ASSIGNED / RELATED / OWN using the existing contract access policy. Permission-name isolation remains exact: possessing one contract permission must not grant another.

For inaccessible, foreign, deleted or out-of-scope contract/addendum resources, API behavior must preserve the existing anti-enumeration contract and return the same not-found response where appropriate.

## 6. Contract state machine

Allowed primary transitions:

- `draft -> approval` using `contracts.change_status`;
- `approval -> signed` using `contracts.change_status`;
- `signed -> in_progress` only through the internal domain command `mark_work_started()`; no external manual endpoint in CP4.2;
- `in_progress -> suspended` using `contracts.change_status` and a mandatory non-empty reason;
- `suspended -> in_progress` using `contracts.change_status`;
- `in_progress -> completed` only through the completion command using `contracts.complete` and only when readiness succeeds;
- `signed -> terminated` using `contracts.terminate` and mandatory reason;
- `in_progress -> terminated` using `contracts.terminate` and mandatory reason;
- `suspended -> terminated` using `contracts.terminate` and mandatory reason;
- `completed -> archived` using `contracts.change_status`;
- `terminated -> archived` using `contracts.change_status`.

All other direct transitions are rejected.

`completed`, `terminated` and `archived` are non-reversible in v1.

### 6.1 Automatic start boundary

The business rule says a signed contract starts when actual work begins, for example when a linked task moves to in-progress or an expertise leaves preparation. Those producer modules do not exist yet.

CP4.2 therefore exposes an internal service/domain command `mark_work_started(contract_id, actor/context)` that performs only `signed -> in_progress` and is not exposed as a normal public status endpoint. Stage 5/6 integrations will call it from real work-start events.

Creating an expertise in preparation alone must not start the contract when Stage 6 is implemented.

## 7. Legal immutability after signing

Before signing, contract data can be edited according to existing edit permission and validation rules.

On `approval -> signed`:

- `original_end_date` is initialized from the then-current `end_date` if not already set;
- the contract's legally significant base terms are frozen;
- active contract items and their prices become the immutable base commercial composition for that signed contract.

After signing, direct edits are prohibited for:

- customer organization;
- customer contact;
- contract number;
- contract date;
- start date;
- original deadline;
- effective end date through normal contract PATCH;
- currency;
- contract item membership;
- contract item prices and other commercial item fields.

Post-signing amount or deadline changes must occur through a signed addendum.

Responsible employees may still be changed while the contract is not completed, terminated or archived. A general operational comment may be edited until archived.

Soft-delete of a contract is allowed only in `draft` or `approval`. A signed contract must proceed through lifecycle actions rather than destructive deletion.

## 8. Data model changes

### 8.1 Contract additions

Add to `contracts`:

- `original_end_date DATE NULL`.

Rules:

- for pre-existing CP4.1 rows, migration may leave it null until signing;
- on signing it is set to the current `end_date` exactly once;
- it never changes after being set;
- `end_date` represents the current effective contractual deadline.

No separate base-amount column is required because the signed base amount is reproducible from immutable signed contract items. `contracts.amount` remains the materialized effective amount.

### 8.2 ContractSuspension

Create `contract_suspensions`:

- `id UUID PK`;
- `contract_id UUID FK contracts(id)`;
- `started_at TIMESTAMPTZ NOT NULL`;
- `ended_at TIMESTAMPTZ NULL`;
- `reason TEXT NOT NULL`;
- `created_by UUID FK users(id)`;
- `created_at TIMESTAMPTZ NOT NULL`.

Invariant: at most one row per contract where `ended_at IS NULL`.

Enforce this in both service logic and a PostgreSQL partial unique index on `contract_id WHERE ended_at IS NULL`.

### 8.3 ContractAddendum

Create `contract_addenda`:

- `id UUID PK`;
- `contract_id UUID FK contracts(id)`;
- `number VARCHAR(...) NOT NULL`;
- `addendum_date DATE NOT NULL`;
- `status contract_addendum_status NOT NULL`;
- `amount_delta NUMERIC(14,2) NULL`;
- `currency VARCHAR(3) NOT NULL DEFAULT 'RUB'`;
- `new_end_date DATE NULL`;
- `description TEXT NULL`;
- `signed_at TIMESTAMPTZ NULL`;
- `created_by UUID FK users(id)`;
- `updated_by UUID FK users(id)` where consistent with current repository conventions;
- `created_at`, `updated_at`;
- `deleted_at TIMESTAMPTZ NULL`;
- `version INTEGER NOT NULL`.

Statuses:

- `draft`;
- `approval`;
- `signed`;
- `cancelled`.

No `document_id` is added in CP4.2 because the Documents module does not exist yet. Stage 8 may add that nullable FK in a later migration.

## 9. Addendum state machine and business rules

Allowed transitions:

- `draft -> approval`;
- `approval -> signed`;
- `draft -> cancelled`;
- `approval -> cancelled`.

`signed` and `cancelled` are terminal in v1.

A signed addendum cannot be edited, soft-deleted or cancelled retroactively. A legal correction is represented by another addendum.

An addendum may contain an amount change, an end-date change, or both. An addendum with neither has no contractual effect and must not be signable.

`amount_delta` may be positive or negative, but signing must never produce a negative effective contract amount.

Addendum currency must equal contract currency. CP4.2 does not implement currency conversion.

If `new_end_date` is set, it must satisfy contract date constraints, including not preceding `start_date` when `start_date` exists.

If the new deadline extends the current effective deadline, `description` is mandatory and serves as the recorded business reason for the extension, satisfying the established rule that contract-term increases require a reason.

### 9.1 Atomic application

On `approval -> signed`, in one database transaction:

1. lock/reload the target contract and addendum according to current repository concurrency conventions;
2. revalidate status, authorization, currency and resulting values;
3. set `signed_at` once;
4. set addendum status to `signed`;
5. if `new_end_date` exists, update `contracts.end_date` to that value;
6. recalculate `contracts.amount` using the authoritative formula;
7. increment applicable versions/timestamps;
8. write audit records;
9. commit.

Any failure rolls the whole transaction back. Retrying an already-signed addendum must not apply its amount or deadline effect a second time.

## 10. Effective amount

The authoritative formula is:

`effective_amount = sum(price of active contract_items) + sum(amount_delta of active signed contract_addenda)`

`contracts.amount` is a materialized value maintained by the contracts service for listing/query compatibility.

Every operation that may affect the formula must use the same shared recalculation path:

- pre-signing item add/update/delete/restore;
- addendum signing;
- any future correction operation explicitly allowed by the domain.

Because contract items become immutable once the contract is signed, the original signed commercial basis remains reconstructible.

The resulting amount must be `>= 0` and the existing contract non-negative invariant remains valid.

## 11. Deadline history and reconstruction

`original_end_date` preserves the deadline at the moment of initial contract signing.

`contracts.end_date` stores the current effective deadline.

Each signed addendum keeps its `new_end_date` and `signed_at`. The historical deadline can therefore be reconstructed by starting with `original_end_date` and applying signed addenda in deterministic signing order (`signed_at`, with a stable ID tie-breaker if needed).

The addendum itself is immutable after signing, so this chain is stable.

## 12. Suspension and resume

### 12.1 Suspend

`POST /api/contracts/{id}/suspend` requires:

- contract currently `in_progress`;
- `contracts.change_status` in scope;
- non-empty reason;
- no existing open suspension.

In one transaction:

- create `ContractSuspension(started_at=now, reason=...)`;
- change contract status to `suspended`;
- write audit.

### 12.2 Resume

`POST /api/contracts/{id}/resume` requires:

- contract currently `suspended`;
- `contracts.change_status` in scope;
- exactly one open suspension.

In one transaction:

- set `ended_at=now` on the open suspension;
- change status to `in_progress`;
- write audit.

Future Stage 5/11 integrations will use the closed suspension duration to shift unfinished task deadlines and recalculate/suppress notifications. CP4.2 does not invent task rows or notification behavior.

## 13. Termination

`POST /api/contracts/{id}/terminate` requires:

- status in `signed`, `in_progress`, `suspended`;
- `contracts.terminate` in scope;
- mandatory non-empty reason.

The command changes the status to `terminated` and records the reason in audit metadata within the same transaction.

If the contract is suspended, the open suspension is closed at termination time so the suspension table never retains an indefinitely open period for a terminal contract.

Future Stage 5 integration must cancel unfinished linked tasks. Existing business data, future expertises, documents and history are preserved.

## 14. Completion readiness

Completion is never automatic.

Expose:

- `GET /api/contracts/{id}/completion-readiness`;
- `POST /api/contracts/{id}/complete`.

The readiness response is structured, not a single boolean only. It contains:

- `ready_to_complete`;
- a list of checks/providers;
- blockers with stable machine-readable codes and user-readable detail.

Minimum future providers/checks required by business rules:

- mandatory expertises completed;
- mandatory tasks done or cancelled;
- required documents generated;
- conclusions delivered to customer.

### 14.1 Fail-closed behavior

Until Stage 5/6/8 providers are wired, required unavailable providers return blockers such as:

- `tasks_provider_unavailable`;
- `expertises_provider_unavailable`;
- `documents_provider_unavailable`;
- `conclusion_delivery_provider_unavailable`.

Therefore `ready_to_complete=false` in normal production CP4.2 state.

`POST /complete` requires `contracts.complete`, reruns readiness inside the command transaction, and rejects completion when any blocker exists. It never trusts a previously returned client-side readiness result.

This is intentional: absence of an integration must never be treated as proof of completion.

## 15. Integration ports/hooks

CP4.2 defines narrow contracts-owned boundaries for future modules rather than cross-importing them now.

Required conceptual ports:

- completion readiness providers;
- work-start trigger into `mark_work_started()`;
- suspension/resume lifecycle hook for task deadline and notification adjustments;
- termination hook for task cancellation.

The exact Python shape may be Protocols/services or another project-consistent dependency mechanism chosen during implementation planning, but the behavioral contract above is fixed.

Unavailable completion providers must fail closed. Non-readiness hooks that have no future consumer yet must not pretend to execute downstream behavior.

## 16. API surface

Existing CP4.1 contract CRUD/item/responsible endpoints remain unless lifecycle restrictions make an operation invalid.

New command-oriented endpoints:

- `POST /api/contracts/{id}/status` for ordinary allowed status changes such as draft->approval, approval->signed and terminal->archived;
- `POST /api/contracts/{id}/suspend`;
- `POST /api/contracts/{id}/resume`;
- `POST /api/contracts/{id}/terminate`;
- `GET /api/contracts/{id}/completion-readiness`;
- `POST /api/contracts/{id}/complete`.

The internal `mark_work_started()` command is not exposed as a normal public endpoint in CP4.2.

Addenda endpoints under the owning contract:

- `GET /api/contracts/{id}/addenda`;
- `POST /api/contracts/{id}/addenda`;
- `GET /api/contracts/{id}/addenda/{addendum_id}` if consistent with current route conventions;
- `PATCH /api/contracts/{id}/addenda/{addendum_id}`;
- `DELETE /api/contracts/{id}/addenda/{addendum_id}` for allowed non-terminal soft deletion;
- `POST /api/contracts/{id}/addenda/{addendum_id}/status` for draft->approval, approval->signed and cancellation paths.

Status must not be freely writable through ordinary contract/addendum PATCH schemas.

## 17. Error and transaction behavior

Business-rule violations use the project's existing domain/API error mapping and must not partially mutate state.

Examples:

- invalid transition;
- wrong dedicated permission;
- status mutation through ordinary PATCH;
- suspend without reason;
- second open suspension;
- resume without open suspension;
- signed contract item mutation;
- invalid addendum transition;
- signing addendum with no effect;
- currency mismatch;
- negative resulting contract amount;
- extending deadline without reason;
- completion with blockers.

Rejected commands must:

- rollback all mutations;
- not create audit entries;
- not increment versions merely because a rejected command was attempted.

Successful multi-record commands must commit atomically with their audit entries.

## 18. Audit behavior

Audit events are required for:

- ordinary status transition;
- signing;
- suspend;
- resume;
- termination including reason;
- completion;
- archive;
- addendum create/update/delete where permitted;
- addendum status transitions;
- signed addendum application.

Audit metadata should record stable identifiers and relevant before/after values without duplicating sensitive payloads unnecessarily.

No audit record is written for a rejected command.

## 19. Test strategy

Implementation follows TDD: representative RED tests are written/run before production changes, then the smallest implementation is added to make them GREEN.

### 19.1 Migration/model tests

Verify:

- Alembic upgrades cleanly from `0011_stage4_contracts_core`;
- exactly one Alembic head exists;
- `original_end_date` exists;
- contract suspension/addendum tables and enum exist;
- one-open-suspension partial unique index works at DB level;
- downgrade/upgrade behavior follows repository migration standards.

### 19.2 State-machine tests

Cover every allowed transition and representative forbidden transitions.

Explicitly verify:

- ordinary status permission cannot terminate or complete;
- terminate permission cannot perform ordinary transitions or completion;
- complete permission cannot terminate or perform ordinary transitions;
- public API cannot manually do `signed -> in_progress`;
- internal work-start command only accepts `signed`;
- terminal statuses cannot be reopened.

### 19.3 Signing and immutability tests

Verify:

- signing initializes `original_end_date` exactly once;
- post-sign contract legal-field edits are rejected;
- post-sign item create/update/delete/restore are rejected;
- responsibles remain editable in allowed active statuses;
- signed contract cannot be soft-deleted.

### 19.4 Suspension/resume tests

Verify:

- suspend requires reason;
- suspension creates open history row atomically;
- second simultaneous/open suspension is rejected;
- DB index independently protects the invariant;
- resume closes the open row and restores in-progress status;
- resume without an open suspension is rejected;
- termination from suspended closes the open suspension.

### 19.5 Addendum tests

Verify:

- CRUD/status permission and scope isolation;
- allowed and forbidden addendum transitions;
- terminal addenda are immutable;
- signed addendum cannot be deleted;
- addendum with no contractual effect cannot be signed;
- currency mismatch is rejected;
- deadline extension without description/reason is rejected;
- invalid shortened deadline is rejected;
- signing applies amount and/or deadline atomically;
- retrying signing cannot double-apply effects;
- negative resulting amount is rejected and rolled back;
- multiple signed amount deltas produce correct materialized amount;
- multiple signed deadline changes preserve original deadline and deterministic history.

### 19.6 Completion-readiness tests

Verify:

- unavailable mandatory providers produce stable blockers;
- default CP4.2 readiness is false while providers are unavailable;
- `contracts.complete` is independently required;
- completion reruns readiness server-side;
- completion with any blocker is rejected with no status/audit mutation;
- a test composition with all readiness providers satisfied allows `in_progress -> completed`;
- archive is allowed only from completed/terminated.

### 19.7 Authorization and anti-enumeration tests

For each new endpoint, verify:

- ALL/ASSIGNED/RELATED/OWN behavior through existing contract access rules;
- wrong permission isolation;
- foreign/out-of-scope resource indistinguishability;
- nested addendum access cannot bypass parent contract scope.

### 19.8 Audit/rollback tests

Verify:

- successful commands create expected audit entries;
- rejected transition/addendum/readiness commands create no audit entries;
- atomic command failures leave contract/addendum/suspension values unchanged.

### 19.9 Regression tests

Run the full backend test suite, Ruff and Alembic checks. The CP4.1 baseline behavior must remain GREEN for contracts that remain in the draft/pre-sign lifecycle.

## 20. Acceptance criteria

CP4.2 is accepted only when all of the following are true:

1. Migration upgrades from CP4.1 cleanly and Alembic has one head.
2. Contract lifecycle transitions match this specification exactly.
3. Dedicated completion/termination permissions cannot be bypassed with `contracts.change_status`.
4. Signed legal terms and items cannot be changed directly.
5. At most one suspension is open for a contract, enforced in service and database.
6. Resume/termination close suspension history correctly.
7. Signed addenda are immutable and apply contractual effects exactly once.
8. Effective amount equals active item total plus active signed addendum deltas and never becomes negative.
9. Original deadline is preserved separately from effective deadline.
10. Deadline extension through addendum requires a recorded reason.
11. Completion remains fail-closed until all mandatory readiness providers report success.
12. No rejected business command leaves partial state or an audit record.
13. Authorization scopes and anti-enumeration behavior match existing contract security conventions.
14. Full backend regression suite, Ruff and Alembic checks are GREEN.
15. Integration branch is not merged or modified automatically; CP4.2 remains reviewable as a stacked change on CP4.1 until explicitly approved.

## 21. Deferred integration checklist

Stage 5 Tasks/Workflow must add:

- actual-work trigger into `mark_work_started()`;
- task readiness provider;
- suspension/resume deadline shifting;
- ordinary overdue-notification suppression/recalculation where notifications exist;
- termination cancellation of unfinished linked tasks.

Stage 6 Expertises must add:

- expertise actual-work trigger into `mark_work_started()` when expertise leaves preparation;
- expertise completion readiness provider.

Stage 8 Documents must add:

- optional `contract_addenda.document_id` linkage if still desired;
- required-documents readiness provider;
- conclusion-delivery readiness signal/provider.

These future integrations must extend the CP4.2 ports rather than weaken fail-closed readiness.

## 22. Branch/PR strategy

CP4.2 is a stacked checkpoint based on CP4.1 head `fa11c71726cea0fb92ed6f1df777456ab0ab830c`.

Working branch: `agent/stage4-cp42-contract-lifecycle-addenda`.

During implementation/review, do not merge CP4.2 or CP4.1 into `codex/feat-gigastudio-frontend-integration` automatically. Any later PR should remain draft/review-oriented until the user explicitly requests integration.
