param(
    [string]$SourceExe = "",
    [switch]$EnableStartup = $true,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"

function Stop-CodexControlInstances {
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -ieq "CodexControl.exe" -or (
            $_.Name -match "^pythonw?\.exe$" -and
            $_.CommandLine -match "CodexControlWindows\.pyw"
        )
    }

    foreach ($process in $processes) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($SourceExe)) {
    $SourceExe = Join-Path $windowsRoot "dist\CodexControl.exe"
}

if (-not (Test-Path -LiteralPath $SourceExe)) {
    throw "EXE not found: $SourceExe"
}

$installDir = Join-Path $env:LOCALAPPDATA "Programs\CodexControl"
$installedExe = Join-Path $installDir "CodexControl.exe"
$startupDir = [Environment]::GetFolderPath("Startup")
$startupShortcut = Join-Path $startupDir "CodexControl.lnk"

Stop-CodexControlInstances
Start-Sleep -Milliseconds 500

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -LiteralPath $SourceExe -Destination $installedExe -Force

if ($EnableStartup) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($startupShortcut)
    $shortcut.TargetPath = $installedExe
    $shortcut.Arguments = "--hidden"
    $shortcut.WorkingDirectory = $installDir
    $shortcut.IconLocation = $installedExe
    $shortcut.Description = "Launch CodexControl at sign-in"
    $shortcut.Save()
} elseif (Test-Path -LiteralPath $startupShortcut) {
    Remove-Item -LiteralPath $startupShortcut -Force
}

if ($Launch) {
    Start-Process -FilePath $installedExe -WorkingDirectory $installDir
}

Write-Output "Installed: $installedExe"
if ($EnableStartup) {
    Write-Output "Startup shortcut: $startupShortcut"
}
