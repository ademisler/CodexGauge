# CodexGauge

CodexGauge is a lightweight macOS menu bar app for tracking Codex account quota in real time.

It is built for people who manage multiple Codex accounts and want a fast, focused tool instead of a large multi-provider dashboard.

## Features

- Codex-only account tracking
- Direct quota reads from OpenAI usage endpoints
- Separate 5-hour and 7-day windows when the account exposes both
- Exact reset timestamps for each quota window
- Automatic refresh every 5 minutes
- Manual refresh on demand
- In-app account add and re-authentication flows
- In-app cancellation for an active login flow
- Local-first account storage

## Why This Exists

Most quota trackers are either:

- broad multi-provider dashboards
- browser-driven tools with extra overhead
- utilities built around logs instead of live account state

CodexGauge is intentionally narrow:

- one provider
- small menu bar UI
- direct live quota fetches
- account-focused workflow

## Accuracy Approach

CodexGauge reads quota data directly from OpenAI using each account's local Codex authentication state.

To reduce stale or misleading readings:

- requests use an ephemeral no-cache session
- live reads are verified across multiple fetches
- inconsistent responses are rejected instead of shown as current truth
- stale snapshots are cleared on refresh failures

## Privacy

CodexGauge is local-first.

- account data stays on your Mac
- the app reads `auth.json` from each account's Codex home
- the public repository does not include local account files, snapshots, or tokens

Application data is stored under:

- `~/Library/Application Support/CodexGauge`

If you are upgrading from an earlier local build, the app migrates data from:

- `~/Library/Application Support/CodexAccounts`

## Requirements

- macOS 14 or later
- a working `codex` CLI installation

## Build From Source

```bash
swift build
./Scripts/package_app.sh
open ./Build/CodexGauge.app
```

## Status

CodexGauge is designed for personal and small-team use cases where fast access to live Codex quota matters more than broad provider support.

## License

MIT
