# Amagra

<p align="center">
  <a href="https://github.com/d4shm1r/amagra/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/d4shm1r/amagra?color=blue" /></a>
  <a href="https://github.com/d4shm1r/amagra/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/d4shm1r/amagra?style=flat&logo=github" /></a>
  <a href="https://github.com/d4shm1r/amagra/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/d4shm1r/amagra" /></a>
  <a href="https://github.com/d4shm1r/amagra/issues"><img alt="Open issues" src="https://img.shields.io/github/issues/d4shm1r/amagra" /></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white" />
  <img alt="Self-hosted" src="https://img.shields.io/badge/self--hosted-✓-success" />
</p>

<p align="center">
  <b>A self-hosted, local-first AI assistant with persistent memory — and it shows its work. Runs entirely on your own hardware via <a href="https://ollama.com">Ollama</a>.</b>
</p>

### The AI you can trust with long-term work.

It remembers your projects across sessions, and **every routing decision is logged and replayable** — so you can see exactly why it answered the way it did. Nothing is a black box, and nothing leaves your hardware.

![Chat](docs/screenshots/chat.png)

<p align="center">
  <img src="docs/screenshots/library.png" width="49%" alt="Library — persistent documents Amagra has read" />
  <img src="docs/screenshots/inspect.png" width="49%" alt="Inspect — decisions, runs, and context at a glance" />
</p>

---

## What you get

- **Nothing is hidden** — every answer can be inspected, replayed, and understood. No black box.
- **It remembers your work** — context carries across sessions, so you stop re-explaining yourself.
- **Fast when the answer is obvious, careful when it isn't** — simple questions return at once; hard ones get more thought.
- **Specialists handle the work they understand best** — the right expert answers each question, automatically.
- **Pick up where you left off** — every conversation keeps its context; switch projects without losing your place.
- **Yours to run** — MIT licensed, self-hosted on your own machine. Nothing leaves your hardware.

---

## Why not just use Ollama, OpenWebUI, or ChatGPT?

You can — and for one-off questions you probably should. Amagra is for the times you
come back to the *same* work for weeks and need the tool to remember it and show its
reasoning. The honest trade-offs:

| | **Amagra** | Plain Ollama / OpenWebUI | Cloud ChatGPT / Claude |
|---|:---:|:---:|:---:|
| Runs fully local & offline | ✅ | ✅ | ❌ |
| Persistent memory across sessions | ✅ built-in | ⚠️ manual / limited | ⚠️ cloud-stored |
| Every answer inspectable & replayable | ✅ | ❌ | ❌ |
| Routes each question to a specialist | ✅ | ❌ | ❌ |
| Your data never leaves your machine | ✅ | ✅ | ❌ |
| Frontier-grade model quality | ❌ your local model | ❌ | ✅ |
| Zero setup | ❌ | ⚠️ | ✅ |

If you want the strongest possible single answer right now, use a frontier cloud model.
If you want a private workspace that *accumulates* context and never asks you to trust a
black box, that's the gap Amagra fills.

---

## Under the hood

The experience is the point. The numbers are here if you want them.

| Metric | Value | Notes |
|---|---|---|
| Routing | keyword-first, then LLM | Every decision is logged and replayable — see accuracy & method in [docs/FINDINGS.md](docs/FINDINGS.md) |
| Memory retrieval (FAISS, warm) | **< 1 ms** | LRU cache hit |
| Memory retrieval (cold embed) | ~60–80 ms | nomic-embed-text via Ollama |
| Skill graph coverage | **21 nodes** | Phrase-weighted disambiguation across all 10 agents |
| Test suite | **766 passing** | ruff + pytest + Docker build on every push and PR |
| Free tier | **100 req / day** | No card required — `POST /register/free` |

> Routing quality is measured honestly, not marketed: there's a wide gap between a self-authored curated set and a held-out adversarial one, and live telemetry (`GET /telemetry/routing`) tracks the real thing. The numbers, the method, the confidence intervals, and the known failure modes all live in [docs/FINDINGS.md](docs/FINDINGS.md) — including why we don't quote a single headline accuracy figure.

---

## Quick start

**Docker (recommended):**

```bash
git clone https://github.com/d4shm1r/amagra
cd amagra
docker compose up
```

Pull the models on first run:

```bash
docker exec agentic-ollama ollama pull nomic-embed-text
docker exec agentic-ollama ollama pull phi4-mini
```

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

> **No GPU?** Remove the `deploy` section from `docker-compose.yml`. Embedding runs on CPU (~2–3s cold, < 1ms warm via LRU).

**Without Docker:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull nomic-embed-text && ollama pull phi4-mini
uvicorn api:app --host 0.0.0.0 --port 8000 &
cd ui && npm install && npm start
```

Reproduce the routing benchmark (no Ollama required):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make benchmark
```

---

## Architecture

> **Evaluating the engineering?** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) maps every claim below to the file that implements it — the LangGraph `StateGraph`, the signal-first router, the verify/reflect/retry loop, and the observability stack.

```
User query
    │
    ▼
QuerySignal  (~1 ms — domain, shape, verbosity heuristics — high-confidence direct route)
    │
    ├─► Direct route  (high-confidence domain match)
    │
    └─► CoreBrain     (LLM reasoning — ambiguous queries only)
            │
            └─► Coordinator (LangGraph)
                    │
                    ├─► Risk gate  (reflect_level: none / light / full)
                    │
                    └─► Specialist agent
                            │
                            ├─► Skill graph disambiguation (21 nodes)
                            ├─► FAISS memory retrieval (< 1 ms warm)
                            ├─► Ollama LLM inference
                            ├─► Critic gate  (score ≥ 0.70 or regenerate)
                            └─► Step verifier  (pass / fail → event_bus)
```

**Memory pipeline:** SQLite → auto-promote to FAISS at 800 entries → cosine similarity → outcome-weighted quality scoring → LRU cache

**Learning loop:** critic gate scores (0.0–1.0) feed `apply_learning_update()` after each response. Scores are stored in SQLite alongside the query, agent, and routing path. The coordinator uses these to adjust per-agent selection confidence on similar future queries — high-scoring paths are preferred, low-scoring paths trigger retry or escalation. Model parameters are not modified; only coordinator-level routing and retry weights change.

---

## Routing in practice

QuerySignal classifies by domain signal — keyword patterns, code syntax, question shape — not intent inference. Below are representative examples from the 138-query evaluation set:

| Query | Routed to | Primary signal |
|---|---|---|
| "Write a pandas groupby with multi-level index" | Data | `pandas`, dataframe vocabulary |
| "Configure OSPF on a Cisco switch" | Networking | protocol name + network device |
| "Fix this LINQ query throwing NullReferenceException" | .NET | `LINQ`, C# exception |
| "Make this explanation shorter" | Terse | brevity instruction |
| "Debug my Dockerfile — build fails at RUN pip install" | DevOps | `Dockerfile`, build toolchain |
| "Explain gradient descent intuitively" | AI/ML | ML terminology |
| "My SSH tunnel keeps dropping after 60s" | Networking | SSH, connectivity timeout |
| "Summarise this RFC for a non-technical audience" | Writer | audience framing |
| "Plot a confusion matrix from sklearn predictions" | Data | visualization + ML library |
| "Write a Python async context manager" | Python | language + stdlib pattern |

Curated eval result: **137 correct, 1 incorrect** (138 queries).

The one miss: *"Write a script to analyse server logs"* routed to Data instead of DevOps — scripting-for-analysis vs scripting-for-operations is a known ambiguity at the boundary between those two agents.

### Known routing overlaps

Three domain pairs produce the most misroutes in practice:

- **Python ↔ Data** — data manipulation queries without an explicit library reference can land on either
- **DevOps ↔ Networking** — infrastructure questions that span server config and network topology
- **Writer ↔ Knowledge** — documentation requests sometimes select Writer when the user wants a factual lookup

These are visible in live telemetry (`GET /telemetry/routing`). The curated eval deliberately includes overlap cases.

---

## API

```bash
# Ask a question (auto-routed)
curl http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Write a Python async context manager"}'

# Continue a conversation thread
curl http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Add error handling to that", "thread_id": "your-thread-id"}'

# Force a specific agent
curl http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "...", "force_agent": "python_dev"}'

# List conversation threads
curl http://localhost:8000/threads

# Memory health
curl http://localhost:8000/memory/stats

# Live routing telemetry
curl http://localhost:8000/telemetry/routing

# Active execution plan (DAG)
curl http://localhost:8000/plan/graph

# Recent events
curl http://localhost:8000/cos/events?n=20
```

Full API docs at `http://localhost:8000/docs`.

---

## Observability — see and replay everything

The reason to choose Amagra over a plain local chat UI: agent behaviour is observable and replayable at every step, not a black box. These are concrete components, not a framework — each emits to a UI panel you can browse live.

| Component | What it does |
|---|---|
| `event_bus` | Typed pub/sub — every routing decision, plan step, verification, and memory retrieval emits an event |
| `world_model` | Session-scoped working context — tracks current goal, known issues, named entities, and completed tasks for the active request; reset between sessions |
| `cognitive_state` | Request lifecycle — begin → route → execute → reflect → end, tracked as structured data |
| `metrics_engine` | Computes four live counters from session events: Reliability (error rate), Intelligence (routing precision), Adaptation (learning updates applied), Productivity (tasks completed per session) |
| `skill_graph` | 21-node skill disambiguation layer, phrase-weighted scoring, resolves edge-case routing ambiguity |
| `step_verifier` | Scores each agent response after execution — pass/retry/abort recommendation to the coordinator |
| `suggestion_engine` | Reads world model issues and failed events, generates proactive action suggestions in the UI |

All of this is browsable in real time from the UI: Event Log, Plan Graph, Metrics Dashboard, Risk Observatory, Memory Browser, Decision Replay.

---

## Auth

Auth is **disabled by default** for local development. Enable it:

```bash
REQUIRE_AUTH=1 ADMIN_TOKEN=your-secret uvicorn api:app ...
```

**Self-service free tier** (100 req/day, no card):

```bash
curl -X POST http://localhost:8000/register/free \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "name": "Your Name"}'
```

**Create a managed API key** (admin):

```bash
curl -X POST http://localhost:8000/admin/keys \
  -H "Authorization: Bearer your-secret" \
  -H "Content-Type: application/json" \
  -d '{"owner": "alice@example.com", "tier": "developer"}'
```

Rate limits are returned on every authenticated response as `X-RateLimit-Limit`, `X-RateLimit-Used`, `X-RateLimit-Remaining`.

---

## Known limitations

- **Streaming available** — use `POST /ask/stream` for SSE streaming responses. When `ANTHROPIC_API_KEY` is set, tokens stream directly from Claude; without it, the response arrives as a single chunk. The default `POST /ask` remains non-streaming.
- **Tool use** — file access, sandboxed code execution, and web search ship driven by the in-agent tool loop at `POST /tools/run`. As of `v1.1.1` that loop is also wired into the default specialist-agent chat flow (`tools/agent_runtime.py`), **config-gated behind `AMAGRA_AGENT_TOOLS=1`** (off by default until phi4-mini's tool-JSON reliability is validated; falls back to a plain invoke).
- **Default inference** — Ollama (local). Cloud provider support (Anthropic, OpenAI, Gemini) via the multi-provider `/ask` path is available; full provider-abstraction UI is committed for `v1.2`.
- **SQLite sprawl** — internal data is split across multiple SQLite files; cross-DB atomicity is not guaranteed. Every path resolves through one registry (`infrastructure/db.py`), and setting `AMAGRA_DB=/path/to/amagra.db` collapses all logical databases into a single file. The default is still separate files (no migration required). To switch to one file, consolidate existing data once and flip the env var:

  ```bash
  # Preview (writes nothing):
  python scripts/migrate_to_single_db.py --target amagra.db --dry-run
  # Consolidate, then archive the old files so they can't diverge:
  python scripts/migrate_to_single_db.py --target amagra.db --apply --archive
  export AMAGRA_DB=$(pwd)/amagra.db   # or set it in docker-compose.yml
  ```

  Migration preserves every table's `rowid` (the FAISS index is keyed on `memories.id`) and copies the FAISS sidecar; on first start in single-file mode the index rebuilds itself if the sidecar isn't found. Single-file mode simplifies backups and container volumes at the cost of one shared writer lock. Making it the default is planned for a later release.
- **Benchmark independence** — routing accuracy is measured on a curated eval set, not production data. See [Routing in practice](#routing-in-practice) for the raw numbers and known failure modes. Independent production telemetry is tracked via `GET /telemetry/routing`.

---

## Roadmap

**v1.0.0 is the first public release.** From here, Amagra evolves toward a provider-agnostic runtime where models, embeddings, and agents can be added without changing the core memory, routing, or observability systems. Commitments are published in the app under **Promises** — explicit delivery targets, not a wishlist. The full plan lives in [docs/ROADMAP.md](docs/ROADMAP.md).

### v1.0.1 — Launch polish · Q3 2026

Post-debut hardening: tests to ~60% coverage, in-product onboarding (Ollama detection, model-pull progress, guided first prompt), Vite migration to retire CRA, single consolidated `amagra.db`, and public launch (Show HN, r/LocalLLaMA, Docker Hub, Homebrew).

### v1.1 — Tool-using agents · Q3 2026 *(✅ shipped v1.1.0)*

Agents gain real capabilities, not just text. **Shipped:** thread management (rename, fork, archive); memory import/export (JSON/Markdown); the jailed file/folder tool (`GET /workspace/read|list|search`, confined via `Path.resolve().is_relative_to(root)`); sandboxed code execution (`POST /sandbox/run`, `setrlimit` + isolated `python3 -I`, opt-in via `AMAGRA_SANDBOX=1`); chat stop/regenerate/edit affordances; live web search (`GET /search/web`, default self-hosted SearXNG, opt-in Brave/Tavily); and a structured tool loop (`POST /tools/run`) that lets the model call the file/sandbox/web tools mid-reasoning. **Remaining polish:** auto-invoking the tool loop inside the default specialist-agent chat flow.

### v1.2 — Multi-provider models & workspaces · Q4 2026

Add support for additional inference backends:

| Provider | Type |
|---|---|
| Ollama | Local inference (default) |
| Anthropic | Cloud inference |
| OpenAI | Cloud inference |
| Gemini | Cloud inference |
| OpenAI-compatible endpoints | Self-hosted models (vLLM, LM Studio, etc.) |

Users select inference model per workspace. Routing, memory, and telemetry are unaffected — the provider swap happens below the coordinator. Also: workspaces (isolated projects per user), RBAC, and a custom agent builder (name, system prompt, keywords via admin UI — no code deploy).

### v1.3 — Team memory & governance · Q1 2027

Shared team memory (per-workspace FAISS index), admin console, encrypted cross-machine sync, SSO/SAML, audit-log export + Chain-of-Authorization trail, configurable retention, and an air-gapped installer.

### v1.4 — Unified workspace UI · Q1 2027

The dashboard's 5 surfaces and ~26 views consolidate into 6 coherent views with observability as the hero screen — a reorganization, not a deletion. Includes a Monaco code pane (read + diff + apply). Orthogonal to the capability work above, so it ships on its own track.

### v2.0 — Agent registry & SDK · 2027

A supported interface for building custom agents. Agents declare a manifest:

```yaml
id: security_auditor
name: Security Auditor
skills: [security, pentesting, compliance]
keywords: [cve, owasp, threat model, audit]
routing_examples:
  - "Review this code for injection vulnerabilities"
  - "Write a threat model for this API"
confidence_threshold: 0.75
capabilities: [memory, coding]
```

The runtime automatically incorporates registered agents into routing, telemetry, and observability — custom agents get memory, critic gate, and step verification for free. Agents become portable artifacts (export/import as YAML or ZIP), served from a curated registry tiered by trust:

| Tier | Description |
|---|---|
| Official | Maintained by Amagra, benchmarked, supported |
| Verified community | Third-party, reviewed, clearly labelled |
| Local | User-created, no quality guarantees |

Amagra remains responsible for runtime infrastructure. Agent capabilities become extensible without compromising runtime quality.

---

> The goal is for every new model and every new agent to increase the value of Amagra's runtime — not compete with it. The memory, routing, and observability layers are the product. Models and agents are adapters.

---

## Contributing

Issues and PRs welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup, conventions, and how to add a new agent (it takes changes to exactly two files). Please review the [Code of Conduct](CODE_OF_CONDUCT.md), and report security issues via [SECURITY.md](SECURITY.md) rather than a public issue.

```bash
ruff check .                                  # lint
PYTHONPATH=. python3 -m pytest tests/ -q      # 766 tests
PYTHONPATH=. python3 evaluation/ablation_eval.py   # routing benchmark
```

---

## Star History

<a href="https://star-history.com/#d4shm1r/amagra&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=d4shm1r/amagra&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=d4shm1r/amagra&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=d4shm1r/amagra&type=Date" />
  </picture>
</a>

---

## License

MIT © 2026 — self-hosting is free and always will be.

Managed hosting, enterprise CoA audit trail, and domain agent packs are paid tiers: [amagra.dev](https://amagra.dev)
