#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="$ROOT_DIR/ReleaseArtifacts"
APP_PATH="$("$ROOT_DIR/Scripts/package_app.sh" | tail -n 1)"
ZIP_PATH="$ARTIFACT_DIR/CodexControl-macos.zip"

rm -rf "$ARTIFACT_DIR"
mkdir -p "$ARTIFACT_DIR"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
shasum -a 256 "$ZIP_PATH" > "$ZIP_PATH.sha256"

printf '%s\n%s\n' "$ZIP_PATH" "$ZIP_PATH.sha256"
