#!/bin/bash
# start-agents.sh — launch / stop Ollama + API + React UI
# Usage:  ai-start [start|stop|status|logs]   (default: start)
#
# No `source` needed: we call the venv's binaries directly
# ($VENV/bin/uvicorn already runs under the venv's Python via its shebang).
# Everything runs in the background; logs go to logs/, PIDs to logs/*.pid.

set -uo pipefail

VENV="$HOME/.venvs/langgraph-env"
AI_DIR="$HOME/agentic-ai"
API_PORT=8000
UI_PORT=3000
LOG_DIR="$AI_DIR/logs"

# Single-file DB mode (optional): export AMAGRA_DB before running, e.g.
#   export AMAGRA_DB=$AI_DIR/amagra.db
# Migrate existing data first:
#   python scripts/migrate_to_single_db.py --target "$AMAGRA_DB" --apply
export AMAGRA_DB="${AMAGRA_DB:-}"

mkdir -p "$LOG_DIR"

ok()   { printf "  \033[32m✓\033[0m  %s\n" "$*"; }
run()  { printf "  \033[34m→\033[0m  %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m  %s\n" "$*"; }

port_up() { lsof -Pi :"$1" -sTCP:LISTEN -t >/dev/null 2>&1; }

# ── start ────────────────────────────────────────────────────
cmd_start() {
  echo ""
  echo "  ╔══════════════════════════════════════╗"
  echo "  ║     Agentic AI — starting services   ║"
  echo "  ╚══════════════════════════════════════╝"
  echo ""

  # 1. Ollama
  if pgrep -x ollama >/dev/null 2>&1; then
    ok "Ollama already running"
  else
    run "Starting Ollama..."
    nohup ollama serve >"$LOG_DIR/ollama.log" 2>&1 &
    echo $! >"$LOG_DIR/ollama.pid"
    sleep 2
    pgrep -x ollama >/dev/null 2>&1 && ok "Ollama started" \
      || warn "Ollama failed — see logs/ollama.log"
  fi

  # 2. API server (venv uvicorn directly — no activate)
  if port_up "$API_PORT"; then
    ok "API already running on :$API_PORT"
  else
    run "Starting API on :$API_PORT..."
    ( cd "$AI_DIR" && AMAGRA_DB="$AMAGRA_DB" \
        nohup "$VENV/bin/python" -m uvicorn api:app --host 0.0.0.0 --port "$API_PORT" \
        >"$LOG_DIR/api.log" 2>&1 & echo $! >"$LOG_DIR/api.pid" )
    ok "API launching (logs/api.log)"
  fi

  # 3. React UI
  if port_up "$UI_PORT"; then
    ok "UI already running on :$UI_PORT"
  else
    run "Starting UI on :$UI_PORT..."
    ( cd "$AI_DIR/ui" && BROWSER=none \
        nohup npm start >"$LOG_DIR/ui.log" 2>&1 & echo $! >"$LOG_DIR/ui.pid" )
    ok "UI launching (logs/ui.log, ~10s first run)"
  fi

  # 4. Front-end window — wait for the UI port, then open once.
  #    Default: the native AMAGRA desktop window (Electron, dev/HMR mode → it
  #    loads the :3000 Vite server, so UI edits hot-reload live).
  #    Override with AMAGRA_OPEN=browser (open a browser tab) or =none.
  run "Waiting for UI..."
  for _ in $(seq 1 30); do port_up "$UI_PORT" && break; sleep 1; done

  local open="${AMAGRA_OPEN:-desktop}"
  if [[ "$open" == "desktop" && ! -x "$AI_DIR/desktop/node_modules/.bin/electron" ]]; then
    warn "desktop deps missing (run: cd desktop && npm install) — opening browser instead"
    open="browser"
  fi
  case "$open" in
    desktop)
      if port_up "$UI_PORT"; then
        run "Opening AMAGRA desktop window..."
        # setsid: run Electron in its own session so a hangup to this script's
        #   process group can't reach it (Electron quits on SIGHUP; nohup only
        #   shields the wrapper, not the Electron grandchild).
        # run.sh (not `npm start`): it unsets ELECTRON_RUN_AS_NODE and passes
        #   --no-sandbox — required here because the npm-installed chrome-sandbox
        #   isn't setuid root and Ubuntu's apparmor_restrict_unprivileged_userns=1
        #   blocks the fallback, so a bare `electron .` aborts with SIGTRAP.
        ( cd "$AI_DIR/desktop" && setsid env AMAGRA_DEV=1 \
            bash run.sh >"$LOG_DIR/desktop.log" 2>&1 & echo $! >"$LOG_DIR/desktop.pid" )
        ok "Desktop launching (logs/desktop.log)"
      fi ;;
    browser)
      port_up "$UI_PORT" && xdg-open "http://localhost:$UI_PORT" >/dev/null 2>&1 & ;;
    none) : ;;
  esac

  echo ""
  echo "  Desktop   : AMAGRA window (AMAGRA_OPEN=browser for a tab instead)"
  echo "  Dashboard : http://localhost:$UI_PORT"
  echo "  API       : http://localhost:$API_PORT"
  echo "  API docs  : http://localhost:$API_PORT/docs"
  echo "  Logs      : ai-start logs   (or tail logs/api.log)"
  echo ""
}

# ── stop ─────────────────────────────────────────────────────
kill_pidfile() {  # $1=name $2=pidfile
  local f="$2"
  if [[ -f "$f" ]] && kill "$(cat "$f")" 2>/dev/null; then
    ok "$1 stopped"
  else
    warn "$1 not tracked — trying pattern match"
  fi
  rm -f "$f"
}

cmd_stop() {
  echo ""
  kill_pidfile "Desktop" "$LOG_DIR/desktop.pid"
  kill_pidfile "UI"  "$LOG_DIR/ui.pid"
  kill_pidfile "API" "$LOG_DIR/api.pid"
  # Fallbacks in case PID files are stale (e.g. reload spawned children)
  pkill -f "desktop/node_modules/electron" 2>/dev/null
  pkill -f "uvicorn api:app"          2>/dev/null
  pkill -f "$AI_DIR/ui/node_modules"  2>/dev/null  # vite dev server + workers
  # Leave Ollama running by default (shared, slow to reload).
  # Stop it too with:  ai-start stop --all
  if [[ "${1:-}" == "--all" ]]; then
    kill_pidfile "Ollama" "$LOG_DIR/ollama.pid"
    pkill -x ollama 2>/dev/null
  fi
  echo ""
}

# ── status / logs ────────────────────────────────────────────
cmd_status() {
  echo ""
  pgrep -x ollama       >/dev/null 2>&1 && ok "Ollama  running" || warn "Ollama  down"
  port_up "$API_PORT"   && ok "API     :$API_PORT" || warn "API     down"
  port_up "$UI_PORT"    && ok "UI      :$UI_PORT"  || warn "UI      down"
  pgrep -f "desktop/node_modules/electron" >/dev/null 2>&1 \
    && ok "Desktop running" || warn "Desktop down"
  echo ""
}

cmd_logs() { tail -f "$LOG_DIR/api.log" "$LOG_DIR/ui.log"; }

case "${1:-start}" in
  start)  cmd_start ;;
  stop)   cmd_stop "${2:-}" ;;
  status) cmd_status ;;
  logs)   cmd_logs ;;
  *)      echo "usage: ai-start [start|stop|status|logs]" ;;
esac
