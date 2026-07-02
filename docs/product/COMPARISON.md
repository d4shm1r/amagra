# How Amagra compares

The self-hosted AI workspace category is crowded — **Open WebUI**, **LibreChat**, and
**AnythingLLM** are the tools most people weigh Amagra against. They're good projects.
This page is the honest head-to-head, including the places they're ahead of us today.

The short version: the others are excellent **chat front-ends** for your models. Amagra
is built around a different question — *not "talk to a model" but "compare models and
inspect every decision."* If you only need a private chat UI, any of these will serve you.
If you need to see **where models disagree** and **replay why the system answered the way
it did**, that's the gap Amagra fills.

---

## Feature matrix

| | **Amagra** | Open WebUI | LibreChat | AnythingLLM |
|---|:---:|:---:|:---:|:---:|
| Runs fully local / offline | ✅ | ✅ | ✅¹ | ✅ |
| Multi-provider (Claude · GPT · local) | ✅ | ✅ | ✅ | ✅ |
| RAG — upload & query your documents | ✅ | ✅ | ✅ | ✅ |
| Multi-model answers side by side, one prompt | ✅ | ✅ | ⚠️ | ❌ |
| **Agreement / divergence score across models** | ✅ | ❌ | ❌ | ❌ |
| **Decision replay — inspect *why* it routed & answered** | ✅ | ❌ | ❌ | ❌ |
| Specialist routing + self-critique (critic gate) | ✅ | ❌ | ❌ | ⚠️² |
| Persistent, outcome-weighted memory across sessions | ✅ | ⚠️³ | ⚠️³ | ⚠️³ |
| Multi-user / RBAC | ⚠️⁴ | ✅ | ✅ | ✅ |
| License | MIT | — | MIT | MIT |

**The two rows in bold are the reason Amagra exists.** Everything else is table stakes the
whole category shares — and where a competitor is ahead (multi-user/RBAC), we say so.

<sub>¹ LibreChat is cloud-key-first but self-hosts against Ollama via its OpenAI-compatible
endpoint. ² AnythingLLM has an agent/skills system, but no per-response critic gate or
regenerate-on-low-score loop. ³ All three persist chat history and support RAG, but none
apply an outcome-weighted learning loop that nudges routing toward paths that scored well.
⁴ Amagra's workspaces + RBAC land in v1.6; today it ships API-key auth and a free tier, not
per-user roles.</sub>

---

## When to pick which

- **Open WebUI** — you want the most polished self-hosted ChatGPT-style chat for Ollama,
  with mature multi-user and a big plugin ecosystem.
- **LibreChat** — you want a multi-provider ChatGPT clone with broad model coverage and
  team features, primarily cloud-key driven.
- **AnythingLLM** — your center of gravity is **document workspaces / RAG**, and you want
  a clean per-workspace knowledge base.
- **Amagra** — you want to **compare models on the same prompt, score how much they agree,
  and replay every routing and answer decision** — fully on hardware you control.

---

*Best-effort snapshot as of v1.5.5 (2026-06). These projects move fast — spot something
out of date or unfair? [Open an issue](https://github.com/d4shm1r/amagra/issues) and we'll
fix it. We'd rather be accurate than flattering.*
