# Pilot Smart Shortcut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a non-technical Windows user a desktop shortcut that starts Docker Desktop if needed, starts the isolated Pilot Compose project, waits until Spravoshnik EPB is reachable, and opens the browser automatically.

**Architecture:** Keep orchestration in focused PowerShell scripts under `deploy/pilot`. `start-pilot.ps1` owns Docker readiness, Compose startup, health polling, and browser launch; `stop-pilot.ps1` safely stops the Pilot project without deleting volumes; `create-desktop-shortcuts.ps1` creates user-facing `.lnk` files that invoke PowerShell hidden. Static contract tests protect project name, paths, no-volume-deletion safety, Docker startup, health polling, and shortcut wiring.

**Tech Stack:** Windows PowerShell 5.1+, Docker Desktop / Docker Compose v2+, existing `docker-compose.pilot.yml`, pytest contract tests.

## Global Constraints

- Pilot project name is `spravoshnik-epb-work`.
- Pilot configuration file is `deploy/pilot/.env.pilot`.
- Pilot compose file is `docker-compose.pilot.yml`.
- HTTP port is read from `PILOT_HTTP_PORT` and defaults to `3000` if absent.
- User startup must not require a terminal.
- Startup may launch Docker Desktop when Docker Engine is unavailable.
- Never use `docker compose down -v` or otherwise delete Pilot volumes from the user-facing scripts.
- Errors must be shown in a Windows message box with an actionable Russian message.
- Existing Pilot data and database must remain untouched by shortcut creation and normal stop/start.

---

### Task 1: Add shortcut contract tests

**Files:**
- Modify: `tests/unit/test_pilot_deployment_contract.py`

**Interfaces:**
- Consumes: repository files as UTF-8 text.
- Produces: regression expectations for `start-pilot.ps1`, `stop-pilot.ps1`, and `create-desktop-shortcuts.ps1`.

- [ ] **Step 1: Write failing tests** requiring the three scripts, the exact Compose project name, Docker Desktop bootstrap, Docker readiness polling, health URL polling, browser launch, hidden shortcut execution, and absence of `down -v`.
- [ ] **Step 2: Run** `python -m pytest tests/unit/test_pilot_deployment_contract.py -q` and verify failure because the scripts do not exist.
- [ ] **Step 3: Commit** the failing contract test.

### Task 2: Implement smart start, stop, and shortcut creation

**Files:**
- Create: `deploy/pilot/start-pilot.ps1`
- Create: `deploy/pilot/stop-pilot.ps1`
- Create: `deploy/pilot/create-desktop-shortcuts.ps1`

**Interfaces:**
- `start-pilot.ps1`: no required parameters; derives repository root from `$PSScriptRoot`, loads the Pilot port from `.env.pilot`, runs Compose with `-p spravoshnik-epb-work`, waits for `http://127.0.0.1:<port>/backend/health/live`, then opens the root URL.
- `stop-pilot.ps1`: runs Compose `stop` for `spravoshnik-epb-work` only; no volume deletion.
- `create-desktop-shortcuts.ps1`: creates `Spravoshnik EPB.lnk` and `Остановить Spravoshnik EPB.lnk` on the current user's Desktop using `WScript.Shell`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ...`, and the Pilot directory as WorkingDirectory.

- [ ] **Step 1: Implement `start-pilot.ps1`** with prerequisite validation, Docker CLI check, Docker Desktop path discovery, bounded Docker wait loop, Compose `up -d`, bounded HTTP health wait loop, browser launch, and Russian message-box failures.
- [ ] **Step 2: Implement `stop-pilot.ps1`** with safe Compose `stop` and Russian error reporting.
- [ ] **Step 3: Implement `create-desktop-shortcuts.ps1`** creating both desktop links with hidden PowerShell execution.
- [ ] **Step 4: Run** `python -m pytest tests/unit/test_pilot_deployment_contract.py -q`; expected PASS.
- [ ] **Step 5: Run full relevant CI** through the repository workflow and confirm success.

### Task 3: Document non-technical startup

**Files:**
- Modify: `docs/PILOT_DEPLOYMENT.md`

**Interfaces:**
- Consumes: scripts from Task 2.
- Produces: installation and user instructions for creating and using the desktop shortcut.

- [ ] **Step 1: Add a Windows desktop shortcut section** with the one-time administrator command `powershell -ExecutionPolicy Bypass -File .\deploy\pilot\create-desktop-shortcuts.ps1` and explain normal user behavior: double-click `Spravoshnik EPB`, wait for browser, use stop shortcut only when desired.
- [ ] **Step 2: Explicitly state** that normal stop preserves PostgreSQL and storage data and that `down -v` remains forbidden for normal operation.
- [ ] **Step 3: Re-run** `python -m pytest tests/unit/test_pilot_deployment_contract.py -q` and the normal CI workflow.
