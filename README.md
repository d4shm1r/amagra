<p align="center">
  <img src="docs/brand/amagra-logo.png" alt="Amagra" width="440" />
</p>

<p align="center">
  <a href="https://github.com/d4shm1r/amagra/releases"><img alt="Release v1.8.0" src="docs/brand/badge-release.svg" /></a>
  <a href="https://github.com/d4shm1r/amagra/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-C48808?style=flat-square&labelColor=2E2010" /></a>
  <a href="https://github.com/d4shm1r/amagra/stargazers"><img alt="Stars" src="https://badgen.net/github/stars/d4shm1r/amagra?color=C48808&labelColor=2E2010&icon=github" /></a>
  <img alt="Self-hosted" src="https://img.shields.io/badge/self--hosted-✓-C48808?style=flat-square&labelColor=2E2010" />
  <img alt="Tests: 986 passing" src="https://img.shields.io/badge/tests-986%20passing-C48808?style=flat-square&labelColor=2E2010" />
</p>

<p align="center">
  <b>The private AI workspace that shows its work.</b><br />
  Run one prompt across Claude, GPT, and your local models — see exactly where they
  disagree, on hardware you control.
</p>

<p align="center">
  Amagra runs entirely on your own machine. It remembers your work across sessions,
  routes each question to the right specialist, and records every routing decision —
  which agent, which memories, what confidence — so you can replay <i>why</i> each
  answer was produced. Nothing leaves your machine.
</p>

<p align="center">
  <img src="docs/screenshots/divergence.gif" width="90%" alt="Run one prompt across GPT, Claude, Gemini and local models — the agreement score resolves live" />
  <br />
  <sub><b>Divergence run</b> — one prompt, every model at once, agreement scored live. Spot a silent prompt failure before your users do.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/replay.gif" width="90%" alt="Click any past answer and replay why the system routed and answered the way it did" />
  <br />
  <sub><b>Decision replay</b> — click any past answer and reconstruct exactly why it was routed and answered that way: which agent, which memories, what confidence.</sub>
</p>

---

## What it does

- **Compare models on one prompt** — send the same prompt to Claude, GPT, and local
  models at once, read every answer side by side, and get an agreement score that tells
  you how much they actually agree. Catch silent prompt failures before your users do.
- **Stays private** — self-hosted via [Ollama](https://ollama.com) or your own cloud key.
  Nothing leaves your machine. MIT licensed.
- **Remembers your work** — context carries across sessions, so you stop re-explaining yourself.
- **Shows its reasoning** — replay any answer's decision: which agent was chosen, what
  memory it drew on, and how the critic scored it.

---

## Why Amagra

For one-off questions, plain Ollama or ChatGPT is fine. Amagra is for the work you come
back to for weeks — where you need the tool to remember it and show how it got there.

Six months in, that compounds: every new conversation starts with your accumulated
projects, decisions, and corrections already in context, and any past answer can be
traced back to what produced it. A chat tool's history scrolls away; a workspace compounds.

| | **Amagra** | Ollama / OpenWebUI | Cloud ChatGPT / Claude |
|---|:---:|:---:|:---:|
| Runs fully local & offline | ✅ | ✅ | ❌ |
| Memory across sessions | ✅ built-in | ⚠️ limited | ⚠️ cloud-stored |
| Every answer inspectable & replayable | ✅ | ❌ | ❌ |
| Compare models on one prompt | ✅ | ❌ | ❌ |
| Your data never leaves your machine | ✅ | ✅ | ❌ |

> Coming from **LangSmith**, **Promptfoo**, or **Helicone**? Amagra covers the same
> prompt-comparison ground, but local-first, in a GUI, with persistent memory — not a
> cloud dashboard or a config file. More in the [FAQ](#faq).

Weighing it against other self-hosted workspaces — **Open WebUI**, **LibreChat**,
**AnythingLLM**? They're great chat front-ends; Amagra adds the two things they don't:
a cross-model **agreement score** and **replay of why it answered**. Full honest
head-to-head in **[COMPARISON.md](docs/product/COMPARISON.md)**.

---

## Quick start

**Download & run (recommended — no Docker, Node, or Python):**

```bash
# Linux x86_64 — one file, double-click or run from a terminal:
curl -L -o Amagra.AppImage \
  https://github.com/d4shm1r/amagra/releases/latest/download/Amagra-x86_64.AppImage
chmod +x Amagra.AppImage
./Amagra.AppImage        # serves http://127.0.0.1:8000 and opens your browser
```

That's the whole install. Everything (interpreter, dependencies, UI) ships inside the file;
your data lives in `~/.local/share/amagra`. For **local** models, install
[Ollama](https://ollama.com) and Amagra's onboarding pulls what it needs. Prefer **cloud**
models? Skip Ollama entirely — add a key under **Settings → Model**.

<sub>Built on Ubuntu 22.04 (runs on 22.04+). macOS/Windows desktop builds are on the [roadmap](docs/ROADMAP.md).</sub>

<details>
<summary><b>Prefer Docker?</b></summary>

**Prebuilt image:**

```bash
docker pull d4shm1r/amagra:latest
docker run --rm -p 8000:8000 d4shm1r/amagra:latest   # open http://localhost:8000
```

For **local** model answers, point it at Ollama with
`--add-host=host.docker.internal:host-gateway -e OLLAMA_BASE_URL=http://host.docker.internal:11434`.
For **cloud** models, add your key (`-e BRAIN_PROVIDER=anthropic -e ANTHROPIC_API_KEY=...`).

**Full stack with Docker Compose (bundles Ollama):**

```bash
git clone https://github.com/d4shm1r/amagra && cd amagra
docker compose up
docker exec agentic-ollama ollama pull nomic-embed-text
docker exec agentic-ollama ollama pull phi4-mini
```

- UI: http://localhost:3000 · API docs: http://localhost:8000/docs
- No GPU? Remove the `deploy` block from `docker-compose.yml` — embeddings run on CPU.

</details>

Building the AppImage yourself, running from source, reproducing the routing benchmark, and
the full API are covered in **[packaging/README.md](packaging/README.md)**,
**[CONTRIBUTING.md](CONTRIBUTING.md)**, and the live docs at `/docs`.

---

## How it works

A fast signal classifier routes most questions instantly; only ambiguous ones go to the
LLM coordinator. Every step emits an event you can watch live.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/how-it-works-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="docs/brand/how-it-works-light.svg" />
    <img src="docs/brand/how-it-works-light.svg" alt="A question enters a signal classifier (~1 ms, domain and shape heuristics). Most questions take the direct route straight to a specialist agent; ambiguous ones go to the coordinator first. The specialist retrieves relevant memory, generates the answer, and a critic scores it — regenerating if the answer is weak. Every step emits an event." width="760" />
  </picture>
</p>

Memory lives in a local vector store with sub-millisecond warm retrieval, and a quiet
learning loop nudges routing toward the paths that score well — no model weights are touched.

The engineering detail — the LangGraph state machine, the routing accuracy and its honest
failure modes, the observability stack — lives in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**
and **[docs/records/FINDINGS.md](docs/records/FINDINGS.md)**.

---

## FAQ

**What is a prompt debugger?**
A way to see how one prompt behaves across different models, side by side, so you can find
where it silently breaks or drifts. Amagra runs your prompt across Claude, GPT, and local
Ollama models at once and scores how much they agree.

**Can I run it fully offline?**
Yes — self-hosted on your own hardware via Ollama, no account or internet needed for local
models. Cloud models work too if you add your own key, but nothing is required to leave your machine.

**How is it different from LangSmith or Promptfoo?**
Those are cloud-hosted or CLI-driven eval tools. Amagra is a self-hosted GUI workspace that
compares models, scores their divergence, and keeps persistent project memory — fully private.

**Is it free?**
Yes — self-hosting is free and MIT licensed, always. A managed free tier (100 requests/day,
no card) and paid hosting/enterprise tiers are also available.

---

## Contributing & security

Issues and PRs welcome — **[CONTRIBUTING.md](CONTRIBUTING.md)** covers setup, conventions, and
how to add a new agent (two files). Please review the [Code of Conduct](CODE_OF_CONDUCT.md), and
report vulnerabilities via **[SECURITY.md](SECURITY.md)** rather than a public issue. Before
exposing Amagra beyond `localhost`, read the security notes in SECURITY.md — the defaults assume
a trusted single user.

---

## License

MIT © 2026 — self-hosting is free and always will be.
Managed hosting, enterprise audit trails, and domain agent packs are paid tiers: [amagra.dev](https://amagra.dev)
