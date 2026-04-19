#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="$ROOT_DIR/ReleaseArtifacts"
APP_PATH="$("$ROOT_DIR/Scripts/package_app.sh" | tail -n 1)"
ZIP_PATH="$ARTIFACT_DIR/CodexControl-macos.zip"
CODE_SIGN_IDENTITY="${CODE_SIGN_IDENTITY:-}"
NOTARY_KEYCHAIN_PROFILE="${NOTARY_KEYCHAIN_PROFILE:-}"

rm -rf "$ARTIFACT_DIR"
mkdir -p "$ARTIFACT_DIR"

if [[ -n "$CODE_SIGN_IDENTITY" && -n "$NOTARY_KEYCHAIN_PROFILE" ]]; then
  "$ROOT_DIR/Scripts/notarize_macos.sh" "$APP_PATH"
fi

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
shasum -a 256 "$ZIP_PATH" > "$ZIP_PATH.sha256"

printf '%s\n%s\n' "$ZIP_PATH" "$ZIP_PATH.sha256"
