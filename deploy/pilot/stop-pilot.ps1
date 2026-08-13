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
        throw "Docker недоступен.`n`nОбратитесь к администратору."
    }

    if (-not (Test-Path -LiteralPath $EnvFile) -or -not (Test-Path -LiteralPath $ComposeFile)) {
        throw "Не найдены файлы конфигурации Pilot.`n`nОбратитесь к администратору."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        Show-PilotMessage -Message "Docker Desktop уже остановлен. Spravoshnik EPB не работает."
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
            throw "Не удалось остановить Spravoshnik EPB."
        }
    }
    finally {
        Pop-Location
    }

    Show-PilotMessage -Message "Spravoshnik EPB остановлен.`n`nБаза данных и документы сохранены."
}
catch {
    Show-PilotMessage -Message $_.Exception.Message -Icon ([System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}
