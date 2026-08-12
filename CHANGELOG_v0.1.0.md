# Changelog v0.1.0

## Stage 1
- Added identity module.
- Added employees and employee business functions.
- Added users, Argon2id password hashes and superuser bootstrap.
- Added RBAC permission catalog and scoped role assignments.
- Added server-side session storage with hashed tokens.
- Added login/logout, absolute timeout, inactivity timeout and login lockout.
- Added session revocation and administrative password reset.
- Added authentication/administration audit events.
- Added PostgreSQL migration `0002_stage1`.
- Added unit and PostgreSQL integration tests for Stage 1.

## Stage gate
Stage 2 must not start until PostgreSQL migration/integration acceptance is green,
as required by `docs/DEVELOPMENT_PLAN.md`.

### Issue #3 — session investigation
A quick investigation was performed on 2026-08-12 as part of Issue #3. Unit tests run locally: 14 passed, 8 skipped (integration tests were skipped because TEST_DATABASE_URL was not set). No code changes were required after the investigation; integration tests should be run in CI or locally with a PostgreSQL test database to fully validate migrations and DB invariants.
