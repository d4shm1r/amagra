#!/usr/bin/env bash
# Freeze the FastAPI backend into the `amagra-server` sidecar and stage it where
# electron-builder's extraResources picks it up (desktop/backend/).
#
# Assumes: Python deps installed (pip install -r requirements.txt pyinstaller)
# and the UI is built (ui/build exists — run `npm --prefix ui ci && npm --prefix
# ui run build` first, which the CI workflow does).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

if [ ! -d ui/build ]; then
  echo "error: ui/build missing — build the UI first (npm --prefix ui run build)" >&2
  exit 1
fi

echo "→ freezing amagra-server (PyInstaller)…"
python -m PyInstaller --clean --noconfirm packaging/amagra-server.spec

# Windows produces amagra-server.exe; unix produces amagra-server.
BIN="amagra-server"
[ -f "dist/amagra-server.exe" ] && BIN="amagra-server.exe"

mkdir -p desktop/backend
cp "dist/$BIN" "desktop/backend/$BIN"
chmod +x "desktop/backend/$BIN" 2>/dev/null || true
echo "✓ sidecar → desktop/backend/$BIN ($(du -h "desktop/backend/$BIN" | cut -f1))"
