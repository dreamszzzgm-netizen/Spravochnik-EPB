# Stage 7 CP7.1 — Universal Documents Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace organization-specific document persistence with a universal logical document/version/link core while preserving the existing Organization Documents API/UX, storage bytes, completeness reporting, permissions, and live management report behavior.

**Architecture:** Keep the modular-monolith boundary `HTTP -> DocumentService -> repository/storage -> PostgreSQL`. Introduce `documents`, immutable `document_versions`, and typed-FK `document_links`; migrate every legacy `organization_documents` row without copying file bytes; expose legacy organization routes as a compatibility façade over the universal core. Compliance rules remain unchanged in CP7.1, and Reports 2.0 is deferred, but the current management report must read the new universal source without regression.

**Tech Stack:** Python 3.13; FastAPI; SQLAlchemy 2.0; PostgreSQL; Alembic; pytest; existing `LocalFileStorage`; Next.js 16 / React 19 frontend only for compatibility regression checks.

## Global Constraints

- Implementation branch: `agent/stage7-cp71-universal-documents`.
- Approved design: `docs/superpowers/specs/2026-08-14-stage7-documents-compliance-reports-design.md`.
- Start from the latest canonical `agent/integration-cp52-smart-import-hardening`; at plan-writing time its HEAD is `14b85a2587532566800a0c45b48c59f1fee12225` and Alembic head is `0020_identifier_constraints`. Re-check both before coding; if canonical advanced, rebase/cherry-pick the approved design+plan and chain the new migration from the actual single head.
- Do not touch `main` directly.
- Use an isolated worktree at execution time via `superpowers:using-git-worktrees`.
- PostgreSQL is authoritative for migration/constraint tests; do not weaken FK/CHECK/partial-index guarantees to make SQLite tests easier.
- Preserve `document_requirements` and current `all` / `has_opo` behavior unchanged; Compliance Engine belongs to CP7.2.
- Preserve existing organization URLs and response shape: `/api/organizations/{organization_id}/documents`, download, delete, and `/organizations/[id]/documents`.
- Do not add a global `Документы` navigation item.
- Physical file bytes must not be copied during migration; legacy `storage_key` values remain valid.
- `document_versions` are immutable. Updating file bytes always means a new version row.
- `document_links` use real nullable typed FKs plus an exactly-one-target CHECK; do not introduce an unconstrained `(entity_type, entity_id)` pair.
- Supported link targets in the schema: organization, OPO, technical device, building, contract, expertise, task.
- Soft deletion remains logical; normal reads exclude deleted logical documents.
- Existing permissions remain the compatibility minimum: `documents.view`, `documents.upload`, `documents.download`, `documents.delete`. Add `documents.edit` / `documents.restore` only when the corresponding CP7.1 action is exposed/tested.
- Authorization must be both permission-aware and target-scope-aware. A second out-of-scope link must not grant document access.
- Keep local private storage and opaque keys. User filenames are metadata, never physical paths.
- Keep SHA-256 integrity metadata.
- No DOCX generation, OCR/AI changes, RTN package generation, NPD actuality engine, cloud storage, storage garbage collector, Compliance UI, or Reports 2.0 in CP7.1.
- No test skips added. Each task follows RED -> GREEN -> focused regression -> commit.

## Locked file structure

New responsibilities:

```text
app/modules/documents/
├── enums.py              # DocumentLifecycleStatus only
├── models.py             # Document, DocumentVersion, DocumentLink, DocumentRequirement
├── policy.py             # upload extension/MIME policy; pure functions
├── repository.py         # universal queries + OrganizationDocumentProjection compatibility reads
├── access.py             # typed target existence/scope resolution for document links
├── service.py            # create/version/link/metadata/delete/restore orchestration
├── schemas.py            # existing compatibility schemas + universal service DTO request shapes if needed
├── routes.py             # existing organization façade only in CP7.1
├── control.py            # existing completeness classifier, unchanged except imports/types if required
└── requirement_routes.py # unchanged except regression
```

Migration:

```text
alembic/versions/0021_universal_documents.py
```

If the actual canonical Alembic head is no longer `0020_identifier_constraints`, rename the migration to the next repository convention and set `down_revision` to that actual head before writing tests.

---

### Task 1: Universal SQLAlchemy model and database constraints

**Files:**
- Create: `app/modules/documents/enums.py`
- Modify: `app/modules/documents/models.py`
- Create: `tests/unit/test_universal_document_models.py`

**Interfaces:**
- Produces `DocumentLifecycleStatus(StrEnum)` values `draft`, `working`, `final`, `archived`.
- Produces SQLAlchemy models `Document`, `DocumentVersion`, `DocumentLink`.
- Keeps `DocumentRequirement` available from the same module.
- Later tasks rely on `Document.id`, `Document.current_version_id`, `Document.version`, `DocumentVersion.document_id`, `DocumentVersion.version_number`, and typed target columns on `DocumentLink`.

- [ ] **Step 1: Write failing model tests**

Create `tests/unit/test_universal_document_models.py`:

```python
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.modules.documents.enums import DocumentLifecycleStatus
from app.modules.documents.models import Document, DocumentLink, DocumentVersion


def test_document_lifecycle_values_are_stable() -> None:
    assert [item.value for item in DocumentLifecycleStatus] == [
        "draft", "working", "final", "archived"
    ]


def test_document_version_has_unique_document_version_number() -> None:
    constraints = list(DocumentVersion.__table__.constraints)
    assert any(
        isinstance(item, UniqueConstraint)
        and tuple(column.name for column in item.columns) == ("document_id", "version_number")
        for item in constraints
    )


def test_document_link_declares_exactly_one_target_check() -> None:
    checks = [
        str(item.sqltext)
        for item in DocumentLink.__table__.constraints
        if isinstance(item, CheckConstraint)
    ]
    assert any("num_nonnulls" in sql and "= 1" in sql for sql in checks)


def test_document_has_optimistic_version_and_current_version_pointer() -> None:
    assert Document.__table__.c.version.nullable is False
    assert Document.__table__.c.current_version_id.nullable is True
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m pytest tests/unit/test_universal_document_models.py -q
```

Expected: import/attribute failures because the universal models do not exist yet.

- [ ] **Step 3: Implement the minimal model**

Create `app/modules/documents/enums.py`:

```python
import enum


class DocumentLifecycleStatus(enum.StrEnum):
    DRAFT = "draft"
    WORKING = "working"
    FINAL = "final"
    ARCHIVED = "archived"
```

Refactor `app/modules/documents/models.py` so `OrganizationDocument` is removed as persistence and the new tables are represented. Use the following invariants exactly:

```python
class Document(Base):
    __tablename__ = "documents"
    # UUID id
    # document_type String(120), title String(255)
    # status String(32), default "working"
    # issued_at / expires_at nullable Date
    # current_version_id nullable UUID
    # created_by / deleted_by nullable FK users.id RESTRICT
    # created_at / updated_at timezone-aware
    # deleted_at nullable timezone-aware
    # version Integer NOT NULL default 1
```

Add checks `status IN ('draft','working','final','archived')` and `version >= 1`.

`DocumentVersion`:

```python
class DocumentVersion(Base):
    __tablename__ = "document_versions"
    # id UUID PK
    # document_id FK documents.id RESTRICT, indexed
    # version_number Integer NOT NULL
    # original_filename String(255)
    # content_type String(255) nullable
    # storage_key String(500) UNIQUE
    # sha256 String(64)
    # size_bytes BigInteger
    # created_by nullable FK users.id RESTRICT
    # created_at timezone-aware
```

Add unique `(document_id, version_number)`, unique `(document_id, id)` for the composite current-version FK, and `version_number >= 1`, `size_bytes >= 0` checks.

On `Document`, add a named composite FK:

```text
(documents.id, documents.current_version_id)
    -> (document_versions.document_id, document_versions.id)
```

This enforces that the current version belongs to the same logical document.

`DocumentLink` has nullable UUID FKs named exactly:

```text
organization_id       -> organizations.id RESTRICT
opo_id                -> opo.id RESTRICT
technical_device_id   -> technical_devices.id RESTRICT
building_id           -> buildings.id RESTRICT
contract_id           -> contracts.id RESTRICT
expertise_id          -> expertises.id RESTRICT
task_id               -> tasks.id RESTRICT
```

Add PostgreSQL CHECK:

```sql
num_nonnulls(
  organization_id, opo_id, technical_device_id, building_id,
  contract_id, expertise_id, task_id
) = 1
```

Add one partial unique index per target, e.g. `(document_id, organization_id) WHERE organization_id IS NOT NULL`, and equivalent indexes for the other six targets.

- [ ] **Step 4: Run focused tests**

```bash
python -m pytest tests/unit/test_universal_document_models.py -q
python -m ruff check app/modules/documents/models.py app/modules/documents/enums.py tests/unit/test_universal_document_models.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/documents/enums.py app/modules/documents/models.py tests/unit/test_universal_document_models.py
git commit -m "feat: add universal document domain models"
```

---

### Task 2: Alembic 0021 migration with lossless legacy conversion

**Files:**
- Create: `alembic/versions/0021_universal_documents.py`
- Modify: `alembic/env.py`
- Create: `tests/integration/test_universal_documents_migration.py`
- Modify: `tests/unit/test_documents_migration.py` if it asserts the old head/table set.

**Interfaces:**
- Consumes the model/table names from Task 1.
- Produces a schema where `organization_documents` no longer exists and all rows are represented by `documents + document_versions + document_links`.
- Reuses legacy `storage_key`; no filesystem access is allowed from the migration.

- [ ] **Step 1: Write a failing migration preservation test**

Follow the existing Alembic integration-test pattern. In `tests/integration/test_universal_documents_migration.py`, downgrade to `0020_identifier_constraints`, insert one active and one soft-deleted legacy row, then upgrade to `0021_universal_documents` and assert:

```python
assert {"documents", "document_versions", "document_links"} <= tables
assert "organization_documents" not in tables

row = connection.execute(sa.text("""
    SELECT d.id, d.document_type, d.title, d.issued_at, d.expires_at,
           d.deleted_at, d.current_version_id,
           v.original_filename, v.content_type, v.storage_key, v.sha256, v.size_bytes,
           l.organization_id
    FROM documents d
    JOIN document_versions v ON v.id = d.current_version_id
    JOIN document_links l ON l.document_id = d.id
    WHERE d.id = :legacy_id
"""), {"legacy_id": legacy_id}).mappings().one()
assert row["storage_key"] == legacy_storage_key
assert row["organization_id"] == organization_id
assert row["original_filename"] == "legacy.pdf"
```

Also assert that the soft-deleted row remains soft-deleted after migration.

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/integration/test_universal_documents_migration.py -q
```

Expected: FAIL because revision `0021_universal_documents` does not exist.

- [ ] **Step 3: Implement upgrade**

Migration requirements:

1. `down_revision = "0020_identifier_constraints"` only if that is still the actual current head.
2. Create `documents`, `document_versions`, `document_links` with exactly the constraints from Task 1.
3. Read every row from `organization_documents`, including soft-deleted rows.
4. Preserve the legacy document UUID as `documents.id` so existing client/bookmark IDs remain stable.
5. For each legacy row generate deterministic IDs for version/link using a module-level UUID namespace and `uuid.uuid5`, e.g. `uuid.uuid5(NAMESPACE, f"organization-document:{legacy_id}:v1")`.
6. Insert `documents.status = 'working'`, `documents.version = 1`, `created_by = NULL`, `deleted_by = NULL`, copy dates/timestamps/deleted_at.
7. Insert version 1 with the existing `storage_key`, hash, size, filename, MIME and timestamps.
8. Insert the organization link.
9. Update `documents.current_version_id` to version 1.
10. Drop `organization_documents` only after all inserts succeed.
11. Never read/copy/delete physical files.

- [ ] **Step 4: Add and test guarded downgrade**

Before downgrade recreates `organization_documents`, execute guards that reject any state not representable by the legacy schema. Raise `RuntimeError("universal documents cannot be downgraded losslessly")` if any of these is true:

```text
- a document has anything other than exactly one organization link;
- a document has more/less than one version;
- current_version_id is not that sole version;
- document.status != 'working';
- document.version != 1;
- created_by IS NOT NULL or deleted_by IS NOT NULL.
```

If guards pass, recreate the exact legacy table shape, copy the sole version/link back without changing storage keys, then drop universal tables in FK-safe order.

Add two tests:

```python
def test_universal_document_migration_round_trip_preserves_legacy_shape(): ...

def test_universal_document_downgrade_refuses_new_version():
    # upgrade, insert version 2, assert command.downgrade raises RuntimeError
```

- [ ] **Step 5: Run migration checks**

```bash
python -m alembic heads
python -m pytest tests/integration/test_universal_documents_migration.py -q
```

Expected: exactly one head, migration tests PASS.

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/0021_universal_documents.py alembic/env.py tests/integration/test_universal_documents_migration.py tests/unit/test_documents_migration.py
git commit -m "feat: migrate organization documents to universal core"
```

---

### Task 3: Storage size enforcement and upload media policy

**Files:**
- Modify: `app/storage/local.py`
- Create: `app/modules/documents/policy.py`
- Modify: `tests/unit/test_storage.py`
- Create: `tests/unit/test_document_upload_policy.py`

**Interfaces:**
- `LocalFileStorage.put(source, *, storage_key=None, max_bytes=None) -> StoredFile`.
- Raises `StorageLimitExceeded` before an oversized temp file is promoted.
- `validate_document_upload(filename: str, content_type: str | None) -> None` raises `DocumentUploadPolicyError` for disallowed file types.

- [ ] **Step 1: Write RED tests for streaming size limit**

Add to `tests/unit/test_storage.py`:

```python
def test_put_rejects_stream_over_limit_without_persisting(tmp_path):
    storage = LocalFileStorage(tmp_path)
    with pytest.raises(StorageLimitExceeded):
        storage.put(io.BytesIO(b"123456"), max_bytes=5)
    assert list(tmp_path.rglob("*")) == []
```

The implementation must delete the temp file on this exception and never call `os.replace` for it.

- [ ] **Step 2: Write RED policy tests**

Create tests that accept normal EPB formats:

```python
@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("doc.pdf", "application/pdf"),
        ("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("table.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("photo.jpg", "image/jpeg"),
        ("scan.png", "image/png"),
        ("scan.tiff", "image/tiff"),
        ("legacy.doc", "application/msword"),
        ("legacy.xls", "application/vnd.ms-excel"),
    ],
)
def test_allowed_document_uploads(name, mime):
    validate_document_upload(name, mime)
```

Reject executable/script extensions (`.exe`, `.dll`, `.bat`, `.cmd`, `.ps1`, `.js`, `.html`) and path-like filenames. Permit `application/octet-stream` only when the filename extension is in the approved business-format list, because browsers/scanners may send generic MIME.

- [ ] **Step 3: Run RED tests**

```bash
python -m pytest tests/unit/test_storage.py tests/unit/test_document_upload_policy.py -q
```

Expected: missing exception/helper failures.

- [ ] **Step 4: Implement minimal safety policy**

In `LocalFileStorage.put`, count chunks while writing. If `size > max_bytes`, close/delete the temp file and raise `StorageLimitExceeded(max_bytes)`.

In `policy.py`, use lowercase `Path(filename).suffix`, reject filenames containing `/`, `\\`, NUL, or no approved extension. Approved extensions in CP7.1 are exactly:

```text
.pdf .doc .docx .xls .xlsx .jpg .jpeg .png .tif .tiff
```

Validate the known strong MIME mappings above. Generic `application/octet-stream` is accepted only for an approved extension. Do not inspect or OCR file contents in CP7.1.

- [ ] **Step 5: Run focused tests and lint**

```bash
python -m pytest tests/unit/test_storage.py tests/unit/test_document_upload_policy.py -q
python -m ruff check app/storage/local.py app/modules/documents/policy.py tests/unit/test_storage.py tests/unit/test_document_upload_policy.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/storage/local.py app/modules/documents/policy.py tests/unit/test_storage.py tests/unit/test_document_upload_policy.py
git commit -m "feat: harden document upload storage policy"
```

---

### Task 4: Universal repository and organization compatibility projection

**Files:**
- Modify: `app/modules/documents/repository.py`
- Create: `tests/integration/test_universal_document_repository.py`

**Interfaces:**
- Produces immutable `OrganizationDocumentProjection` with the legacy response fields.
- Produces `get_document`, `get_document_for_update`, `get_current_version`, `list_document_links`, `list_organization_documents`, `get_organization_document`.
- Existing route/report code must no longer depend on a mapped `OrganizationDocument` class.

- [ ] **Step 1: Write RED repository tests**

Seed one `Document`, current `DocumentVersion`, and `DocumentLink(organization_id=...)`. Assert:

```python
rows = list_organization_documents(db_session, organization.id)
assert len(rows) == 1
row = rows[0]
assert row.id == document.id
assert row.organization_id == organization.id
assert row.original_filename == "passport.pdf"
assert row.storage_key == version.storage_key
```

Add a soft-deleted document and assert it is excluded. Add a second document linked only to another organization and assert it is excluded.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_universal_document_repository.py -q
```

Expected: repository still queries legacy `OrganizationDocument`.

- [ ] **Step 3: Implement projection queries**

Define:

```python
@dataclass(frozen=True, slots=True)
class OrganizationDocumentProjection:
    id: uuid.UUID
    organization_id: uuid.UUID
    document_type: str
    title: str
    original_filename: str
    content_type: str | None
    storage_key: str
    sha256: str
    size_bytes: int
    issued_at: date | None
    expires_at: date | None
    created_at: datetime
    updated_at: datetime
```

`list_organization_documents` joins:

```text
Document
-> DocumentLink where organization_id = requested org
-> DocumentVersion where id = Document.current_version_id
```

and filters `Document.deleted_at IS NULL`.

`get_organization_document` must apply both document ID and organization link in SQL; do not load by ID first and check organization afterward.

Update `document_tables_available` to require `documents`, `document_versions`, `document_links`, and `document_requirements`.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/integration/test_universal_document_repository.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/documents/repository.py tests/integration/test_universal_document_repository.py
git commit -m "refactor: read organization documents from universal tables"
```

---

### Task 5: Universal create and immutable version service

**Files:**
- Modify: `app/modules/documents/service.py`
- Create: `tests/integration/test_universal_document_service.py`

**Interfaces:**
- `create_document(db, *, actor_user_id, target: DocumentTarget, document_type, title, original_filename, content_type, source, issued_at=None, expires_at=None) -> Document`.
- `add_version(db, *, actor_user_id, document, expected_version, original_filename, content_type, source) -> DocumentVersion`.
- `DocumentTarget` is a frozen dataclass with exactly one nullable typed target ID and a constructor/check that rejects zero or multiple targets.
- `DocumentVersionConflictError` maps stale expected version to HTTP 409 in any façade endpoint that exposes it later.

- [ ] **Step 1: Write RED create test**

Test that one call creates all three rows atomically and sets the current version:

```python
document = service.create_document(
    db_session,
    actor_user_id=user_id,
    target=DocumentTarget(organization_id=organization.id),
    document_type="insurance",
    title="Insurance 2026",
    original_filename="insurance.pdf",
    content_type="application/pdf",
    source=io.BytesIO(b"%PDF-test"),
)
assert document.current_version_id is not None
assert db_session.scalar(select(func.count()).select_from(DocumentVersion)) == 1
assert db_session.scalar(select(func.count()).select_from(DocumentLink)) == 1
```

Verify `created_by == actor_user_id` and SHA/size on the version.

- [ ] **Step 2: Write RED compensation test**

Monkeypatch `db.commit()` to raise after `storage.put()`. Assert the just-created `storage_key` no longer exists and no universal rows remain committed.

- [ ] **Step 3: Write RED version test**

Create v1, then:

```python
version2 = service.add_version(
    db_session,
    actor_user_id=user_id,
    document=document,
    expected_version=1,
    original_filename="insurance-v2.pdf",
    content_type="application/pdf",
    source=io.BytesIO(b"%PDF-v2"),
)
assert version2.version_number == 2
assert document.current_version_id == version2.id
assert document.version == 2
assert len(repository.list_versions(db_session, document.id)) == 2
```

Then retry with `expected_version=1` and assert `DocumentVersionConflictError` and no v3 row/file.

- [ ] **Step 4: Run RED**

```bash
python -m pytest tests/integration/test_universal_document_service.py -q
```

Expected: missing universal service APIs.

- [ ] **Step 5: Implement service transaction boundaries**

Rules:

```text
create:
validate upload policy -> storage.put(max_bytes=20 MiB) -> Document(status=working, version=1)
-> DocumentVersion(version_number=1) -> DocumentLink -> flush
-> set current_version_id -> write_audit(action="document.created") -> commit
```

`add_version` locks/reloads the logical document for mutation, checks `expected_version == document.version`, stores bytes with the same policy/limit, assigns `version_number = document.version + 1`, updates `current_version_id` and `document.version`, writes `document.version_uploaded` audit, then commits. On any DB failure after storage write, rollback and delete only the newly written storage object.

Never rewrite/delete v1 when v2 is created.

- [ ] **Step 6: Run focused tests**

```bash
python -m pytest tests/integration/test_universal_document_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/modules/documents/service.py tests/integration/test_universal_document_service.py
git commit -m "feat: add universal document creation and versioning"
```

---

### Task 6: Typed links and scope-aware access

**Files:**
- Create: `app/modules/documents/access.py`
- Modify: `app/modules/documents/service.py`
- Modify: `app/modules/documents/repository.py`
- Create: `tests/integration/test_document_link_access.py`

**Interfaces:**
- `DocumentAccessService.can_access_document(db, *, authorization, document_id) -> bool`.
- `DocumentService.add_link(..., target: DocumentTarget) -> DocumentLink`.
- `DocumentService.remove_link(..., link_id) -> None`.
- Link creation validates that the target exists, is not soft-deleted where the target supports soft deletion, and is accessible under the caller's document permission scope.

- [ ] **Step 1: Write RED exactly-one and duplicate-link tests**

At service level, assert `DocumentTarget()` and `DocumentTarget(organization_id=a, contract_id=b)` raise `DocumentTargetError`. Add the same link twice and assert the second call becomes a deterministic conflict rather than an unhandled `IntegrityError`.

- [ ] **Step 2: Write RED scope-leak test**

Seed a document linked to organization A and organization B. Give a scoped user access only to A. Assert:

```python
assert access.can_access_document(
    db_session, authorization=ctx_for_a, document_id=document.id
) is True
```

Then seed a document linked only to B and assert access is False. The implementation must answer “accessible if at least one active link is accessible”, not “all links must be accessible”. It must never expose the inaccessible B link through a response to A-scoped users.

- [ ] **Step 3: Write RED target tests for all seven typed FKs**

For superuser/all-scope context, create one link each to Organization, OPO, TechnicalDevice, Building, Contract, Expertise, and Task. Assert persistence succeeds. Use the existing module repositories/authorization rules to validate target existence and scope; do not duplicate business ownership columns inside documents.

- [ ] **Step 4: Run RED**

```bash
python -m pytest tests/integration/test_document_link_access.py -q
```

- [ ] **Step 5: Implement target resolvers and access evaluation**

`access.py` may depend on domain models/repositories but must not import HTTP routes. For each link target, resolve related organization scope using established rules:

- Organization: existing `can_access_organization`.
- OPO: owner/operating organizations via existing `can_access_opo`.
- TechnicalDevice / Building: existing organization ownership helpers.
- Contract: use contracts repository scoped lookup instead of reimplementing contract role logic.
- Expertise: use expertise repository scoped lookup.
- Task: use tasks repository scoped lookup.

If a target is not visible under the supplied `AuthorizationContext`, behave as not found/fail closed when adding the link.

`can_access_document` loads only non-deleted document links and evaluates them without returning hidden link metadata.

Write audit actions `document.link_added` / `document.link_removed` on successful service mutations.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/integration/test_document_link_access.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/modules/documents/access.py app/modules/documents/service.py app/modules/documents/repository.py tests/integration/test_document_link_access.py
git commit -m "feat: add scoped universal document links"
```

---

### Task 7: Metadata optimistic locking, soft delete, restore, and audit

**Files:**
- Modify: `app/modules/documents/service.py`
- Modify: `app/modules/documents/schemas.py`
- Create: `tests/integration/test_document_metadata_lifecycle.py`

**Interfaces:**
- `update_metadata(..., expected_version, title=None, document_type=None, status=None, issued_at=UNSET, expires_at=UNSET) -> Document`.
- `soft_delete_document(..., actor_user_id, expected_version) -> Document`.
- `restore_document(..., actor_user_id, expected_version) -> Document`.
- All three increment `Document.version` and reject stale versions with `DocumentVersionConflictError`.

- [ ] **Step 1: Write RED stale-version test**

```python
service.update_metadata(
    db_session,
    actor_user_id=user_id,
    document=document,
    expected_version=1,
    title="Updated",
)
assert document.version == 2
with pytest.raises(DocumentVersionConflictError):
    service.update_metadata(
        db_session,
        actor_user_id=user_id,
        document=document,
        expected_version=1,
        title="Lost update",
    )
```

- [ ] **Step 2: Write RED delete/restore test**

Assert delete sets `deleted_at`, `deleted_by`, increments version, does not delete any `DocumentVersion` or physical file, and normal repository reads hide it. Restore clears `deleted_at/deleted_by`, increments version, and makes it visible again.

- [ ] **Step 3: Write RED audit assertions**

Query `AuditEvent` and assert actions exist for metadata update, delete, restore with `entity_type="document"` and the logical document ID. Do not put filenames, file bytes, or document contents in audit metadata.

- [ ] **Step 4: Implement and run**

```bash
python -m pytest tests/integration/test_document_metadata_lifecycle.py -q
```

Expected after implementation: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/documents/service.py app/modules/documents/schemas.py tests/integration/test_document_metadata_lifecycle.py
git commit -m "feat: add document metadata lifecycle controls"
```

---

### Task 8: Preserve Organization Documents HTTP API exactly

**Files:**
- Modify: `app/modules/documents/routes.py`
- Modify: `app/modules/documents/schemas.py`
- Modify: `tests/integration/test_documents_acceptance.py`
- Modify: `tests/integration/test_organization_documents.py`

**Interfaces:**
- Existing HTTP response remains `OrganizationDocumentResponse` with `organization_id` and current-version file metadata.
- Existing upload endpoint creates universal Document + v1 + organization link through `DocumentService`.
- Existing download resolves the current version through the compatibility projection.
- Existing DELETE soft-deletes the logical document; URL and 204 response remain unchanged.

- [ ] **Step 1: Rewrite direct legacy-model assertions to universal assertions**

In acceptance tests, replace:

```python
document = db_session.get(OrganizationDocument, uploaded["id"])
```

with:

```python
document = db_session.get(Document, uuid.UUID(uploaded["id"]))
assert document is not None
assert document.deleted_at is not None
versions = repository.list_versions(db_session, document.id)
assert len(versions) == 1
links = repository.list_document_links(db_session, document.id)
assert links[0].organization_id == organization.id
```

Keep all current endpoint/status/response assertions.

- [ ] **Step 2: Add upload-limit and file-policy HTTP tests**

Test a `.exe` upload returns 422 and creates no DB/file object. Test a stream just over 20 MiB returns 413 and creates no DB/file object. Do not rely only on `UploadFile.size`.

- [ ] **Step 3: Run RED against the old routes**

```bash
python -m pytest tests/integration/test_documents_acceptance.py tests/integration/test_organization_documents.py -q
```

Expected: failures from removed legacy model/service signature.

- [ ] **Step 4: Refactor façade routes**

Pass `authorization.user_id` and `DocumentTarget(organization_id=organization_id)` into the universal service. Keep permission dependencies exactly:

```text
documents.view
documents.download
documents.upload
documents.delete
```

Map `DocumentUploadPolicyError -> 422`, `StorageLimitExceeded -> 413`, storage unavailable -> controlled 503, and inaccessible target/document -> 404 where current scope behavior is fail-closed.

Remove the current “store first, inspect actual size, then delete oversized row” route-level workaround; the storage/service layer now enforces streaming max size before promotion/commit.

- [ ] **Step 5: Run compatibility tests**

```bash
python -m pytest tests/integration/test_documents_acceptance.py tests/integration/test_organization_documents.py -q
```

Expected: PASS with unchanged endpoint contracts.

- [ ] **Step 6: Commit**

```bash
git add app/modules/documents/routes.py app/modules/documents/schemas.py tests/integration/test_documents_acceptance.py tests/integration/test_organization_documents.py
git commit -m "refactor: keep organization document API on universal core"
```

---

### Task 9: Keep current document completeness and management report live

**Files:**
- Modify: `app/modules/analytics/repository.py`
- Modify: `tests/integration/test_documents_acceptance.py`
- Modify: `tests/integration/test_document_control.py`
- Modify: `tests/unit/test_management_reports_v2.py` only if it imports the legacy model.

**Interfaces:**
- Current `/api/reports/management` response schema and superuser restriction remain unchanged.
- `load_document_control` consumes `OrganizationDocumentProjection` / universal joins, not a legacy mapped model.
- `app/modules/documents/control.py` classification semantics stay unchanged in CP7.1.

- [ ] **Step 1: Write RED report regression using universal rows only**

Seed organizations, `DocumentRequirement`, universal `Document + current DocumentVersion + DocumentLink` records, then call `/api/reports/management`. Preserve these assertions from existing acceptance behavior:

```python
assert documents["source_available"] is True
assert documents["valid"] == 1
assert documents["expiring_14"] == 1
assert documents["missing"] == 1
```

Also assert a soft-deleted universal document does not satisfy a requirement.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/integration/test_documents_acceptance.py tests/integration/test_document_control.py tests/unit/test_management_reports_v2.py -q
```

Expected: analytics repository still imports/queries `OrganizationDocument`.

- [ ] **Step 3: Refactor analytics read model**

Replace `_DOCUMENT_TABLES` with:

```python
_DOCUMENT_TABLES = {
    "documents", "document_versions", "document_links", "document_requirements"
}
```

Load organization-linked active documents via the compatibility repository or one focused SQL query joining current versions. Keep all existing `DocumentSnapshot`, `RequirementSnapshot`, `classify_document`, `missing_requirements` behavior unchanged.

Do not introduce CP7.2 Compliance states or CP7.4 report navigation here.

- [ ] **Step 4: Run report regressions**

```bash
python -m pytest tests/integration/test_documents_acceptance.py tests/integration/test_document_control.py tests/unit/test_management_reports_v2.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/analytics/repository.py tests/integration/test_documents_acceptance.py tests/integration/test_document_control.py tests/unit/test_management_reports_v2.py
git commit -m "refactor: read management document control from universal core"
```

---

### Task 10: Full migration/security/regression gate and checkpoint documentation

**Files:**
- Modify: `PROJECT_STATUS.md`
- Create: `docs/superpowers/reviews/2026-08-14-stage7-cp71-universal-documents-completion.md`
- Modify only test/docs files needed to record verified evidence; no opportunistic CP7.2 work.

**Interfaces:**
- Produces the CP7.1 completion evidence needed before CP7.2 can branch.

- [ ] **Step 1: Run focused security suite**

```bash
python -m pytest \
  tests/unit/test_storage.py \
  tests/unit/test_document_upload_policy.py \
  tests/integration/test_document_link_access.py \
  tests/integration/test_document_metadata_lifecycle.py \
  tests/integration/test_organization_documents.py -q
```

Expected: PASS, zero skips added.

- [ ] **Step 2: Run migration from legacy state and guarded round trip**

Against disposable PostgreSQL via `TEST_DATABASE_URL`:

```bash
python -m pytest tests/integration/test_universal_documents_migration.py -q
python -m alembic heads
```

Expected: migration tests PASS and exactly one head (`0021_universal_documents`, unless renumbered because canonical advanced).

- [ ] **Step 3: Run full backend regression**

```bash
python -m ruff check app tests alembic
python -m pytest -q
```

Expected: PASS. Do not accept new skips or warnings caused by CP7.1 without resolving them.

- [ ] **Step 4: Run frontend compatibility regression**

From `frontend/`:

```bash
npm run lint
npm run typecheck
npm test -- --run
npm run build
```

Expected: PASS; `/organizations/[id]/documents` needs no user-visible rewrite for CP7.1.

- [ ] **Step 5: Verify no legacy persistence references remain**

Run:

```bash
git grep -n "OrganizationDocument\|organization_documents" -- ':!docs/**' ':!alembic/versions/0016_documents.py' ':!alembic/versions/0021_universal_documents.py'
```

Expected: no production persistence references to the old model/table. Test text may reference the legacy table only where explicitly testing migration compatibility.

- [ ] **Step 6: Verify physical-file preservation on migrated seed**

Use the migration test fixture/storage root to assert the pre-upgrade storage key exists before and after upgrade and that no second file is created for that legacy row. Record the exact evidence in the completion review.

- [ ] **Step 7: Self-review against CP7.1 acceptance**

Confirm all of these with test/command evidence:

```text
[ ] universal tables/services exist
[ ] legacy organization documents migrated without byte copies
[ ] old organization API/UX contract still works
[ ] v2 upload leaves v1 immutable
[ ] one logical document can have multiple typed links
[ ] exactly-one-target is enforced by PostgreSQL
[ ] current-version same-document integrity is enforced
[ ] stale metadata/version mutations conflict, not overwrite
[ ] link-aware scope prevents IDOR/leakage
[ ] deleted documents are hidden but bytes/versions retained
[ ] current completeness + management report remain live
[ ] one Alembic head
[ ] full backend/frontend gates green
```

- [ ] **Step 8: Write completion review and update status**

In the review file record: branch/head, migration head, migration round-trip result, backend test count, frontend test count, Ruff/lint/typecheck/build results, security test evidence, and any explicitly deferred P3 items. Do not claim numbers that were not observed in the command output.

Update `PROJECT_STATUS.md` with **CP7.1 complete only after all gates above pass**. State CP7.2 is next and not yet implemented.

- [ ] **Step 9: Commit documentation**

```bash
git add PROJECT_STATUS.md docs/superpowers/reviews/2026-08-14-stage7-cp71-universal-documents-completion.md
git commit -m "docs: record CP7.1 universal documents completion"
```

- [ ] **Step 10: Push and open a Draft PR**

Push `agent/stage7-cp71-universal-documents` and open a Draft PR targeting `agent/integration-cp52-smart-import-hardening`. Do not merge automatically. The PR body must list the migration/data-preservation strategy, exact verification evidence, and explicitly deferred CP7.2/7.3/7.4 scope.

---

## Implementation dependency order

```text
Task 1 models/constraints
  -> Task 2 migration
  -> Task 3 storage/policy
  -> Task 4 repository projection
  -> Task 5 create/version service
  -> Task 6 links/access
  -> Task 7 metadata lifecycle
  -> Task 8 organization API compatibility
  -> Task 9 current reports compatibility
  -> Task 10 full gate + review
```

Do not parallelize Tasks 1-2, 4-9 against different schema assumptions. Task 3 can be developed independently after the branch/worktree is established, but it must be integrated before Task 5.

## Plan self-review

- **Spec coverage:** Universal logical documents, immutable versions, typed links, migration without byte copies, compatibility façade, local storage safety, optimistic locking, soft delete/restore, scope-aware access, audit, and current report compatibility all map to explicit tasks.
- **Scope control:** Compliance Engine/UI, Reports 2.0, DocumentGeneration, OCR/AI, RTN, NPD actuality, cloud storage and GC are explicitly excluded.
- **Migration ambiguity resolved:** Legacy document IDs are preserved; version/link IDs are deterministic; downgrade is allowed only while the state is representable losslessly and otherwise fails closed.
- **Current-version integrity resolved:** composite `(document_id, version_id)` relationship prevents a document from pointing at another document's version.
- **Duplicate links resolved:** per-target PostgreSQL partial unique indexes prevent duplicate logical links.
- **Oversized upload behavior resolved:** stream limit is enforced inside storage before atomic promotion, not after a full write/DB insert.
- **Type consistency:** `DocumentLifecycleStatus` is distinct from the existing compliance `DocumentStatus` classifier, avoiding enum/name collision.
- **Compatibility source resolved:** current organization endpoints and management report consume universal projections; the legacy mapped `OrganizationDocument` is removed after migration.
- No `TBD`, `TODO`, “implement later”, or silent data-loss path is part of this plan.
