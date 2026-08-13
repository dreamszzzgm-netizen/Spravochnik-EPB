# Organization Smart Import + Legal Form Fields Design

## Goal
Add a privacy-preserving organization requisites import and make organization data/form fields correctly depend on legal form without touching Stage 5 Workflow work.

## Boundary
This branch is based on CP5.1 `c7f6efbd16796f6ac207e5717045cc1bc3994d08` and must not merge/rebase from CP5.2.

## Data model
Add nullable `residence_address` (500 chars) and `passport_details` (text) to `organizations` by a new linear Alembic migration after `0013_stage5_tasks_core`.

Existing identifiers remain canonical: `inn`, `kpp`, `ogrn`, `ogrnip`.

Legal-form behavior:
- `legal_entity`: INN/KPP/OGRN, legal and actual address, director.
- `branch`: INN/KPP/OGRN, legal and actual address, director, existing parent link behavior unchanged.
- `individual_entrepreneur`: INN/OGRNIP, residence address, passport details. KPP/OGRN must not be sent by the create UI.

Backend remains tolerant of legacy records; this change does not destructively rewrite existing identifiers when merely reading an organization.

## Smart import flow
The first increment accepts pasted requisites text. It does not perform OCR and does not call any external AI.

`POST /api/organizations/import-preview`

Input: `{ "text": "..." }`.

Output contains a candidate organization payload, extracted identifier candidates, extraction confidence by field, and duplicate warnings. The endpoint performs no INSERT/UPDATE/DELETE.

Parsing is deterministic and local: normalize whitespace and common Russian labels, then extract INN/KPP/OGRN/OGRNIP, organization name, addresses, leader/IP name, phone and email where labels make the field sufficiently unambiguous.

The UI exposes an "Умный импорт" card on `/organizations/new`: user pastes requisites, requests preview, reviews the candidate, then presses "Применить к форме". Only that action copies values into client-side form state. Final persistence still happens through the existing Create Organization action.

## Security and privacy
No external network request is used by this feature. Passport details are never sent to an AI provider and are not written to logs. Preview is read-only with respect to business tables.

## Error handling
Empty/very short text is rejected with validation error. Unknown labels simply produce missing candidate fields plus warnings rather than guessed values. Duplicate identifiers are warnings, not automatic merges.

## Tests
TDD order:
1. parser/schema tests RED;
2. parser + schemas GREEN;
3. migration/API persistence tests;
4. preview no-write and duplicate-warning tests;
5. frontend legal-form helpers and smart-import UI tests;
6. full backend + frontend CI.