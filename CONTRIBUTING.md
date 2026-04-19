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
$env:PYTHONPATH = "windows"
python -m unittest discover -s windows/tests -v
```

### Website

```bash
./Scripts/deploy_site.sh
```

### Release Artifacts

```bash
./Scripts/build_release_artifacts.sh
```

## Pull Request Guidance

- Keep changes scoped and reviewable.
- Do not commit real account data, `auth.json`, snapshots, or screenshots with real user identities.
- Prefer synthetic demo data for UI assets and documentation.
- Reuse the shared logo and mark assets under [`site/assets`](./site/assets) instead of creating ad-hoc variants.
- If you touch quota logic, include the exact scenario you validated.
- If you touch switching logic, describe the expected desktop restart behavior.

## Before Opening a PR

- Build the macOS app successfully.
- Run Windows tests in an isolated environment if you changed the Windows implementation.
- Regenerate release artifacts if you changed packaging or release-facing assets.
- Re-check the repository for absolute local paths, real customer emails, or token-like strings.
