# Identity — the architectural contract

Amagra's design already separates **capabilities** (providers, memory backends,
tool adapters — replaceable) from **orchestration** (planner, coordinator,
dispatch, policies — engineered). The third layer, **identity**, existed too —
but *emergent*, scattered across modules with no owner: preferences in
`config/profile.json`, goals in the task-graph store, permissions in
`api_keys`, accumulated learning in decision weights + calibration + memory.

This document makes identity an explicit, testable contract. It is an
**ownership model, not a code reorganization**: every subsystem keeps its own
storage and write path. What changes is that identity now has a name, a shape,
a single read surface (`models/identity.py`), and invariants that CI enforces.

---

## 1. The governing principle

> **Identity changes through learning.
> Orchestration changes through engineering.
> Capabilities change through replacement.**

Three layers, three *mechanisms of change* — and conflating them is what makes
AI systems hard to reason about:

| Layer         | Changes because…                                             | Example in Amagra |
|---------------|--------------------------------------------------------------|-------------------|
| Identity      | evidence, learning, user preferences, accumulated experience | `apply_learning_update()` moves a decision weight |
| Orchestration | developers improve algorithms and coordination logic         | a better critic gate, a new routing policy |
| Capabilities  | better models, tools, or providers become available          | swapping phi4-mini for another model via `providers/` |

Note the deliberate refinement over the naive form ("identity is stable"):
Amagra's identity is *not* static — the learning loop is the product. Identity
is **mutable, but only through one discipline**: attributable learning events
and explicit configuration. Never as a side effect of an upgrade or a swap.

## 2. The entity

```text
Identity
│
├── Intrinsic            changes rarely — explicit configuration / governance
│   ├── Profile            config/profile.json (preferences, values, "never do")
│   ├── Goals              task-graph store (persistent intents)
│   └── Permissions        api_keys tiers (access grants — never key material)
│
├── Learned              changes continuously — attributable learning events
│   ├── Decision weights   decision/weights.py (routing experience)
│   ├── Calibration        confidence-vs-outcome history per agent
│   └── Memory             memory store shape (what experience exists, how much)
│
└── Meta                 schema version, snapshot timestamp (never fingerprinted)
```

The **intrinsic / learned split** is the part that carries governance weight:
intrinsic mutations are human decisions (edit the profile, grant a key, set a
goal); learned mutations are expected outcomes of operation. A change appearing
in the wrong half is a bug by definition — and `changed_paths()` names the
exact subtree that moved, so every identity change is attributable.

## 3. Ownership: read from one place, write where you always did

`models/identity.py` is a **pure consumer** — the same posture as
`infrastructure/transparency.py`. It stores nothing, mutates nothing, and adds
no write path. `F-01` still holds: only `apply_learning_update()` touches
weights; only the memory filter gate writes memories; only the operator edits
the profile.

What the contract adds:

- **one serialization format** — `snapshot()` returns the whole identity as one
  document (portable, diffable, snapshot/restore-ready)
- **one comparison primitive** — `fingerprint()` hashes the content
  (volatile meta excluded), so "did identity change?" is one equality check
- **one attribution primitive** — `changed_paths(before, after)` names the
  subtrees that moved, so "why did identity change?" has a concrete answer
- **one API surface** — `GET /identity`, `GET /identity/fingerprint`

## 4. The invariant family (enforced in `tests/test_identity.py`)

The point of the contract is that these stop being slogans and become
regression gates:

1. **Capability replacement must not modify identity.**
   Swapping the model provider (env change + registry rebuild) leaves the
   fingerprint unchanged.
2. **Runtime restart preserves identity.**
   Dropping in-process caches and re-reading from disk reproduces the same
   fingerprint — identity lives in durable state, not process memory.
3. **Identity mutations are attributable.**
   A learned change (e.g. a weight update) alters *only* the `learned` subtree;
   an intrinsic change (e.g. a profile edit) alters *only* `intrinsic` —
   and `changed_paths()` names the exact leaf either way.
4. **Absence degrades the content, never the shape.**
   On a fresh install every source is empty but the identity structure is
   intact — subsystems can rely on the shape unconditionally.

Extensions of the same family, documented as intent (not yet mechanically
enforced): upgrading the planner does not erase identity; rebuilding embeddings
does not change identity (memory *references* are identity; vector encodings
are capability).

## 5. Relationship to the other architecture docs

- **`PLUGIN_ARCHITECTURE.md`** answers *extension trust*: core runtime vs
  runtime loop vs features — what can be swapped or toggled. Identity is an
  orthogonal axis: *behavioral ownership* — which state belongs to the user's
  AI rather than to any implementation. Both hold simultaneously; neither
  replaces the other.
- **`PLATFORM_ENTITY_MODEL.md` §14** places Identity in the multi-tenant
  entity model (per-Organization, referenced by Workspaces — same
  reference-don't-own rule as every other resource).
- **`PROMPT_ARTIFACT_CONTRACT.md`** is the precedent: Prompt was implicit in
  the implementation until it was named as a platform entity. Identity follows
  the same move — the symmetry fix for state instead of configuration.

## 6. Non-goals

- **No new store.** Identity is a view, not a database. Consolidating storage
  behind the contract is possible later (single-file `AMAGRA_DB` mode already
  points that way) but is not required by it.
- **No behavior change.** Nothing routes, learns, or responds differently
  because this contract exists.
- **No multi-tenant enforcement yet.** In SaaS mode identity is per-tenant and
  `GET /identity` must be gated per key — reserved in §14 of the entity model,
  implemented when tenancy is.

---

*The invariants live in `tests/test_identity.py`; the surface in
`models/identity.py`; the API in `routes/identity.py`.*
