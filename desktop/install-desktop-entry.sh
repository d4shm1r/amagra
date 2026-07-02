#!/usr/bin/env bash
# Install (or refresh) the AMAGRA launcher entry for the current user.
#
# Generates ~/.local/share/applications/amagra.desktop from THIS checkout's
# path — nothing is hardcoded, so it works on any machine and survives moving
# the repo (just re-run it). Also installs the app icon into the hicolor theme
# so `Icon=amagra` resolves in every desktop environment.
#
#   bash desktop/install-desktop-entry.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor"

mkdir -p "$APPS_DIR" "$ICON_DIR/512x512/apps" "$ICON_DIR/256x256/apps" "$ICON_DIR/128x128/apps" "$ICON_DIR/scalable/apps"

# Icons (512 source; smaller sizes fall back to it if ImageMagick is absent)
cp "$REPO_DIR/ui/public/logo512.png" "$ICON_DIR/512x512/apps/amagra.png"
if command -v convert >/dev/null 2>&1; then
  convert "$REPO_DIR/ui/public/logo512.png" -resize 256x256 "$ICON_DIR/256x256/apps/amagra.png"
  convert "$REPO_DIR/ui/public/logo512.png" -resize 128x128 "$ICON_DIR/128x128/apps/amagra.png"
else
  cp "$REPO_DIR/ui/public/logo512.png" "$ICON_DIR/256x256/apps/amagra.png"
  cp "$REPO_DIR/ui/public/logo512.png" "$ICON_DIR/128x128/apps/amagra.png"
fi
cp "$REPO_DIR/ui/public/icon.svg" "$ICON_DIR/scalable/apps/amagra.svg"

cat > "$APPS_DIR/amagra.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AMAGRA
GenericName=Local AI Assistant
Comment=Private, offline-first agentic AI — native desktop app
Exec=bash -lc "env -u ELECTRON_RUN_AS_NODE $REPO_DIR/desktop/node_modules/.bin/electron $REPO_DIR/desktop --no-sandbox"
Icon=amagra
Terminal=false
Categories=Development;
Keywords=AI;assistant;agent;LLM;local;offline;amagra;
StartupNotify=true
StartupWMClass=amagra-desktop
Actions=Stop;

[Desktop Action Stop]
Name=Stop AMAGRA services
Exec=bash -lc "$REPO_DIR/start-agents.sh stop"
EOF

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" || true
command -v gtk-update-icon-cache  >/dev/null 2>&1 && gtk-update-icon-cache -q "$ICON_DIR" || true

echo "✓ Installed $APPS_DIR/amagra.desktop (Exec → $REPO_DIR)"
