# Project status

## Current version
Application scaffold: **v0.1.0**

## Completed
- Stage 0 implementation.
- Stage 1 implementation.
- Unit acceptance available in this environment: 14 passed.

## Pending mandatory Stage 1 gate
The repository requires a real PostgreSQL run before Stage 2:
- `alembic upgrade head`;
- PostgreSQL integration tests;
- identity migration constraints;
- login lock transaction behavior;
- session timeout/revocation persistence;
- RBAC scope queries.

The CI workflow already provisions PostgreSQL 17 and runs these checks.

Per `docs/DEVELOPMENT_PLAN.md`, Stage 2 is not started until this gate is green.
