#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SPARKLE_VERSION="${SPARKLE_VERSION:-2.9.1}"
DIST_DIR="$ROOT_DIR/.sparkle-dist"
FRAMEWORK_PATH="$DIST_DIR/Sparkle.framework"
BIN_DIR="$DIST_DIR/bin"
STAMP_PATH="$DIST_DIR/.version"
ARCHIVE_URL="https://github.com/sparkle-project/Sparkle/releases/download/$SPARKLE_VERSION/Sparkle-$SPARKLE_VERSION.tar.xz"
TEMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

if [[ -f "$STAMP_PATH" ]] && [[ "$(cat "$STAMP_PATH")" == "$SPARKLE_VERSION" ]] && [[ -d "$FRAMEWORK_PATH" ]] && [[ -x "$BIN_DIR/sign_update" ]]; then
  printf '%s\n' "$DIST_DIR"
  exit 0
fi

ARCHIVE_PATH="$TEMP_DIR/Sparkle.tar.xz"
curl -L --fail --silent --show-error "$ARCHIVE_URL" -o "$ARCHIVE_PATH"
tar -xJf "$ARCHIVE_PATH" -C "$TEMP_DIR"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
ditto "$TEMP_DIR/Sparkle.framework" "$FRAMEWORK_PATH"
ditto "$TEMP_DIR/bin" "$BIN_DIR"
printf '%s\n' "$SPARKLE_VERSION" > "$STAMP_PATH"

printf '%s\n' "$DIST_DIR"
