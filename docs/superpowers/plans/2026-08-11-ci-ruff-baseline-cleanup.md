# CI/Ruff Baseline Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the repository-wide Ruff gate by fixing exactly the three proven baseline lint findings without changing runtime behavior.

**Architecture:** Treat `python -m ruff check app tests` as the RED/GREEN regression gate for this checkpoint. Make only three syntax/import cleanups in existing files; do not alter authorization, API behavior, migrations, frontend, dependencies, Ruff configuration, or GitHub Actions. After Ruff turns green, run the full PostgreSQL backend suite and migration invariants on the exact implementation SHA.

**Tech Stack:** Python 3.12+, Ruff, pytest, PostgreSQL 17, Alembic, GitHub Actions.

## Global Constraints

- Repository: `dreamszzzgm-netizen/Spravochnik-EPB`.
- Base branch: `codex/feat-gigastudio-frontend-integration`.
- Verified base SHA: `b81621ffddaac09b7556ba0ed8ac90337edf5fac`.
- Working branch: `agent/ci-ruff-baseline-cleanup`.
- Alembic head/current must remain `0010_stage3`.
- Integration verification must use a real PostgreSQL test database with `TEST_DATABASE_URL`; skipped integration tests are not acceptable.
- Do not modify `frontend/**`.
- Do not modify `alembic/**` or database schema.
- Do not modify authorization logic or API behavior.
- Do not modify Ruff configuration or GitHub Actions workflow.
- Do not run repository-wide auto-fix as part of the implementation.
- Implementation diff is limited to the three proven Ruff files plus the design and plan documents.

---

## File Map

**Modify**
- `app/modules/identity/routes.py` — remove the blank separation that makes the application import block unsorted.
- `app/modules/organizations/models.py` — wrap one 101-character `Enum(...)` expression without changing arguments.
- `tests/integration/test_organizations.py` — remove unused `OrganizationContact` import.

**Documentation only**
- `docs/superpowers/specs/2026-08-11-ci-ruff-baseline-cleanup-design.md`
- `docs/superpowers/plans/2026-08-11-ci-ruff-baseline-cleanup.md`

---

### Task 1: Fix identity import ordering

**Files:**
- Modify: `app/modules/identity/routes.py:8-18`

**Interfaces:**
- Consumes the existing identity module imports.
- Produces the exact same imported symbols and runtime module namespace.

- [ ] **Step 1: Preserve RED evidence**

The existing GitHub Actions run on baseline `b81621f` already reports:

```text
I001 app/modules/identity/routes.py:1
Import block is un-sorted or un-formatted
```

No additional functional test is required because this checkpoint changes formatting only and Ruff is the behavior-under-test.

- [ ] **Step 2: Apply the minimal import-group fix**

Change only this sequence:

```python
from app.modules.identity.dependencies import (
    get_current_user,
    get_session_token,
    require_permission,
)
from app.modules.identity.repository import get_user_permission_codes

from app.modules.identity.models import (
```

to:

```python
from app.modules.identity.dependencies import (
    get_current_user,
    get_session_token,
    require_permission,
)
from app.modules.identity.models import (
```

and place:

```python
from app.modules.identity.repository import get_user_permission_codes
```

immediately after the closing `)` of the models import block and before `from app.modules.identity.schemas import (`. This preserves all symbols while matching Ruff's import ordering.

- [ ] **Step 3: Run targeted Ruff**

```powershell
python -m ruff check app/modules/identity/routes.py
```

Expected: `All checks passed!`

---

### Task 2: Wrap the organization contact enum expression

**Files:**
- Modify: `app/modules/organizations/models.py:71-74`

**Interfaces:**
- Consumes the existing `ContactType`, `enum_values`, and SQLAlchemy `Enum` expression.
- Produces an identical SQLAlchemy mapped column definition.

- [ ] **Step 1: Preserve RED evidence**

The existing baseline Ruff failure is:

```text
E501 app/modules/organizations/models.py:72:101
Line too long (101 > 100)
```

- [ ] **Step 2: Wrap without changing arguments**

Replace:

```python
Enum(ContactType, name="contact_type", values_callable=enum_values, create_constraint=False),
```

with:

```python
Enum(
    ContactType,
    name="contact_type",
    values_callable=enum_values,
    create_constraint=False,
),
```

Do not change defaults, nullability, enum name, or values callable.

- [ ] **Step 3: Run targeted Ruff**

```powershell
python -m ruff check app/modules/organizations/models.py
```

Expected: `All checks passed!`

---

### Task 3: Remove the unused organization contact import

**Files:**
- Modify: `tests/integration/test_organizations.py:10-17`

**Interfaces:**
- Consumes the existing test module imports.
- Produces identical test behavior because `OrganizationContact` is not referenced in the file.

- [ ] **Step 1: Preserve RED evidence**

The existing baseline Ruff failure is:

```text
F401 tests/integration/test_organizations.py:14
OrganizationContact imported but unused
```

- [ ] **Step 2: Remove exactly one import**

Change:

```python
from app.modules.organizations.models import (
    ContactType,
    IdentifierType,
    Organization,
    OrganizationContact,
    OrganizationIdentifier,
    OrganizationType,
)
```

to:

```python
from app.modules.organizations.models import (
    ContactType,
    IdentifierType,
    Organization,
    OrganizationIdentifier,
    OrganizationType,
)
```

No test bodies change.

- [ ] **Step 3: Run targeted Ruff**

```powershell
python -m ruff check tests/integration/test_organizations.py
```

Expected: `All checks passed!`

---

### Task 4: Execute repository-wide GREEN verification

**Files:**
- No further implementation changes expected.

**Interfaces:**
- Verifies the entire backend lint/test/migration boundary on the exact implementation tree.

- [ ] **Step 1: Global Ruff**

```powershell
python -m ruff check app tests
```

Required: `All checks passed!` and exit code 0.

- [ ] **Step 2: PostgreSQL test database**

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5433/spravoshnik_test"
python -m pytest -q
```

Required: `0 failed`, `0 errors`, `0 skipped`. The expected count at the current baseline is 411 passed.

- [ ] **Step 3: Alembic invariant**

```powershell
python -m alembic heads
python -m alembic current
```

Required:

```text
0010_stage3 (head)
0010_stage3 (head)
```

- [ ] **Step 4: Diff hygiene**

```powershell
git diff --check
git status -sb
git diff --stat b81621f...HEAD
git diff --name-only b81621f...HEAD
```

Required implementation scope:

```text
app/modules/identity/routes.py
app/modules/organizations/models.py
tests/integration/test_organizations.py
docs/superpowers/specs/2026-08-11-ci-ruff-baseline-cleanup-design.md
docs/superpowers/plans/2026-08-11-ci-ruff-baseline-cleanup.md
```

No frontend, migrations, configuration, workflow, dependency, or unrelated file changes are allowed.

---

### Task 5: GitHub Actions verification and handoff

**Files:**
- No further implementation changes expected.

- [ ] **Step 1: Push the exact implementation branch**

```powershell
git push origin agent/ci-ruff-baseline-cleanup
```

- [ ] **Step 2: Inspect GitHub Actions**

The workflow must now pass:

```text
ruff check app tests
alembic upgrade head
pytest
```

If Ruff still fails, stop and inspect the exact new finding before any additional edit. If Alembic or pytest fails after Ruff becomes green, classify it as a new blocker rather than widening the lint cleanup silently.

- [ ] **Step 3: Handoff exact SHA**

Report:

```text
Branch / exact HEAD
Global Ruff result
Full PostgreSQL pytest result
Alembic heads/current
GitHub Actions result
git diff --check
changed file list
blocking findings
verdict READY FOR PR / BLOCKED
```

---

## Completion Gate

This checkpoint is `COMPLETE` only with evidence on the exact implementation SHA:

```text
Global Ruff                  PASS, 0 errors
Full PostgreSQL pytest       PASS, 0 failed/errors/skipped
Alembic heads/current        0010_stage3
GitHub Actions Ruff          PASS
GitHub Actions Alembic       PASS
GitHub Actions pytest        PASS
git diff --check             clean
frontend diff                none
migration diff               none
workflow/config diff          none
behavioral code changes      none
changed implementation files exactly 3
```
