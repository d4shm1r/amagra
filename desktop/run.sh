#!/usr/bin/env bash
# Launch the AMAGRA desktop app (Electron).
#
# The window itself boots the backend (reuses a healthy server on :8000 if one is
# already up, e.g. `ai-start`, otherwise spawns the dev venv) — so this is all you
# need to open the app.
#
#   bash desktop/run.sh          # from the repo root
#   ./run.sh                     # from inside desktop/
#
# `env -u ELECTRON_RUN_AS_NODE` is defensive: some sandboxes export that var, which
# would make Electron run as plain Node. A normal terminal doesn't need it.
cd "$(dirname "$0")" || exit 1
exec env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/electron . --no-sandbox "$@"
