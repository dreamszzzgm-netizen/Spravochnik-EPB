# One-command Development Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe one-command Windows development startup and shutdown for Spravoshnik EPB while preserving the harness on port 3000.

**Architecture:** Keep the approved PowerShell orchestration approach. Put reusable, testable decision and identity logic in `scripts/Spravoshnik.Dev.psm1`; keep `Start-Spravoshnik.ps1` and `Stop-Spravoshnik.ps1` as thin orchestration entry points; use dedicated child runner scripts so started processes can be positively identified later. Store advisory PIDs in ignored `.runtime/processes.json`, but always verify process identity before stopping anything.

**Tech Stack:** Windows PowerShell 5.1-compatible syntax for developer entry points, PowerShell 7 (`pwsh`) for CI tests, Docker Compose, PostgreSQL 17, Python 3.12+, Alembic, FastAPI/Uvicorn, Next.js 16.2.1, npm.

## Global Constraints

- `3000` is reserved for the harness and must never be modified, stopped, reconfigured, or claimed by these scripts.
- `3100` is the Spravoshnik EPB Next.js frontend port and is already defined by `frontend/package.json`.
- `8000` is the Spravoshnik EPB FastAPI backend port.
- `5432` is the Spravoshnik EPB PostgreSQL development database port.
- Existing healthy Spravoshnik services must be reused; duplicate processes must not be launched.
- Port occupancy alone is not service identity; health endpoints are authoritative for reuse decisions.
- A port occupied by a non-Spravoshnik service is a hard, non-destructive failure.
- PostgreSQL must be healthy before migrations run.
- `python -m alembic upgrade head` runs on every startup and migration failure is a hard stop.
- An empty `users` table triggers an interactive offer to create `admin`; the password must never be passed on the command line or written to disk.
- FastAPI and Next.js run in separate PowerShell windows.
- Startup readiness polling is bounded to 30 seconds per service.
- Shutdown must never kill a process based only on its port.
- `.runtime/processes.json` is advisory; stale or mismatched PIDs must be ignored safely.
- `Stop-Spravoshnik.ps1` leaves PostgreSQL running unless `-Database` is supplied.
- No new production runtime dependency is introduced.

---

## File Structure

- Create `scripts/Spravoshnik.Dev.psm1` — reusable health, decision, runtime-state, and process-identity helpers.
- Create `scripts/Run-SpravoshnikBackend.ps1` — dedicated backend child-window runner.
- Create `scripts/Run-SpravoshnikFrontend.ps1` — dedicated frontend child-window runner.
- Create `Start-Spravoshnik.ps1` — top-level startup orchestrator.
- Create `Stop-Spravoshnik.ps1` — conservative shutdown orchestrator.
- Create `tests/powershell/DevScripts.Tests.ps1` — dependency-free PowerShell test harness for pure helper behavior and static safety contracts.
- Modify `.gitignore` — ignore `.runtime/`.
- Modify `.github/workflows/ci.yml` — run PowerShell helper tests under `pwsh`.
- Modify `README.md` — document one-command startup, shutdown, ports, first-run admin behavior, and fallback manual commands.

---

### Task 1: Testable PowerShell helper module

**Files:**
- Create: `scripts/Spravoshnik.Dev.psm1`
- Create: `tests/powershell/DevScripts.Tests.ps1`

**Interfaces:**
- Produces: `Resolve-SpravoshnikServiceAction([bool]$HealthOk, [bool]$PortInUse) -> string` returning `Reuse`, `Conflict`, or `Start`.
- Produces: `Test-SpravoshnikHealthPayload($Payload) -> bool`.
- Produces: `Test-SpravoshnikProcessCommandLine([string]$CommandLine, [string]$ExpectedRunnerPath, [string]$RepositoryRoot) -> bool`.
- Produces: `Get-SpravoshnikRuntimeStatePath([string]$RepositoryRoot) -> string`.
- Produces: `Read-SpravoshnikRuntimeState([string]$RepositoryRoot) -> PSCustomObject` returning an object with optional `backend` and `frontend` properties.
- Produces: `Write-SpravoshnikRuntimeProcess([string]$RepositoryRoot, [string]$Service, [int]$Pid, [string]$RunnerPath) -> void`.
- Produces: `Remove-SpravoshnikRuntimeProcess([string]$RepositoryRoot, [string]$Service) -> void`.
- Produces: `Test-SpravoshnikPortInUse([int]$Port) -> bool` using .NET active TCP listeners rather than `Get-NetTCPConnection`.
- Produces: `Get-SpravoshnikHttpHealth([string]$Url) -> PSCustomObject|null` using a short HTTP timeout and JSON parsing.
- Produces: `Wait-SpravoshnikHealth([scriptblock]$Probe, [int]$TimeoutSeconds = 30, [int]$PollMilliseconds = 500) -> bool`.

- [ ] **Step 1: Write failing helper tests**

Create `tests/powershell/DevScripts.Tests.ps1` with a small dependency-free assertion harness and tests for the intended public helpers:

```powershell
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$modulePath = Join-Path $repoRoot 'scripts\Spravoshnik.Dev.psm1'
Import-Module $modulePath -Force

$script:Failures = 0

function Assert-Equal($Expected, $Actual, [string]$Name) {
    if ($Expected -ne $Actual) {
        $script:Failures++
        Write-Host "FAIL: $Name -- expected '$Expected', got '$Actual'"
    } else {
        Write-Host "PASS: $Name"
    }
}

function Assert-True([bool]$Value, [string]$Name) {
    Assert-Equal $true $Value $Name
}

function Assert-False([bool]$Value, [string]$Name) {
    Assert-Equal $false $Value $Name
}

Assert-Equal 'Reuse' (Resolve-SpravoshnikServiceAction -HealthOk $true -PortInUse $true) 'healthy service is reused'
Assert-Equal 'Conflict' (Resolve-SpravoshnikServiceAction -HealthOk $false -PortInUse $true) 'wrong service on port is conflict'
Assert-Equal 'Start' (Resolve-SpravoshnikServiceAction -HealthOk $false -PortInUse $false) 'free port starts service'

$goodHealth = [pscustomobject]@{ status = 'ok'; database = 'ok'; storage = 'ok'; version = '0.1.0' }
$badHealth = [pscustomobject]@{ status = 'degraded' }
Assert-True (Test-SpravoshnikHealthPayload $goodHealth) 'health payload accepts status ok'
Assert-False (Test-SpravoshnikHealthPayload $badHealth) 'health payload rejects non-ok status'
Assert-False (Test-SpravoshnikHealthPayload $null) 'health payload rejects null'

$root = 'D:\Spravoshnik-EPB'
$runner = 'D:\Spravoshnik-EPB\scripts\Run-SpravoshnikBackend.ps1'
$goodCmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Spravoshnik-EPB\scripts\Run-SpravoshnikBackend.ps1" -RepositoryRoot "D:\Spravoshnik-EPB"'
$wrongCmd = 'powershell.exe -File "C:\Other\Run-SpravoshnikBackend.ps1"'
Assert-True (Test-SpravoshnikProcessCommandLine -CommandLine $goodCmd -ExpectedRunnerPath $runner -RepositoryRoot $root) 'process identity accepts expected runner and root'
Assert-False (Test-SpravoshnikProcessCommandLine -CommandLine $wrongCmd -ExpectedRunnerPath $runner -RepositoryRoot $root) 'process identity rejects unrelated process'

$counter = 0
Assert-True (Wait-SpravoshnikHealth -Probe { $script:counter++; return ($script:counter -ge 2) } -TimeoutSeconds 2 -PollMilliseconds 10) 'polling succeeds before timeout'
Assert-False (Wait-SpravoshnikHealth -Probe { return $false } -TimeoutSeconds 0 -PollMilliseconds 10) 'polling times out cleanly'

if ($script:Failures -gt 0) {
    throw "$script:Failures PowerShell test(s) failed"
}
```

- [ ] **Step 2: Run tests and verify RED**

Run on Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Expected: FAIL because `scripts/Spravoshnik.Dev.psm1` and its functions do not exist yet.

- [ ] **Step 3: Implement minimal helper module**

Create `scripts/Spravoshnik.Dev.psm1` with Windows PowerShell 5.1-compatible functions. The core decision logic must be exactly equivalent to:

```powershell
function Resolve-SpravoshnikServiceAction {
    param([bool]$HealthOk, [bool]$PortInUse)
    if ($HealthOk) { return 'Reuse' }
    if ($PortInUse) { return 'Conflict' }
    return 'Start'
}

function Test-SpravoshnikHealthPayload {
    param($Payload)
    return ($null -ne $Payload -and $Payload.status -eq 'ok')
}
```

Implement process identity by normalizing paths with `[System.IO.Path]::GetFullPath()` and requiring both the exact expected runner path and repository root to appear in the command line, case-insensitively. Implement runtime state under `<repo>\.runtime\processes.json`; create the directory on write, tolerate missing/invalid state by returning an empty object, and write JSON atomically through a temporary file then `Move-Item -Force`.

Implement port detection through:

```powershell
[System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
```

Implement HTTP health with `Invoke-WebRequest -UseBasicParsing -TimeoutSec 2`, then `ConvertFrom-Json`, returning `$null` on connection/HTTP/JSON failure. `Wait-SpravoshnikHealth` must use a stopwatch and bounded polling.

Export only the public helper functions needed by the entry scripts and tests.

- [ ] **Step 4: Run PowerShell tests and verify GREEN**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Expected: all helper tests print `PASS` and process exits 0.

Also run under PowerShell 7 when available:

```powershell
pwsh -NoProfile -File tests/powershell/DevScripts.Tests.ps1
```

Expected: same PASS result.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/Spravoshnik.Dev.psm1 tests/powershell/DevScripts.Tests.ps1
git commit -m "test(dev): add startup orchestration helpers"
```

---

### Task 2: Startup orchestrator and positively identifiable child runners

**Files:**
- Create: `scripts/Run-SpravoshnikBackend.ps1`
- Create: `scripts/Run-SpravoshnikFrontend.ps1`
- Create: `Start-Spravoshnik.ps1`
- Modify: `tests/powershell/DevScripts.Tests.ps1`

**Interfaces:**
- Consumes helper module interfaces from Task 1.
- Produces root command `.\Start-Spravoshnik.ps1`.
- Produces child runners that accept mandatory `-RepositoryRoot`.
- Runtime state entries use shape `{ pid, runnerPath, startedAt }` under properties `backend` and `frontend`.

- [ ] **Step 1: Add failing static safety and runner-contract tests**

Extend `tests/powershell/DevScripts.Tests.ps1` to assert the startup and runner files exist and satisfy safety contracts after import helpers:

```powershell
$startPath = Join-Path $repoRoot 'Start-Spravoshnik.ps1'
$backendRunner = Join-Path $repoRoot 'scripts\Run-SpravoshnikBackend.ps1'
$frontendRunner = Join-Path $repoRoot 'scripts\Run-SpravoshnikFrontend.ps1'

Assert-True (Test-Path $startPath) 'startup entry point exists'
Assert-True (Test-Path $backendRunner) 'backend runner exists'
Assert-True (Test-Path $frontendRunner) 'frontend runner exists'

if (Test-Path $startPath) {
    $startText = Get-Content $startPath -Raw
    Assert-False ($startText -match '(?<!\d)3000(?!\d)') 'startup script never references port 3000'
    Assert-False ($startText -match '(?i)\b(netsh|portproxy|wsl\.exe|wsl\s)\b') 'startup script never changes WSL or portproxy'
    Assert-True ($startText -match 'python\s+-m\s+alembic\s+upgrade\s+head') 'startup applies migrations'
    Assert-True ($startText -match 'app\.modules\.identity\.bootstrap') 'startup uses project bootstrap module'
    Assert-False ($startText -match '--password') 'startup never passes admin password on command line'
}
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Expected: FAIL on missing `Start-Spravoshnik.ps1` and child runners.

- [ ] **Step 3: Implement backend and frontend runner scripts**

Create `scripts/Run-SpravoshnikBackend.ps1`:

```powershell
param([Parameter(Mandatory = $true)][string]$RepositoryRoot)
$ErrorActionPreference = 'Stop'
Set-Location $RepositoryRoot
try { $Host.UI.RawUI.WindowTitle = 'Spravoshnik EPB - Backend :8000' } catch {}
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
```

Create `scripts/Run-SpravoshnikFrontend.ps1`:

```powershell
param([Parameter(Mandatory = $true)][string]$RepositoryRoot)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $RepositoryRoot 'frontend')
try { $Host.UI.RawUI.WindowTitle = 'Spravoshnik EPB - Frontend :3100' } catch {}
npm run dev
exit $LASTEXITCODE
```

Do not repeat `-p 3100`; `frontend/package.json` owns that configuration.

- [ ] **Step 4: Implement startup orchestration**

Create `Start-Spravoshnik.ps1` with this exact dependency order and behavior:

1. Resolve `$RepositoryRoot = $PSScriptRoot`.
2. Import `scripts/Spravoshnik.Dev.psm1`.
3. Verify `docker`, `python`, and `npm` with `Get-Command`; on absence, print `[ERROR]` and exit 1.
4. Run `docker compose up -d postgres`; check `$LASTEXITCODE`.
5. Resolve the postgres container ID with `docker compose ps -q postgres`; poll `docker inspect -f '{{.State.Health.Status}}' <id>` until `healthy` or 30 seconds. Fail safely on timeout.
6. Run `python -m alembic upgrade head` from the repo root and hard-stop on nonzero exit.
7. Query user count with:

   ```powershell
   docker compose exec -T postgres psql -U spravoshnik -d spravoshnik -tAc "SELECT COUNT(*) FROM users;"
   ```

   Trim and parse the integer. If it is `0`, prompt `Create initial administrator admin? [Y/n]`. Treat blank or `Y/y` as yes; run:

   ```powershell
   python -m app.modules.identity.bootstrap --username admin --name "Administrator"
   ```

   without `--password`. On bootstrap failure, stop startup. If declined, continue but set a final `NoUsersWarning` flag.
8. Probe `http://127.0.0.1:8000/health` with `Get-SpravoshnikHttpHealth` + `Test-SpravoshnikHealthPayload`, combine that with `Test-SpravoshnikPortInUse 8000`, and use `Resolve-SpravoshnikServiceAction`.
9. On `Reuse`, print `[OK] Backend already running`. On `Conflict`, print `[ERROR] Port 8000 is occupied by another service` and exit 1. On `Start`, launch a new `powershell.exe` child via `Start-Process -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', <runner>, '-RepositoryRoot', <root>)`, write the returned shell PID to runtime state, and poll backend health for at most 30 seconds.
10. Repeat the same decision flow for frontend using port `3100` and health URL `http://127.0.0.1:3100/backend/health`.
11. Only after proxied frontend health is confirmed, call `Start-Process 'http://localhost:3100'`.
12. Print a compact final summary. If bootstrap was declined, include an explicit warning that login is impossible until an account is created.

All native-command failures must be checked through `$LASTEXITCODE`; all fatal errors must exit nonzero. Do not catch and suppress fatal dependency failures.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Expected: helper and startup static-contract tests all PASS.

- [ ] **Step 6: Manual startup acceptance on Windows**

From a state where backend/frontend are stopped but Docker is available:

```powershell
.\Start-Spravoshnik.ps1
```

Verify:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:3100/backend/health
```

Expected for both: HTTP success and JSON containing `"status":"ok"`.

Run `.\Start-Spravoshnik.ps1` a second time while services are healthy. Expected: it reuses both services and opens no duplicate backend/frontend windows.

- [ ] **Step 7: Commit Task 2**

```bash
git add Start-Spravoshnik.ps1 scripts/Run-SpravoshnikBackend.ps1 scripts/Run-SpravoshnikFrontend.ps1 tests/powershell/DevScripts.Tests.ps1
git commit -m "feat(dev): add one-command startup"
```

---

### Task 3: Safe shutdown using verified runtime process identity

**Files:**
- Create: `Stop-Spravoshnik.ps1`
- Modify: `scripts/Spravoshnik.Dev.psm1`
- Modify: `tests/powershell/DevScripts.Tests.ps1`

**Interfaces:**
- Consumes Task 1 runtime-state and identity helpers.
- Produces `.\Stop-Spravoshnik.ps1 [-Database]`.
- Produces helper `Get-SpravoshnikProcessCommandLine([int]$Pid) -> string|null` using `Get-CimInstance Win32_Process` on Windows.

- [ ] **Step 1: Add failing shutdown safety tests**

Extend `tests/powershell/DevScripts.Tests.ps1`:

```powershell
$stopPath = Join-Path $repoRoot 'Stop-Spravoshnik.ps1'
Assert-True (Test-Path $stopPath) 'shutdown entry point exists'

if (Test-Path $stopPath) {
    $stopText = Get-Content $stopPath -Raw
    Assert-False ($stopText -match '(?<!\d)3000(?!\d)') 'shutdown script never references port 3000'
    Assert-False ($stopText -match '(?i)\b(netsh|portproxy|wsl\.exe|wsl\s)\b') 'shutdown script never changes WSL or portproxy'
    Assert-True ($stopText -match 'Test-SpravoshnikProcessCommandLine') 'shutdown verifies process identity before termination'
    Assert-True ($stopText -match 'taskkill') 'shutdown terminates verified process trees'
    Assert-True ($stopText -match 'compose\s+stop\s+postgres') 'database switch stops only postgres service'
}
```

Add state-file tests using a temporary directory: write a backend runtime process, read it back, remove it, and verify stale/missing state is tolerated.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Expected: FAIL because `Stop-Spravoshnik.ps1` does not exist yet.

- [ ] **Step 3: Add process command-line lookup helper**

In `scripts/Spravoshnik.Dev.psm1`, add:

```powershell
function Get-SpravoshnikProcessCommandLine {
    param([int]$Pid)
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$Pid" -ErrorAction Stop
        if ($null -eq $process) { return $null }
        return [string]$process.CommandLine
    } catch {
        return $null
    }
}
```

Export it. Tests of this OS-facing helper may be limited to null-safe behavior in CI; command-line identity itself remains tested purely by `Test-SpravoshnikProcessCommandLine`.

- [ ] **Step 4: Implement conservative shutdown**

Create `Stop-Spravoshnik.ps1` with optional switch:

```powershell
param([switch]$Database)
```

Behavior:

1. Resolve repository root and import the helper module.
2. Read `.runtime/processes.json`.
3. For `frontend`, then `backend`, if an entry exists, obtain the current command line for its PID.
4. Require `Test-SpravoshnikProcessCommandLine` to match both the exact runner path and repository root.
5. If identity matches, run `taskkill.exe /PID <pid> /T /F`, check exit code, then remove that runtime-state entry.
6. If PID is gone or identity does not match, print a safe `[SKIP]` message, remove only stale advisory state, and do not terminate anything.
7. If no runtime entry exists, do not search by port and do not kill manually-started or unrelated services.
8. If `-Database` is supplied, run `docker compose stop postgres` from the repository root after process handling. Otherwise print that PostgreSQL remains running.
9. Never reference or act on the harness port.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Expected: all tests PASS.

- [ ] **Step 6: Manual shutdown acceptance on Windows**

Start the app through `.\Start-Spravoshnik.ps1`, then run:

```powershell
.\Stop-Spravoshnik.ps1
```

Verify backend/frontend child windows close, `curl.exe http://127.0.0.1:8000/health` and `curl.exe http://127.0.0.1:3100/backend/health` no longer connect, and PostgreSQL remains healthy.

Then start again and run:

```powershell
.\Stop-Spravoshnik.ps1 -Database
```

Verify the normal `postgres` compose service stops. Confirm no operation is performed against the harness.

- [ ] **Step 7: Commit Task 3**

```bash
git add Stop-Spravoshnik.ps1 scripts/Spravoshnik.Dev.psm1 tests/powershell/DevScripts.Tests.ps1
git commit -m "feat(dev): add safe one-command shutdown"
```

---

### Task 4: Runtime ignore rule, CI coverage, and developer documentation

**Files:**
- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `tests/powershell/DevScripts.Tests.ps1`

**Interfaces:**
- CI command: `pwsh -NoProfile -File tests/powershell/DevScripts.Tests.ps1`.
- User-facing commands: `.\Start-Spravoshnik.ps1`, `.\Stop-Spravoshnik.ps1`, `.\Stop-Spravoshnik.ps1 -Database`.

- [ ] **Step 1: Add failing repository-contract assertions**

Extend the PowerShell test harness to verify `.runtime/` is ignored:

```powershell
$gitignore = Get-Content (Join-Path $repoRoot '.gitignore') -Raw
Assert-True ($gitignore -match '(?m)^\.runtime/$') '.runtime is ignored by git'
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Expected: FAIL on `.runtime is ignored by git` until `.gitignore` is updated.

- [ ] **Step 3: Update `.gitignore`**

Append exactly:

```gitignore
.runtime/
```

- [ ] **Step 4: Add PowerShell tests to CI**

In `.github/workflows/ci.yml`, add after Python dependency installation and before the existing backend verification commands:

```yaml
      - run: pwsh -NoProfile -File tests/powershell/DevScripts.Tests.ps1
```

Do not change the existing Ruff, Alembic, or pytest commands.

- [ ] **Step 5: Update README developer startup documentation**

Add a Windows development section that documents:

```powershell
.\Start-Spravoshnik.ps1
```

and explains that it starts/validates PostgreSQL, applies migrations, offers first-admin bootstrap on an empty database, reuses healthy backend/frontend instances, opens separate service windows when needed, and opens `http://localhost:3100` after readiness.

Document shutdown:

```powershell
.\Stop-Spravoshnik.ps1
.\Stop-Spravoshnik.ps1 -Database
```

Document the fixed ports and explicitly state that port 3000 belongs to the harness and is not managed by Spravoshnik scripts. Preserve the existing manual startup commands as troubleshooting/fallback documentation rather than deleting them.

- [ ] **Step 6: Run complete fresh verification**

Run PowerShell tests:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\powershell\DevScripts.Tests.ps1
```

Run backend checks from repository root:

```powershell
python -m ruff check app tests
python -m pytest
python -m alembic upgrade head
```

Run frontend checks from `frontend/`:

```powershell
npm test
npm run lint
npm run typecheck
npm run build
```

Expected: every command exits 0. Do not claim completion if any command is skipped or fails; report the actual unverified portion instead.

- [ ] **Step 7: Final Windows acceptance**

With the normal development database available:

```powershell
.\Stop-Spravoshnik.ps1
.\Start-Spravoshnik.ps1
```

Verify both health URLs return `status: ok`, the browser opens on `http://localhost:3100`, login works with an existing `admin`, and a second startup does not create duplicate service windows.

- [ ] **Step 8: Commit Task 4**

```bash
git add .gitignore .github/workflows/ci.yml README.md tests/powershell/DevScripts.Tests.ps1
git commit -m "docs(dev): document one-command workflow"
```

---

## Plan Self-Review

- Spec coverage: startup dependency checks, PostgreSQL health, automatic migrations, empty-user bootstrap, separate windows, health-based reuse, port conflicts, bounded polling, browser opening, runtime PID state, conservative shutdown, optional database stop, harness protection, testing, and documentation are all assigned to explicit tasks.
- Placeholder scan: no `TBD`, `TODO`, deferred implementation, or unspecified error-handling steps remain.
- Interface consistency: helper names used by Tasks 2-4 are defined in Task 1 or explicitly added in Task 3; runtime state uses the same `backend`/`frontend` property names throughout.
- Scope remains one developer-workflow feature; no production deployment/containerization work is included.
