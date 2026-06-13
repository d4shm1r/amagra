.PHONY: dev stop benchmark routing-eval logs clean

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

# Routing accuracy benchmark (no Docker needed — runs against local Python env)
benchmark:
	PYTHONPATH=. python3 evaluation/ablation_eval.py

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
