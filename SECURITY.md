# Security Policy

## Supported Scope

This repository contains a local-first desktop tool that reads local Codex authentication state to show quota and switch active accounts.

Security-sensitive areas include:

- token refresh and quota fetch logic
- account switching and ambient session replacement
- desktop restart helpers
- repository hygiene around screenshots, docs, and sample data

## Reporting a Vulnerability

Please do not open a public issue with:

- tokens
- `auth.json` contents
- snapshots
- private file paths
- screenshots that reveal real accounts

Use GitHub private security reporting if available for the repository. If private reporting is not available in your environment, open a minimal public issue without sensitive payloads and state that you can provide details privately.

## Repository Hygiene Rules

- Never commit real `auth.json` files.
- Never commit live account snapshots.
- Never commit screenshots with real account identities.
- Prefer synthetic demo data for docs and UI examples.
