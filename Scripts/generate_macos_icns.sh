#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_SVG="$ROOT_DIR/site/assets/codexcontrol-mark.svg"
OUTPUT_ICNS="${1:-$ROOT_DIR/Build/CodexControl.icns}"
TEMP_DIR="$(mktemp -d)"
ICONSET_DIR="$TEMP_DIR/CodexControl.iconset"
MASTER_PNG="$TEMP_DIR/master-1024.png"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

mkdir -p "$ICONSET_DIR" "$(dirname "$OUTPUT_ICNS")"

sips -z 1024 1024 -s format png "$SOURCE_SVG" --out "$MASTER_PNG" >/dev/null

render_icon() {
  local pixels="$1"
  local name="$2"
  sips -z "$pixels" "$pixels" "$MASTER_PNG" --out "$ICONSET_DIR/$name" >/dev/null
}

render_icon 16 icon_16x16.png
render_icon 32 icon_16x16@2x.png
render_icon 32 icon_32x32.png
render_icon 64 icon_32x32@2x.png
render_icon 128 icon_128x128.png
render_icon 256 icon_128x128@2x.png
render_icon 256 icon_256x256.png
render_icon 512 icon_256x256@2x.png
render_icon 512 icon_512x512.png
render_icon 1024 icon_512x512@2x.png

iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT_ICNS"
printf '%s\n' "$OUTPUT_ICNS"
