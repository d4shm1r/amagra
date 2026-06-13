#!/bin/bash
# start-agents.sh — launch Ollama + API + React UI
# Also callable via `ai-start` alias in ~/.bashrc

VENV="$HOME/.venvs/langgraph-env"
AI_DIR="$HOME/agentic-ai"
API_PORT=8000
UI_PORT=3000

ok()  { printf "  \033[32m✓\033[0m  %s\n" "$*"; }
run() { printf "  \033[34m→\033[0m  %s\n" "$*"; }
warn(){ printf "  \033[33m!\033[0m  %s\n" "$*"; }

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     Agentic AI — starting services   ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── 1. Ollama ────────────────────────────────────────────────
if pgrep -x ollama > /dev/null 2>&1; then
    ok "Ollama already running"
else
    run "Starting Ollama..."
    ollama serve > /tmp/ollama.log 2>&1 &
    sleep 2
    if pgrep -x ollama > /dev/null 2>&1; then
        ok "Ollama started"
    else
        warn "Ollama failed to start — check /tmp/ollama.log"
    fi
fi

# ── 2. API server ────────────────────────────────────────────
if lsof -Pi :$API_PORT -sTCP:LISTEN -t > /dev/null 2>&1; then
    ok "API already running on :$API_PORT"
else
    run "Starting API server on :$API_PORT..."
    gnome-terminal --title="API :$API_PORT" -- bash -c "
      source $VENV/bin/activate
      cd $AI_DIR
      uvicorn api:app --host 0.0.0.0 --port $API_PORT --reload
      exec bash" 2>/dev/null &
    sleep 1
    ok "API server launching in new terminal"
fi

# ── 3. React UI ──────────────────────────────────────────────
if lsof -Pi :$UI_PORT -sTCP:LISTEN -t > /dev/null 2>&1; then
    ok "UI already running on :$UI_PORT"
else
    run "Starting React UI on :$UI_PORT..."
    gnome-terminal --title="UI :$UI_PORT" -- bash -c "
      cd $AI_DIR/ui
      npm start
      exec bash" 2>/dev/null &
    ok "React UI launching (takes ~10s on first run)"
fi

sleep 2

# ── 4. Browser ───────────────────────────────────────────────
run "Opening browser..."
xdg-open "http://localhost:$UI_PORT" 2>/dev/null &

echo ""
echo "  Dashboard : http://localhost:$UI_PORT"
echo "  API       : http://localhost:$API_PORT"
echo "  API docs  : http://localhost:$API_PORT/docs"
echo ""
