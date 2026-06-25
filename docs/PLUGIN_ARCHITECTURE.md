# Amagra — Plugin Architecture (declared philosophy)

> **Thesis:** Amagra is not a modular *application*. It is a modular *runtime*.
> The goal is a **small core and a large ecosystem** — not a lightweight app, but
> a small runtime that lets the ecosystem grow without touching it.

This document exists because three surfaces currently say three things, and they
need reconciling:

- the **README** leads with *"prompt debugger"* — a wedge **feature**,
- the **architecture** is already a **runtime** (Context/Result spine, provider
  registries, an extension host),
- the **roadmap** points at a **platform** (v2.0 Agent Registry & SDK).

All three are true at different altitudes. The canonical ladder:

> **Feature** (the debugger is how people meet it) → **Runtime** (what it actually
> is) → **Platform** (where it's going).

---

## The three layers

Amagra is not VS-Code-flat (core + leaf extensions). It has a **middle layer** —
the execution model — that a code editor doesn't have. Conflating these three is
the central trap.

```
Core Runtime          stable, in-core, everything depends on it
 ├─ Context / Result        (core/contract.py, runtime.py, run_log.py)
 ├─ Event Bus               (infrastructure/event_bus.py)
 ├─ Workspace / threads / storage
 ├─ Provider registries     (providers/registry.py, memory_core.get_backend)
 └─ Extension Host          (core/registry.py — "inverted extension registry")

Runtime Loop          the execution model — pluggable at the IMPLEMENTATION level,
 ├─ Routing                 not removable wholesale (these are organs, not features)
 ├─ Memory
 ├─ Critique
 ├─ Learning
 └─ Coherence

Features              pure extensions — nothing depends on them; toggle freely
 ├─ Prompt Debugger
 ├─ Consensus
 ├─ Sandbox
 ├─ Web Search
 ├─ Observability panels
 └─ Agent packs
```

### Organs vs. features (the memory rule)

A code editor survives if you uninstall Python support. **An accountable AI
runtime does not survive if you uninstall memory, routing, and learning** — they
are the feedback loop that *is* the product. So the test is never:

> ❌ "Can I remove memory?"

It is:

> ✅ "Can I swap the memory implementation?"

Memory already answers yes (`MemoryBackend(ABC)` → SQLite / FAISS / pgvector). The
interface and the loop stay in core; the implementation is a plugin. Routing
should become the same. **Disable a retrieval policy, swap a backend — yes. Unplug
the organ and keep the body — no.**

---

## Current state (what's already a seam vs. what's a built-in)

The decomposition has *already happened* in several critical places. The work is
to **unify and open what's modular**, not to break up a monolith.

| Subsystem | State | Evidence |
|---|---|---|
| Model inference | ✅ interface | `providers/base.py` `ModelProvider` / `EmbeddingProvider` ABCs + `registry.py` + `manifest.py` |
| Memory storage | ✅ interface | `memory_core/backend.py` `MemoryBackend(ABC)` → SQLite / FAISS / **pgvector** via `get_backend()` |
| Extension host | ✅ seed | `core/registry.py` — self-described "inverted extension registry / extension host" |
| Runtime contract | ✅ core | `core/contract.py` (`Context`/`Result`), `runtime.py` (onion middleware), `run_log.py` |
| Event bus | ✅ core | `infrastructure/event_bus.py` `emit` / `subscribe` |
| Agents | ◑ registry | `agents/registry.py` — registry exists; not yet a unified contribution |
| **Routing** | ❌ **built-in** | `orchestration/router.py` — still module functions (`decide`, `decide_with_confidence`), **the one organ not behind an interface** |
| Contribution model | ❌ fragmented | separate registries per subsystem; no single `contributes:` manifest |

---

## Router — the obvious next seam

Everything else converged on interfaces; routing is still a concrete mechanism.
Formalizing it is small and high-leverage:

```python
@dataclass(frozen=True)
class RoutingDecision:
    agent: str
    confidence: float
    signal: dict          # domain / shape / verbosity / etc.

class Router(Protocol):
    def decide(self, query: str, context: Context) -> RoutingDecision: ...
```

Today's signal router becomes `SignalRouter`; the coordinator depends on the
`Router` protocol, not the functions. That immediately unlocks `LLMRouter`,
`HybridRouter`, `GraphRouter`, `EnterpriseRouter` — without touching the
coordinator, exactly mirroring where providers and memory already are.

---

## The contribution model (the platform opportunity)

Today extensibility is **per-subsystem** (model registry, memory registry, agent
registry, tool registry). Users eventually want **one package, one install, one
lifecycle, one permission surface**:

```yaml
id: security-pack
version: 1.0.0
contributes:
  agents:   [security_auditor]
  tools:    [cve_lookup]
  panels:   [threat_dashboard]
  commands: [generate_threat_model]
  routes:   [security_router]
  providers: []            # memory backends, model providers, routers
permissions:
  - model_access
  - workspace_read
```

One extension host loads all contribution *types* from one manifest. This is the
v2.0 Agent Registry/SDK, **generalized from agents to every contribution kind.**

---

## Two architectures, two milestones (do not conflate)

This is the most important boundary in this document.

> **Extensibility ≠ Trust.** The architecture for *loading* contributions and the
> architecture for *isolating untrusted* contributions are **different projects.**

- **First-party / contribution model** (v2.0): an in-process extension host that
  loads first-party and trusted contributions from a unified manifest. The host is
  a *convenience layer*. Permissions are declared but cooperatively enforced.
- **Third-party marketplace** (a *later, separate* milestone): the moment outside
  authors load code, the extension host becomes a **security boundary**, not a
  convenience. An AI extension's blast radius dwarfs a VS Code theme's — it can
  reach prompts, memory, documents, API keys, model outputs, and tool calls. That
  demands real isolation (out-of-process host / capability model), a vetted
  registry with trust tiers, and a permission system that is *enforced*, not
  documented. The existing `sandbox` is a **resource jail, not a security
  boundary** — it does not isolate network or filesystem.

Shipping the marketplace on the convenience-layer host would be the single
biggest mistake available. Keep them as separate roadmap items.

### Hot-path caveat

VS Code tolerates extension latency; Amagra's hot path is ~1 ms routing and
< 1 ms warm memory. In-process protocol calls are fine. Any isolation boundary
(out-of-process host) must sit at **coarse seams** — a whole agent or tool call —
**never per-token**.

---

## Refactor path (strangler-fig — no big-bang rewrite)

1. **Declare the philosophy** — this document + the roadmap track. *(now)*
2. **Close the interface gap** — `Router` protocol + `SignalRouter`; coordinator
   depends on the protocol. No behavior change.
3. **Unify the registries** — one contribution model (`contributes:`), built-ins
   re-registered through it as first-party plugins. Still no third-party loading.
4. **Expose the SDK** — documented contracts + manifest, so first-party/trusted
   authors can add contributions.
5. **(Separate milestone) Isolation & marketplace** — out-of-process host,
   enforced permissions, vetted registry, trust tiers.

The acceptance test, refined from the "VS Code for AI" idea:

> Can a user run Amagra with **chat + models + projects**, then add memory
> backends, routing strategies, consensus, observability, the debugger, and agent
> packs **one contribution at a time** — while the *runtime loop* (memory ↔ routing
> ↔ critique ↔ learning ↔ coherence) stays intact and swappable, not removable?

When that's yes, Amagra is a **small runtime with a large ecosystem.**
