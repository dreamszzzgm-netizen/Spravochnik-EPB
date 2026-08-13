Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

$ProjectName = "spravoshnik-epb-work"
$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$EnvFile = Join-Path $ScriptDir ".env.pilot"
$ComposeFile = Join-Path $RepoRoot "docker-compose.pilot.yml"

function Show-PilotError {
    param([Parameter(Mandatory = $true)][string]$Message)

    [System.Windows.Forms.MessageBox]::Show(
        $Message,
        "Spravoshnik EPB",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}

function Test-DockerEngine {
    try {
        & docker info *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Get-PilotHttpPort {
    param([Parameter(Mandatory = $true)][string]$Path)

    $port = 3000
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*PILOT_HTTP_PORT\s*=\s*([0-9]+)\s*$') {
            $port = [int]$Matches[1]
            break
        }
    }
    return $port
}

try {
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        throw "Не найден файл настроек Pilot:`n$EnvFile`n`nОбратитесь к администратору."
    }

    if (-not (Test-Path -LiteralPath $ComposeFile)) {
        throw "Не найден файл docker-compose.pilot.yml.`n`nОбратитесь к администратору."
    }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker не установлен или недоступен.`n`nУстановите Docker Desktop или обратитесь к администратору."
    }

    if (-not (Test-DockerEngine)) {
        $dockerDesktopCandidates = @(
            (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
            (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
        )
        $dockerDesktop = $dockerDesktopCandidates |
            Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
            Select-Object -First 1

        if (-not $dockerDesktop) {
            throw "Docker Desktop не запущен, и программа Docker Desktop.exe не найдена.`n`nЗапустите Docker Desktop вручную или обратитесь к администратору."
        }

        Start-Process -FilePath $dockerDesktop | Out-Null

        $dockerReady = $false
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            Start-Sleep -Seconds 2
            if (Test-DockerEngine) {
                $dockerReady = $true
                break
            }
        }

        if (-not $dockerReady) {
            throw "Docker Desktop запущен, но Docker Engine не стал доступен.`n`nПопробуйте перезапустить Docker Desktop или обратитесь к администратору."
        }
    }

    Push-Location $RepoRoot
    try {
        & docker compose `
            -p $ProjectName `
            --env-file $EnvFile `
            -f $ComposeFile `
            up -d

        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось запустить контейнеры Spravoshnik EPB."
        }
    }
    finally {
        Pop-Location
    }

    $port = Get-PilotHttpPort -Path $EnvFile
    $healthUrl = "http://127.0.0.1:$port/backend/health/live"
    $appUrl = "http://127.0.0.1:$port"

    $applicationReady = $false
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                $applicationReady = $true
                break
            }
        }
        catch {
            # The frontend/backend may still be starting.
        }
        Start-Sleep -Seconds 2
    }

    if (-not $applicationReady) {
        throw "Spravoshnik EPB запущен, но веб-интерфейс не стал доступен.`n`nОбратитесь к администратору."
    }

    Start-Process $appUrl | Out-Null
}
catch {
    Show-PilotError -Message $_.Exception.Message
    exit 1
}
