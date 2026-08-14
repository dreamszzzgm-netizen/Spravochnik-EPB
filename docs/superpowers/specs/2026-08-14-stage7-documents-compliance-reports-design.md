# Stage 7 — Documents, Compliance & Reports — Design

**Project:** Spravochnik EPB  
**Date:** 2026-08-14  
**Status:** Approved design, ready for implementation planning after user review  
**Design branch:** `agent/stage7-documents-compliance-reports-design`  
**Base:** `agent/integration-cp52-smart-import-hardening` @ `14b85a2587532566800a0c45b48c59f1fee12225`

## 1. Purpose

Stage 7 turns the already implemented organization document control into a reusable document and compliance foundation for the whole system, then rebuilds management reporting on top of that source of truth.

The stage deliberately evolves the existing implementation instead of replacing working behavior with an unrelated subsystem.

The target sequence is:

```text
CP7.1 Universal Documents Core
        ↓
CP7.2 Compliance Engine
        ↓
CP7.3 Compliance UI
        ↓
CP7.4 Reports 2.0
```

## 2. Existing baseline that must be preserved

The current integration baseline already contains:

- organization-scoped document upload/list/download/soft-delete;
- local file storage through `LocalFileStorage` and `STORAGE_ROOT`;
- `organization_documents`;
- `document_requirements`;
- document completeness rules with `all` and `has_opo` applicability;
- management report endpoint `/api/reports/management`;
- `/organizations/[id]/documents` workspace;
- permission codes for document view/upload/download/delete;
- live organization/contract/task/document data in management reporting;
- Expertise Core with a persistent expertise entity and real UI;
- PostgreSQL/Alembic migration history.

Stage 7 must keep current user-visible Organization Documents behavior working during migration.

## 3. Architectural principles

Stage 7 follows the project architecture:

1. `Document` is a universal logical entity.
2. A physical file is stored once.
3. A logical document may be linked to multiple business entities.
4. Document metadata is stored in PostgreSQL; file bytes remain in local server storage.
5. Document versioning is separate from business links.
6. Compliance is a rules/evaluation layer, not another document table.
7. Reports are read models/aggregations and never become a second source of business truth.
8. Files, requirements and findings remain permission-protected on the backend.
9. Important deletion is logical unless physical cleanup is an explicitly controlled maintenance action.
10. The normal application continues to work without external internet access.

## 4. Approaches considered

### A. Universal document core with generic typed links — selected

Create `documents`, `document_versions`, and `document_links`, migrate Organization Documents onto them, and let other modules adopt the same core.

**Advantages:** one source of truth, no file duplication, reusable versioning, consistent security and future task/expertise attachments.  
**Cost:** requires a compatibility migration from the existing organization-specific table.

### B. Keep a separate document table per module

Retain `organization_documents` and later add `expertise_documents`, `contract_documents`, etc.

**Rejected because:** duplicated storage/security/versioning logic, harder reporting, harder cross-links, and conflicts with the already approved architecture.

### C. Content-addressable blob store as the main domain model

Make checksums/blobs the primary abstraction and treat documents only as references to blobs.

**Deferred because:** useful for deduplication but unnecessarily infrastructure-heavy for v1. Stage 7 keeps checksum support without making blob identity the business identity.

## 5. Stage boundary

Stage 7 includes:

- universal logical documents;
- document versions;
- typed business links;
- organization document compatibility migration;
- compliance requirements and evaluation;
- compliance presentation inside business workspaces;
- Reports 2.0 over live data;
- tests, migrations, permissions, audit and migration safety.

Stage 7 does **not** include:

- DOCX template rendering / DocumentGeneration engine;
- OCR/AI extraction changes;
- RTN package generation;
- full NPD actuality checking;
- task document attachments unless needed only as a link target foundation;
- storage garbage collection beyond safe bookkeeping;
- external cloud storage;
- new global `Документы` navigation item.

## 6. CP7.1 — Universal Documents Core

### 6.1 Domain model

#### `documents`

Logical document metadata.

Recommended fields:

```text
id UUID PK
document_type VARCHAR(120) NOT NULL
title VARCHAR(255) NOT NULL
status VARCHAR(32) NOT NULL  # draft | working | final | archived
issued_at DATE NULL
expires_at DATE NULL
current_version_id UUID NULL
created_by UUID NULL/RESTRICT
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
deleted_by UUID NULL/RESTRICT
version INTEGER NOT NULL DEFAULT 1
```

`document_type` remains a stable code/string in CP7.1 so the stage does not prematurely introduce a full document-type administration subsystem.

#### `document_versions`

Immutable physical revisions of a logical document.

```text
id UUID PK
document_id UUID NOT NULL FK documents(id) ON DELETE RESTRICT
version_number INTEGER NOT NULL
original_filename VARCHAR(255) NOT NULL
content_type VARCHAR(255) NULL
storage_key VARCHAR(500) NOT NULL UNIQUE
sha256 CHAR(64) NOT NULL
size_bytes BIGINT NOT NULL
created_by UUID NULL/RESTRICT
created_at TIMESTAMPTZ NOT NULL
```

Constraints:

- unique `(document_id, version_number)`;
- `version_number >= 1`;
- file metadata is immutable after creation;
- a new file revision creates a new row instead of rewriting the old one.

#### `document_links`

Associates one logical document with one or more supported domain entities.

To preserve referential integrity in PostgreSQL, CP7.1 must **not** use an unconstrained `(entity_type, entity_id)` pair as the only database protection.

Preferred v1 design: nullable typed foreign keys with an exactly-one-target CHECK:

```text
id UUID PK
document_id UUID NOT NULL FK documents(id) ON DELETE RESTRICT
organization_id UUID NULL FK organizations(id) ON DELETE RESTRICT
opo_id UUID NULL FK opo(id) ON DELETE RESTRICT
technical_device_id UUID NULL FK technical_devices(id) ON DELETE RESTRICT
building_id UUID NULL FK buildings(id) ON DELETE RESTRICT
contract_id UUID NULL FK contracts(id) ON DELETE RESTRICT
expertise_id UUID NULL FK expertises(id) ON DELETE RESTRICT
task_id UUID NULL FK tasks(id) ON DELETE RESTRICT
created_at TIMESTAMPTZ NOT NULL
```

Database CHECK: exactly one target FK is non-null.

Uniqueness must prevent duplicate links for the same document/target.

This is intentionally verbose but gives real FK enforcement and avoids silent orphaned relations.

### 6.2 Current version

`documents.current_version_id` points to the current `document_versions` row.

The service must enforce that the selected current version belongs to the same logical document. This can be protected by a composite relationship/constraint or by a transactionally validated service operation plus supporting uniqueness.

A version upload is atomic:

```text
validate permission + target
→ store new physical file safely
→ create DocumentVersion
→ update current_version_id
→ audit
→ commit
```

If DB commit fails after a physical file is written, the service must perform safe compensating cleanup of the just-created unreferenced file.

### 6.3 File storage rules

Continue using local private storage.

Requirements:

- UUID/opaque storage keys, never user filenames as paths;
- sanitized original filename stored only as metadata;
- path traversal prevention;
- size limit enforced server-side;
- MIME/extension policy checked server-side;
- SHA-256 calculated on upload;
- downloads require authorization every time;
- no public static directory for private files;
- storage writes use a temporary file + atomic move where feasible.

No automatic cross-document deduplication is required in CP7.1. SHA-256 is retained for integrity and future deduplication/verification.

### 6.4 Compatibility migration from `organization_documents`

The migration must preserve all existing records and files.

For every non-deleted `organization_documents` row:

1. create one `documents` row;
2. create version 1 in `document_versions` using the existing storage metadata;
3. set `documents.current_version_id`;
4. create one `document_links.organization_id` relation;
5. preserve `issued_at`, `expires_at`, title and `document_type`;
6. map prior soft-delete state when historical deleted rows are migrated.

The physical file must **not** be copied during the data migration. Existing `storage_key` remains valid.

The migration must be deterministic and reversible enough for the normal Alembic downgrade policy used by the project. If a fully lossless downgrade is impossible after new multi-link/version data is created, downgrade must fail clearly or be documented as development-only before production usage; it must never silently discard data.

### 6.5 Compatibility API

Existing organization document UI should not break while CP7.1 lands.

Preferred approach:

- retain current organization-scoped endpoints as façade endpoints;
- implement them using `DocumentService` + universal repository;
- return the current response shape needed by the current frontend;
- add universal internal/application service APIs rather than forcing every UI consumer to migrate in the same commit.

New entity workspaces can then adopt the universal service incrementally.

### 6.6 Service boundaries

Recommended module responsibilities:

```text
app/modules/documents/
├── models.py
├── schemas.py
├── repository.py
├── service.py
├── routes.py
├── requirements.py / requirement_service.py
└── control.py
```

`DocumentService` owns:

- create logical document + initial version + first link;
- add version;
- link/unlink supported entities;
- soft delete/restore logical document;
- authorized download resolution;
- metadata update with optimistic version check.

HTTP routes must not perform storage/database orchestration directly.

### 6.7 Authorization

Keep existing permissions as the minimum compatibility set:

```text
documents.view
documents.upload
documents.download
documents.delete
```

Add only if required by concrete actions:

```text
documents.edit
documents.restore
```

Authorization has two parts:

1. permission code;
2. scope access to every business entity being linked/read.

A user must not gain access to a document merely because the same document is linked to another entity outside their scope.

The document read decision is therefore link-aware and scope-aware.

### 6.8 Audit

Audit at least:

- document created;
- version uploaded;
- metadata changed;
- link added/removed;
- soft deleted/restored;
- requirement created/changed/disabled later in CP7.2.

Downloading does not need to become a high-volume audit event in CP7.1 unless the existing security policy already requires it.

## 7. CP7.2 — Compliance Engine

### 7.1 Definition

Compliance is a deterministic evaluator answering:

> For this business entity, which requirements apply, what evidence satisfies them, and which items need attention?

It is not a workflow engine and not a duplicate document registry.

### 7.2 Requirement model

Evolve the existing `document_requirements` into a more general requirement model while preserving current behavior.

Recommended logical shape:

```text
ComplianceRequirement
- id
- code (stable unique code)
- title
- requirement_kind
- evidence_kind
- document_type (nullable when evidence is not a document)
- applicability_scope
- required
- expiry_required
- warning_days
- active
- created_at / updated_at
```

For Stage 7 the supported evidence kind is primarily `document`. The schema should permit later non-document evidence without implementing unrelated engines now.

Supported applicability in Stage 7 must cover at least the already implemented behavior:

```text
all organizations
organization has OPO
```

The design should also support typed entity scope for future rules:

```text
organization
opo
technical_device
building
contract
expertise
```

CP7.2 should only implement applicability predicates that have real current data and acceptance tests; no generic expression language is introduced in v1.

### 7.3 Evaluation states

Canonical derived states:

```text
COMPLIANT       # required evidence exists and is not near expiry
EXPIRING        # evidence exists and expires within warning threshold
EXPIRED         # expires_at < today
MISSING         # required applicable evidence does not exist
NO_EXPIRY       # expiry is required by rule but evidence has no expires_at
NOT_APPLICABLE  # rule does not apply; usually omitted from issue lists
```

For reports/UI, `EXPIRING` is bucketed into:

- `≤ 14 days`;
- `15–40 days`;

The currently used 14/40-day management categories remain stable for continuity. User-configurable notification intervals remain a separate Notifications concern.

### 7.4 Evidence selection

If multiple active documents of the same required type are linked to the entity, the evaluator must use a deterministic rule.

Stage 7 rule:

1. ignore soft-deleted logical documents;
2. prefer `final`, then `working`, then `draft`;
3. among equal statuses, prefer the document with the latest `expires_at` when present;
4. then latest `issued_at`;
5. then latest `updated_at`.

The evaluation result should identify the evidence document ID so UI can navigate directly to it.

### 7.5 Findings

Compliance status is primarily computed from live data.

Do **not** create a mutable `compliance_findings` source-of-truth table in Stage 7 unless later performance evidence requires a cache.

The service returns immutable evaluation DTOs/read models containing:

```text
requirement
entity reference
state
selected evidence document
expires_at
days_remaining
reason
```

This prevents stale findings when a document is uploaded or expiry metadata changes.

## 8. CP7.3 — Compliance UI

### 8.1 Navigation

There is no global `Документы` menu item.

Documents remain in business workspaces.

For organization workspace, preserve `/organizations/[id]/documents` and enrich it with a compliance summary.

For entities adopted later in Stage 7, use their own card/workspace routes rather than introducing a global file explorer.

### 8.2 Organization documents screen

Target layout:

```text
Документы организации

Комплектность: 8 / 10
[ Соответствует 8 ] [ Истекает 1 ] [ Отсутствует 1 ]

Требования
✓ Договор с АСФ
✓ Финансовый резерв
⚠ Протокол аттестации — истекает через 9 дней
✕ Свидетельство ОПО — отсутствует    [Загрузить документ]

Документы
...existing document list/upload behavior...
```

The UI must use text + icons + color, never color alone.

Clicking a finding should open or focus the related document; `MISSING` should offer upload with the required document type preselected.

### 8.3 Empty and degraded states

Explicit states:

- no requirements configured;
- no documents uploaded;
- storage unavailable;
- insufficient permission;
- backend migration/version mismatch should fail clearly and never show fabricated completeness.

## 9. CP7.4 — Reports 2.0

### 9.1 Purpose

`/reports` becomes a management read model over existing modules.

Reports never own contract/task/expertise/document state.

### 9.2 Report navigation

Stage 7 target:

```text
Отчёты
├── Обзор
├── Документы и соответствие
├── Договоры
├── Экспертизы
└── Задачи
```

`РТН` is added when RTN Core exists and has real data.

### 9.3 Documents & Compliance report

Required top-level counters:

```text
Срок истёк
Истекает ≤ 14 дней
Истекает 15–40 дней
Не загружен
Срок не указан
Соответствует
```

Required filters/drill-down:

- organization;
- document type / requirement;
- state;
- expiry window;
- direct link to the owning business card/document workspace.

No duplicated snapshot table is required for v1.

### 9.4 Management report API

The existing `/api/reports/management` may remain for compatibility, but report construction should be split into focused read-model services instead of one ever-growing route/service.

Recommended conceptual services:

```text
ManagementOverviewQuery
DocumentComplianceReportQuery
ContractReportQuery
ExpertiseReportQuery
TaskReportQuery
```

They may use optimized SQL queries/views, but business mutation logic is forbidden in reporting code.

### 9.5 Access

Current management reporting is superuser-only. Stage 7 preserves this rule unless a later permissions design explicitly introduces a `reports.view_management` capability.

Do not silently broaden access during the refactor.

## 10. Data flow

### Upload document

```text
UI
→ organization/entity document endpoint
→ permission + scope check
→ DocumentService
→ validate metadata/file
→ LocalFileStorage
→ Document + DocumentVersion + DocumentLink transaction
→ audit
→ response
```

### Compliance evaluation

```text
UI / Report
→ ComplianceService.evaluate(entity)
→ load active applicable requirements
→ load linked active documents
→ deterministic evidence selection
→ derive state + days_remaining
→ DTO/read model
```

### Reports

```text
/reports
→ report query service
→ Contracts / Tasks / Expertises / Compliance read queries
→ aggregate DTO
→ frontend cards/tables/charts
```

## 11. Error handling

Use the project error semantics consistently:

- `400/422` malformed/invalid metadata;
- `403` missing permission;
- `404` inaccessible or missing scoped entity/document (fail closed where scope disclosure matters);
- `409` optimistic version conflict or duplicate relation;
- `413` oversized upload;
- controlled file-processing/storage error for failed storage access;
- `503` only when a required storage/infrastructure dependency is unavailable.

A failed multi-step upload must not leave a database row referencing a missing file.

## 12. Concurrency

Logical document metadata uses optimistic locking (`version` / expected version) for edits that can overwrite concurrent user changes.

New immutable `document_versions` do not overwrite one another. The transaction selecting a new current version must protect against lost updates.

Duplicate links and duplicate version numbers are prevented by database constraints.

## 13. Migration strategy

Stage 7 migrations must extend the current linear Alembic history from the actual integration head at implementation time.

The implementation plan must first re-check the Alembic head because later integration commits may advance beyond the design baseline.

Migration acceptance includes:

1. upgrade from the current canonical integration schema;
2. data preservation of existing organization documents;
3. physical storage keys unchanged;
4. no duplicate physical copies;
5. old organization document endpoints still work after migration;
6. migration round-trip where safely supported;
7. a single Alembic head.

## 14. Testing strategy

### Unit/domain

- compliance classification boundaries;
- applicability;
- evidence selection;
- exactly-one link target validation;
- filename/path safety helpers;
- MIME/size rules;
- version ordering.

### Service

- create initial document atomically;
- add version;
- link/unlink;
- soft delete/restore;
- storage compensation after DB failure;
- scope-aware authorization;
- optimistic conflicts.

### Repository/integration

- FK/CHECK/unique constraints;
- migration of old organization documents;
- current version integrity;
- soft-deleted records excluded from normal queries;
- report counts match seeded business data.

### HTTP

- current organization document API compatibility;
- upload/download/delete permissions;
- inaccessible foreign scope fails closed;
- compliance endpoint response states;
- reports remain management restricted.

### Frontend

- organization documents workspace continues working;
- compliance counters and issue list;
- direct upload from `MISSING` requirement;
- report filters and drill-down;
- loading/empty/error states;
- lint/typecheck/tests/build.

### Security

- traversal filenames;
- spoofed MIME/extension cases supported by policy;
- unauthorized direct download;
- deleted document download denial;
- link-based scope escalation attempts;
- oversized uploads.

## 15. Acceptance criteria by checkpoint

### CP7.1 ready

- universal tables/services exist;
- all existing organization documents migrated without file copies;
- current organization document UX/API works on universal core;
- version 2 can be added without destroying version 1;
- one logical document can be safely linked to more than one supported entity;
- backend permissions/scopes are enforced;
- regression suite and migration checks green.

### CP7.2 ready

- active requirements are evaluated against universal linked documents;
- `COMPLIANT/EXPIRING/EXPIRED/MISSING/NO_EXPIRY` are deterministic;
- current `all`/`has_opo` behavior is preserved;
- findings are live derived results, not stale mutable records;
- unit/integration/report count tests green.

### CP7.3 ready

- organization workspace shows completeness and actionable findings;
- missing requirement can start a correctly typed upload;
- status semantics match the design system;
- existing document operations remain available.

### CP7.4 ready

- `/reports` has live Overview + Documents & Compliance + Contracts + Expertises + Tasks views;
- document-control categories include expired, ≤14, 15–40, missing, no-expiry, compliant;
- filters/drill-down resolve to real cards;
- report code performs no business mutations;
- management access remains protected.

## 16. Implementation order and isolation

Implementation should use separate checkpoint branches/PRs, stacked or integrated only after verification:

```text
agent/stage7-cp71-universal-documents
        ↓
agent/stage7-cp72-compliance-engine
        ↓
agent/stage7-cp73-compliance-ui
        ↓
agent/stage7-cp74-reports-2
```

CP7.1 is the first implementation plan. CP7.2+ are not implemented opportunistically inside CP7.1.

## 17. Explicit decisions

1. Universal Documents replaces entity-specific document persistence as the long-term model.
2. Existing Organization Documents behavior is preserved through a compatibility façade during migration.
3. Physical files are not copied during the migration.
4. Document versions are immutable physical revisions.
5. Business links belong to the logical document, not a physical version.
6. `document_links` uses real typed FKs with exactly one target, not an unconstrained polymorphic ID.
7. Compliance is evaluated from live requirements + evidence.
8. Compliance findings are derived, not a mutable source-of-truth table in Stage 7.
9. Current `all` / `has_opo` requirement behavior is preserved.
10. Reports are read models and never mutate source entities.
11. There is no global `Документы` navigation item.
12. Report access is not broadened silently.
13. Stage 7 does not implement the document generation/template engine.
14. CP7.1 is planned and implemented before CP7.2–CP7.4.

## 18. Self-review

- No unresolved `TBD`/`TODO` requirements are intentionally left in this design.
- The design is compatible with the existing Organization Documents implementation and the approved project architecture.
- CP7.1 is isolated enough for one implementation plan; later compliance/report checkpoints depend on it but are not part of its coding scope.
- The main ambiguity of a generic polymorphic relation is resolved explicitly in favor of typed FK columns plus an exactly-one-target constraint.
- The main migration risk—existing physical files—is resolved explicitly by reusing existing storage keys without copying bytes.

## 19. Next step

After user review and approval of this written specification, create a detailed implementation plan for **CP7.1 — Universal Documents Core** using the project planning workflow. No production code changes are part of this design commit.
