#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build/release"
APP_DIR="$ROOT_DIR/Build/CodexControl.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
FRAMEWORKS_DIR="$CONTENTS_DIR/Frameworks"
APP_ICON_PATH="$ROOT_DIR/Build/CodexControl.icns"
SPARKLE_DIST_DIR="$("$ROOT_DIR/Scripts/bootstrap_sparkle.sh" | tail -n 1)"
SPARKLE_FRAMEWORK_PATH="$SPARKLE_DIST_DIR/Sparkle.framework"
CODE_SIGN_IDENTITY="${CODE_SIGN_IDENTITY:-}"

cd "$ROOT_DIR"
swift build -c release
"$ROOT_DIR/Scripts/generate_macos_icns.sh" "$APP_ICON_PATH" >/dev/null

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$FRAMEWORKS_DIR"

cp "$BUILD_DIR/CodexControl" "$MACOS_DIR/CodexControl"
cp "$ROOT_DIR/Support/Info.plist" "$CONTENTS_DIR/Info.plist"
cp "$APP_ICON_PATH" "$RESOURCES_DIR/CodexControl.icns"
ditto "$SPARKLE_FRAMEWORK_PATH" "$FRAMEWORKS_DIR/Sparkle.framework"

if [[ -n "$CODE_SIGN_IDENTITY" ]]; then
  codesign --force --deep --options runtime --timestamp --sign "$CODE_SIGN_IDENTITY" "$APP_DIR" >/dev/null
else
  codesign --force --deep --sign - "$APP_DIR" >/dev/null
fi

echo "$APP_DIR"
