Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

$ProjectName = "spravoshnik-epb-work"
$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$EnvFile = Join-Path $ScriptDir ".env.pilot"
$ComposeFile = Join-Path $RepoRoot "docker-compose.pilot.yml"

function Show-PilotMessage {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [System.Windows.Forms.MessageBoxIcon]$Icon = [System.Windows.Forms.MessageBoxIcon]::Information
    )

    [System.Windows.Forms.MessageBox]::Show(
        $Message,
        "Spravoshnik EPB",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        $Icon
    ) | Out-Null
}

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not available.`n`nPlease contact the administrator."
    }

    if (-not (Test-Path -LiteralPath $EnvFile) -or -not (Test-Path -LiteralPath $ComposeFile)) {
        throw "Pilot configuration files were not found.`n`nPlease contact the administrator."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        Show-PilotMessage -Message "Docker Desktop is already stopped. Spravoshnik EPB is not running."
        exit 0
    }

    Push-Location $RepoRoot
    try {
        & docker compose `
            -p $ProjectName `
            --env-file $EnvFile `
            -f $ComposeFile `
            stop

        if ($LASTEXITCODE -ne 0) {
            throw "Spravoshnik EPB could not be stopped."
        }
    }
    finally {
        Pop-Location
    }

    Show-PilotMessage -Message "Spravoshnik EPB stopped.`n`nDatabase and documents were preserved."
}
catch {
    Show-PilotMessage -Message $_.Exception.Message -Icon ([System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}
