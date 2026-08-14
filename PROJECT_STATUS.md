# Project status

**Last synchronized:** 2026-08-14  
**Roadmap basis:** `DEVELOPMENT_PLAN.md` v2.0 (2026-08-13), `ARCHITECTURE Spravoshnik EPB.md`, `README_Spravochnik.md`, approved Stage 7 design/plan.

## 1. Current development baseline

### Canonical integration

- Canonical integration branch: `agent/integration-cp52-smart-import-hardening`.
- Current canonical HEAD: `14b85a2587532566800a0c45b48c59f1fee12225`.
- Latest canonical merge: PR #19 — **Organizations 2.0 + Smart Import (CP-N1..N3)**.
- Canonical Alembic head: `0020_identifier_constraints`.
- Canonical contains:
  - Stage 0 application foundation;
  - Stage 1 identity / sessions / RBAC / scoped permissions / audit foundation;
  - Stage 2 organizations / contacts;
  - Stage 3 OPO / Technical Devices / Buildings / custom fields / authorization closure;
  - Stage 4 Contracts Core + Contract Lifecycle/Addenda;
  - Stage 5 Tasks Core + Workflow Engine;
  - Organization Smart Import base + hardening;
  - Reports + Organization Documents + Document Completeness;
  - Expertise Core CP6.1;
  - Organizations 2.0 + persistent ImportSession/ImportCandidate workflow CP-N1..N3.

### Active implementation checkpoint

- Active checkpoint: **Stage 7 / CP7.1 — Universal Documents Core**.
- Active branch: `agent/stage7-cp71-universal-documents`.
- Active HEAD before this status update: `8bbb1c11ad3e097ca2a38bc61dd661ea13480de3`.
- Branch relation to canonical: **ahead only**, merge-base equals canonical HEAD `14b85a2`; no canonical commits are missing from the CP7.1 branch.
- Current Alembic head on CP7.1: `0021_universal_documents`.

### Latest CP7.1 verification

GitHub Actions run `31830131769` on HEAD `8bbb1c11ad3e097ca2a38bc61dd661ea13480de3`:

- `ruff check app tests` — **PASS**;
- single Alembic head check — **PASS** (`0021_universal_documents`);
- `alembic upgrade head` — **PASS**;
- backend pytest — **704 passed / 0 failed / 300 warnings**;
- PostgreSQL 17 test service — **PASS**.

The workflow is still temporarily named/implemented as a diagnostic `pytest -x --tb=short` gate. The full suite passed, but before declaring CP7.1 complete the workflow must be restored to the normal CI form and re-run on the final HEAD.

---

## 2. Roadmap status — DEVELOPMENT_PLAN v2.0

### CP5.2 — Workflow Engine core

**Status: COMPLETE / integrated into canonical.**

Implemented:

- logical workflow templates with stable codes;
- numbered versions and explicit publication;
- ordered task templates;
- business-function assignee selection;
- relative due dates through injected resolver;
- priority / order / required flag;
- provenance from created task to workflow version/task template;
- atomic instantiation;
- duplicate-safe workflow behavior;
- backend permission `workflows.manage`;
- audit coverage;
- migration/service/transaction/API/security tests.

Still intentionally deferred outside CP5.2:

- frontend workflow-management UI;
- notifications/mentions;
- WorkingCalendarService implementation;
- document attachments;
- CP5.3 Contract ↔ Tasks lifecycle integration.

### CP-N1 / PR1 — Organization Types & Conditional Fields

**Status: COMPLETE / merged via PR #19.**

Implemented:

- `LEGAL_ENTITY`, `SOLE_PROPRIETOR`, `BRANCH`;
- legal-form-aware validation;
- branch parent organization relation;
- IP-specific OGRNIP / residence / passport fields;
- legal-entity/branch-specific OGRN/KPP behavior;
- bank details;
- organization completeness assessment/UI;
- identifier constraints for head organizations and branches;
- backend/frontend regression coverage.

### CP-N2 / PR2 — ImportSession + Organization Excel Preview

**Status: COMPLETE / merged via PR #19.**

Implemented:

- persistent `ImportSession` / candidates;
- XLSX batch parser;
- Russian header/synonym normalization;
- identifier normalization;
- candidate validation;
- duplicate/conflict classification;
- preview before persistence;
- non-destructive handling of ambiguous INN-only matches;
- deterministic branch matching by INN + KPP.

### CP-N3 / PR2 — Confirmed Organization Import + Import Report

**Status: COMPLETE / merged via PR #19.**

Implemented:

- explicit user confirmation;
- create/update decisions;
- conflict decisions;
- transactional apply;
- persistent import report;
- audit;
- repeat-import duplicate hardening.

### PR3 — Recognition / Smart Fill

**Status: PARTIAL.**

Implemented:

- local organization requisites parsing / OCR adapter;
- read-only preview before normal domain save;
- PDF/image processing support in the local recognition path;
- no direct write from recognition into working organization tables.

Not yet complete relative to DEVELOPMENT_PLAN v2.0:

- full generalized Recognition subsystem for all declared formats/types;
- confidence model and field-level uncertainty UX as a complete product flow;
- expansion to OPO data, Technical Device passports and contracts;
- fully productized local OCR runtime/deployment validation;
- AI Gateway policy integration for optional external recognition.

### PR4 / CP-N4 — Documents & Compliance Control

**Status: ACTIVE / substantially implemented, not yet closed.**

Already merged in canonical (PR #16):

- organization-scoped document workspace;
- local private file storage;
- upload/download/soft delete;
- checksum and size metadata;
- administrator-managed document completeness requirements;
- applicability `all` / `has_opo`;
- missing/expired/expiring/no-expiry calculations;
- management-report integration.

Implemented on active CP7.1 branch:

- universal logical `Document`;
- immutable `DocumentVersion` records;
- `DocumentLink` with real typed FKs;
- supported targets: Organization, OPO, Technical Device, Building, Contract, Expertise, Task;
- one physical file/logical document can have multiple business links without binary duplication;
- lossless migration from legacy `organization_documents` to universal documents;
- guarded fail-closed downgrade when universal state cannot be represented losslessly;
- current-version ownership constraints;
- optimistic metadata locking;
- soft delete and restore;
- audit for document lifecycle and link operations;
- scope-aware document access with anti-enumeration behavior;
- immutable file-version creation;
- streaming upload size enforcement (20 MiB);
- MIME/extension policy;
- atomic local-file promotion and cleanup on failed DB operations;
- compatibility facade preserving Organization Documents API/UX;
- management-report repository migrated away from legacy `OrganizationDocument` dependency;
- dedicated migration/repository/service/security/HTTP/storage tests.

Still required before PR4 / CP-N4 can be called complete:

1. restore normal CI workflow and run final full backend gate;
2. create CP7.1 completion review;
3. update final diff review / remove any diagnostic-only CI changes;
4. open Draft PR `agent/stage7-cp71-universal-documents -> agent/integration-cp52-smart-import-hardening`;
5. merge only after review/approval;
6. finish configurable **Document Types** as a first-class settings model (scope, date/expiry requirements, allowed formats, required flag, ordering and applicability rules);
7. unify validity policy to the DEVELOPMENT_PLAN intervals and statuses required by CP-N4;
8. complete Compliance Engine beyond the current organization-level required-document rules.

### PR5 / CP-N5 — Management Reports

**Status: PARTIAL / working foundation exists.**

Implemented:

- real `/api/reports/management` data source;
- real `/reports` UI foundation;
- organization/contract/task/document management data;
- document states including expired, expiring, valid, missing and no-expiry;
- deep-link from report problem to organization documents;
- report calculation remains a read model, not a second business-data source.

Not complete relative to DEVELOPMENT_PLAN v2.0:

- exact `5 / 14 / 30` document intervals (historical implementation uses `14 / 40` buckets in part of the report layer);
- complete organization-quality reports;
- complete task reports by 5/14/30 / assignee / workflow source / period;
- full drill-down parity for every KPI;
- server-side scoped pagination/count verification for all report lists;
- report export where approved.

### PR6 — Workflow & Tasks 2.0

**Status: PARTIAL, strong backend core exists.**

Implemented:

- Task Core CRUD;
- multiple assignees;
- priorities and statuses;
- computed overdue state;
- links to organizations/contracts/contract items/OPO/TD/buildings and expertise support in active domain code;
- comments;
- soft delete/restore;
- scoped authorization;
- Workflow Engine CP5.2;
- workflow provenance and atomic generation.

Still required:

- full checklist subsystem;
- document attachments through universal Documents;
- full frontend Tasks migration / UX completeness where still mock/partial;
- operational templates from DEVELOPMENT_PLAN;
- user-facing workflow management;
- deadline/calendar/notification integration;
- CP5.3 Contract ↔ Tasks lifecycle integration.

### PR7 — OPO Workspace

**Status: CORE IMPLEMENTED / operational workspace incomplete.**

Existing Stage 3 foundation provides:

- OPO entity;
- owner/operator organization links;
- OPO scope/security;
- CRUD and custom-field foundation;
- soft-delete/security behavior.

Still required:

- full OPO workspace UX/tabs from roadmap;
- universal Documents/Compliance integration in the OPO card;
- control-date/report/calendar integration;
- Smart Import/Recognition for OPO data.

### PR8 — Technical Devices & Buildings

**Status: CORE IMPLEMENTED / operational workspace incomplete.**

Existing Stage 3 foundation provides:

- separate Technical Device and Building entities;
- optional OPO linkage;
- ability to exist independently of OPO;
- custom-field definitions/typed values;
- parent-scope security.

Still required:

- complete operational card UX;
- passport/document flow through universal Documents;
- control dates;
- Reports/Calendar integration;
- Recognition for Technical Device passports.

### PR9 — Contracts Operational MVP+

**Status: SUBSTANTIALLY IMPLEMENTED / integrations remain.**

Implemented:

- Contracts Core;
- 1 contract -> N contract items;
- money calculation;
- responsible users;
- scoped authorization;
- lifecycle/status state machine;
- signing prerequisites;
- suspension/resume;
- termination;
- completion readiness framework;
- additional agreements;
- optimistic/concurrency protections where required by the checkpoint.

Still required:

- CP5.3 Contract ↔ Tasks lifecycle integration;
- universal Documents integration in final operational UX;
- workflow launch/integration from contract scenarios;
- final user-facing Contracts API/UI migration where still incomplete;
- readiness providers for modules intentionally deferred to their owning stages.

### PR10 — Calendar, Deadlines & Notifications

**Status: NOT IMPLEMENTED as a complete product module.**

There is scheduler/worker infrastructure in the Pilot deployment, but the roadmap still requires:

- `CalendarService` aggregation;
- document/OPO/TD/building/contract/task sources;
- user-configurable 30/14/5 warning intervals;
- in-app notifications;
- idempotent notification generation;
- security-scoped calendar access.

### PR11 — Document Generation

**Status: NOT IMPLEMENTED as the target subsystem.**

Still required:

- TemplateRegistry/versioning;
- Context Builder;
- business-rule preparation;
- DOCX renderer;
- optional PDF;
- generated files persisted through universal Documents;
- generation permissions and tests.

### PR12 — NPD & Corporate Knowledge Base

**Status: NOT IMPLEMENTED as the target subsystem.**

Still required:

- structured NPD registry;
- metadata and local files;
- local full-text/structured search;
- ACL-aware corporate materials;
- controlled actuality update flow.

### PR13 — AI Gateway + RAG

**Status: NOT IMPLEMENTED as the target subsystem.**

Existing OCR/import work is only a foundation. Still required:

- unified AI Gateway;
- policy / permission / data-classification checks;
- PII sanitation and confirmation;
- local-first routing;
- ACL-filtered RAG;
- source-backed answers;
- external AI disable switch and safety tests.

---

## 3. Expertise pause / Resume Gate

Development priority remains outside the full Expertise feature set according to DEVELOPMENT_PLAN v2.0.

### Already integrated

Stage 6 CP6.1 Expertise Core is merged into canonical:

- `1 Expertise = exactly 1 ExpertiseSubjectRef` enforced in DB/service;
- technical-device/building subject XOR;
- contract-item links;
- status history/state machine;
- optimistic locking;
- scoped permissions/IDOR protection;
- real frontend list/detail/create foundation.

### Not part of current priority

Do not continue now without an explicit Expertise Resume Gate:

- inspection;
- diagnostics/NDT;
- defects/photos;
- calculations;
- conclusion generation;
- RTN registration attempts;
- expert-specific workflow expansion;
- AI assistance for expertise work.

PR #18 (CP6.2 Expertise Collaboration) remains separate/open and is not part of the current canonical roadmap priority unless explicitly resumed.

---

## 4. CP-N1..N5 control point

| Checkpoint | Status |
| --- | --- |
| CP-N1 — Organization Types & Conditional Fields | **DONE** |
| CP-N2 — ImportSession + Organization Excel Preview | **DONE** |
| CP-N3 — Confirmed Organization Import + Import Report | **DONE** |
| CP-N4 — Document Types + Validity + Required Rules | **IN PROGRESS** |
| CP-N5 — `/reports` Document Control MVP | **PARTIAL / needs alignment to final acceptance** |

The product-review gate from DEVELOPMENT_PLAN §33 must be performed only after CP-N4 and CP-N5 are both closed against their final acceptance criteria.

---

## 5. Immediate next actions

1. Finish CP7.1 Universal Documents checkpoint:
   - restore normal `.github/workflows/ci.yml`;
   - re-run full backend verification on final HEAD;
   - record completion review;
   - review final diff;
   - open Draft PR to canonical integration;
   - merge only after explicit review/approval.
2. Complete CP-N4:
   - configurable Document Types;
   - unified validity states/thresholds;
   - Compliance rules beyond current organization-only requirements;
   - entity-card Compliance UX.
3. Complete CP-N5:
   - exact 5/14/30 report buckets;
   - scope-safe KPI/drill-down parity;
   - organization/task report completeness.
4. Run DEVELOPMENT_PLAN §33 product review.
5. Only then choose the next operational block: PR6 integrations or PR7 OPO workspace.

---

## 6. Deferred / known boundaries

### CP5.3 — Contract ↔ Tasks integration

Still deferred:

- first linked work start driving internal `signed -> in_progress`;
- task deadline pause/shift during contract suspension;
- unfinished task cancellation on contract termination;
- real task completion-readiness provider for contracts.

### Recognition runtime

Local OCR/recognition code exists, but runtime availability must be verified on the target Pilot server (Tesseract/configuration) before Recognition can be considered production-ready.

### Pilot deployment

Stage 5.9 Pilot Deployment remains an independent operational checkpoint. Target architecture remains LAN/VPN, PostgreSQL, local file storage, worker/scheduler and controlled migrations/backups. No public-internet deployment is assumed.

### Document storage

Files remain server-local and private. User filenames are metadata only; storage keys are internal identifiers. Soft delete does not physically destroy file content until a separate retention/permanent-delete policy is explicitly designed and approved.

---

## 7. Definition of Done reminder

A checkpoint is not marked `DONE` merely because production code exists. Final closure still requires, where applicable:

- backend business/security tests;
- migration verification;
- lint;
- frontend lint/typecheck/tests/build when frontend is affected;
- browser acceptance for the user scenario;
- no blocking defects;
- final diff review;
- reproducible migration/version state;
- documented completion evidence;
- Git actions consistent with repository safety rules.
