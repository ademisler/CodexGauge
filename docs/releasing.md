# Releasing CodexControl

This repository supports both manual local releases and tag-driven GitHub releases.

## Versioning

- Update [CHANGELOG.md](../CHANGELOG.md)
- Commit the release preparation changes
- Tag with `vX.Y.Z`

## Local Validation

Before cutting a release:

```bash
swift build
./Scripts/package_app.sh
PYTHONPATH=windows python3 -m unittest discover -s windows/tests -v
```

If the website changed:

```bash
./Scripts/deploy_site.sh
```

## Release Artifacts

Build the macOS release archive locally:

```bash
./Scripts/build_release_artifacts.sh
```

This writes:

- `ReleaseArtifacts/CodexControl-macos.zip`
- `ReleaseArtifacts/CodexControl-macos.zip.sha256`

## GitHub Release Workflow

Pushing a tag such as `v1.0.0` triggers `.github/workflows/release.yml`.

That workflow:

- packages the macOS app
- zips the `.app`
- creates or updates the matching GitHub Release
- uploads the zip and SHA-256 checksum

## Homebrew Tap Update

After a new GitHub Release is live:

1. copy the release asset SHA-256 for `CodexControl-macos.zip`
2. update `Casks/codexcontrol.rb` in `ademisler/homebrew-tap`
3. bump the version and SHA there
4. push the tap repo

Install command:

```bash
brew install --cask ademisler/tap/codexcontrol
```

## Site Deployment

The website intentionally stays on manual deploy by default.

Reason:

- automated deployment should use a narrow Cloudflare Pages token
- the current setup should not depend on a broad personal API credential

Manual deploy:

```bash
./Scripts/deploy_site.sh
```

## Repository Hygiene

Before tagging:

- scan for real tokens, emails, and local paths
- confirm screenshots still use synthetic demo accounts
- confirm no `auth.json`, snapshots, or managed-home data entered the tree
