# Amagra — Positioning & Messaging

The single source of messaging truth. The README, the landing page, social posts,
release notes, and talks all derive from this — so the story stays coherent
everywhere. If a line here changes, the downstream copy follows.

---

## The one sentence

> **Amagra is the local AI workspace that lets you compare models and inspect every AI decision.**

Everything else — memory, agents, routing, critics, consensus, governance, the SDK —
*supports* this sentence; none of it competes for the headline. If a feature can't be
framed as *"this is how you compare models"* or *"this is how you inspect a decision,"*
it's a footnote in the pitch, not a lead.

---

## The three-layer story

The same arc in every channel — broad enough to click, deep enough to remember.

| Layer | Line | Job |
|---|---|---|
| **Hook** | "Run one prompt across GPT, Claude, Gemini and local models — at once." | Gets the click. Familiar, visual, instantly understood. |
| **Differentiator** | "See exactly *why* they differ, and *how* the system decided." | Separates Amagra from the dozen other comparison tools. |
| **Philosophy** | "AI should be observable, reproducible, and under your control." | The reason to star, share, and come back. |

The philosophy is the durable part. **Trust through observability** is the promise;
replay, divergence scores, and the inspector are the *evidence* that the promise is real.
Sell the worry removed, not the trace produced:

- *Why did it choose this agent?* → routing replay
- *Did it hallucinate?* → critic score + inspect
- *Why did Claude disagree with GPT?* → divergence view
- *Can I reproduce this tomorrow?* → it's local, logged, replayable

---

## Channel hooks

Always lead **comparison → glass box → local**. Title variants to test:

- **Show HN:** "Show HN: Amagra – a local AI workspace that shows you *why* it answered"
- **Show HN (alt):** "Show HN: Compare GPT, Claude, Gemini and local models on one prompt — and replay every decision"
- **X / LinkedIn:** "I spent months building an open-source AI workspace that runs one prompt across GPT, Claude, Gemini and Ollama side by side — scores how much they agree, and lets you replay *why* it picked what it did. Fully on your hardware. MIT."
- **r/LocalLLaMA:** "Built a self-hosted workspace that compares your local models against GPT/Claude/Gemini and shows the routing + agreement for each — no cloud, no telemetry"
- **Newsletter one-liner (hand writers their copy):** "A solo dev's open-source, fully-local AI workspace that compares frontier and local models side by side and makes every AI decision inspectable and replayable."

---

## The 10-second demo (the content engine)

These already *move* on screen — the unfair advantage most infra projects don't have.
Each is one reusable GIF:

1. **Divergence run** — paste a prompt, fire it at 4 models, the Aligned / Mixed / Divergent score resolves. *(the hook shot)*
2. **Decision replay** — click a past answer, watch the routing decision reconstruct. *(the differentiator shot)*
3. **Offline proof** — pull the network, it still answers locally. *(the philosophy shot)*

Three GIFs ≈ the entire pitch, no narration needed.

---

## The evidence backlog

Stop asking *"what feature next."* Start asking *"what evidence next."* Each item is
reusable across README, posts, docs, talks, and release notes — so it compounds.
Priority order:

1. The three demo GIFs above — highest leverage, reused everywhere.
2. A **head-to-head vs OpenWebUI / LibreChat / AnythingLLM** table — the comparison people already search for.
3. A **before / after prompt-debugging** example — one weak prompt, the divergence that exposes it, the fix.
4. A **5-minute walkthrough video** — becomes the README hero and the source material YouTube reviewers reuse.
5. The **routing benchmark / FINDINGS numbers**, packaged as a shareable card.
6. **One real user quote** after first use — the most persuasive asset, and the one you can't manufacture.

---

## Guardrails

- **Conversion before the push — but discovery is not one-shot.** Show HN, a later Reddit
  thread, a YouTube review, AI-newsletter mentions, and GitHub Trending are *separate*
  waves. The job isn't "don't blow our one chance" — it's to remove the first-run cliff
  *before* spending a wave, because each wave converts better only if the floor is solid.
  (This is why frictionless install/onboarding is distribution work, not feature work.)
- **Kill the category sprawl in copy.** Never list "chat client / agent framework / memory
  system / prompt debugger / observability platform" in one breath — it reads as unfocused
  to every audience at once. Pick the one sentence; let the rest be discovered *inside* the
  product.

---

## The strategic read

The constraint is **"almost nobody has seen it,"** not "they saw it and left." Those demand
opposite responses — and this is the better problem. So the next unit of work that moves
Amagra is **evidence + reach**, not another advanced feature no one has watched yet. The
payoff isn't only traffic: the first real cohort reveals which parts people instantly get,
which they ignore, and what makes them come back — feedback no analytics dashboard can give.
