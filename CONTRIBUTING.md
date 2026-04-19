# Contributing

## Development Setup

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

## Pull Request Guidance

- Keep changes scoped and reviewable.
- Do not commit real account data, `auth.json`, snapshots, or screenshots with real user identities.
- Prefer synthetic demo data for UI assets and documentation.
- If you touch quota logic, include the exact scenario you validated.
- If you touch switching logic, describe the expected desktop restart behavior.

## Before Opening a PR

- Build the macOS app successfully.
- Run Windows tests in an isolated environment if you changed the Windows implementation.
- Re-check the repository for absolute local paths, real customer emails, or token-like strings.
