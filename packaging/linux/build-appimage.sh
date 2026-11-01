#!/usr/bin/env bash
# Build dist/FocusLock.AppImage from this checkout.
#   packaging/linux/build-appimage.sh [work-dir]
#
# Starts from python-appimage's portable Python 3.12 (which bundles Tk:
# https://github.com/niess/python-appimage), adds numpy and FocusLock's
# files under usr/share/focuslock, and swaps in packaging/AppRun, which
# expects exactly that layout. Needs curl, python3 and an internet
# connection; runs on any x86_64 Linux, including GitHub's runners (no
# FUSE needed: the downloaded AppImages are extracted, not mounted).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${1:-$ROOT/build/appimage}"
OUT="$ROOT/dist/FocusLock.AppImage"
export ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1

rm -rf "$WORK"
mkdir -p "$WORK" "$ROOT/dist"
cd "$WORK"

echo "== Python 3.12 with Tk (python-appimage)"
url="$(curl -fsSL https://api.github.com/repos/niess/python-appimage/releases/tags/python3.12 | python3 -c '
import json, re, sys
assets = json.load(sys.stdin)["assets"]
pat = re.compile(r"python3\.12\.(\d+)-cp312-cp312-manylinux2014_x86_64\.AppImage$")
best = max((int(m.group(1)), a["browser_download_url"]) for a in assets if (m := pat.search(a["name"])))
print(best[1])')"
echo "$url"
curl -fsSL -o python.AppImage "$url"
chmod +x python.AppImage
./python.AppImage --appimage-extract >/dev/null
APPDIR="$WORK/squashfs-root"
PY="$APPDIR/opt/python3.12/bin/python3.12"

echo "== numpy (ambient sounds)"
"$PY" -m pip install --quiet --no-warn-script-location --no-cache-dir numpy

echo "== FocusLock"
mkdir -p "$APPDIR/usr/share/focuslock"
cp "$ROOT"/*.py "$ROOT"/*.sh "$ROOT/icon.svg" "$APPDIR/usr/share/focuslock/"
# Python's own launcher, menu entry and metadata make way for FocusLock's.
rm -f "$APPDIR/AppRun" "$APPDIR"/*.desktop "$APPDIR"/*.png "$APPDIR/.DirIcon"
rm -rf "$APPDIR/usr/share/metainfo" "$APPDIR/usr/share/applications"
install -m 755 "$ROOT/packaging/AppRun" "$APPDIR/AppRun"
cp "$ROOT/packaging/focuslock.desktop" "$APPDIR/focuslock.desktop"
cp "$ROOT/icon.svg" "$APPDIR/focuslock.svg"
ln -s focuslock.svg "$APPDIR/.DirIcon"
find "$APPDIR" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "== appimagetool"
curl -fsSL -o appimagetool \
  https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool
./appimagetool --no-appstream "$APPDIR" "$OUT"
echo "Built $OUT"
