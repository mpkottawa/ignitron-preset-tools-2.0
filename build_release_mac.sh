#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Ignitron Preset Tools v2.0"
ENTRY="$ROOT/ignitron_preset_tools_v2.0.py"
BUILD_ROOT="$ROOT/build"
DIST_ROOT="$ROOT/release"
DIST_APP="$DIST_ROOT/$APP_NAME.app"
DIST_PACKAGE="$DIST_ROOT/$APP_NAME macOS"
ZIP_PATH="$DIST_ROOT/$APP_NAME-macOS.zip"
FIRMWARE_SOURCE="$ROOT/Ignitron"
FIRMWARE_RELEASE="$DIST_PACKAGE/ignitron firmware"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must be run on macOS to build a real .app bundle."
  exit 1
fi

if [[ ! -f "$ENTRY" ]]; then
  echo "Missing entry point: $ENTRY"
  exit 1
fi

python3 -m pip install -r "$ROOT/requirements.txt"

ICON_ARGS=()
if [[ -f "$ROOT/IPT.icns" ]]; then
  ICON_ARGS=(--icon "$ROOT/IPT.icns")
else
  echo "No IPT.icns found. Building macOS app without a custom dock icon."
  echo "To add one, convert IPT.ico to IPT.icns on macOS and rerun this script."
fi

pyinstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_ROOT" \
  --workpath "$BUILD_ROOT/pyinstaller-macos" \
  --specpath "$BUILD_ROOT" \
  ${ICON_ARGS[@]+"${ICON_ARGS[@]}"} \
  --add-data "$ROOT/reference:reference" \
  --add-data "$ROOT/data:data" \
  --add-data "$ROOT/IPT.ico:." \
  --add-data "$ROOT/preset_puller.py:." \
  --add-data "$ROOT/preset_chart.py:." \
  --add-data "$ROOT/preset_converter.py:." \
  "$ENTRY"

cp "$ROOT/README.md" "$DIST_APP/Contents/Resources/README.md"
cp "$ROOT/RELEASE_NOTES.md" "$DIST_APP/Contents/Resources/RELEASE_NOTES.md"
rm -rf "$DIST_PACKAGE"
mkdir -p "$DIST_PACKAGE"
cp -R "$DIST_APP" "$DIST_PACKAGE/"
cp "$ROOT/README.md" "$DIST_PACKAGE/README.md"
cp "$ROOT/RELEASE_NOTES.md" "$DIST_PACKAGE/RELEASE_NOTES.md"
if [[ -d "$FIRMWARE_SOURCE" ]]; then
  rm -rf "$FIRMWARE_RELEASE"
  cp -R "$FIRMWARE_SOURCE" "$FIRMWARE_RELEASE"
  rm -rf \
    "$FIRMWARE_RELEASE/.pio" \
    "$FIRMWARE_RELEASE/backups" \
    "$FIRMWARE_RELEASE/captures" \
    "$FIRMWARE_RELEASE/logs" \
    "$FIRMWARE_RELEASE/output" \
    "$FIRMWARE_RELEASE/tmp" \
    "$FIRMWARE_RELEASE/preview_cache"
fi

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$DIST_PACKAGE" "$ZIP_PATH"

echo "Built $APP_NAME for macOS"
echo "App: $DIST_APP"
echo "Package: $DIST_PACKAGE"
echo "Zip: $ZIP_PATH"
