# Project status

## Current verified development baseline

- Official integration GREEN baseline: `650008fc5a80eaf6165d2d0aba249041aae2a98d`.
- Stacked parent checkpoint: **Stage 4 / CP4.1 — Contracts Core backend**, HEAD `fa11c71726cea0fb92ed6f1df777456ab0ab830c`.
- Active checkpoint: **Stage 4 / CP4.2 — Contract Lifecycle and Addenda backend**.
- Feature branch: `agent/stage4-cp42-contract-lifecycle-addenda`.
- Verified implementation head before final documentation/review fixes: `bd4fd1e2aeffc32c71c172da9220f13bc065102c`.
- Alembic head: `0012_stage4_contract_lifecycle` (`alembic/versions/0012_stage4_contract_lifecycle_addenda.py`).
- Verification at that head: GitHub Actions run `31587099510` — Ruff PASS, `alembic upgrade head` PASS, **498 passed / 275 warnings**.

## Completed through CP4.2

- Stage 0 — application foundation.
- Stage 1 — identity, sessions, RBAC, permission scopes and audit foundation.
- Stage 2 — organizations and contacts.
- Stage 3 — OPO, technical devices, buildings, custom fields and scoped authorization closure.
- Stage 4 CP4.1 — Contracts Core backend:
  - contracts schema/ORM and deterministic expertise-type reference data;
  - contract create/read/update, soft delete and restore;
  - atomic responsible replacement;
  - contract items with real technical-device/building subject links;
  - Decimal amount calculation;
  - scoped ALL/RELATED/ASSIGNED/OWN authorization and non-enumerating 404 behavior;
  - audit and rollback coverage.
- Stage 4 CP4.2 — Contract Lifecycle and Addenda backend:
  - contract state machine with `draft -> approval -> signed`, internal-only work start, suspend/resume, terminate, complete and archive transitions;
  - signing prerequisites: start/end dates, at least one active item, at least one responsible;
  - immutable `original_end_date` captured at signing;
  - post-signing legal-term and contract-item immutability;
  - contract suspension history with mandatory reason and PostgreSQL partial unique index enforcing one open interval;
  - termination with mandatory reason and closure of an open suspension;
  - fail-closed completion readiness through explicit Tasks/Expertises/Documents/conclusion-delivery providers;
  - manual completion only with `contracts.complete` and fresh server-side readiness;
  - additional agreements with `draft/approval/signed/cancelled` lifecycle and signed/cancelled immutability;
  - effective amount = active contract-item total + signed addendum deltas;
  - signed addenda may change effective deadline while preserving `original_end_date`;
  - deadline extension requires a business reason; projected negative contract amount is rejected atomically;
  - dedicated permissions: ordinary status changes, termination, completion and addenda management are isolated;
  - command API endpoints for lifecycle/readiness/addenda with existing ALL/RELATED/ASSIGNED/OWN scopes and non-enumerating nested 404 behavior;
  - migration round-trip `0012 -> 0011 -> 0012` verified in integration tests.

## CP4.2 boundary / deferred cross-module work

The following effects are intentionally deferred to the owning later stages rather than faked in CP4.2:

- Stage 5 Tasks/Workflow: actual task creation, deadline pause/shift on suspension/resume, unfinished-task cancellation on termination, work-start producer integration;
- Stage 6 Expertises: expertise work-start producer and real expertise readiness provider;
- Stage 8 Documents: real document readiness provider and optional addendum document link;
- later Notifications: suspension-aware overdue suppression and recalculation;
- conclusion-delivery provider when the expertise/document delivery workflow exists;
- frontend migration of Contracts from mock data to the backend lifecycle/addenda API.

Until those providers are connected, completion readiness deliberately returns blockers and `ready_to_complete=false`.

## Integration policy

CP4.2 is developed as a stacked checkpoint on top of CP4.1 and is prepared for review as a **draft** pull request only. **Do not merge CP4.2 into `codex/feat-gigastudio-frontend-integration` automatically.** Integration remains untouched until explicit user approval.
