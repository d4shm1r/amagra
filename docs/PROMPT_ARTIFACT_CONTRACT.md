# Prompt-as-Artifact Contract

*Proposed **v4 amendment** to [`PLATFORM_ENTITY_MODEL.md`](PLATFORM_ENTITY_MODEL.md). Kept
separate until reviewed, then folded in. This is the keystone the Prompt-IDE roadmap
(Monaco, Explorer, AI Actions, Extensions, Marketplace) hangs off — none of them are
buildable cleanly until it lands.*

---

## The finding (one sentence)

> The canonical entity model makes the **response** a first-class, versioned, durable
> resource (`Artifact`, §5) and the **prompt** nothing at all — so the system has
> *execution memory but no source memory*.

Evidence, in the code that ships today:

| Side | Where it lives | Durability | Identity |
|------|----------------|-----------|----------|
| **Response (R1)** | server: `Artifact` / `model_choices` store | persisted, queryable | first-class id |
| **Prompt (P1)** | browser `localStorage` (`prompt_editor_v1`) + a **raw string field** inside each decision record ([`debug_prompt.py:165`](../routes/debug_prompt.py#L165)) | ephemeral / non-canonical | **none** |

The prompt is the *source code*; the response is the *compiled output*. Today the build
artifact outlives the source. That inversion is the structural bug. Everything else
(Explorer, inline diagnostics, AI Actions, extensions, marketplace) is downstream of
fixing it.

---

## The amendment: `Prompt` as a design-plane resource

Add one resource to the Workspace **design plane** (alongside Agent / Tool / Workflow),
and one link on the runtime side. Nothing else in the entity model changes.

```text
Workspace
  design plane (versioned config)
    ├── Agent          (+ AgentVersion)
    ├── Tool           (+ ToolVersion)
    ├── Workflow       (+ WorkflowVersion)
    ├── Prompt         (+ PromptVersion)      ◄── NEW (this doc)
    └── …
  runtime plane (append-only artifacts)
    └── Conversation
         └── Run        (+ prompt_version_id) ◄── NEW link: which source produced this
              ├── Trace → Event
              └── Artifact[]                   (R1 — the response, unchanged)
```

```text
Prompt
 ├── id          (globally unique, per version snapshot)
 ├── slug        (stable concept key, unique within scope — "game-level-gen")
 ├── name        (presentation only)
 └── version     (draft | published | pinned snapshot)

PromptVersion
 ├── id
 ├── prompt_id
 ├── n           (v1, v2, v3 …)
 ├── source      (the prompt text — the source of truth)
 ├── variables   (Record<string, any> — see §AST)
 ├── created_at
 └── parent_id   (the version this was edited from — gives the diff graph)
```

Because `Prompt` is just another design-plane resource, it inherits the existing rules
**for free**:

- **Versioning** (entity model §8): `draft → published → pinned`. "Run v3 again" is a
  pointer to a `PromptVersion`, not a re-typed string.
- **Reference-not-own** (§2): a `Run` *binds* a `PromptVersion` by id; it never copies
  the text. The decision record stops storing raw prompt text and stores
  `prompt_version_id` instead — closing the asymmetry.
- **Templates / Marketplace** (§8): a published `Prompt` promoted to the Global Library
  *is* a marketplace template. No new machinery.
- **Design/runtime split** (§4): deleting a `Run` never touches the `Prompt`; resetting a
  `Prompt` never deletes run history.

### The link that makes P and R symmetric

`Run.prompt_version_id` is the whole point. Once a run records *which* prompt version
produced it:

- Explorer can show `R1, R2, R3` **under** the `PromptVersion` that produced them.
- A response artifact can answer "what was I generated from."
- Diff becomes "compare the two `PromptVersion.source` strings whose runs you're
  comparing."
- `model_choices` decisions attach to `prompt_version_id`, so "you chose Claude for
  *this prompt*" survives an edit to the prompt instead of silently re-keying.

---

## Local substrate: it already half-exists

This is single-tenant local-first today, so the design-plane `Prompt` resource is backed
by **files on disk**, via the FS jail that already ships
([`tools/workspace.py`](../tools/workspace.py), [`routes/workspace.py`](../routes/workspace.py)).

Root: `$AMAGRA_WORKSPACE` (default `<project>/workspace`), created on demand, with a
path-escape jail (`_safe_resolve`). Layout convention:

```text
$AMAGRA_WORKSPACE/
  <project-slug>/
    prompts/
      <prompt-slug>/
        prompt.json            # { id, slug, name, current_version }
        versions/
          v1.prompt            # PromptVersion.source (plain text — git-diffable)
          v2.prompt
          v1.meta.json         # { variables, created_at, parent }
        runs/
          R1.response.json     # Artifact: { prompt_version_id, output, model, metrics, trace_ref }
          R2.response.json
```

Plain `.prompt` files as the source of truth means **git-diff comes for free** (roadmap
item 9), the Explorer is a thin view over `/workspace/list`, and extensions attach to
paths instead of in-memory objects.

### Read/write API contract

The jail is **read-only** today (`read`, `list`, `search`). The single foundation
endpoint set this needs is **write semantics**, going through the same `_safe_resolve`
chokepoint so the security boundary is unchanged:

| Method | Path | Maps to | Status today |
|--------|------|---------|--------------|
| GET  | `/workspace/read?path=`  | `ws.read_file`  | ✅ ships |
| GET  | `/workspace/list?path=`  | `ws.list_dir`   | ✅ ships |
| GET  | `/workspace/search?q=`   | `ws.search`     | ✅ ships |
| POST | `/workspace/write`       | `ws.write_file` *(new)* | ❌ to build |
| POST | `/workspace/mkdir`       | `ws.mkdir` *(new)*      | ❌ to build |
| POST | `/workspace/move`        | `ws.move` *(new)*       | ❌ to build |
| POST | `/workspace/delete`      | `ws.delete` *(new)*     | ❌ to build |

Writes reuse the existing typed errors (`PathEscape → 403`, `NotFound → 404`,
`TooLarge/NotText/WorkspaceError → 400`) and bounds (`DEFAULT_MAX_READ_BYTES`). Writing is
a higher-trust capability than reading — gate it behind the same owner-action check as
`/debug/prompt` (see [`routes/consensus.py:14`](../routes/consensus.py#L14)).

---

## The AST is a projection, not a rewrite

The prompt analysis already exists and is good: `computeMetrics`, `detectDomain`,
`structChecks` ([`PromptEditorTab.jsx:478`](../ui/src/PromptEditorTab.jsx#L478)). What's
missing is **stable node identity** so a finding can point at a span and a fix can edit
one node.

```text
Today:   "missing context"  →  string warning in a right-rail list
Needed:  Diagnostic { nodeId: "block.3", span: [L4,L6], fix: (ast) => ast' }
```

The AST is an **index layer over the existing analysis**, not a new parser. `variables`
(`{{engine: "html5"}}`) become typed `PromptVersion.variables`; the existing checks become
the linter pass that walks the parse tree and emits span-anchored `Diagnostic`s. This is
what unlocks click-to-fix, inline highlighting, AI Actions, and diff-based editing — all
of which are mechanical once nodes have ids.

---

## Migration (closing the asymmetry, in order)

1. **Define** `Prompt` / `PromptVersion` + the FS layout above. (schema only)
2. **Add write ops** to the FS jail (`write_file`, `mkdir`, `move`, `delete`) behind the
   owner-action gate.
3. **Repoint the editor**: `prompt_editor_v1` localStorage → `/workspace/*`. Prompts
   become files; tabs become open files. One-time import of any existing localStorage
   tabs.
4. **Persist responses as artifacts** next to their prompt (`runs/R*.response.json`) with
   `prompt_version_id`. Decisions (`model_choices`) gain `prompt_version_id` and stop
   relying on the raw-string key.

After step 4 the asymmetry is closed: P1 and R1 are both first-class, file-backed,
versioned, and linked.

---

## What each roadmap item becomes once this lands

| Roadmap item | Was | Becomes (after the amendment) |
|--------------|-----|-------------------------------|
| Explorer | new subsystem | thin view over `/workspace/list` |
| Versioning / diff | new subsystem | `git diff` of `versions/*.prompt` |
| Inline diagnostics | blocked | AST projection of existing analysis |
| AI Actions | new subsystem | functions that edit a `PromptVersion` node |
| Response-as-artifact | contradicts chat | the `R*.response.json` already on disk |
| Extensions | blocked (no AST) | functions bound to `Prompt`/`Artifact` types |
| Marketplace | blocked | published `Prompt` in the Global Library (§8) |

## What this deliberately does NOT do

- Does not delete the chat surface. Chat is **demoted** to an input shim across Phase 2,
  retired only once `R*.response.json` reaches parity. (Hard-to-reverse + it's the
  current activation path.)
- Does not introduce multi-tenant entities. Local single-tenant uses the FS substrate;
  the Org/Project/Workspace hierarchy in the canonical model is the future cloud shape,
  and the `Prompt` resource slots into it unchanged.
- Does not rewrite the prompt analyzer. The AST indexes it.
