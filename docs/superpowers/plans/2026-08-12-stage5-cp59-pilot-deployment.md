# Stage 5.9 Pilot Deployment v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the verified CP5.1 application as a reproducible LAN pilot stack with persistent PostgreSQL/storage, gated migrations, frontend proxying, worker/scheduler processes, explicit administrator bootstrap, manual backup and smoke-tested deployment instructions.

**Architecture:** Docker Compose orchestrates one PostgreSQL service, one immutable backend image reused by migrate/API/worker/scheduler, one standalone Next.js frontend image, and a manual backup profile. Only the frontend port is published to the LAN; database/backend remain private. Existing Alembic, health and bootstrap commands are reused rather than duplicated.

**Tech Stack:** Docker Engine + Docker Compose v2, Python 3.12, FastAPI/Uvicorn, Alembic, PostgreSQL 17, Node 22, Next.js 16 standalone output, GitHub Actions, PowerShell-oriented operator documentation.

## Global Constraints

- Branch: `agent/stage5-cp59-pilot-deployment`, based exactly on CP5.1 `c7f6efbd16796f6ac207e5717045cc1bc3994d08`.
- Pilot is LAN/VPN only; no direct public-internet deployment.
- Only frontend is host-published by the pilot Compose file.
- PostgreSQL and application storage must persist across normal `down` / `up` cycles.
- Migration is a one-shot gate and backend/worker/scheduler cannot start after a failed migration.
- No committed administrator password, database password, API key or generated `.env.pilot` file.
- Initial superuser creation reuses `spravoshnik-bootstrap-superuser` and remains explicit/interactively passworded.
- Existing domain behavior and Alembic schema are unchanged by this checkpoint.
- Existing Python CI remains authoritative for backend regression.
- `SESSION_COOKIE_SECURE=false` is allowed only for the initial plain-HTTP LAN pilot and documentation must require `true` once TLS is added.
- No automatic integration merge.

---

## File structure

**Create**

- `Dockerfile.backend` — immutable backend runtime image for API/migrate/worker/scheduler.
- `.dockerignore` — excludes local data, VCS, caches and frontend build artifacts from backend context.
- `frontend/Dockerfile` — multi-stage standalone Next.js image.
- `docker-compose.pilot.yml` — pilot runtime topology and maintenance backup profile.
- `deploy/pilot/.env.pilot.example` — non-secret configuration template.
- `deploy/pilot/backup.sh` — container-side DB + storage backup command.
- `tests/unit/test_pilot_deployment_contract.py` — repository-level pilot security/config contract.
- `.github/workflows/pilot-ci.yml` — compose/image/frontend/smoke validation.
- `docs/PILOT_DEPLOYMENT.md` — Russian operator runbook.

**Modify**

- `frontend/next.config.mjs` — enable standalone output while preserving existing rewrites/security headers.
- `.gitignore` — ignore real pilot env and pilot runtime data while retaining example/runbook files.
- `PROJECT_STATUS.md` — record pilot checkpoint only after verification.

---

### Task 1: Define the deployment security contract (RED)

**Files:**
- Create: `tests/unit/test_pilot_deployment_contract.py`

**Interfaces:**
- Consumes: repository paths only; no Docker daemon dependency.
- Produces: a stable file/config contract that later tasks make GREEN.

- [ ] **Step 1: Write failing repository-contract tests**

Create tests using `pathlib.Path` only so normal `pytest` does not require Docker:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pilot_files_exist():
    for relative in (
        "Dockerfile.backend",
        "frontend/Dockerfile",
        "docker-compose.pilot.yml",
        "deploy/pilot/.env.pilot.example",
        "deploy/pilot/backup.sh",
        "docs/PILOT_DEPLOYMENT.md",
    ):
        assert (ROOT / relative).is_file(), relative


def test_pilot_compose_exposes_only_frontend():
    compose = (ROOT / "docker-compose.pilot.yml").read_text(encoding="utf-8")
    assert '${PILOT_HTTP_PORT:-3000}:3000' in compose
    assert "5432:5432" not in compose
    assert "8000:8000" not in compose
    assert "service_completed_successfully" in compose
    assert "/health/ready" in compose


def test_pilot_has_no_committed_default_secrets():
    env_example = (ROOT / "deploy/pilot/.env.pilot.example").read_text(
        encoding="utf-8"
    )
    assert "POSTGRES_PASSWORD=CHANGE_ME" in env_example
    assert "ADMIN_PASSWORD=" not in env_example
```

Also assert the compose names all required services (`postgres`, `migrate`, `backend`, `worker`, `scheduler`, `frontend`, `backup`), uses `APP_ENV=production`, maps storage/backups to `./var/pilot/...`, and does not contain a hard-coded `spravoshnik:spravoshnik` production password.

- [ ] **Step 2: Run RED test**

Run:

```bash
pytest tests/unit/test_pilot_deployment_contract.py -q
```

Expected: FAIL because the pilot deployment files do not yet exist.

- [ ] **Step 3: Commit RED**

```bash
git add tests/unit/test_pilot_deployment_contract.py
git commit -m "test(pilot): define deployment security contract"
```

Review gate: failures must be caused by missing pilot files/contract, not import/lint defects.

---

### Task 2: Build the reusable backend container image

**Files:**
- Create: `Dockerfile.backend`
- Create: `.dockerignore`
- Test: `tests/unit/test_pilot_deployment_contract.py`

**Interfaces:**
- Consumes: `pyproject.toml`, `README.md`, `app/`, `alembic/`, `alembic.ini`.
- Produces: image containing `spravoshnik-api`, `spravoshnik-worker`, `spravoshnik-scheduler`, `spravoshnik-bootstrap-superuser`, and `alembic`.

- [ ] **Step 1: Extend the contract test for backend image contents**

Assert `Dockerfile.backend` contains Python 3.12, copies Alembic history, installs the package without dev extras, creates `/var/lib/spravoshnik/storage`, and defaults to `spravoshnik-api`.

- [ ] **Step 2: Verify RED**

```bash
pytest tests/unit/test_pilot_deployment_contract.py -q
```

Expected: backend Dockerfile assertions FAIL.

- [ ] **Step 3: Create `Dockerfile.backend`**

Required shape:

```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY alembic ./alembic
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && mkdir -p /var/lib/spravoshnik/storage
ENV STORAGE_ROOT=/var/lib/spravoshnik/storage
EXPOSE 8000
CMD ["spravoshnik-api"]
```

Do not embed `DATABASE_URL` or credentials in the image.

- [ ] **Step 4: Create `.dockerignore`**

Exclude at minimum `.git`, `.venv`, Python caches, `.pytest_tmp`, `frontend/node_modules`, `frontend/.next`, `var/`, `.env`, `.env.pilot`, editor artifacts and test caches. Do not exclude Alembic or README/pyproject files required by the build.

- [ ] **Step 5: Run unit contract + Python regression**

```bash
pytest tests/unit/test_pilot_deployment_contract.py -q
ruff check app tests
```

Expected: PASS for backend-image assertions.

- [ ] **Step 6: Build backend image in GitHub Actions or Docker-capable environment**

```bash
docker build -f Dockerfile.backend -t spravoshnik-epb-backend:pilot .
```

Expected: image build succeeds and `docker run --rm ... spravoshnik-api --help` is not required because the entry point starts a server; instead verify installed CLI with:

```bash
docker run --rm --entrypoint sh spravoshnik-epb-backend:pilot -c \
  'command -v spravoshnik-api && command -v spravoshnik-worker && command -v spravoshnik-scheduler && command -v spravoshnik-bootstrap-superuser && command -v alembic'
```

- [ ] **Step 7: Commit GREEN**

```bash
git add Dockerfile.backend .dockerignore tests/unit/test_pilot_deployment_contract.py
git commit -m "feat(pilot): add backend runtime image"
```

---

### Task 3: Build standalone Next.js frontend image

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `frontend/next.config.mjs`
- Test: `tests/unit/test_pilot_deployment_contract.py`

**Interfaces:**
- Consumes: `frontend/package-lock.json`, existing Next.js app and `BACKEND_ORIGIN` rewrite.
- Produces: runtime server on `0.0.0.0:3000` with `/backend/*` routed to `http://backend:8000`.

- [ ] **Step 1: Extend RED contract**

Assert:

- `next.config.mjs` contains `output: "standalone"`;
- `frontend/Dockerfile` uses `npm ci` and `npm run build`;
- runtime copies `.next/standalone`, `.next/static`, and `public`;
- runtime sets `HOSTNAME=0.0.0.0` and exposes 3000;
- backend origin is `http://backend:8000` in the container build/runtime environment.

- [ ] **Step 2: Verify RED**

```bash
pytest tests/unit/test_pilot_deployment_contract.py -q
```

Expected: frontend container assertions FAIL.

- [ ] **Step 3: Enable standalone output without removing existing settings**

Modify the exported Next config to include:

```javascript
output: "standalone",
```

Preserve current rewrites and security headers.

- [ ] **Step 4: Create multi-stage `frontend/Dockerfile`**

Use Node 22 Alpine. Build stage runs `npm ci` and `npm run build` with `BACKEND_ORIGIN=http://backend:8000`. Runtime copies only production standalone output/static/public and runs `node server.js` as a non-root Node user when supported by the base image.

- [ ] **Step 5: Run frontend quality gates**

From `frontend/` run the scripts actually defined in `package.json`:

```bash
npm ci
npm run lint
npm test -- --run
npm run build
```

If `typecheck` is defined, run it as well. Do not invent a missing script.

- [ ] **Step 6: Build frontend image**

```bash
docker build -f frontend/Dockerfile -t spravoshnik-epb-frontend:pilot frontend
```

Expected: build succeeds.

- [ ] **Step 7: Commit GREEN**

```bash
git add frontend/Dockerfile frontend/next.config.mjs tests/unit/test_pilot_deployment_contract.py
git commit -m "feat(pilot): add standalone frontend image"
```

---

### Task 4: Compose topology, configuration, migration gate and backup

**Files:**
- Create: `docker-compose.pilot.yml`
- Create: `deploy/pilot/.env.pilot.example`
- Create: `deploy/pilot/backup.sh`
- Modify: `.gitignore`
- Test: `tests/unit/test_pilot_deployment_contract.py`

**Interfaces:**
- Consumes: backend/frontend images from Tasks 2-3, existing `/health/ready`, Alembic, bootstrap CLI.
- Produces: complete pilot orchestration plus manual backup profile.

- [ ] **Step 1: Extend RED contract for topology/security**

Assert compose contains:

```text
postgres
migrate
backend
worker
scheduler
frontend
backup
```

and the following invariants:

```text
postgres -> healthcheck pg_isready
migrate -> depends_on postgres: service_healthy
backend/worker/scheduler -> depends_on migrate: service_completed_successfully
frontend -> depends_on backend: service_healthy
backend health -> /health/ready
only frontend ports -> ${PILOT_HTTP_PORT:-3000}:3000
storage bind -> ./var/pilot/storage
backup bind -> ./var/pilot/backups
backup profile -> maintenance
```

Also assert `.gitignore` excludes `deploy/pilot/.env.pilot`, `var/pilot/storage/`, and `var/pilot/backups/`.

- [ ] **Step 2: Verify RED**

```bash
pytest tests/unit/test_pilot_deployment_contract.py -q
```

Expected: topology assertions FAIL.

- [ ] **Step 3: Create environment template**

Use clearly invalid/change-required values, e.g.:

```dotenv
PILOT_HTTP_PORT=3000
POSTGRES_USER=spravoshnik
POSTGRES_DB=spravoshnik
POSTGRES_PASSWORD=CHANGE_ME
DATABASE_URL=postgresql+psycopg://spravoshnik:CHANGE_ME@postgres:5432/spravoshnik
SESSION_COOKIE_SECURE=false
```

Document URL-encoding requirements for special characters in `DATABASE_URL`; do not silently construct credentials in code.

- [ ] **Step 4: Create `docker-compose.pilot.yml`**

Use one backend build anchor/config shared by migrate/backend/worker/scheduler. Long-running services use `restart: unless-stopped`; migrate is one-shot. Set `APP_ENV=production`, storage path, database URL and existing timing settings from environment. Do not publish database/backend ports.

- [ ] **Step 5: Create `deploy/pilot/backup.sh`**

The script runs inside a PostgreSQL 17 Alpine maintenance container with `/storage` read-only and `/backups` writable. Required algorithm:

```sh
set -eu
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="/backups/$STAMP"
mkdir -p "$TARGET"
pg_dump -Fc -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$TARGET/database.dump"
tar -czf "$TARGET/storage.tar.gz" -C /storage .
printf 'timestamp=%s\napp_version=%s\n' "$STAMP" "${APP_VERSION:-unknown}" > "$TARGET/manifest.txt"
```

Use `PGPASSWORD` from runtime environment only. Never echo passwords.

- [ ] **Step 6: Validate Compose syntax with safe CI env**

Create a temporary non-secret env file (not committed) and run:

```bash
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml config
```

Expected: exit 0.

Inspect rendered ports and confirm only frontend publishes host ports.

- [ ] **Step 7: Run unit contract**

```bash
pytest tests/unit/test_pilot_deployment_contract.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit GREEN**

```bash
git add docker-compose.pilot.yml deploy/pilot/.env.pilot.example deploy/pilot/backup.sh .gitignore tests/unit/test_pilot_deployment_contract.py
git commit -m "feat(pilot): add LAN compose and backup topology"
```

---

### Task 5: Dedicated pilot CI and real smoke startup

**Files:**
- Create: `.github/workflows/pilot-ci.yml`
- Test: existing Python tests + pilot contract + real Docker Compose smoke.

**Interfaces:**
- Consumes: all deployment artifacts from Tasks 2-4.
- Produces: objective GitHub verification that images/config/startup are usable.

- [ ] **Step 1: Add a failing/verification-only workflow on the pilot branch**

Trigger on `push` and `pull_request` when pilot/container/frontend files change. Workflow must not use production secrets.

- [ ] **Step 2: Add `frontend-quality` job**

Steps:

```text
checkout
setup Node 22 with npm cache
cd frontend && npm ci
run existing lint/typecheck/test scripts
BACKEND_ORIGIN=http://backend:8000 npm run build
```

- [ ] **Step 3: Add `pilot-images-and-smoke` job**

Create a temporary CI env with a throwaway database password and `DATABASE_URL` pointing at `postgres`. Then run:

```bash
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml config
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml build backend frontend
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml up -d postgres
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml run --rm migrate
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml up -d backend
```

Poll backend container health until healthy, then execute an internal health request:

```bash
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml exec -T backend \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready').read().decode())"
```

Then start worker/scheduler/frontend and assert all long-running services are running. Use a final `if: always()` cleanup:

```bash
docker compose --env-file /tmp/pilot.env -f docker-compose.pilot.yml down -v --remove-orphans
```

CI uses `-v` only because CI state is disposable; operator docs must not use it for normal pilot shutdown.

- [ ] **Step 4: Run/check GitHub Actions**

Expected:

- existing `ci` remains GREEN;
- `pilot-ci` frontend job GREEN;
- compose config/build/smoke GREEN.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pilot-ci.yml
git commit -m "ci(pilot): validate images compose and smoke startup"
```

---

### Task 6: Russian pilot runbook and operator acceptance

**Files:**
- Create: `docs/PILOT_DEPLOYMENT.md`
- Modify: `PROJECT_STATUS.md`
- Test: `tests/unit/test_pilot_deployment_contract.py`

**Interfaces:**
- Consumes: verified compose commands and service names.
- Produces: exact Windows/PowerShell-oriented installation/update/backup/restore procedure.

- [ ] **Step 1: Write the runbook using only commands verified by Task 5**

Required sections:

1. prerequisites and server requirements;
2. clone/update repository and select pilot branch/release;
3. copy `deploy/pilot/.env.pilot.example` to `deploy/pilot/.env.pilot`;
4. generate/change database password and update URL safely;
5. build stack;
6. first start;
7. explicit superuser bootstrap with interactive password;
8. identify server LAN IPv4 address (`ipconfig`) and open `http://SERVER_IP:PORT` from another LAN computer;
9. health/status (`docker compose ps`, backend health via exec);
10. logs;
11. normal stop/start without `-v`;
12. manual backup using maintenance profile;
13. update procedure: backup -> pull -> build -> migrate/start -> health check;
14. restore safety procedure;
15. destructive reset warning for `down -v`;
16. plain HTTP/session cookie limitation and TLS future rule;
17. known functional limitations (technical pilot, frontend mocks, no Stage 6 expertises yet).

- [ ] **Step 2: Make contract test require critical safety language**

Assert the runbook contains `down -v` warning, backup-before-update/restore, VPN/LAN restriction, interactive bootstrap command, and `SESSION_COOKIE_SECURE` TLS note.

- [ ] **Step 3: Run deployment contract and full backend regression**

```bash
pytest tests/unit/test_pilot_deployment_contract.py -q
ruff check app tests
alembic upgrade head
pytest
```

Expected: all PASS.

- [ ] **Step 4: Update `PROJECT_STATUS.md` only with fresh evidence**

Record exact final pilot HEAD, existing Alembic head (`0013_stage5_tasks_core`; no schema migration is introduced), backend test count, pilot workflow result, image/smoke result and deployment branch.

- [ ] **Step 5: Commit documentation/status**

```bash
git add docs/PILOT_DEPLOYMENT.md PROJECT_STATUS.md tests/unit/test_pilot_deployment_contract.py
git commit -m "docs(pilot): add LAN installation and recovery runbook"
```

---

### Task 7: Whole-branch verification and stacked draft PR

**Files:**
- Review all files changed from CP5.1 base.
- No production edits unless review/verification proves a defect.

**Interfaces:**
- Consumes: Tasks 1-6.
- Produces: reviewable Pilot Deployment v0.1 checkpoint; no merge.

- [ ] **Step 1: Verify ancestry**

Compare base `c7f6efbd16796f6ac207e5717045cc1bc3994d08` to pilot HEAD. Expected: merge-base is exactly CP5.1 and branch is behind 0.

- [ ] **Step 2: Whole-branch security review**

Check explicitly:

- no real secrets/passwords committed;
- postgres/backend do not publish host ports;
- `down -v` appears only in CI cleanup/destructive-warning context;
- migration failure blocks long-running backend processes;
- frontend proxy target is internal service name;
- storage/backups use host-persistent locations;
- bootstrap is explicit and password is not embedded;
- backup script does not log credentials;
- public-internet deployment is not implied.

Fix Critical/Important findings before completion.

- [ ] **Step 3: Fresh final verification on exact HEAD**

Require both workflows on the exact final commit:

```text
ci: Ruff PASS + Alembic PASS + full pytest PASS
pilot-ci: frontend quality PASS + compose/image/smoke PASS
```

Do not reuse results from an earlier head.

- [ ] **Step 4: Create stacked draft PR**

Base: `agent/stage5-cp51-tasks-core`
Head: `agent/stage5-cp59-pilot-deployment`
Draft: true

PR body must include exact CI runs and: **DO NOT MERGE into `codex/feat-gigastudio-frontend-integration` automatically.**

- [ ] **Step 5: Verify PR merge-ref CI**

Check the pull-request-triggered workflows against the CP5.1 base. Leave PR draft and unmerged.

- [ ] **Step 6: Update Issue #3 handoff**

Record final pilot HEAD, parent CP5.1, compose services, LAN entry point, bootstrap/backup commands, known pilot limitations and verified CI evidence.
