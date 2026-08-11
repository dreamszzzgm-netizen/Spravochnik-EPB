# Stage 4 CP4.1 — Contracts Core Design

**Status:** IN DEVELOPMENT  
**Date:** 2026-08-11  
**Baseline:** `650008fc5a80eaf6165d2d0aba249041aae2a98d`  
**Branch:** `agent/stage4-cp41-contracts-core`

## 1. Goal

Create the first production-grade Contracts vertical slice on top of the official GREEN baseline without entering the Tasks, Expertises, Documents, or Addenda implementations prematurely.

CP4.1 establishes the contract aggregate, contract responsibles, contract items, concrete item subjects, amount recalculation, scoped authorization, audit events, and HTTP API. The existing mock frontend is intentionally not switched to the API in this checkpoint; frontend integration is a follow-up after the backend contract is independently GREEN.

## 2. Source-of-truth requirements

This design follows the current project documents:

- `docs/DATA_MODEL.md`: `contracts`, `contract_responsibles`, `contract_items`, `contract_item_technical_devices`, `contract_item_buildings`; amount is the sum of active items.
- `docs/BUSINESS_RULES.md`: contract contains one or more items; every item has at least one expertise subject; status is not an arbitrary UI string.
- `docs/PERMISSIONS.md`: `contracts.view/create/edit/delete/restore/manage_responsibles/manage_items` are backend-enforced permissions with scope.
- `docs/UI_MAP.md`: `/contracts` registry and `/contracts/{id}` card are the target UI contract.
- `docs/DEVELOPMENT_PLAN.md`: Stage 4 is the next major module after OPO / technical devices / buildings.

## 3. Checkpoint boundary

### In scope

1. PostgreSQL schema and SQLAlchemy models for:
   - `contracts`;
   - `contract_responsibles`;
   - `expertise_types` reference data required by contract items;
   - `contract_items`;
   - `contract_item_technical_devices`;
   - `contract_item_buildings`.
2. Contract CRUD with soft delete/restore.
3. Responsible employee replacement as one atomic operation.
4. Contract item create/update/soft-delete with concrete TD/building subject links.
5. Server-owned `amount` recalculation from active contract items.
6. Customer/contact integrity checks.
7. Date and money validation.
8. Permission + scope enforcement for contract reads/writes.
9. Separate view-permission checks before linking a technical device/building to an item, preventing UUID existence oracles across scopes.
10. Audit events for contract, responsible, and item mutations.
11. Integration and migration tests.

### Explicitly out of scope

- contract status transitions beyond the initial immutable `draft` state;
- suspension/resume and deadline shifting;
- termination and task cancellation;
- completion readiness checks;
- additional agreements;
- Tasks/Workflow integration;
- Expertise creation;
- Documents;
- frontend migration from mock contracts to API.

Those are CP4.2+ because they depend on modules that do not exist yet or deserve their own testable lifecycle checkpoint.

## 4. Domain model

### 4.1 Contract

Fields:

- `id: UUID`;
- `customer_organization_id: UUID`;
- `customer_contact_id: UUID | None`;
- `number: str`;
- `contract_date: date`;
- `start_date: date | None`;
- `end_date: date | None`;
- `amount: Decimal` — server-owned aggregate;
- `currency: str` — `RUB` in CP4.1;
- `status: ContractStatus` — always `draft` on create in CP4.1;
- `comment: str | None`;
- `created_by: UUID`;
- `created_at`, `updated_at`, `deleted_at`;
- `version: int`.

Validation:

- number is stripped and non-empty;
- if both dates exist, `start_date <= end_date`;
- customer organization must exist and not be deleted;
- optional customer contact must exist, not be deleted, and belong to the same customer organization;
- clients cannot set `amount`, `currency`, or `status` through CP4.1 create/update payloads.

### 4.2 Contract responsibles

`contract_responsibles(contract_id, employee_id, role_note)` with composite primary key.

Replacement rules:

- only active/non-deleted employees may be assigned;
- duplicate IDs are normalized by the service;
- the full replacement occurs in the same transaction as audit;
- the response is deterministic (employee IDs sorted for serialization/tests).

### 4.3 Expertise types

CP4.1 creates the reference table because `contract_items.expertise_type_id` is required by the approved data model. Initial deterministic seeds are:

- `technical_device_epb` — «ЭПБ технического устройства»;
- `building_epb` — «ЭПБ здания/сооружения».

The table is an extensible directory. CP4.1 does not pretend that this seed set already covers every future non-EPB service.

### 4.4 Contract items

Fields:

- `id`;
- `contract_id`;
- `name`;
- `expertise_type_id`;
- `price NUMERIC(14,2)`;
- `currency='RUB'`;
- `comment`;
- timestamps;
- `deleted_at`;
- `version`.

Each active item must contain at least one subject across:

- `contract_item_technical_devices`;
- `contract_item_buildings`.

A cross-table minimum cannot be expressed reliably with a simple CHECK constraint, so it is a service-layer invariant. Real FKs and unique composite PKs protect the actual references.

Price must be non-negative. Amount is recalculated after item create/update/delete in the same transaction:

`contract.amount = SUM(active contract_items.price)`.

## 5. Authorization model

All endpoints require authentication. Missing permission is `403`; an existing entity outside the current permission scope is indistinguishable from an absent UUID and returns `404`.

### Contract scope evaluation

For a given contract permission context:

- `ALL` → all contracts;
- `RELATED` → `customer_organization_id` is in `related_organization_ids`;
- `ASSIGNED` → `ctx.employee_id` is in `contract_responsibles`;
- `OWN` → `contract.created_by == ctx.user_id`;
- superuser → all.

List queries apply the same rule in SQL; item/detail routes use the same policy helper.

### Create rule

Creating a contract requires `contracts.create` and the customer organization must be referenceable by that exact permission context (`ALL` or `RELATED`). `ASSIGNED`/`OWN` alone cannot be used to guess or claim an unrelated customer organization at creation time.

### Subject-link rule

`contracts.manage_items` authorizes mutation of the contract, but does **not** grant implicit read access to every TD/building UUID.

Before a technical device is linked, the actor must also have `technical_devices.view` scope that can access it. Before a building is linked, the actor must also have `buildings.view` scope that can access it. A missing cross-resource view permission or foreign-scope subject returns the same `404` as an absent subject.

This preserves the Stage 3 fail-closed authorization invariant and prevents cross-scope UUID existence probing.

## 6. API contract

### Contracts

- `GET /api/contracts`
  - query: `q`, `page`, `page_size`, `customer_organization_id`, `status`;
  - response envelope: `{items,total,page,page_size}`.
- `POST /api/contracts`
  - creates `draft`, amount `0.00`, currency `RUB`.
- `GET /api/contracts/{contract_id}`.
- `PATCH /api/contracts/{contract_id}`
  - basic editable fields only; no amount/status mutation.
- `DELETE /api/contracts/{contract_id}`
  - soft delete.
- `POST /api/contracts/{contract_id}/restore`.

### Responsibles

- `PUT /api/contracts/{contract_id}/responsibles`
  - payload `{employee_ids: UUID[]}`;
  - permission `contracts.manage_responsibles`.

### Reference data

- `GET /api/reference/expertise-types`
  - authenticated, permission `contracts.view`;
  - active deterministic rows.

### Items

- `GET /api/contracts/{contract_id}/items`;
- `POST /api/contracts/{contract_id}/items`;
- `PATCH /api/contracts/{contract_id}/items/{item_id}`;
- `DELETE /api/contracts/{contract_id}/items/{item_id}`.

Create payload:

```json
{
  "name": "ЭПБ сосудов",
  "expertise_type_id": "uuid",
  "price": "125000.00",
  "comment": null,
  "technical_device_ids": ["uuid"],
  "building_ids": []
}
```

Update payload uses full replacement semantics for subject arrays when either subject field is supplied. The resulting item must still have at least one subject.

## 7. Transactions and audit

Service methods own transactions. A mutation and its audit event commit together.

Audit actions:

- `contract.created`;
- `contract.updated`;
- `contract.deleted`;
- `contract.restored`;
- `contract.responsibles_updated`;
- `contract_item.created`;
- `contract_item.updated`;
- `contract_item.deleted`.

If validation fails before commit, neither domain rows nor audit rows are persisted.

## 8. Migration design

New head: `0011_stage4_contracts_core`, parent `0010_stage3`.

Migration creates enum `contract_status`, tables, indexes, FKs, price/date checks, and deterministic expertise type seeds. Downgrade drops child tables first and then the enum/table in reverse dependency order.

`alembic/env.py` imports the Contracts models so metadata remains complete.

`tests/conftest.py` truncation list is expanded for Stage 4 tables and the session migration guard is advanced from `0010_stage3` to `0011_stage4_contracts_core` so downgrade/upgrade migration integrity remains exercised.

## 9. TDD and verification strategy

CP4.1 is executed with observable RED/GREEN commits through GitHub Actions because the current execution environment cannot reach the repository with local git.

1. Commit integration/migration tests **before** Contracts production code.
2. Push test-only commit and confirm Actions fails for the expected missing migration/module/API reason.
3. Implement the minimum production code.
4. Run Actions and targeted checks until GREEN.
5. Add authorization regression cases and repeat RED→GREEN if needed.
6. Final gate:
   - `ruff check app tests`;
   - `alembic upgrade head`;
   - full `pytest`;
   - single Alembic head `0011_stage4_contracts_core`;
   - compare against exact baseline;
   - no unrelated changes;
   - draft PR targeting `codex/feat-gigastudio-frontend-integration`;
   - **no merge**.

## 10. Acceptance criteria

CP4.1 is READY FOR VERIFICATION when all of the following are demonstrated:

1. Contract creation is draft-only and amount starts at zero.
2. Contact from another/deleted organization is rejected.
3. Contract dates are validated server-side.
4. List/detail enforce ALL/RELATED/ASSIGNED/OWN without scope borrowing.
5. Foreign and absent contract UUIDs are both 404.
6. Responsible replacement is atomic and permission-gated.
7. Every contract item has at least one real subject.
8. Cross-scope TD/building IDs cannot be linked or probed.
9. Item mutation recalculates contract amount exactly.
10. Soft-deleted items do not contribute to amount.
11. Contract soft delete/restore is permission-gated.
12. Audit events exist for successful mutations and no audit is written for rejected mutation.
13. Migration upgrade/downgrade/upgrade remains valid under the existing test harness.
14. Full backend regression and Ruff are GREEN on the exact PR head.
