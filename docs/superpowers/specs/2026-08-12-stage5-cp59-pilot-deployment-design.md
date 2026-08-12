# Stage 5.9 — Pilot Deployment v0.1 design

Date: 2026-08-12
Parent checkpoint: Stage 5 / CP5.1 Tasks Core
Base commit: `c7f6efbd16796f6ac207e5717045cc1bc3994d08`

## 1. Goal

Create the first reproducible technical LAN deployment of Spravoshnik EPB without changing domain behavior.

The pilot is intended for controlled internal evaluation on one organization-owned server or Windows workstation with Docker Desktop. It is not a public-internet deployment and is not yet the full production replacement for all EPB work.

Success means a clean machine with Docker can start the stack, migrate a persistent PostgreSQL database, create the first administrator explicitly, expose the browser UI to the LAN, persist files, run worker/scheduler processes, pass health checks, and create a recoverable pilot backup.

## 2. Chosen approach

Use Docker Compose as the single pilot orchestration boundary.

Alternatives considered:

1. **Recommended: Docker Compose with separate process services.** Reuses one backend image for API, migration, worker and scheduler; uses a separate Next.js image and PostgreSQL image. Best isolation, reproducibility and upgrade path for the current modular monolith.
2. Native Windows services plus locally installed PostgreSQL/Node/Python. Simpler conceptually but creates machine-specific setup drift and a harder rollback/update story.
3. One large container for backend, frontend, scheduler and database. Rejected because process failures, persistence, health and upgrades become coupled.

The pilot therefore uses approach 1.

## 3. Runtime topology

```text
LAN browser
    |
    | http://SERVER_IP:${PILOT_HTTP_PORT}
    v
frontend (Next.js)
    |
    | /backend/* -> http://backend:8000/*
    v
backend (FastAPI)
    |
    +---- PostgreSQL
    +---- local file storage

worker ------ PostgreSQL / storage
scheduler --- PostgreSQL / storage
migrate ----- PostgreSQL (one-shot gate)
backup ------ PostgreSQL + storage + backup directory (manual profile)
```

### Services

- `postgres`: PostgreSQL 17, internal Docker network only, persistent named database volume.
- `migrate`: one-shot backend image running `alembic upgrade head` after PostgreSQL is healthy.
- `backend`: FastAPI process, internal only, starts after successful migration, readiness health check uses `/health/ready`.
- `worker`: existing `spravoshnik-worker`, starts after successful migration.
- `scheduler`: existing `spravoshnik-scheduler`, starts after successful migration.
- `frontend`: Next.js standalone production server, the only normal application service published to the LAN.
- `backup`: manual Compose profile that writes a timestamped PostgreSQL dump, storage archive and manifest to the host backup directory.

No message broker, reverse proxy, TLS termination or public ingress is added in Pilot v0.1.

## 4. Images

### Backend image

Create a production-oriented Python 3.12 image containing:

- installed `spravoshnik-epb` package;
- `app/`;
- Alembic configuration and migration history;
- application entry points already defined in `pyproject.toml`.

The same immutable image is used by `migrate`, `backend`, `worker` and `scheduler` so application code and migration history cannot drift between processes.

### Frontend image

Use a multi-stage Node image:

1. install from `package-lock.json` with `npm ci`;
2. build Next.js in standalone mode;
3. copy standalone server, static assets and `public/` into the runtime stage.

`BACKEND_ORIGIN=http://backend:8000` is embedded for the internal rewrite target. The browser never needs a backend host/port and uses same-origin `/backend/*` requests.

## 5. Networking and exposure

- Compose creates one private application network.
- PostgreSQL is not mapped to a host port in the pilot file.
- Backend is not mapped to a host port in the pilot file.
- Worker, scheduler and migrate expose no ports.
- Frontend publishes `${PILOT_HTTP_PORT:-3000}:3000` on the server, therefore LAN clients use `http://SERVER_IP:3000` by default.
- Remote access remains via VPN/LAN. Direct public-internet publishing is explicitly unsupported by this checkpoint.

## 6. Persistence

### Database

Use a named Docker volume for `/var/lib/postgresql/data`.

The normal `docker compose down` command must not destroy data. Documentation must warn against `down -v` except for intentional destructive reset.

### File storage

Use a host bind directory under `./var/pilot/storage` mapped to `/var/lib/spravoshnik/storage`.

This keeps uploaded/generated pilot files visibly inside the local project/server data directory and makes them independently back-up-able.

### Backups

Use `./var/pilot/backups` as a host bind directory. A backup run creates a timestamped directory containing at minimum:

- PostgreSQL custom-format dump;
- compressed storage archive;
- manifest with timestamp, application version and migration/schema head when obtainable.

Pilot v0.1 provides backup creation and a documented restore procedure. Automatic scheduled backup/retention remains a later administration stage.

## 7. Configuration and secrets

Add `deploy/pilot/.env.pilot.example` as a safe template. The real `.env.pilot` is ignored by Git.

Required/operator-set values include:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `PILOT_HTTP_PORT`
- session/login timeout settings as needed.

Production container settings include:

- `APP_ENV=production`
- `STORAGE_ROOT=/var/lib/spravoshnik/storage`
- `LOG_LEVEL=INFO`
- `SESSION_COOKIE_SECURE=false` for the initial plain-HTTP LAN pilot.

The installation guide must explicitly state that `SESSION_COOKIE_SECURE=true` becomes mandatory when HTTPS/TLS is introduced.

No administrator password, database password or API secret is committed to the repository.

## 8. Migration gate and startup ordering

Startup order:

1. PostgreSQL becomes healthy.
2. `migrate` executes `alembic upgrade head` and exits successfully.
3. backend, worker and scheduler may start only after successful migration.
4. frontend starts after backend is healthy.

A failed migration blocks application processes instead of allowing an old schema/new code mismatch.

Application startup does not auto-create an administrator.

## 9. Initial administrator bootstrap

Reuse the existing command:

```text
spravoshnik-bootstrap-superuser --username <name> --name <full name>
```

The operator runs it explicitly in a one-off backend container after migration. Password entry remains interactive by default so credentials are not stored in Compose files or shell history.

Repeated bootstrap with the same username must fail rather than silently replacing credentials.

## 10. Health and observability

Reuse existing backend endpoints:

- `/health/live`
- `/health/ready`
- `/health`

Backend Compose health uses `/health/ready`, which verifies database connectivity and writable storage.

Frontend health may use a local HTTP request to `/`.

Container restart policy for long-running pilot services: `unless-stopped`.

Pilot logs remain Docker/container logs plus the existing application logging configuration. Central log aggregation is out of scope.

## 11. Backup / restore safety

Backup is an explicit operator command, not a background action in Pilot v0.1.

Restore documentation must require:

1. stop application writers;
2. make a safety backup of the current state;
3. restore PostgreSQL dump;
4. restore the matching storage archive;
5. run/verify migrations for the target application version;
6. start services and check `/health/ready`;
7. verify login and representative business data.

No destructive automatic restore command is exposed as a normal always-on service.

## 12. CI / verification

Keep the existing Python CI unchanged for domain regression and add a dedicated pilot deployment workflow scoped to pilot/container/frontend files.

Pilot verification should prove:

- backend Python regression remains green;
- frontend dependency install succeeds;
- frontend lint/typecheck/tests succeed where scripts exist;
- Next.js production build succeeds;
- `docker compose ... config` succeeds with CI-safe non-secret values;
- backend image builds;
- frontend image builds;
- Compose can start PostgreSQL, run migrations and reach backend readiness in a smoke test;
- the pilot compose file does not publish PostgreSQL or backend ports.

The smoke test must clean up its containers/volumes after the CI run.

## 13. Operator documentation

Add a Russian pilot runbook covering:

- prerequisites: Docker Desktop / Docker Engine + Compose;
- first-time `.env.pilot` creation;
- building images;
- starting the stack;
- creating the administrator;
- finding the server LAN IP;
- browser URL for client PCs;
- health/status checks;
- logs;
- manual backup;
- update procedure;
- restore procedure;
- normal stop/start;
- destructive reset warning;
- known pilot limitations.

PowerShell examples are the primary examples because the current development/deployment workstation is Windows; commands remain standard Docker Compose commands where possible.

## 14. Scope exclusions

Pilot v0.1 does **not** add:

- HTTPS/reverse proxy certificates;
- public internet access;
- VPN server configuration;
- automatic scheduled backup/retention;
- automated destructive restore;
- monitoring stack;
- external AI/Ollama containers;
- frontend migration from mock data beyond what already exists;
- Stage 5 CP5.2/CP5.3 domain behavior;
- Stage 6 expertise implementation.

## 15. Acceptance criteria

Pilot v0.1 is ready when all are true:

1. clean Compose build succeeds;
2. PostgreSQL data and application storage survive normal restart/down-up;
3. migration gate reaches current Alembic head before backend starts;
4. `/health/ready` is healthy through the internal backend service;
5. frontend is reachable on the configured LAN port;
6. browser frontend proxy can reach backend via `/backend/*`;
7. first superuser can be created explicitly with no committed password;
8. worker and scheduler stay running after migration;
9. manual backup produces database dump + storage archive + manifest;
10. Russian runbook documents first install, start/stop, update, backup and restore;
11. dedicated pilot CI validates configuration, images and smoke startup;
12. existing backend regression suite remains green;
13. no automatic merge into the integration branch occurs.

## 16. Branch / review policy

Implementation branch: `agent/stage5-cp59-pilot-deployment`.

It is stacked on the final CP5.1 head and will be published as a draft review checkpoint. It must not be merged automatically into `codex/feat-gigastudio-frontend-integration`.
