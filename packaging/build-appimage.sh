#!/usr/bin/env bash
#
# build-appimage.sh — produce dist/Amagra-x86_64.AppImage (Linux, single file).
#
# Strategy (the reliable recipe for a Python app with native deps):
#   1. Build the React UI to static files (FastAPI serves them — one process, no Node at runtime).
#   2. Use a RELOCATABLE Python from the python-appimage project as the base, so the
#      bundled interpreter + stdlib + libpython travel with the AppImage (no host Python needed).
#   3. pip-install requirements.txt into that base.
#   4. Overlay our code, AppRun, .desktop, and icon.
#   5. Repack with appimagetool.
#
# Prerequisites (install once on the build machine):
#   - npm            (to build the UI)
#   - curl, file     (download + appimagetool checks)
#   - FUSE           (to run appimagetool / the resulting AppImage)
# The script downloads the relocatable Python base and appimagetool automatically.
#
# Usage:   packaging/build-appimage.sh [--py 3.12]
# Output:  dist/Amagra-x86_64.AppImage
#
# Note: build for the OLDEST glibc you want to support — an AppImage built on
# Ubuntu 24.04 runs on >=24.04, not necessarily on older distros. Ubuntu-first
# is the target here; for max reach build inside an older manylinux container.

set -euo pipefail

PYVER="3.12"
[ "${1:-}" = "--py" ] && PYVER="${2:?--py needs a version}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIST="$ROOT/dist"
WORK="$DIST/appimage-build"
APPDIR="$WORK/Amagra.AppDir"
ARCH="$(uname -m)"

# Relocatable Python (manylinux2014, cp${ver}) from python-appimage releases. The exact
# patch version in the asset name changes over time, so resolve it from the release API
# rather than pinning a patch (which silently 404s on the next upstream bump).
PY_TAG="python${PYVER}"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"

# Optional GitHub auth to dodge the 60-req/hr unauthenticated API limit on shared CI IPs.
GH_API_AUTH=()
[ -n "${GITHUB_TOKEN:-}" ] && GH_API_AUTH=(-H "Authorization: Bearer ${GITHUB_TOKEN}")

say() { printf "\n\033[1;34m▶ %s\033[0m\n" "$*"; }

say "Clean workspace"
rm -rf "$WORK"; mkdir -p "$WORK" "$DIST"

say "Build the UI (vite)"
( cd "$ROOT/ui" && (npm ci || npm install) && npx vite build )
[ -f "$ROOT/ui/build/index.html" ] || { echo "UI build failed — no ui/build/index.html"; exit 1; }

say "Resolve relocatable Python base ($PY_TAG, manylinux2014/$ARCH)"
# Pick the manylinux2014 build (oldest glibc → widest reach) for this tag + arch.
PY_APPIMAGE_URL="$(
  curl -fsSL "${GH_API_AUTH[@]}" \
    "https://api.github.com/repos/niess/python-appimage/releases/tags/${PY_TAG}" \
  | grep -oE "https://[^\"]+manylinux2014_${ARCH}\.AppImage" | head -n1
)"
[ -n "$PY_APPIMAGE_URL" ] || {
  echo "Could not resolve a python-appimage base for ${PY_TAG}/${ARCH} (API rate-limited? set GITHUB_TOKEN)"; exit 1; }
echo "  → $PY_APPIMAGE_URL"

say "Fetch relocatable Python base"
PYBASE="$WORK/python-base.AppImage"
curl -fL "$PY_APPIMAGE_URL" -o "$PYBASE"
chmod +x "$PYBASE"
( cd "$WORK" && "$PYBASE" --appimage-extract >/dev/null )
mv "$WORK/squashfs-root" "$APPDIR"
# The base ships its own AppRun/.desktop/icon for plain Python — drop them, we provide our own.
rm -f "$APPDIR/AppRun" "$APPDIR"/*.desktop "$APPDIR"/*.png "$APPDIR/.DirIcon" 2>/dev/null || true

PYBIN="$APPDIR/opt/${PY_TAG}/bin/python${PYVER}"
[ -x "$PYBIN" ] || { echo "Bundled python not at $PYBIN — adjust PYVER/URL"; exit 1; }

say "Install Python dependencies into the bundle"
"$PYBIN" -m pip install --no-cache-dir --upgrade pip >/dev/null
"$PYBIN" -m pip install --no-cache-dir -r "$ROOT/requirements.txt"
# uvicorn is the server entrypoint AppRun calls; ensure it's present.
"$PYBIN" -m pip install --no-cache-dir "uvicorn[standard]" >/dev/null

say "Copy application code + built UI"
APP="$APPDIR/opt/amagra"
mkdir -p "$APP"
# Ship runtime code and the built UI; exclude dev/test/scratch and the payments
# feature is included only if it has been committed (kept generic via rsync excludes).
# NOTE: do not exclude 'evaluation' — it's a RUNTIME dependency (math_metrics is imported
# by training/, cognition/, memory_core/, decision/, infrastructure/, routes/). Only 'tests'
# is genuinely dev-only. The benchmark scripts under evaluation/ are small and harmless to ship.
rsync -a \
  --exclude '.git' --exclude '.github' --exclude 'node_modules' --exclude 'dist' \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.pytest_cache' \
  --exclude 'tests' --exclude 'logs' \
  --exclude 'ui/node_modules' --exclude 'ui/src' --exclude 'ui/public' \
  --exclude '*.db' --exclude '*.db-*' --exclude 'provider_config.json' \
  "$ROOT/"  "$APP/"
# Keep only the compiled UI under ui/ (drop sources copied above if any slipped through).
rm -rf "$APP/ui/src" "$APP/ui/public" "$APP/ui/node_modules"

say "Install launcher, desktop entry, and icon"
install -m 755 "$HERE/AppRun" "$APPDIR/AppRun"
install -m 644 "$HERE/amagra.desktop" "$APPDIR/amagra.desktop"
# Icon: prefer the app's 512px logo, fall back to the SVG.
if [ -f "$ROOT/ui/build/logo512.png" ]; then
    install -m 644 "$ROOT/ui/build/logo512.png" "$APPDIR/amagra.png"
elif [ -f "$ROOT/ui/build/icon.svg" ]; then
    install -m 644 "$ROOT/ui/build/icon.svg" "$APPDIR/amagra.svg"
fi
cp -f "$APPDIR/amagra.png" "$APPDIR/.DirIcon" 2>/dev/null || true

say "Fetch appimagetool"
TOOL="$WORK/appimagetool.AppImage"
curl -fL "$APPIMAGETOOL_URL" -o "$TOOL"
chmod +x "$TOOL"

say "Pack the AppImage"
OUT="$DIST/Amagra-${ARCH}.AppImage"
# ARCH must be exported for appimagetool's filename/runtime selection.
ARCH="$ARCH" "$TOOL" "$APPDIR" "$OUT" || {
    echo "appimagetool needs FUSE. On a host without FUSE, run: $TOOL --appimage-extract-and-run $APPDIR $OUT"
    exit 1
}

say "Done → $OUT"
ls -lh "$OUT"
