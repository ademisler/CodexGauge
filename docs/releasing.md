# Releasing CodexControl

This repository supports both manual local releases and tag-driven GitHub releases.

## Versioning

- Update [CHANGELOG.md](../CHANGELOG.md)
- Commit the release preparation changes
- Tag with `vX.Y.Z`

## Local Validation

Before cutting a release:

```bash
./Scripts/bootstrap_sparkle.sh
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

If `CODE_SIGN_IDENTITY` and `NOTARY_KEYCHAIN_PROFILE` are both present in the environment, the same command also notarizes and staples the `.app` before zipping it.

Build the Windows release package locally:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\package_release.ps1 -Clean
```

This writes:

- `ReleaseArtifacts/CodexControl-windows.zip`
- `ReleaseArtifacts/CodexControl-windows.zip.sha256`

## GitHub Release Workflow

Pushing a tag such as `v1.1.0` triggers `.github/workflows/release.yml`.

That workflow:

- ensures the GitHub Release exists for the tag
- packages the macOS app
- optionally signs and notarizes the macOS app if Apple secrets are configured
- zips the `.app`
- builds a zipped Windows package
- creates or updates the matching GitHub Release
- uploads both platform archives and SHA-256 checksums

### Optional Apple Secrets

If you want GitHub Actions to sign and notarize macOS builds, configure:

- `APPLE_DEVELOPER_ID_APPLICATION_P12_BASE64`
- `APPLE_DEVELOPER_ID_APPLICATION_P12_PASSWORD`
- `APPLE_DEVELOPER_ID_APPLICATION_IDENTITY`
- `APPLE_NOTARY_APPLE_ID`
- `APPLE_NOTARY_TEAM_ID`
- `APPLE_NOTARY_APP_PASSWORD`

Without these secrets, release builds still complete, but the macOS archive is ad-hoc signed and not notarized.

## Sparkle Feed

After a macOS release archive exists, generate the appcast locally using the keychain-resident Sparkle key:

```bash
./Scripts/generate_appcast.sh
```

If direct keychain access is inconvenient in automation, export the private Sparkle key once to a local ignored path and pass it explicitly:

```bash
SPARKLE_PRIVATE_KEY_FILE=.tmp/sparkle-private.key ./Scripts/generate_appcast.sh
```

By default this writes:

- `site/appcast.xml`

and expects the release asset URL:

- `https://github.com/ademisler/CodexControl/releases/download/vX.Y.Z/CodexControl-macos.zip`

Release notes for Sparkle should live under `site/releases/`.

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
