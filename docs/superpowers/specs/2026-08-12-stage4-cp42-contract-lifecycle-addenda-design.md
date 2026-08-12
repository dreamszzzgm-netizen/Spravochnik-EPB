# Stage 4 CP4.2 — Contract Lifecycle, Suspensions, Completion Readiness and Addenda

Date: 2026-08-12
Status: Approved design
Base checkpoint: CP4.1 Contracts Core (`fa11c71726cea0fb92ed6f1df777456ab0ab830c`)
Working branch: `agent/stage4-cp42-contract-lifecycle-addenda`

## 1. Goal

Complete the Stage 4 contract-domain lifecycle that can be implemented safely before Tasks, Expertises and Documents exist. CP4.2 adds the contract state machine, suspension/resume history, termination/completion commands, completion-readiness infrastructure, additional agreements, signing-time immutability, effective amount/deadline application, authorization and audit behavior.

The design deliberately avoids fake cross-module behavior. Effects that require future Tasks, Expertises, Documents or Notifications are kept fail-closed or deferred to their owning stages.

## 2. Scope

CP4.2 includes:

- strict contract status transition rules;
- separate permissions for ordinary status changes, termination and completion;
- validation and freezing of legally significant terms when a contract is signed;
- one-open-suspension invariant and suspension history;
- resume closing the current suspension;
- termination with preserved history;
- completion-readiness aggregation that fails closed while required providers are unavailable;
- manual completion only after readiness succeeds;
- additional agreements with their own lifecycle;
- atomic application of signed addendum amount/deadline changes;
- preservation of the original signed deadline;
- effective amount recalculation from signed base items plus signed addendum deltas;
- authorization/scope enforcement using the existing contracts access policy;
- audit entries for accepted commands and no audit entries for rejected commands;
- migration, schemas/routes, service/repository changes and tests.

## 3. Non-goals

CP4.2 does not implement:

- Tasks models/routes/deadline recalculation/task cancellation;
- Expertise models or actual producer-side automatic-start triggers;
- Documents storage or addendum document attachment;
- Notifications;
- frontend contracts migration;
- automatic contract completion;
- a generic workflow engine;
- generic event sourcing.

## 4. Architectural approach

`app/modules/contracts` remains the owner of:

- contract statuses and transition validation;
- signing rules;
- suspensions;
- addenda;
- effective contract amount and deadline;
- completion-readiness orchestration;
- contract audit commands.

Contracts must not directly import future Tasks, Expertises or Documents modules in CP4.2.

The selected approach is a lifecycle foundation with fail-closed readiness boundaries. Two alternatives were rejected:

1. Defer lifecycle behavior to Stage 5 — this would leave Stage 4 materially incomplete.
2. Treat missing future dependencies as successful — this could allow a contract to complete without real tasks, expertises or documents.

## 5. Permission model

The approved permission split is authoritative:

- `contracts.change_status` — ordinary lifecycle transitions only;
- `contracts.terminate` — termination only;
- `contracts.complete` — completion only;
- `contracts.manage_addenda` — addendum CRUD/status commands;
- existing `contracts.edit`, `contracts.delete`, `contracts.restore`, `contracts.manage_items`, `contracts.manage_responsibles` retain their current meaning subject to lifecycle restrictions below.

Scope semantics remain ALL / ASSIGNED / RELATED / OWN through the existing contract access policy. Exact permission-name isolation remains mandatory.

For inaccessible, foreign, deleted or out-of-scope contract/addendum resources, nested endpoints must preserve the existing anti-enumeration behavior and return the same not-found response where applicable.

## 6. Contract state machine

Allowed primary transitions:

- `draft -> approval` — `contracts.change_status`;
- `approval -> signed` — `contracts.change_status`;
- `signed -> in_progress` — internal `mark_work_started()` only;
- `in_progress -> suspended` — `contracts.change_status`, mandatory reason;
- `suspended -> in_progress` — `contracts.change_status`;
- `in_progress -> completed` — `contracts.complete` plus successful readiness;
- `signed -> terminated` — `contracts.terminate`, mandatory reason;
- `in_progress -> terminated` — `contracts.terminate`, mandatory reason;
- `suspended -> terminated` — `contracts.terminate`, mandatory reason;
- `completed -> archived` — `contracts.change_status`;
- `terminated -> archived` — `contracts.change_status`.

All other direct transitions are rejected. `completed`, `terminated` and `archived` are non-reversible in v1.

### 6.1 Signing prerequisites

`approval -> signed` is allowed only when all of the following are true:

- `start_date` is present;
- `end_date` is present;
- date constraints are valid;
- at least one active contract item exists;
- at least one contract responsible exists;
- effective amount recalculation succeeds and does not produce a negative amount.

The contract may have a zero amount because no positive-minimum rule has been approved.

On successful signing:

- `original_end_date` is set from current `end_date` exactly once;
- the active item composition and item commercial fields become the immutable signed base;
- an audit record is written in the same transaction.

### 6.2 Actual-work start boundary

The business rule says a signed contract starts when actual work begins, such as a linked task moving to in-progress or an expertise leaving preparation.

CP4.2 provides an internal contracts service/domain command `mark_work_started(contract_id, actor/context)` that accepts only a currently `signed` contract and performs `signed -> in_progress`. It is not exposed as a public manual status endpoint.

Stage 5/6 will invoke this command from real producer events. Creating an expertise in preparation alone must not start the contract.

## 7. Legal immutability after signing

Before signing, contract data can be edited according to existing permission and validation rules.

After signing, direct edits are prohibited for:

- customer organization;
- customer contact;
- contract number;
- contract date;
- start date;
- original deadline;
- effective `end_date` through normal contract PATCH;
- currency;
- contract item membership;
- contract item price, expertise type, linked subject/object set and other commercial item fields.

Post-signing amount or deadline changes occur only through signed addenda.

Responsible employees may be changed while the contract is `signed`, `in_progress` or `suspended`. They are frozen in `completed`, `terminated` and `archived`.

The operational contract comment may be edited until `archived`; it is not treated as a contractual term.

Soft-delete of a contract is allowed only in `draft` or `approval`. A signed contract must use lifecycle actions rather than deletion.

## 8. Data model changes

### 8.1 Contract addition

Add to `contracts`:

- `original_end_date DATE NULL`.

Rules:

- draft/approval rows may keep it null;
- on signing it is initialized from current `end_date` exactly once;
- for any pre-existing row already in a post-signing status during migration, backfill it from `end_date`;
- after initialization it never changes;
- `end_date` is the current effective contractual deadline.

No base-amount column is needed because the signed base amount is reconstructible from immutable signed contract items. `contracts.amount` remains the materialized effective amount.

### 8.2 `contract_suspensions`

Create:

- `id UUID PK`;
- `contract_id UUID FK contracts(id) NOT NULL`;
- `started_at TIMESTAMPTZ NOT NULL`;
- `ended_at TIMESTAMPTZ NULL`;
- `reason TEXT NOT NULL`;
- `created_by UUID FK users(id) NOT NULL`;
- `created_at TIMESTAMPTZ NOT NULL`.

Invariant: at most one row per contract with `ended_at IS NULL`.

Enforce the invariant both in service logic and with a PostgreSQL partial unique index on `contract_id WHERE ended_at IS NULL`.

### 8.3 `contract_addenda`

Create:

- `id UUID PK`;
- `contract_id UUID FK contracts(id) NOT NULL`;
- `number VARCHAR(120) NOT NULL`;
- `addendum_date DATE NOT NULL`;
- `status contract_addendum_status NOT NULL`;
- `amount_delta NUMERIC(14,2) NULL`;
- `currency VARCHAR(3) NOT NULL`;
- `new_end_date DATE NULL`;
- `description TEXT NULL`;
- `signed_at TIMESTAMPTZ NULL`;
- `created_by UUID FK users(id) NOT NULL`;
- `updated_by UUID FK users(id) NOT NULL`;
- `created_at TIMESTAMPTZ NOT NULL`;
- `updated_at TIMESTAMPTZ NOT NULL`;
- `deleted_at TIMESTAMPTZ NULL`;
- `version INTEGER NOT NULL`.

`contract_addendum_status` values:

- `draft`;
- `approval`;
- `signed`;
- `cancelled`.

When an addendum is created, omitted currency is copied from its parent contract. No currency conversion exists in CP4.2.

No `document_id` is created in CP4.2 because the Documents module does not exist. Stage 8 may add a nullable FK later.

## 9. Addendum parent-status rules

An addendum may be created only for a contract in:

- `signed`;
- `in_progress`;
- `suspended`.

No new addendum may be created for `draft`, `approval`, `completed`, `terminated` or `archived` contracts.

An existing draft/approval addendum may be edited or soft-deleted only while the parent contract remains `signed`, `in_progress` or `suspended`.

A parent contract must still be in `signed`, `in_progress` or `suspended` when an addendum is signed. If the parent became terminal before signing, the command is rejected.

## 10. Addendum state machine

Allowed transitions:

- `draft -> approval`;
- `approval -> signed`;
- `draft -> cancelled`;
- `approval -> cancelled`.

`signed` and `cancelled` are terminal in v1.

Only `draft` and `approval` addenda may be edited or soft-deleted. `signed` and `cancelled` rows are immutable and retained as business history.

A signed addendum cannot be cancelled retroactively. A correction is represented by another addendum.

An addendum may contain an amount change, an end-date change, or both. An addendum with neither a non-zero `amount_delta` nor a `new_end_date` is not signable.

`amount_delta` may be positive or negative, but signing must never produce a negative effective contract amount.

Addendum currency must equal contract currency.

If `new_end_date` is set, it must not precede `start_date` when `start_date` exists.

If `new_end_date` extends the current effective `end_date`, non-empty `description` is mandatory and serves as the recorded reason for the extension.

### 10.1 Atomic signing/application

On `approval -> signed`, one database transaction must:

1. reload/lock the target contract and addendum using the project's repository/concurrency convention;
2. revalidate contract/addendum status, authorization, parent status, currency and resulting values;
3. set `signed_at` exactly once;
4. set addendum status to `signed`;
5. update `contracts.end_date` when `new_end_date` is present;
6. recalculate `contracts.amount` using the authoritative formula;
7. increment applicable versions/timestamps;
8. write audit entries;
9. commit.

Any failure rolls the entire transaction back. Retrying an already-signed addendum must not double-apply its effect.

## 11. Effective amount

Authoritative formula:

`effective_amount = sum(price of active contract_items) + sum(amount_delta of active signed contract_addenda)`

`contracts.amount` is a materialized value maintained by one shared recalculation service path.

The same recalculation path is used by:

- pre-sign item add/update/delete/restore;
- initial signing validation;
- addendum signing;
- any future explicitly approved correction operation.

Because item mutations are prohibited after signing, the original signed commercial basis stays reconstructible.

The resulting amount must be `>= 0`.

## 12. Deadline history and reconstruction

`original_end_date` preserves the deadline at initial signing. `contracts.end_date` stores the current effective deadline.

Every signed addendum retains `new_end_date` and `signed_at`. Deadline history is reconstructed from `original_end_date` by applying signed addenda ordered by `signed_at`, then UUID as a stable tie-breaker.

Signed addenda are immutable, making the chain stable.

## 13. Suspension and resume

### 13.1 Suspend

`POST /api/contracts/{id}/suspend` requires:

- contract status `in_progress`;
- scoped `contracts.change_status`;
- non-empty reason;
- no open suspension.

One transaction:

- creates `ContractSuspension(started_at=now, reason=...)`;
- changes status to `suspended`;
- writes audit;
- commits.

### 13.2 Resume

`POST /api/contracts/{id}/resume` requires:

- contract status `suspended`;
- scoped `contracts.change_status`;
- exactly one open suspension.

One transaction:

- closes the open suspension with `ended_at=now`;
- changes status to `in_progress`;
- writes audit;
- commits.

The closed suspension provides the authoritative pause interval. Stage 5 and the future notifications implementation will consume that interval to shift unfinished task deadlines and recalculate/suppress notifications. CP4.2 does not create placeholder task/notification effects.

## 14. Termination

`POST /api/contracts/{id}/terminate` requires:

- status `signed`, `in_progress` or `suspended`;
- scoped `contracts.terminate`;
- non-empty reason.

The reason is persisted in audit metadata in the same transaction as the status change.

If termination occurs from `suspended`, the open suspension is closed at termination time.

Stage 5 must later add cancellation of unfinished linked tasks. Contract/expertise/document/history data is preserved.

## 15. Completion readiness

Completion is never automatic.

Expose:

- `GET /api/contracts/{id}/completion-readiness`;
- `POST /api/contracts/{id}/complete`.

Readiness response contains:

- `ready_to_complete: bool`;
- `checks: list[CompletionCheck]`;
- `blockers: list[CompletionBlocker]` with stable machine-readable codes and user-readable details.

Required check keys:

- `tasks` — mandatory tasks done/cancelled;
- `expertises` — mandatory expertises completed;
- `documents` — required documents generated;
- `conclusion_delivery` — conclusions delivered to customer.

### 15.1 Provider boundary

Contracts owns a `CompletionReadinessProvider` boundary. Each provider has a stable key and returns a structured check result for one contract. The contracts service aggregates exactly the four required keys above.

The application composition root supplies the provider registry. Until an owning future module supplies a real provider, that key uses an explicit unavailable provider that returns a blocker, never success.

Stable unavailable blocker codes:

- `tasks_provider_unavailable`;
- `expertises_provider_unavailable`;
- `documents_provider_unavailable`;
- `conclusion_delivery_provider_unavailable`.

Therefore normal CP4.2 production readiness is `false` until the future modules are integrated.

`POST /complete` requires scoped `contracts.complete`, reruns readiness server-side inside the completion command, and rejects completion if any blocker exists. It never trusts a previous client-side readiness result.

Tests may inject deterministic satisfied providers to prove the completion transition itself works.

## 16. Future integration boundaries

CP4.2 implements only boundaries needed now:

- inbound internal `mark_work_started()` for future Tasks/Expertises producers;
- completion-readiness provider registry with fail-closed unavailable providers;
- authoritative suspension intervals persisted for future deadline/notification logic.

CP4.2 does **not** add empty no-op hooks for future task cancellation or notification recalculation. Stage 5/notifications integration will coordinate those side effects when real consumers exist. This keeps YAGNI and avoids pretending an absent side effect occurred.

## 17. API surface

Existing CP4.1 contract CRUD/item/responsible endpoints remain, with lifecycle restrictions enforced in the service.

New contract command endpoints:

- `POST /api/contracts/{id}/status` — ordinary allowed transitions (`draft -> approval`, `approval -> signed`, `completed|terminated -> archived`);
- `POST /api/contracts/{id}/suspend`;
- `POST /api/contracts/{id}/resume`;
- `POST /api/contracts/{id}/terminate`;
- `GET /api/contracts/{id}/completion-readiness`;
- `POST /api/contracts/{id}/complete`.

`mark_work_started()` is internal only and has no CP4.2 public route.

Addenda endpoints:

- `GET /api/contracts/{id}/addenda`;
- `POST /api/contracts/{id}/addenda`;
- `GET /api/contracts/{id}/addenda/{addendum_id}`;
- `PATCH /api/contracts/{id}/addenda/{addendum_id}`;
- `DELETE /api/contracts/{id}/addenda/{addendum_id}` for draft/approval soft deletion only;
- `POST /api/contracts/{id}/addenda/{addendum_id}/status` for the allowed addendum transitions.

Contract/addendum status fields are not writable through ordinary PATCH schemas.

## 18. Error and transaction behavior

Business-rule violations use the project's existing domain/API error mapping and must not partially mutate state.

Representative rejected cases:

- invalid transition;
- wrong dedicated permission;
- public/manual `signed -> in_progress`;
- signing without required dates/items/responsible;
- status mutation through ordinary PATCH;
- suspend without reason;
- second open suspension;
- resume without open suspension;
- signed item mutation;
- addendum on an invalid parent status;
- invalid addendum transition;
- signing an effectless addendum;
- currency mismatch;
- negative resulting amount;
- invalid deadline;
- deadline extension without reason;
- completion with blockers.

Rejected commands must:

- roll back all mutations;
- create no audit entry;
- not increment versions merely because an attempt was rejected.

Successful multi-record commands commit atomically with audit.

## 19. Audit behavior

Audit events are required for:

- ordinary contract status transition;
- contract signing;
- suspend;
- resume;
- termination including reason;
- completion;
- archive;
- addendum create/update/delete;
- addendum status transition;
- signed addendum effect application.

Audit metadata records stable IDs and relevant before/after business values without copying unnecessary sensitive payloads.

Rejected commands create no audit record.

## 20. Test strategy

Implementation follows TDD: representative RED tests are written/run before production changes, then the smallest implementation makes them GREEN.

### 20.1 Migration/model tests

Verify:

- upgrade from `0011_stage4_contracts_core`;
- exactly one Alembic head;
- `original_end_date` and required backfill behavior;
- suspension/addendum tables and enum;
- one-open-suspension partial unique index at DB level;
- repository-standard upgrade/downgrade behavior.

### 20.2 State-machine and permission tests

Cover every allowed transition plus representative forbidden transitions.

Explicitly verify:

- `contracts.change_status` cannot terminate or complete;
- `contracts.terminate` cannot do ordinary transitions or completion;
- `contracts.complete` cannot terminate or do ordinary transitions;
- public API cannot manually perform `signed -> in_progress`;
- internal work-start accepts only `signed`;
- terminal statuses cannot reopen.

### 20.3 Signing/immutability tests

Verify:

- signing rejects missing start/end dates, items or responsibles;
- signing initializes `original_end_date` exactly once;
- post-sign legal-field edits are rejected;
- post-sign item create/update/delete/restore are rejected;
- responsibles remain editable only in allowed active statuses;
- signed contract cannot be soft-deleted.

### 20.4 Suspension/resume tests

Verify:

- suspend requires reason;
- suspension creates open history atomically;
- second open suspension is rejected;
- DB index independently protects the invariant;
- resume closes the open row and returns to in-progress;
- resume without open suspension is rejected;
- termination from suspended closes the open suspension.

### 20.5 Addendum tests

Verify:

- create/edit/delete/status permission and scope isolation;
- parent-status rules;
- allowed/forbidden addendum transitions;
- terminal addenda immutable;
- signed/cancelled addenda cannot be deleted;
- effectless addendum cannot be signed;
- currency mismatch rejected;
- deadline extension without description rejected;
- invalid shortened deadline rejected;
- signing applies amount/deadline atomically;
- retry cannot double-apply;
- negative resulting amount rolls back;
- multiple deltas produce correct materialized amount;
- multiple deadline changes preserve original deadline and deterministic history.

### 20.6 Completion-readiness tests

Verify:

- unavailable required providers produce stable blockers;
- default CP4.2 readiness is false;
- `contracts.complete` is independently required;
- completion reruns readiness server-side;
- completion with blockers leaves status/audit unchanged;
- injected satisfied providers allow `in_progress -> completed`;
- archive only from completed/terminated.

### 20.7 Authorization/anti-enumeration tests

For each new endpoint verify:

- ALL/ASSIGNED/RELATED/OWN behavior through existing contract access rules;
- exact permission isolation;
- foreign/out-of-scope indistinguishability;
- nested addendum access cannot bypass parent contract scope.

### 20.8 Audit/rollback tests

Verify successful commands create expected audit entries; rejected transition/addendum/readiness commands create none; atomic failures leave contract/addendum/suspension state unchanged.

### 20.9 Regression tests

Run full backend pytest, Ruff and Alembic checks. CP4.1 behavior remains GREEN for contracts that stay in the pre-sign lifecycle.

## 21. Acceptance criteria

CP4.2 is accepted only when:

1. Migration upgrades cleanly from CP4.1 and Alembic has one head.
2. Lifecycle transitions match this spec exactly.
3. Dedicated completion/termination permissions cannot be bypassed with `contracts.change_status`.
4. Signing prerequisites are enforced atomically.
5. Signed legal terms and items cannot be changed directly.
6. At most one suspension is open, enforced in service and DB.
7. Resume/termination close suspension history correctly.
8. Addenda can exist only on eligible signed/active parent contracts.
9. Signed/cancelled addenda are immutable; signed effects apply exactly once.
10. Effective amount equals active signed-base item total plus active signed addendum deltas and never becomes negative.
11. Original deadline is preserved separately from effective deadline.
12. Deadline extension requires a recorded reason.
13. Completion remains fail-closed until all four mandatory readiness providers succeed.
14. Rejected commands leave no partial state, audit entry or spurious version increment.
15. Authorization scopes and anti-enumeration match existing contract security conventions.
16. Full backend regression suite, Ruff and Alembic checks are GREEN.
17. Integration branch is not merged or modified automatically; CP4.2 remains a stacked review checkpoint until explicit user approval.

## 22. Deferred integration checklist

Stage 5 Tasks/Workflow must add:

- actual-work trigger into `mark_work_started()`;
- `tasks` readiness provider;
- suspension/resume task-deadline shifting;
- termination cancellation of unfinished linked tasks;
- notification-related handling when the notification subsystem exists.

Stage 6 Expertises must add:

- expertise actual-work trigger into `mark_work_started()` when expertise leaves preparation;
- `expertises` readiness provider.

Stage 8 Documents must add:

- optional `contract_addenda.document_id` linkage if still required;
- `documents` readiness provider;
- `conclusion_delivery` readiness provider/signal.

Future integrations extend these boundaries rather than weakening fail-closed readiness.

## 23. Branch/PR strategy

CP4.2 is stacked on CP4.1 head `fa11c71726cea0fb92ed6f1df777456ab0ab830c`.

Working branch: `agent/stage4-cp42-contract-lifecycle-addenda`.

Do not merge CP4.2 or CP4.1 into `codex/feat-gigastudio-frontend-integration` automatically. Any CP4.2 PR stays draft/review-oriented until the user explicitly requests integration.
