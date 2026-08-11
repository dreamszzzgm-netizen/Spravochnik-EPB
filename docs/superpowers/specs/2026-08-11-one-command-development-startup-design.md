# One-command development startup for Spravoshnik EPB

Date: 2026-08-11
Branch: `codex/feat-gigastudio-frontend-integration`
Status: approved design

## Goal

Provide a single Windows PowerShell command that starts the local Spravoshnik EPB development environment safely and predictably without interfering with the existing harness on port 3000.

The command must:

1. Start PostgreSQL in Docker when needed.
2. Wait until PostgreSQL is healthy.
3. Apply Alembic migrations automatically.
4. Detect an empty `users` table and offer to create the initial `admin` account interactively.
5. Start FastAPI on port 8000 in a separate PowerShell window only when it is not already running as Spravoshnik EPB.
6. Start Next.js on port 3100 in a separate PowerShell window only when it is not already running as Spravoshnik EPB.
7. Verify readiness through health endpoints rather than only checking whether ports are occupied.
8. Open `http://localhost:3100` automatically after the full application is ready.
9. Never modify, stop, reconfigure, or claim port 3000, which is reserved for the harness.

## Fixed local port layout

- `3000` — harness; never touched by Spravoshnik startup/shutdown scripts.
- `3100` — Spravoshnik EPB Next.js frontend.
- `8000` — Spravoshnik EPB FastAPI backend.
- `5432` — Spravoshnik EPB PostgreSQL development database.

The frontend package already uses port 3100 by default. The startup orchestration must rely on that project setting instead of duplicating a second frontend port definition.

## Chosen approach

Use a PowerShell orchestrator stored in the repository root.

Primary entry point:

```powershell
.\Start-Spravoshnik.ps1
```

Companion shutdown command:

```powershell
.\Stop-Spravoshnik.ps1
```

This approach was chosen over Makefile-only or Node.js orchestration because the target development environment is Windows, the workflow must open separate PowerShell windows, and PowerShell can inspect Docker, processes, HTTP health, and browser launch behavior without adding another runtime dependency.

## Startup sequence

`Start-Spravoshnik.ps1` performs these steps in order:

1. Resolve the repository root from the script location rather than assuming the caller's current directory.
2. Check that required executables are available: `docker`, `python`, and `npm`.
3. Start the development PostgreSQL service with Docker Compose if necessary.
4. Poll Docker health until PostgreSQL reports healthy, with a finite timeout.
5. Run:

   ```powershell
   python -m alembic upgrade head
   ```

   from the repository root.
6. If migration fails, stop startup immediately and display a clear error.
7. Query the application database for the number of rows in `users`.
8. If `users` is empty, prompt the user to create the initial administrator.
9. If the user agrees, invoke the existing bootstrap module:

   ```powershell
   python -m app.modules.identity.bootstrap --username admin --name "Administrator"
   ```

   Do not pass `--password`; password entry must remain interactive and hidden through Python `getpass`.
10. Probe backend health at `http://127.0.0.1:8000/health`.
11. If that endpoint already returns the expected Spravoshnik health response, treat backend as already running and do not launch a duplicate.
12. If port 8000 is occupied but the Spravoshnik health check does not succeed, abort with an explanatory error rather than killing the owning process.
13. If backend is absent and port 8000 is available, open a separate PowerShell window in the repository root and run:

    ```powershell
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
    ```

14. Poll backend health until ready, with a finite timeout.
15. Probe frontend through `http://127.0.0.1:3100/backend/health`.
16. If this endpoint returns the expected proxied Spravoshnik health response, treat frontend as already running and do not launch a duplicate.
17. If port 3100 is occupied but the Spravoshnik proxied health check does not succeed, abort with an explanatory error rather than killing the owning process.
18. If frontend is absent and port 3100 is available, open a separate PowerShell window in `frontend/` and run:

    ```powershell
    npm run dev
    ```

19. Poll `http://127.0.0.1:3100/backend/health` until ready, with a finite timeout.
20. Open `http://localhost:3100` in the default browser.
21. Print a compact summary of service state and addresses.

## Service identity and duplicate prevention

Port occupancy alone is not sufficient evidence that the correct service is running.

Backend is considered healthy only when `GET http://127.0.0.1:8000/health` succeeds and returns the expected application health payload containing at least `status: "ok"`.

Frontend is considered healthy only when `GET http://127.0.0.1:3100/backend/health` succeeds and returns the proxied backend health payload. This verifies both the Next.js server and its same-origin rewrite to FastAPI.

If a port is occupied but the corresponding Spravoshnik health check fails, the orchestrator must not terminate the process. It reports the conflict and exits so that unrelated local software cannot be killed accidentally.

## Database behavior

PostgreSQL remains Docker-managed. Startup should target the normal development `postgres` service only; it should not require the test database service for ordinary application use.

Alembic migrations run on every startup after PostgreSQL becomes healthy. This makes a fresh `git pull` safer because schema changes are applied before the backend starts.

A migration failure is a hard stop. The backend must not be launched against a known incompatible schema.

## Initial administrator bootstrap

The first-run check occurs only after migrations have succeeded.

If the `users` table contains one or more rows, no account is created or changed.

If the table is empty, the launcher asks whether to create the initial `admin`. On confirmation it calls the project's existing bootstrap module without a password command-line argument. The password is therefore entered interactively and must not be written to the PowerShell script, Git repository, command history, environment file, or startup logs.

If the user declines, startup may continue, but the final summary must state that the application has no user account and login will not be possible until bootstrap is performed.

## Separate process windows

FastAPI and Next.js run in separate PowerShell windows so their logs remain readable and independent.

The launcher itself remains an orchestration/status window. It does not multiplex application logs into one console.

Existing healthy Spravoshnik processes are reused and no duplicate window is opened for them.

## Shutdown behavior

`Stop-Spravoshnik.ps1` must be conservative.

Default behavior:

- stop only Spravoshnik frontend/backend processes that can be positively identified as belonging to this project;
- leave PostgreSQL running for quick subsequent restarts;
- never touch port 3000, harness processes, WSL portproxy configuration, or unrelated processes.

Optional full local shutdown:

```powershell
.\Stop-Spravoshnik.ps1 -Database
```

With `-Database`, after stopping project frontend/backend processes, also stop the Spravoshnik development PostgreSQL service with Docker Compose.

The shutdown implementation must not kill an arbitrary process merely because it owns port 8000 or 3100. Positive project identity is required.

## Process ownership strategy

To make safe shutdown possible, the startup script should record process identifiers for the PowerShell/child processes it starts in a repository-local runtime state file ignored by Git, for example under `.runtime/`.

The state file is advisory, not authoritative. Before stopping a recorded PID, the shutdown script must verify that the process still exists and that its command line/path matches the expected Spravoshnik backend or frontend command. Stale PID entries must be ignored safely.

The startup script must also tolerate missing or stale runtime state and rely on HTTP health checks for reuse decisions.

## Error handling

All startup steps use clear status prefixes such as:

```text
[OK] PostgreSQL is healthy
[OK] Migrations applied
[START] Backend starting on :8000
[OK] Backend ready
[START] Frontend starting on :3100
[OK] Frontend ready
[OPEN] http://localhost:3100
```

Fatal conditions use `[ERROR]` and stop the remaining startup sequence. Examples include:

- Docker unavailable;
- PostgreSQL fails to become healthy within the timeout;
- Alembic migration failure;
- port 8000 occupied by a non-Spravoshnik service;
- backend fails to become healthy within the timeout;
- port 3100 occupied by a non-Spravoshnik service;
- frontend fails to become healthy within the timeout.

The script must not silently continue past a failed dependency.

## Timeouts

Use bounded polling rather than fixed sleeps. A default readiness timeout of 30 seconds per service is sufficient for the development workflow and can be a script constant rather than a user-facing configuration option in the first implementation.

## Security constraints

- Never store the administrator password in source code or a script variable persisted to disk.
- Do not pass the bootstrap password on the command line.
- Do not expose session secrets or database passwords beyond the project's existing environment configuration.
- Do not kill unidentified processes occupying expected ports.
- Do not change WSL, Windows portproxy, firewall, or harness configuration.

## Testing strategy

Implementation should separate pure decision/helper logic from process-launch side effects where practical so key behavior can be tested without starting real applications.

At minimum, verify:

1. healthy existing backend is reused;
2. healthy existing frontend is reused;
3. occupied wrong-service port causes a safe failure rather than process termination;
4. migration failure prevents backend startup;
5. empty users result selects the bootstrap path;
6. non-empty users result skips bootstrap;
7. declined bootstrap continues with an explicit no-login warning;
8. readiness polling times out cleanly;
9. shutdown ignores stale recorded PIDs;
10. shutdown refuses to kill a PID whose command line does not identify the expected Spravoshnik process;
11. `-Database` controls whether PostgreSQL is stopped;
12. no script contains logic that changes or terminates port 3000/harness resources.

Manual acceptance on Windows should then confirm the complete flow from a stopped development environment to a browser opened at `http://localhost:3100`, followed by successful authenticated use when an admin exists.

## Out of scope

This design does not:

- containerize the frontend/backend;
- create a production service manager;
- modify the harness;
- modify WSL port forwarding;
- change application authentication behavior;
- automatically reset an existing administrator password;
- start the PostgreSQL test database for normal application use;
- replace existing `Makefile` commands.

The scripts are a developer convenience layer over the current architecture, not a new deployment architecture.
