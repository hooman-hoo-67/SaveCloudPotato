#!/usr/bin/env bash
#
# Build SaveCloud as an AppImage.
#
# One file that is both the interface and the command line: opened
# from a menu it shows a window, given arguments it behaves like the
# CLI. That matters because Steam launch options have to point at
# something, and an AppImage stays where it is put - unlike a virtual
# environment, whose path changes the moment it is recreated.
#
# Usage:  packaging/build-appimage.sh [output-directory]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUTPUT="${1:-$ROOT/dist}"

APPDIR="$ROOT/build/AppDir"

ARCH="${ARCH:-$(uname -m)}"

echo "==> Freezing"

cd "$ROOT"

python -m PyInstaller \
    --noconfirm \
    --distpath "$ROOT/build/frozen" \
    --workpath "$ROOT/build/pyinstaller" \
    packaging/savecloud.spec

echo "==> Assembling AppDir"

rm -rf "$APPDIR"

mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -a "$ROOT/build/frozen/savecloud/." "$APPDIR/usr/bin/"

cp "$ROOT/packaging/savecloud.desktop" \
   "$APPDIR/usr/share/applications/savecloud.desktop"

cp "$ROOT/packaging/savecloud.png" \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/savecloud.png"

#
# appimagetool looks for these at the AppDir root as well.
#

cp "$ROOT/packaging/savecloud.desktop" "$APPDIR/savecloud.desktop"

cp "$ROOT/packaging/savecloud.png" "$APPDIR/savecloud.png"

cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
#
# Hand every argument through, so `SaveCloud.AppImage wrap <game> --
# %command%` reaches the CLI unchanged.
#
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/savecloud" "$@"
RUN

chmod +x "$APPDIR/AppRun"

echo "==> Packaging"

mkdir -p "$OUTPUT"

TOOL="${APPIMAGETOOL:-appimagetool}"

if ! command -v "$TOOL" >/dev/null 2>&1; then
    echo "appimagetool not found. Download it from" >&2
    echo "  https://github.com/AppImage/appimagetool/releases" >&2
    echo "and put it on PATH, or set APPIMAGETOOL to its path." >&2
    exit 1
fi

#
# No FUSE in a container, and extracting is how appimagetool itself
# says to run without it.
#

ARCH="$ARCH" "$TOOL" "$APPDIR" "$OUTPUT/SaveCloud-$ARCH.AppImage"

echo "==> Built $OUTPUT/SaveCloud-$ARCH.AppImage"
