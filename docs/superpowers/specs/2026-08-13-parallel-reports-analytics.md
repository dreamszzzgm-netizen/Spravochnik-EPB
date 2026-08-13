# Parallel feature — Reports & Management Analytics

## Status

Approved parallel scope for development while `agent/stage5-cp52-workflow-engine` is in progress.

Base commit: `c7f6efbd16796f6ac207e5717045cc1bc3994d08` (verified CP5.1 baseline).

This feature MUST NOT depend on unfinished CP5.2 workflow internals.

## Goal

Turn the existing `/reports` navigation placeholder into a real management reporting module that reads operational data and highlights items requiring attention.

Analytics is read-oriented: it is not a second source of business truth and must not duplicate domain state.

## Initial report areas

### 1. Contracts

- total;
- active;
- completed;
- terminated;
- ending soon;
- total contract value where data is available;
- filtering by period, organization and responsible employee where supported.

### 2. Expertises

Use only already-implemented expertise data. Do not invent CP5.2 workflow metrics.

Planned metrics include:

- total;
- in progress;
- on RTN review;
- registered;
- rejected;
- completed.

Where the backend does not yet expose a required entity, the UI must show an honest unavailable/empty state rather than fake production values.

### 3. Tasks

Use CP5.1 task data only for the parallel implementation:

- total;
- new;
- in progress;
- completed;
- cancelled;
- overdue as computed state;
- breakdown by assignee/priority when existing data supports it.

Do NOT add workflow-template efficiency metrics until CP5.2 is complete.

### 4. Organizations

- organizations created in period;
- activity by contracts/expertises when supported;
- list of organizations requiring document attention.

## Management document control

A dedicated `Document Control` section MUST be present in the management report.

Required states:

- expired;
- expiring within 14 days;
- expiring within 15–40 days;
- valid;
- missing/not uploaded;
- uploaded but expiration date not specified when the document type requires expiry control.

Every summary count should be drillable to the underlying organizations/documents where routing/data support it.

### Missing document semantics

`missing` cannot be derived merely from the absence of a row. The system needs an explicit completeness rule describing which document types are expected/applicable to an organization.

Design a small completeness service/rule layer that can later be reused by:

- reports;
- organization card;
- notifications.

The first implementation should support configurable/applicable requirements conceptually such as:

- required for all organizations;
- required only when an organization has an OPO;
- required for owner/operator role where such relation is available;
- optional.

Do not hard-code business assumptions into report rendering components.

## UI

Implement `/reports` in the existing Next.js/shadcn design system.

Suggested first screen:

- period filters;
- organization filter where available;
- management KPI cards;
- document-control KPI block;
- tables/lists for items requiring attention;
- clear empty/loading/error states;
- links to source entities when a route exists.

The existing design tokens, accessibility patterns, responsive layout and AppShell MUST be preserved.

## Export

Architect the report dataset so screen rendering is not the only consumer.

Target outputs later/when dependencies permit:

- print;
- PDF;
- XLSX.

Do not create separate business queries per output format. Prefer a common report/service dataset.

## Tests / acceptance

Minimum acceptance coverage:

1. `/reports` no longer routes to 404;
2. navigation opens the reports page;
3. summary calculations are deterministic for a fixed dataset;
4. overdue/expiring document boundary rules are tested;
5. missing-document result comes from completeness requirements, not guessed absence;
6. report does not mutate domain data;
7. links from attention lists lead to valid source routes when present;
8. mobile/responsive and accessibility patterns remain consistent;
9. no dependency on CP5.2 workflow tables/services;
10. existing frontend/backend test suites remain green after integration.

## Parallel-development guardrails

Do NOT modify workflow-engine internals, workflow templates, workflow-instantiated tasks or CP5.2 migrations.

Prefer changes under:

- a new isolated analytics/report backend module/service;
- `frontend/src/app/reports/`;
- focused reusable report components;
- existing navigation only where needed to activate the route;
- focused tests.

If document persistence/completeness tables are not yet present in the verified baseline, isolate the rule/service contract first and avoid inventing fake persistent data structures that conflict with the future Documents module.
