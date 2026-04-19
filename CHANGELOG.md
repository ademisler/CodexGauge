# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

- Added Sparkle-based macOS update plumbing with signed appcast generation scripts
- Added Windows release packaging for GitHub Releases
- Added notarization-ready macOS release scripts and workflow hooks
- Updated the project brand to the dark Orbit Dial mark with green ring and red core
- Refined the website visual system and iconography to match the app brand

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
