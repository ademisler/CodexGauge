from __future__ import annotations

import base64
import os
from pathlib import Path

from .file_locations import APP_SUPPORT_DIRECTORY, ensure_directories


DEFAULT_RESTART_DELAY_SECONDS = 0.8
RESTART_LOG_PATH = APP_SUPPORT_DIRECTORY / "codex-desktop-restart.log"
RESTART_SCRIPT_PATH = APP_SUPPORT_DIRECTORY / "codex-desktop-restart.ps1"
RESTART_LAUNCHER_PATH = APP_SUPPORT_DIRECTORY / "codex-desktop-restart.cmd"
POWERSHELL_EXE = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


class CodexDesktopControlError(RuntimeError):
    """Friendly Codex Desktop control error."""


def build_restart_script(delay_seconds: float = DEFAULT_RESTART_DELAY_SECONDS) -> str:
    delay_ms = max(0, int(round(delay_seconds * 1000)))
    log_path = _powershell_literal_path(RESTART_LOG_PATH)

    return f"""
$ErrorActionPreference = 'Stop'
$logPath = {log_path}
New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($logPath)) -Force | Out-Null
function Write-Log([string]$message) {{
    Add-Content -LiteralPath $logPath -Value ("[{{0}}] {{1}}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'), $message)
}}
Write-Log 'Restart requested.'
$mainProcess = Get-CimInstance Win32_Process | Where-Object {{
    $_.Name -eq 'Codex.exe' -and
    $_.ExecutablePath -and
    $_.ExecutablePath -notlike '*\\resources\\codex.exe' -and
    $_.CommandLine -notmatch '--type='
}} | Select-Object -First 1
$launcherPath = $mainProcess.ExecutablePath
if ($launcherPath) {{
    Write-Log ("Using running launcher path: " + $launcherPath)
}}
if (-not $launcherPath) {{
    $package = Get-AppxPackage | Where-Object {{
        $_.Name -eq 'OpenAI.Codex' -or $_.PackageFamilyName -like 'OpenAI.Codex*'
    }} | Sort-Object Version -Descending | Select-Object -First 1
    if ($package -and $package.InstallLocation) {{
        $launcherPath = Join-Path $package.InstallLocation 'app\\Codex.exe'
        Write-Log ("Using package launcher path: " + $launcherPath)
    }}
}}
if (-not $launcherPath) {{
    Write-Log 'Unable to locate the Codex Desktop executable.'
    throw 'Unable to locate the Codex Desktop executable.'
}}
Start-Sleep -Milliseconds {delay_ms}
$codexProcesses = Get-CimInstance Win32_Process | Where-Object {{
    $_.Name -ieq 'Codex.exe' -or
    $_.ExecutablePath -like '*\\OpenAI.Codex_*\\app\\Codex.exe' -or
    $_.ExecutablePath -like '*\\OpenAI.Codex_*\\app\\resources\\codex.exe'
}}
Write-Log ("Found " + $codexProcesses.Count + " Codex processes to stop.")
$codexProcesses | ForEach-Object {{
    try {{
        & taskkill.exe /PID $_.ProcessId /F /T | Out-Null
        Write-Log ("taskkill succeeded for PID " + $_.ProcessId)
    }} catch {{
        Write-Log ("taskkill failed for PID " + $_.ProcessId + ": " + $_.Exception.Message)
    }}
    try {{
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        Write-Log ("Stop-Process succeeded for PID " + $_.ProcessId)
    }} catch {{
        Write-Log ("Stop-Process failed for PID " + $_.ProcessId + ": " + $_.Exception.Message)
    }}
}}
$deadline = (Get-Date).AddSeconds(8)
while ((Get-Date) -lt $deadline) {{
    $remaining = Get-CimInstance Win32_Process | Where-Object {{
        $_.Name -ieq 'Codex.exe' -or
        $_.ExecutablePath -like '*\\OpenAI.Codex_*\\app\\Codex.exe' -or
        $_.ExecutablePath -like '*\\OpenAI.Codex_*\\app\\resources\\codex.exe'
    }}
    if (-not $remaining) {{
        Write-Log 'All Codex processes exited.'
        break
    }}
    Write-Log ("Still waiting for " + $remaining.Count + " Codex processes to exit.")
    $remaining | ForEach-Object {{
        try {{
            & taskkill.exe /PID $_.ProcessId /F /T | Out-Null
        }} catch {{}}
    }}
    Start-Sleep -Milliseconds 250
}}
if (Get-CimInstance Win32_Process | Where-Object {{
    $_.Name -ieq 'Codex.exe' -or
    $_.ExecutablePath -like '*\\OpenAI.Codex_*\\app\\Codex.exe' -or
    $_.ExecutablePath -like '*\\OpenAI.Codex_*\\app\\resources\\codex.exe'
}}) {{
    Write-Log 'Continuing with relaunch after timeout while some Codex processes still appear alive.'
}}
Start-Sleep -Milliseconds 700
Start-Process -FilePath $launcherPath
Write-Log 'Codex Desktop relaunched.'
""".strip()


def encode_powershell_script(script: str) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def restart_codex_desktop(delay_seconds: float = DEFAULT_RESTART_DELAY_SECONDS) -> None:
    ensure_directories()
    RESTART_SCRIPT_PATH.write_text(build_restart_script(delay_seconds), encoding="utf-8")
    RESTART_LAUNCHER_PATH.write_text(build_restart_launcher(), encoding="ascii")

    try:
        os.startfile(str(RESTART_LAUNCHER_PATH))
    except OSError as error:
        raise CodexDesktopControlError("Failed to restart Codex Desktop.") from error


def _powershell_literal_path(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def build_restart_launcher() -> str:
    powershell_path = _cmd_literal_path(POWERSHELL_EXE)
    script_path = _cmd_literal_path(RESTART_SCRIPT_PATH)
    return (
        "@echo off\r\n"
        f"start \"\" /min {powershell_path} -NoProfile -NonInteractive -WindowStyle Hidden "
        f"-ExecutionPolicy Bypass -File {script_path}\r\n"
        "exit /b 0\r\n"
    )


def _cmd_literal_path(path: Path) -> str:
    return '"' + str(path).replace('"', '""') + '"'
