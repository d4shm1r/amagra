.PHONY: dev stop test benchmark benchmark-memory routing-eval diagram logs clean

# Python interpreter for local (non-Docker) targets. Override for your venv:
#   make test PYTHON=~/.venvs/langgraph-env/bin/python
PYTHON ?= python3

# Start the full stack (API + UI + Ollama)
dev:
	docker compose up

# Start in background
start:
	docker compose up -d

stop:
	docker compose down

# Pull required models (run once after first docker compose up)
models:
	docker exec agentic-ollama ollama pull nomic-embed-text
	docker exec agentic-ollama ollama pull phi4-mini

# Full test suite (no Docker needed — runs against local Python env)
test:
	PYTHONPATH=. $(PYTHON) -m pytest tests/ -q

# Routing accuracy benchmark (no Docker needed — runs against local Python env)
benchmark:
	PYTHONPATH=. $(PYTHON) workbench/evaluation/ablation_eval.py

# Memory recall release gate — deterministic, no Ollama. Writes the gate verdict
# that synthesis features (e.g. "Explain this project") check before running.
# Exit code 0 = PASS (synthesis allowed), 1 = FAIL (stays gated).
benchmark-memory:
	PYTHONPATH=. $(PYTHON) workbench/evaluation/memory_recall_bench.py

# Regenerate the README "How it works" diagram (light + dark SVG).
# Run after changing the routing flow so the picture stops lying.
diagram:
	$(PYTHON) workbench/brand/gen_architecture_diagram.py

# Tail API logs
logs:
	docker compose logs -f api

# Remove generated runtime files (databases, logs) — does not touch source
clean:
	find logs/ -name "*.db" -delete 2>/dev/null || true
	find logs/ -name "*.json" -delete 2>/dev/null || true
	find memory/ -name "*.db" -delete 2>/dev/null || true
	rm -f tasks.db
	@echo "Runtime state cleared. Databases will be recreated on next start."
