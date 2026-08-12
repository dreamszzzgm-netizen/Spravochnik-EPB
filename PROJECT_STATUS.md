# Project status

## Current verified development baseline

- Official integration GREEN baseline remains unchanged: `650008fc5a80eaf6165d2d0aba249041aae2a98d`.
- Stacked business checkpoint: **Stage 5 / CP5.1 — Tasks Core backend**, final HEAD `c7f6efbd16796f6ac207e5717045cc1bc3994d08`.
- Active operational checkpoint: **Stage 5.9 — Pilot Deployment v0.1**.
- Feature branch: `agent/stage5-cp59-pilot-deployment`.
- Verified runtime head before this status commit: `539e5565f012d718632ac668fe78ae3e02c4e290`.
- Alembic head remains `0013_stage5_tasks_core`; Pilot Deployment introduces no schema migration.

## Verified Pilot v0.1 deployment

Pilot v0.1 packages the existing modular monolith as a reproducible internal LAN stack using Docker Compose.

Runtime services:

- `postgres` — PostgreSQL 17 with persistent named volume;
- `migrate` — one-shot `alembic upgrade head` gate;
- `backend` — FastAPI application using the shared backend image;
- `worker` — existing background worker using the same backend image;
- `scheduler` — existing scheduler using the same backend image;
- `frontend` — Next.js 16 standalone production server;
- `backup` — manual `maintenance` profile for DB + storage backup.

Security / networking:

- only frontend `${PILOT_HTTP_PORT:-3000}:3000` is published to the host/LAN;
- PostgreSQL and backend have no host port mapping in `docker-compose.pilot.yml`;
- frontend proxies same-origin `/backend/*` to internal `http://backend:8000`;
- application processes start only after successful migration;
- first administrator is created explicitly with `spravoshnik-bootstrap-superuser` and no password is committed;
- real `deploy/pilot/.env.pilot` and pilot runtime storage/backups are ignored by Git;
- initial plain-HTTP LAN pilot uses `SESSION_COOKIE_SECURE=false`; the runbook requires `true` when TLS is introduced;
- public-internet deployment is not supported; use trusted LAN/VPN.

Persistence / recovery:

- PostgreSQL uses named volume `pilot_postgres_data`;
- application file storage is persisted at `./var/pilot/storage`;
- manual backups are persisted at `./var/pilot/backups`;
- backup output includes `database.dump`, `storage.tar.gz`, and `manifest.txt`;
- manifest records timestamp, app version and schema head;
- Russian runbook documents install, start/stop, LAN access, bootstrap, health, logs, backup, update and restore safety;
- runbook explicitly warns that normal operators must not use `docker compose down -v` because it destroys the database volume.

## Pilot verification evidence

At verified runtime head `539e5565f012d718632ac668fe78ae3e02c4e290`:

### Backend CI

GitHub Actions run #217 (`31606605532`):

- Ruff: PASS;
- `alembic upgrade head`: PASS through `0013_stage5_tasks_core`;
- pytest: **555 passed / 282 warnings**.

### Dedicated Pilot CI

GitHub Actions `pilot-ci` run #219 (`31606605562`): **GREEN**.

`frontend-quality`:

- `npm ci`: PASS;
- ESLint: PASS;
- TypeScript typecheck: PASS;
- Vitest: PASS;
- Next.js production build: PASS.

`pilot-images-and-smoke`:

- rendered Compose configuration/security port checks: PASS;
- backend Docker image build: PASS;
- frontend standalone Docker image build: PASS;
- expected backend CLI entry points present: PASS;
- PostgreSQL startup/health: PASS;
- migration container exit code `0`: PASS;
- backend `/health/ready`: PASS;
- backend, worker, scheduler and frontend running: PASS;
- frontend same-origin `/backend/health/live` proxy: PASS;
- manual backup profile: PASS;
- backup manifest schema head `0013_stage5_tasks_core`: PASS;
- disposable CI stack cleanup: PASS.

## Completed through CP5.1

- Stage 0 — application foundation.
- Stage 1 — identity, sessions, RBAC, permission scopes and audit foundation.
- Stage 2 — organizations and contacts.
- Stage 3 — OPO, technical devices, buildings, custom fields and scoped authorization closure.
- Stage 4 CP4.1 — Contracts Core backend.
- Stage 4 CP4.2 — Contract Lifecycle and Addenda backend.
- Stage 5 CP5.1 — Tasks Core backend, including scoped API, multiple assignees, business links, task lifecycle, computed overdue, comments, audit and hardening.

## Stage 5 boundary / deferred work

### CP5.2 — Workflow Engine

Deferred intentionally:

- workflow templates and immutable versions;
- workflow task templates;
- source workflow/version metadata on generated tasks;
- business-function assignee resolution;
- workflow instantiation.

### CP5.3 — Contract ↔ Tasks integration

Deferred intentionally:

- first real linked work start driving internal contract `signed -> in_progress`;
- deadline pause/shift on contract suspension/resume;
- unfinished task cancellation on contract termination;
- real Tasks completion-readiness provider for contracts.

### Later owning stages

- Stage 6 adds `task_expertises` after the physical `expertises` table exists and is the recommended point for the first genuinely useful production-workflow pilot.
- Stage 8 adds task document attachments and broader document/comment relations.
- Frontend task/business screens that still use mock-data are not converted by Pilot v0.1.
- Automatic scheduled backup/retention, TLS/reverse proxy and monitoring remain later administration/deployment work.

## Pilot operator documentation

- Design: `docs/superpowers/specs/2026-08-12-stage5-cp59-pilot-deployment-design.md`
- Implementation plan: `docs/superpowers/plans/2026-08-12-stage5-cp59-pilot-deployment.md`
- Runbook: `docs/PILOT_DEPLOYMENT.md`
- Environment template: `deploy/pilot/.env.pilot.example`
- Compose file: `docker-compose.pilot.yml`

## Integration policy

Pilot Deployment v0.1 is stacked on the final CP5.1 head and must remain a **draft review checkpoint**. **Do not merge it into `codex/feat-gigastudio-frontend-integration` automatically.** Integration remains untouched until explicit user approval.
