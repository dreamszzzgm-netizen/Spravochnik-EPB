# Project status

## Current verified development baseline

- Official integration GREEN baseline: `650008fc5a80eaf6165d2d0aba249041aae2a98d`.
- Active checkpoint: **Stage 4 / CP4.1 — Contracts Core backend**.
- Feature branch: `agent/stage4-cp41-contracts-core`.
- Verified code head: `39dd6947e327e355ead14500f5965ac0fa5c32bb`.
- Alembic head: `0011_stage4_contracts_core`.
- Verification: GitHub Actions CI #94 — Ruff PASS, `alembic upgrade head` PASS, **440 passed**.

## Completed through CP4.1

- Stage 0 — application foundation.
- Stage 1 — identity, sessions, RBAC, permission scopes and audit foundation.
- Stage 2 — organizations and contacts.
- Stage 3 — OPO, technical devices, buildings, custom fields and scoped authorization closure.
- Stage 4 CP4.1 — Contracts Core backend:
  - contracts schema/ORM and deterministic expertise-type reference data;
  - contract create/read/update, soft delete and restore;
  - atomic responsible replacement;
  - contract items with real technical-device/building subject links;
  - exact Decimal amount recalculation from active items;
  - customer/contact, dates, money and subject invariants;
  - scoped ALL/RELATED/ASSIGNED/OWN authorization with non-enumerating 404 behavior;
  - separate `technical_devices.view` / `buildings.view` checks for cross-resource subject links;
  - operation-specific contract permissions without scope borrowing;
  - audit events and rollback behavior for contract/responsible/item mutations;
  - registry filters and paginated response envelope;
  - migration, service, authorization and HTTP regression coverage.

## CP4.1 boundary / deferred work

The following are intentionally **not** part of CP4.1 and remain for later checkpoints:

- contract lifecycle transitions beyond initial `draft`;
- suspension/resume/termination/completion readiness;
- additional agreements;
- Tasks/Workflow integration;
- Expertise creation;
- Documents integration;
- frontend migration of Contracts from mock data to the backend API.

## Integration policy

CP4.1 is developed and verified on its feature branch. It is prepared for review as a draft pull request only. **Do not merge into `integration` as part of the checkpoint implementation session.**
