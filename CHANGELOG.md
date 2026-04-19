# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Fixed

- Windows packaged account switching so the hidden PowerShell restart helper no longer uses `DETACHED_PROCESS`, which previously prevented Codex Desktop from relaunching after a switch

## [1.1.1] - 2026-04-19

### Added

- Windows-side presentation logic tests covering active account detection and practical quota sorting
- Tracked Windows build assets for the packaged tray application icon and preview image

### Changed

- Synced the Windows app from the latest stable `CodexControl-dev` implementation
- Updated release metadata and direct download references to `1.1.1`

### Removed

- Sparkle-based macOS update plumbing, appcast generation, and the in-app update action

### Fixed

- Windows active-account logic so shared provider IDs do not incorrectly mark multiple accounts as active
- Windows restart command path normalization for a consistent PowerShell launch path
- Windows quota presentation flow with the newer sorting and filtering layer from the stable dev copy

## [1.1.0] - 2026-04-19

### Added

- Sparkle updater integration for the macOS app with an in-app "Check for Updates" action
- Sparkle bootstrap and appcast generation scripts for local signed release preparation
- Windows release packaging script and GitHub Release asset upload workflow
- Notarization helper script and CI hooks for optional Apple credential-based signing
- Updated website iconography, install cards, and release metadata for the new distribution flow

### Changed

- Replaced the previous blue Orbit Dial mark with the dark, green, and red production brand
- Updated direct download references from `1.0.0` to `1.1.0`
- Embedded Sparkle.framework into the packaged macOS app bundle

### Fixed

- macOS packaging so Sparkle's framework and helper bundle are copied into the app
- Website CTA and navigation affordances so external destinations use explicit icons

## [1.0.0] - 2026-04-19

### Added

- Native macOS menu bar app for Codex quota tracking and account switching
- Windows tray app with quota reads, account management, and switching support
- Cloudflare Pages website for `codexcontrol.app`
- Homebrew cask distribution through `ademisler/homebrew-tap`
- GitHub Actions CI and tag-driven release automation
- Release and deployment scripts for macOS packaging and site publishing

### Changed

- Established CodexControl branding, website assets, and project release structure
- Adopted the Orbit Dial brand mark across the website, app packaging, and release assets
- Professionalized repository surface, documentation, and release readiness

### Fixed

- Weekly quota window handling for paid and Team accounts
- Active account switching behavior on macOS
- Account removal confirmation flow on macOS
- Window-specific quota coloring and account sorting logic
