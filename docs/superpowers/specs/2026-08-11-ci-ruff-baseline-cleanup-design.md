# CI/Ruff Baseline Cleanup — Design

## Goal

Restore the global backend Ruff gate on the current integration baseline without changing application behavior, database schema, frontend behavior, or authorization semantics.

## Baseline

- Repository: `dreamszzzgm-netizen/Spravochnik-EPB`
- Base branch: `codex/feat-gigastudio-frontend-integration`
- Verified base SHA: `b81621ffddaac09b7556ba0ed8ac90337edf5fac`
- Working branch: `agent/ci-ruff-baseline-cleanup`
- Known GitHub Actions failure: `ruff check app tests`

## Confirmed Ruff Findings

Exactly three baseline findings are in scope:

1. `I001 app/modules/identity/routes.py:1` — import block ordering/formatting.
2. `E501 app/modules/organizations/models.py:72` — line length 101 > 100.
3. `F401 tests/integration/test_organizations.py:14` — unused `OrganizationContact` import.

## Approaches Considered

### A. Three minimal manual fixes — selected

Make only the exact formatting/import edits needed for the three findings.

Benefits:
- smallest diff;
- no behavior change;
- easiest review and regression attribution;
- preserves the verified Stage 3 authorization baseline.

### B. Run `ruff --fix` across the repository — rejected

This could modify unrelated files and expand the checkpoint beyond the three proven findings.

### C. Suppress findings with `# noqa` or configuration changes — rejected

This would hide debt instead of fixing it and would weaken future lint enforcement.

## Planned Changes

### `app/modules/identity/routes.py`

Move the `get_user_permission_codes` import into the correctly ordered application import group. No imported symbol or runtime behavior changes.

### `app/modules/organizations/models.py`

Wrap the `Enum(...)` call across multiple lines. The SQLAlchemy expression remains semantically identical.

### `tests/integration/test_organizations.py`

Remove the unused `OrganizationContact` import only. No test logic changes.

## Explicit Non-Goals

Do not modify:

- authorization logic;
- API behavior;
- models beyond line wrapping;
- migrations or Alembic revisions;
- frontend files;
- dependencies;
- Ruff configuration;
- GitHub Actions workflow;
- unrelated lint warnings;
- tests except removal of the unused import.

## Verification

The checkpoint is complete only when evidence on the exact implementation SHA shows:

1. `python -m ruff check app tests` — PASS, 0 errors.
2. `python -m pytest -q` with `TEST_DATABASE_URL` set — PASS, 0 failed/errors/skipped.
3. `python -m alembic heads` — `0010_stage3 (head)`.
4. `python -m alembic current` — `0010_stage3 (head)`.
5. `git diff --check` — clean.
6. Diff contains only the design/plan documents and the three explicitly listed source/test files.
7. GitHub Actions reaches and passes Ruff; subsequent Alembic/pytest steps must be inspected rather than assumed.

## Risk Assessment

Risk is low because all three implementation edits are syntactic/non-behavioral. The main process risk is accidental scope expansion; therefore repository-wide auto-fix and unrelated cleanup are prohibited in this checkpoint.
