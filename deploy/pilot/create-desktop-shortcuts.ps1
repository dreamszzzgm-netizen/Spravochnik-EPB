Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$StartScript = Join-Path $ScriptDir "start-pilot.ps1"
$StopScript = Join-Path $ScriptDir "stop-pilot.ps1"
$Desktop = [Environment]::GetFolderPath("Desktop")
$PowerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

function New-PilotShortcut {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $shell = New-Object -ComObject WScript.Shell
    $shortcutPath = Join-Path $Desktop $Name
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $PowerShellExe
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""
    $shortcut.WorkingDirectory = $RepoRoot
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7
    $shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,15"
    $shortcut.Save()
}

try {
    if (-not (Test-Path -LiteralPath $StartScript)) {
        throw "Не найден start-pilot.ps1. Обратитесь к администратору."
    }
    if (-not (Test-Path -LiteralPath $StopScript)) {
        throw "Не найден stop-pilot.ps1. Обратитесь к администратору."
    }

    New-PilotShortcut `
        -Name "Spravoshnik EPB.lnk" `
        -ScriptPath $StartScript `
        -Description "Запустить Spravoshnik EPB"

    New-PilotShortcut `
        -Name "Остановить Spravoshnik EPB.lnk" `
        -ScriptPath $StopScript `
        -Description "Остановить Spravoshnik EPB без удаления данных"

    [System.Windows.Forms.MessageBox]::Show(
        "Ярлыки Spravoshnik EPB созданы на рабочем столе.",
        "Spravoshnik EPB",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}
catch {
    [System.Windows.Forms.MessageBox]::Show(
        $_.Exception.Message,
        "Spravoshnik EPB",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}
