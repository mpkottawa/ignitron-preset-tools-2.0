#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Ignitron Preset Tools v2.0"
ENTRY="$ROOT/ignitron_preset_tools_v2.0.py"
BUILD_ROOT="$ROOT/build"
DIST_ROOT="$ROOT/release"
DIST_APP="$DIST_ROOT/$APP_NAME.app"
ZIP_PATH="$DIST_ROOT/$APP_NAME-macOS.zip"

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
  "${ICON_ARGS[@]}" \
  --add-data "$ROOT/reference:reference" \
  --add-data "$ROOT/data:data" \
  --add-data "$ROOT/Ignitron:Ignitron" \
  --add-data "$ROOT/IPT.ico:." \
  --add-data "$ROOT/preset_puller.py:." \
  --add-data "$ROOT/preset_chart.py:." \
  --add-data "$ROOT/preset_converter.py:." \
  "$ENTRY"

cp "$ROOT/README.md" "$DIST_APP/Contents/Resources/README.md"
cp "$ROOT/RELEASE_NOTES.md" "$DIST_APP/Contents/Resources/RELEASE_NOTES.md"

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$DIST_APP" "$ZIP_PATH"

echo "Built $APP_NAME for macOS"
echo "App: $DIST_APP"
echo "Zip: $ZIP_PATH"
