#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build/release"
APP_DIR="$ROOT_DIR/Build/CodexControl.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_ICON_PATH="$ROOT_DIR/Build/CodexControl.icns"

cd "$ROOT_DIR"
swift build -c release
"$ROOT_DIR/Scripts/generate_macos_icns.sh" "$APP_ICON_PATH" >/dev/null

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

cp "$BUILD_DIR/CodexControl" "$MACOS_DIR/CodexControl"
cp "$ROOT_DIR/Support/Info.plist" "$CONTENTS_DIR/Info.plist"
cp "$APP_ICON_PATH" "$RESOURCES_DIR/CodexControl.icns"

codesign --force --deep --sign - "$APP_DIR" >/dev/null

echo "$APP_DIR"
