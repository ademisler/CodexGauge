# CodexControl for Windows

This folder contains the Windows implementation of CodexControl.

## What It Does

- Tracks Codex account quota from local `auth.json` state
- Shows live 5-hour and 7-day windows when available
- Supports account switching, add account, refresh, reauthenticate, open folder, and remove
- Runs as a tray app with a dashboard window
- Persists accounts and snapshots under `%APPDATA%\\CodexControl`
- Migrates local data from previous local app directories automatically

## Run Locally

```powershell
python -m pip install -r .\windows\requirements.txt
python .\windows\CodexControlWindows.pyw
```

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\build.ps1
```

This produces:

- `%REPO%\\windows\\dist\\CodexControl.exe`

## Install

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\install.ps1 -EnableStartup -Launch
```

The installer places the app under:

- `%LocalAppData%\\Programs\\CodexControl`

and registers a startup shortcut so the tray app can launch hidden at sign-in.

## Tests

```powershell
$env:PYTHONPATH = (Resolve-Path .\windows)
python -m unittest discover .\windows\tests
```
