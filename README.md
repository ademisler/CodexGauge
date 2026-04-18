# CodexControl

CodexControl is a local desktop app for OpenAI Codex users who need two things in one place:

- live quota visibility
- fast account switching

It tracks each saved Codex account directly from local authentication state, reads quota windows from OpenAI, and lets you switch the active `~/.codex` account without signing in again from scratch.

## What It Does

- Shows live Codex quota directly from OpenAI
- Separates the 5-hour and 7-day windows when both are present
- Shows exact reset timestamps for each quota window
- Refreshes automatically every 5 minutes
- Supports manual refresh at any time
- Adds and reauthenticates accounts in-app
- Cancels an in-progress browser login flow in-app
- Switches the active Codex account used by the CLI
- Keeps account data local on your machine
- Runs on macOS and includes a Windows implementation in [`windows`](./windows)

## Why This Exists

Most tools in this space are optimized for a different problem:

- multi-provider dashboards
- browser-heavy quota trackers
- log-based estimators
- account switchers without accurate live quota

CodexControl is built specifically for people managing multiple Codex identities who care about the current truth:

- which account is active
- which account is still usable right now
- when each limit resets
- how to switch immediately

## Accuracy Model

CodexControl reads quota from OpenAI using each account's local Codex auth state.

To keep the numbers trustworthy:

- requests use an ephemeral no-cache session
- live reads are verified across multiple fetches
- inconsistent responses are rejected instead of shown
- stale snapshots are cleared on refresh failures
- per-window usage is preserved exactly as returned by OpenAI, even when the account is currently blocked by a shorter window

This matters for Team and paid accounts where the 5-hour window can be exhausted while the 7-day window still has remaining capacity.

## Privacy

CodexControl is local-first.

- account files stay on your machine
- the app reads local `auth.json` files from each Codex home
- the public repository does not include tokens, snapshots, or personal account data

macOS data path:

- `~/Library/Application Support/CodexControl`

Windows data path:

- `%APPDATA%\\CodexControl`

Migration from previous local app directories is automatic.

## Requirements

### macOS

- macOS 14 or later
- a working `codex` CLI installation

### Windows

- Python 3.11+
- a working `codex` CLI installation

## Build From Source

### macOS

```bash
swift build
./Scripts/package_app.sh
open ./Build/CodexControl.app
```

### Windows

```powershell
python -m pip install -r .\windows\requirements.txt
python .\windows\CodexControlWindows.pyw
```

Build a standalone EXE:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\build.ps1
```

Install the built EXE and register startup:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\install.ps1 -EnableStartup -Launch
```

## Scope

CodexControl is intentionally focused. It is not trying to be:

- a general AI quota dashboard
- a browser automation layer
- a multi-provider billing console

It is for Codex accounts, live quota windows, and fast active-account control.

## License

MIT
