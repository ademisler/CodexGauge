#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SPARKLE_DIST_DIR="$("$ROOT_DIR/Scripts/bootstrap_sparkle.sh" | tail -n 1)"
SIGN_UPDATE_BIN="$SPARKLE_DIST_DIR/bin/sign_update"
PLIST_BUDDY="/usr/libexec/PlistBuddy"

VERSION="${VERSION:-$("$PLIST_BUDDY" -c 'Print :CFBundleShortVersionString' "$ROOT_DIR/Support/Info.plist")}"
BUILD_NUMBER="${BUILD_NUMBER:-$("$PLIST_BUDDY" -c 'Print :CFBundleVersion' "$ROOT_DIR/Support/Info.plist")}"
MINIMUM_SYSTEM_VERSION="${MINIMUM_SYSTEM_VERSION:-14.0.0}"
ARCHIVE_PATH="${ARCHIVE_PATH:-$ROOT_DIR/ReleaseArtifacts/CodexControl-macos.zip}"
DOWNLOAD_URL="${DOWNLOAD_URL:-https://github.com/ademisler/CodexControl/releases/download/v$VERSION/CodexControl-macos.zip}"
RELEASE_NOTES_URL="${RELEASE_NOTES_URL:-https://codexcontrol.app/releases/v$VERSION.md}"
APPCAST_PATH="${APPCAST_PATH:-$ROOT_DIR/site/appcast.xml}"
PUBLISHED_AT="${PUBLISHED_AT:-$(LC_ALL=C date -u '+%a, %d %b %Y %H:%M:%S %z')}"
SPARKLE_PRIVATE_KEY_FILE="${SPARKLE_PRIVATE_KEY_FILE:-}"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "archive not found: $ARCHIVE_PATH" >&2
  exit 1
fi

sign_args=()
if [[ -n "$SPARKLE_PRIVATE_KEY_FILE" ]]; then
  sign_args=(--ed-key-file "$SPARKLE_PRIVATE_KEY_FILE")
fi

signature_fragment="$("$SIGN_UPDATE_BIN" "${sign_args[@]}" "$ARCHIVE_PATH" | awk '/sparkle:edSignature=/{print $0}' | tail -n 1)"
if [[ -z "$signature_fragment" ]]; then
  echo "failed to generate Sparkle signature for $ARCHIVE_PATH" >&2
  exit 1
fi

mkdir -p "$(dirname "$APPCAST_PATH")"
cat > "$APPCAST_PATH" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>CodexControl Updates</title>
    <link>https://codexcontrol.app/</link>
    <description>Release feed for CodexControl macOS updates.</description>
    <language>en</language>
    <item>
      <title>Version $VERSION</title>
      <link>https://codexcontrol.app/</link>
      <sparkle:version>$BUILD_NUMBER</sparkle:version>
      <sparkle:shortVersionString>$VERSION</sparkle:shortVersionString>
      <sparkle:minimumSystemVersion>$MINIMUM_SYSTEM_VERSION</sparkle:minimumSystemVersion>
      <sparkle:releaseNotesLink>$RELEASE_NOTES_URL</sparkle:releaseNotesLink>
      <pubDate>$PUBLISHED_AT</pubDate>
      <enclosure url="$DOWNLOAD_URL"
                 $signature_fragment
                 type="application/octet-stream" />
    </item>
  </channel>
</rss>
EOF

printf '%s\n' "$APPCAST_PATH"
