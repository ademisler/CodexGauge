# CodexControl

<p align="center">
  <img src="./site/assets/codexcontrol-mark.svg" alt="CodexControl logo" width="72">
</p>

<p align="center">
  <img src="./docs/images/codexcontrol-demo-ui.png" alt="CodexControl demo UI" width="430">
</p>

<p align="center">
  <strong>Local-first Codex quota tracking and account switching for macOS and Windows.</strong>
</p>

<p align="center">
  <a href="https://codexcontrol.app">Website</a>
  ·
  <a href="https://github.com/ademisler/CodexControl">GitHub</a>
  ·
  <a href="https://github.com/ademisler/CodexControl/releases">Releases</a>
  ·
  <a href="https://github.com/ademisler/CodexControl/blob/main/SECURITY.md">Security</a>
</p>

<p align="center">
  <img alt="macOS 14+" src="https://img.shields.io/badge/macOS-14%2B-111111?logo=apple&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-supported-111111?logo=windows&logoColor=white">
  <img alt="Local-first" src="https://img.shields.io/badge/storage-local--first-111111">
  <img alt="MIT License" src="https://img.shields.io/badge/license-MIT-111111">
</p>

CodexControl is a focused desktop app for people who actively manage multiple OpenAI Codex accounts.

It does two things well:

- shows live quota directly from OpenAI
- switches the active Codex account used by the local CLI

## Install

### Homebrew

```bash
brew install --cask ademisler/tap/codexcontrol
```

### Direct Download

- macOS and Windows release: [CodexControl 1.1.0](https://github.com/ademisler/CodexControl/releases/tag/v1.1.0)
- Homebrew tap: [ademisler/homebrew-tap](https://github.com/ademisler/homebrew-tap)

## Why CodexControl

Most tools around this workflow fall into one of these categories:

- multi-provider dashboards with too much surface area
- browser-driven quota trackers with extra runtime overhead
- scripts that estimate usage instead of reading the live account state
- switchers that do not tell you which account is actually usable right now

CodexControl is intentionally narrower:

- Codex-only
- local-first
- fast to scan
- built around real quota windows and active-account control

## Core Capabilities

| Capability | What it does |
| --- | --- |
| Live quota reads | Fetches Codex quota windows directly from OpenAI using each account's local auth state |
| 5-hour and 7-day windows | Preserves per-window usage independently when both windows are available |
| Exact reset times | Shows when each quota window refills |
| Active account switching | Replaces the ambient `~/.codex` session with the selected account |
| Reauthentication | Refreshes a saved account without rebuilding the account list |
| Local account management | Add, remove, relabel, refresh, and open account folders from the app |
| Periodic refresh | Rechecks all accounts every 5 minutes |
| Sparkle updates | Checks for signed macOS updates from the in-app updater feed |

## How It Works

1. CodexControl reads each account from local Codex homes.
2. It loads `auth.json` for that account and refreshes tokens when required.
3. It requests quota data directly from OpenAI.
4. It keeps the account list sorted by practical usefulness, so usable accounts stay on top.
5. When you switch accounts, it updates the ambient Codex session and restarts Codex Desktop to apply the new identity.

## Accuracy Approach

Quota accuracy is a first-order requirement in this project.

CodexControl uses these safeguards:

- cache-bypassing network sessions
- repeated live reads with equivalence checks
- rejection of inconsistent live responses
- per-window normalization that preserves the original OpenAI values
- stale snapshot clearing on refresh failures

This is especially important for Team and paid plans where the 5-hour window can be exhausted while the 7-day window still has remaining capacity.

## Privacy and Security

CodexControl is local-first by design.

- account files stay on your machine
- the app reads local `auth.json` files from Codex homes
- the public repository does not ship real account data, snapshots, or tokens
- demo screenshots in this repository use synthetic accounts only

Current storage locations:

- macOS: `~/Library/Application Support/CodexControl`
- Windows: `%APPDATA%\\CodexControl`

Migration from previous local app directories is automatic.

## Platform Notes

### macOS

- Built with SwiftUI + AppKit
- Ships as a menu bar app
- Supports Codex Desktop restart after account switching
- Uses Sparkle for signed app update delivery
- Includes release scripts for signing and notarization when Apple credentials are available

### Windows

- Lives under [`windows`](./windows)
- Uses Python with a tray-first workflow
- Includes add account, refresh, reauthenticate, switch, and install scripts

## Website

The project website lives at [codexcontrol.app](https://codexcontrol.app).

- Static landing page source: [`site`](./site)
- Cloudflare Pages config: [`wrangler.jsonc`](./wrangler.jsonc)
- Deploy command: `./Scripts/deploy_site.sh`
- Sparkle appcast: [`site/appcast.xml`](./site/appcast.xml)
- Homebrew cask: `ademisler/tap/codexcontrol`

## Build From Source

### macOS

```bash
./Scripts/bootstrap_sparkle.sh
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

## Repository Structure

```text
Sources/CodexControl/         macOS app
Scripts/                      macOS packaging helpers
Support/                      app metadata
site/releases/                Sparkle release notes hosted on codexcontrol.app
site/                         marketing website for codexcontrol.app
wrangler.jsonc                Cloudflare Pages config
CHANGELOG.md                  release history
docs/releasing.md             release process
windows/                      Windows implementation and scripts
docs/images/                  repository screenshots
```

## Contributing

Setup and contribution notes live in [CONTRIBUTING.md](./CONTRIBUTING.md).

## Security

Security reporting guidance lives in [SECURITY.md](./SECURITY.md).

## License

MIT
