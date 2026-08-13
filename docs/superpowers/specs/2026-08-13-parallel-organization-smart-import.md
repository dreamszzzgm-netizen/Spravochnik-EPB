# Parallel feature — Organization Smart Import

## Status

Approved parallel scope for development while `agent/stage5-cp52-workflow-engine` is in progress.

Base commit: `c7f6efbd16796f6ac207e5717045cc1bc3994d08` (verified CP5.1 baseline).

This feature MUST NOT depend on unfinished CP5.2 workflow internals.

## Goal

Improve organization create/edit UX and add safe smart import so uploaded organization requisites are recognized, mapped to candidate fields, previewed, corrected by the user, and only then saved through the normal Organizations application/service layer.

## Functional scope

### 1. Dynamic organization form

Supported organization types remain:

- `legal_entity` — Юридическое лицо;
- `individual_entrepreneur` — Индивидуальный предприниматель;
- `branch` — Филиал.

The visible fields MUST change when organization type changes.

For a legal entity show at minimum:

- full/legal name;
- short name;
- INN;
- KPP;
- OGRN;
- legal address;
- actual address;
- director;
- phone;
- email.

For an individual entrepreneur show at minimum:

- name / full name of entrepreneur;
- INN;
- OGRNIP;
- residence address;
- passport data;
- phone;
- email.

KPP and OGRN MUST NOT be presented as normal IP fields. OGRNIP MUST NOT be presented as a normal legal-entity field.

Changing the selector in the client MUST NOT silently destroy values already typed in fields that become temporarily hidden.

### 2. Structured IP passport data

Do not store passport data as one opaque free-text string if schema changes are needed anyway.

Target structure:

- `residence_address`;
- `passport_series`;
- `passport_number`;
- `passport_issued_by`;
- `passport_issue_date`;
- `passport_department_code`.

Passport data are sensitive personal data. Never send raw passport values to an external AI provider.

### 3. Smart import

The organization create screen MUST expose an import action for organization/requisites documents.

Target accepted sources for staged implementation:

- PDF;
- DOCX;
- XLSX;
- JPG/PNG or scanned PDF when local OCR/recognition becomes available.

The architecture MUST follow:

`upload -> parse/extract -> normalize -> recognize/map -> candidate data -> validation -> preview -> user correction -> explicit confirmation -> normal organization create/update service`

Recognition/import MUST NOT write directly to organization tables.

### 4. Candidate model

Create a transport/domain-neutral candidate representation sufficient to populate the form. It should support at minimum:

- detected organization type;
- legal/full name;
- short name;
- INN;
- KPP;
- OGRN;
- OGRNIP;
- legal address;
- actual/residence address;
- director/entrepreneur name;
- phone;
- email;
- structured passport fields;
- per-field confidence/warnings where available.

The result MUST remain editable before persistence.

### 5. Privacy rule

Use deterministic/local parsers first. Local OCR/local AI may be added behind an abstraction. Raw passport/personal data MUST NOT be sent to external AI APIs.

No full imported document or full AI prompt/response should be logged to ordinary application logs.

## Backend validation

Server-side validation is mandatory; hiding fields in the UI is not sufficient.

Examples:

- `individual_entrepreneur`: OGRNIP is applicable; KPP is not required;
- `legal_entity`: OGRN/KPP are applicable; OGRNIP is not required;
- identifier uniqueness rules remain enforced;
- user confirmation is required before persistence of recognized values.

## Tests / acceptance

Minimum acceptance coverage:

1. create legal entity with existing fields remains green;
2. create IP with OGRNIP and residence/passport data;
3. update IP data;
4. organization type selector renders the correct field groups;
5. switching type does not silently erase client state;
6. import produces candidate data, not persisted organization rows;
7. candidate can populate the form and user can edit before save;
8. external-AI path is never used for passport data;
9. existing organization authorization/scoping tests remain green;
10. migrations have one valid Alembic head after integration.

## Parallel-development guardrails

Do NOT modify CP5.2 workflow modules, workflow templates, workflow task instantiation, or unfinished CP5.2 migrations.

If this feature needs an Alembic revision, create it only on this feature branch and expect migration-head reconciliation/rebase after CP5.2 is complete.

Prefer changes under:

- `app/modules/organizations/`;
- a new isolated import/recognition service/module if needed;
- `frontend/src/app/organizations/`;
- `frontend/src/lib/api/`;
- focused tests.
