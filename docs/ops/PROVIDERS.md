# Choosing your model — local or API (and keeping Amagra light)

Amagra is a lightweight core with a **pluggable model backend** — like VS Code: the
editor stays small, and you add only the language support you need. Here the "language
support" is the model: run a small one locally for full privacy, or point Amagra at an
API so **nothing heavy runs on your device at all.**

One env var picks the backend. `LLM_PROVIDER` sets it for the agents; if unset it falls
back to `BRAIN_PROVIDER`, so a single switch moves both routing and answers together.

## The three backends

### 1. `ollama` — local & private (default)
Runs entirely on your hardware. Pick a model sized to your RAM.
```bash
# default
OLLAMA_MODEL=phi4-mini:latest          # ~4 GB RAM when answering
# lightweight (recommended on 8 GB laptops)
OLLAMA_MODEL=llama3.2:1b               # ~1.5 GB    — or qwen2.5:1.5b
```

### 2. `openai` — any OpenAI-compatible API (nothing heavy runs locally)
One setting (`OPENAI_BASE_URL`) switches vendor. The device only runs the ~300 MB app.
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Same adapter, different vendors — just change the base URL:
# Groq        OPENAI_BASE_URL=https://api.groq.com/openai/v1     OPENAI_MODEL=llama-3.1-8b-instant
# OpenRouter  OPENAI_BASE_URL=https://openrouter.ai/api/v1       OPENAI_MODEL=...
# Together    OPENAI_BASE_URL=https://api.together.xyz/v1
# LM Studio   OPENAI_BASE_URL=http://localhost:1234/v1           OPENAI_API_KEY=not-needed
# Remote Ollama (heavy box elsewhere on your LAN, light laptop here):
#             OPENAI_BASE_URL=http://192.168.1.50:11434/v1       OPENAI_API_KEY=not-needed
```

### 3. `anthropic` — Claude
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

## Footprint — what actually runs on your machine

| Mode | Local RAM | Privacy | Best for |
|---|---|---|---|
| `openai` / `anthropic` (API) | **~0.3–0.8 GB** | data goes to the API | 8 GB laptops; "use ≤50% of my machine" |
| `ollama` + 1–1.5B model | ~1.5 GB | 100% local | modest hardware, fully private |
| `ollama` + phi4-mini | ~4 GB | 100% local | 16 GB+ machines |

### The light recipe for an 8 GB laptop
Either point the brain at an API (above), **or** stay local but small:
```bash
OLLAMA_MODEL=llama3.2:1b
OLLAMA_KEEP_ALIVE=30s     # unload the model when idle → frees RAM while you browse
```
With idle-unload, Amagra sits at a few hundred MB when you're not actively chatting and
only spikes during a reply.

## Two honest caveats
- **API mode is not "100% local."** Your prompts go to whichever API you choose. Amagra is
  *private by default (local), flexible by choice (any model/API)* — you decide per the
  privacy/footprint trade-off. Routing stays local either way.
- **Embeddings stay local.** Memory/RAG uses `nomic-embed-text` (~0.5 GB) to keep the FAISS
  index consistent — switching the chat backend doesn't change retrieval. So even "API mode"
  keeps a small local embedder (or you re-index against an API embedder later).

## Resilience
If a non-default backend can't be built (missing package, bad key), Amagra logs it and
**falls back to local Ollama** rather than failing to start. So a typo in a key never
takes the app down.

## What's next (not yet shipped)
This ships as backend + config today. The first-run **onboarding picker** ("Local & private"
vs "Connect an API") and a settings UI are the next step — the registry/manifest layer
(`providers/`, `agents/manifests/`) is already built to drive a marketplace-style chooser.
