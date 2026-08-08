# Stage 0 Acceptance

## A. Scope

PASS if no business modules are introduced.

## B. Database

- PostgreSQL target;
- schema created only through Alembic;
- Stage 0 tables: `stored_files`, `background_jobs`, `outbox_events`;
- `TIMESTAMPTZ` used for event timestamps;
- mandatory SHA-256 on stored files.

## C. Backend

- FastAPI boots;
- `/health/live` works without external dependencies;
- `/health/ready` verifies database and storage;
- request/correlation IDs are propagated.

## D. Infrastructure

- local private storage adapter;
- worker separate from scheduler;
- persistent outbox;
- DB-backed jobs with `FOR UPDATE SKIP LOCKED`;
- active job idempotency index.

## E. Tests

One command:

```bash
pytest
```

CI supplies a real PostgreSQL service and runs migrations + all tests.

## F. Invariants

- user-supplied filenames are never storage paths;
- SHA-256 is mandatory;
- job/outbox retries keep technical failure metadata;
- Stage 0 contains no business workflows.

## G. Security

- no secrets committed;
- `.env` ignored;
- storage rejects traversal keys;
- production API docs disabled;
- logs have an explicit safe-metadata boundary.

## H. Regression

Not applicable: first implementation stage.

## I. Verdict

Local sandbox: unit/compile verification can run without Docker.
Full acceptance requires CI or a local PostgreSQL instance.
