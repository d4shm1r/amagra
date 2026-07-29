# How Amagra compares

The self-hosted AI workspace category is crowded — **Open WebUI**, **LibreChat**, and
**AnythingLLM** are the tools most people weigh Amagra against, and **OpenHands** is what
they mean when they ask for an autonomous agent. They're good projects. This page is the
honest head-to-head, including the places they're ahead of us today.

Every competitor cell below is sourced to that project's own documentation or license
file — links at the bottom. Every Amagra cell is sourced to a file in this repository.
Nothing here is asserted from memory or from a third-party blog post.

The short version: the others are excellent **chat front-ends** for your models, and
OpenHands is an excellent **autonomous coding agent**. Amagra is built around a different
question — *not "talk to a model" and not "go do this task alone," but "compare models and
inspect every decision."* If you only need a private chat UI, Open WebUI is more mature
than we are. If you need an agent to work unattended on a repo, use OpenHands. If you need
to see **where models disagree** and **replay why the system answered the way it did**,
that's the gap Amagra fills.

---

## 1. Chat workspace — the table stakes

| | **Amagra 1.8.0** | Open WebUI | LibreChat | AnythingLLM |
|---|:---:|:---:|:---:|:---:|
| Runs fully local / offline | ✅ | ✅ | ✅¹ | ✅ |
| Multi-provider (Claude · GPT · local) | ✅ | ✅ | ✅ | ✅ |
| RAG — upload & query your documents | ✅ | ✅ | ✅ | ✅ |
| Multi-model answers side by side, one prompt | ✅ | ✅ | ❌² | ❌² |
| **Agreement / divergence score across models** | ✅ | ❌³ | ❌ | ❌ |
| **Decision replay — reconstruct *why* it routed & answered** | ✅ | ❌⁴ | ❌ | ❌⁴ |
| Automatic model routing | ✅ | ❌ | ❌ | ✅⁵ |
| Specialist routing + self-critique (critic gate) | ✅ | ❌ | ❌ | ❌ |
| Persistent memory across sessions | ✅ | ✅ | ✅ | ✅ |
| Multi-user / RBAC | ❌⁶ | ✅ | ✅ | ✅ |
| License | MIT | BSD-3 + branding clause⁷ | MIT | MIT |

**The two bold rows are the reason Amagra exists.** Everything else is table stakes the
category shares — and on several of those rows a competitor is now ahead of us.

<sub>¹ LibreChat is cloud-key-first but self-hosts against Ollama via its OpenAI-compatible
endpoint. ² Not documented as a feature by either project. ³ Open WebUI ships a model
**arena with A/B testing and ELO leaderboards** — that ranks models by *human preference
over many prompts*; it does not score how much two answers to *one* prompt agree.
⁴ Open WebUI has OpenTelemetry traces and AnythingLLM has chat/event logs — both are
infrastructure-level logging, not reconstruction of a single answer's routing decision.
⁵ AnythingLLM's Model Router selects a model per message from **rules you write**
(keyword/token/time-based, or an LLM-classified plain-English rule); it is configuration,
not a scored decision, and exposes no per-decision explanation. ⁶ Amagra ships API-key auth
only — no user roles, no per-user isolation. A prior version of this page said RBAC would
"land in v1.6"; it did not, and we are now at 1.8.0. ⁷ Open WebUI's license forbids
removing its branding above 50 users/30 days without a commercial license.</sub>

---

## 2. Agent capability — the axis people ask about second

This is the "can it act on my machine?" question. Amagra is deliberately *not* the leader
here, and the table says so.

| | **Amagra 1.8.0** | Open WebUI | LibreChat | AnythingLLM | OpenHands |
|---|:---:|:---:|:---:|:---:|:---:|
| Code execution | ✅ | ✅ | ✅ | ✅ | ✅ |
| Filesystem access | ✅ user-account scope | via tools | via MCP | workspace | sandbox mount |
| Browser automation | ⚠️⁸ | ✅ | ✅ | ✅ | ✅ |
| Planning / multi-step | ✅ | ⚠️ | ✅ | ✅ | ✅ |
| **MCP support** | ❌ | ✅ | ✅ | ✅ | ✅ |
| Scheduled / recurring runs | ❌ | ✅⁹ | ❌ | ❌ | ❌ |
| Unattended long-horizon execution | ❌ | ❌ | ❌ | ❌ | ✅¹⁰ |
| Sandbox isolation | ⚠️ | ✅ | ✅ | ✅ | ✅ Docker/session |

<sub>⁸ [tools/browser.py](../../tools/browser.py) exists but is gated behind `AMAGRA_BROWSER=1`
and Playwright is **not** installed by default ([requirements.txt:73-76](../../requirements.txt#L73-L76)).
⁹ Open WebUI "Automations" schedules prompts on recurring schedules. ¹⁰ OpenHands runs
hours-long async tasks in a per-session Docker sandbox; its MIT core excludes SSO, RBAC,
and audit logs, which sit behind a Polyform-licensed enterprise tier.</sub>

**Read this table honestly:** MCP is now universal in this category and Amagra has none.
That is the single biggest capability gap on this page.

---

## 3. Where the competition is ahead

Stated plainly, because a comparison page that only flatters us is worth nothing:

- **Open WebUI** — more mature on nearly every axis except decision inspection: RBAC,
  SSO/OIDC/LDAP, SCIM, 13 vector DBs, 8 extraction engines, native MCP, scheduled
  automations, a plugin ecosystem, and horizontal scaling. If you want a polished
  self-hosted ChatGPT, it beats us today.
- **LibreChat** — a broader code interpreter (Python, Node, Go, C/C++, Java, PHP, Rust,
  Fortran), an agent marketplace, subagents, and Programmatic Tool Calling.
- **AnythingLLM** — cleaner document-workspace model, and its Model Router covers the
  common "cheap model for easy questions" case with no code.
- **OpenHands** — genuinely autonomous long-horizon execution. Nothing in Amagra
  competes with this, and the honest answer to "can Amagra work overnight on my repo?"
  is *no*.

---

## 4. When to pick which

- **Open WebUI** — the most polished self-hosted ChatGPT-style chat, mature multi-user,
  big plugin ecosystem. Check the branding clause before commercial deployment.
- **LibreChat** — multi-provider ChatGPT clone with broad model coverage, strong agent
  and code-execution story, team features.
- **AnythingLLM** — your center of gravity is document workspaces / RAG.
- **OpenHands** — you want an agent to autonomously write and debug code against a repo.
- **Amagra** — you want to **compare models on the same prompt, score how much they agree,
  and replay every routing and answer decision** — fully on hardware you control.

---

## Sources

Competitor claims verified **2026-07-28** against:

- Open WebUI — [features index](https://raw.githubusercontent.com/open-webui/docs/main/docs/features/index.mdx) · [LICENSE](https://raw.githubusercontent.com/open-webui/open-webui/main/LICENSE) · [MCP docs](https://docs.openwebui.com/features/extensibility/mcp/) · [multi-model chats](https://docs.openwebui.com/features/chat-conversations/chat-features/multi-model-chats/)
- LibreChat — [README](https://github.com/danny-avila/LibreChat) · [Agents](https://www.librechat.ai/docs/features/agents) · [Code Interpreter](https://www.librechat.ai/docs/features/code_interpreter) · [User Memory](https://www.librechat.ai/docs/features/memory)
- AnythingLLM — [docs home](https://docs.anythingllm.com/) · [Model Router overview](https://docs.anythingllm.com/model-router/overview) · [MCP compatibility](https://docs.anythingllm.com/mcp-compatibility/overview)
- OpenHands — [GitHub](https://github.com/OpenHands/OpenHands) · [docs](https://docs.openhands.dev/)

Amagra claims verified against this repository at 1.8.0:
[routes/consensus.py](../../routes/consensus.py) (agreement score, divergent/partial/consensus verdict) ·
[routes/snapshots.py](../../routes/snapshots.py) (`replay`, `fork_replay`, `diff_snapshots`) ·
[cognition/dual_trajectory.py](../../cognition/dual_trajectory.py) (critic gate) ·
[memory_core/backend.py](../../memory_core/backend.py) (FAISS-backed memory) ·
[tools/browser.py](../../tools/browser.py) (gated browser).

*These projects move fast. Spot something out of date or unfair?
[Open an issue](https://github.com/d4shm1r/amagra/issues) and we'll fix it. We'd rather be
accurate than flattering.*
