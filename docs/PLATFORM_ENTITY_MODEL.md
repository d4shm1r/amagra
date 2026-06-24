# Platform Entity Model

Canonical entity model for a multi-tenant platform where users create unlimited
workspaces, agents, tools, knowledge sources, and automations.

This resolves the open questions from the initial hierarchy draft into a single
recommended design. The guiding principle: **separate the things that organize
from the things that do work, and within each, separate configuration (design
plane) from execution (runtime plane).**

> **v2 changes** — added resource identity (§2), the cascade now resolves on
> stable slugs not display names (§3), a runtime parentage chain (§5), an
> Environment/Deployment layer (§6), first-class Schedule/Trigger (§9), and the
> Artifact entity (§5). Access grants can now attach at Workspace as well as
> Project (§1).
>
> **v3 changes** — added vaulted Credentials/Secrets as a distinct scoped
> resource (§10) and an Evaluation suite — Evaluator, Dataset, EvalRun (§11).

---

## 1. The canonical hierarchy

```text
Organization                (tenant — billing, members, plan)
└── Project                 (grouping + coarse access boundary)
    └── Workspace           (collaboration boundary — carries its own grants)
        ├── Agents            ─┐
        ├── Tools              │
        ├── KnowledgeBases     │ design plane
        ├── Workflows          │ (versioned configuration)
        ├── MemoryStores       │
        ├── Schedules          │
        ├── Triggers           │
        ├── Credentials        │
        ├── Evaluators         │
        ├── Datasets          ─┘
        │
        ├── Environments      ─┐ deployment plane
        │                      │ (frozen version sets)
        │
        ├── Conversations     ─┐
        ├── Runs               │
        ├── Traces             │
        ├── Events             │ runtime plane
        ├── Artifacts          │ (execution artifacts)
        ├── EvalRuns           │
        └── MemoryRecords     ─┘
```

Three planes hang off the Workspace: **design** (versioned config), **deployment**
(frozen version sets you execute against), and **runtime** (immutable execution
artifacts).

- **Organization** is the tenant. Billing, plan limits, and the user roster live
  here — *not* under Project. A user belongs to an Organization and is granted
  access to specific Projects/Workspaces within it. This is the boundary that
  breaks if you put billing under Project (a user in two projects, one bill).
- **Project** is a grouping and *coarse* access boundary inside the tenant, not a
  billing unit.
- **Workspace** is the primary unit users live in day to day, and is itself a
  collaboration boundary: access grants attach at **either** Project or Workspace,
  so one project can hold an Engineering, a Support, and a Research workspace with
  different permissions.

Cross-tenant shared content (official templates, model catalog, marketplace
integrations) lives in a **Global Library** owned by the platform, not by any
Organization.

---

## 2. Reference, don't own (the rule that matters most)

A resource lives at **exactly one scope** and is **bound** by reference
everywhere else. Agents never own a private copy of a tool — they hold a
*binding* to a tool that lives at some scope.

Every resource carries a stable identity separate from its display name:

```text
Tool
 ├── id        (globally unique, per version snapshot)
 ├── slug      (stable concept key, unique within its scope)
 ├── name      (presentation only — may change freely)
 └── version   (draft | published | pinned snapshot)

AgentBinding(agent_id, resource_slug, version_ref, overrides?)
```

- **`slug`** is what makes "the same concept" across scopes — *not* the name.
- **`id`** identifies a specific version snapshot.
- A binding references a resource by `slug` (+ a `version_ref`: pinned id or
  "float to latest published").

Consequences:

- Editing a Workspace tool updates it for every agent bound to it. One source of
  truth, no copy-paste drift.
- "Share a tool between agents" = two bindings to the same resource. No copy.
- An agent can still hold **per-binding overrides** (e.g. a tighter prompt or a
  scoped credential) without forking the resource.

---

## 3. Scope resolution (the cascade)

When an agent resolves a resource **by slug**, scopes are merged
**most-specific-wins**, like CSS. Names play no part in resolution.

```text
Global  →  Organization  →  Project  →  Workspace  →  Agent
(weakest)                                            (strongest)
```

- A Workspace tool with slug `search` shadows a Global tool with slug `search`
  for agents in that workspace.
- An Agent-level override shadows the Workspace definition for that one agent.
- Resolution is deterministic and logged, so you can always answer "why did this
  agent get *this* version of the tool."

---

## 4. Design plane vs runtime plane

Keep configuration and execution artifacts as **separate entities**, never
siblings. This is what makes versioning, templating, and "reset without losing
config" trivial.

| Design plane (config, versioned) | Runtime plane (artifacts, append-only) |
|----------------------------------|----------------------------------------|
| Agent                            | Conversation                           |
| Tool                             | Run                                    |
| KnowledgeBase                    | Trace / Event                          |
| Workflow                         | Artifact                               |
| MemoryStore (the container)      | MemoryRecord                           |
| Schedule / Trigger               | DataIngestionJob                       |
| Credential (vaulted ref)         | EvalRun                                |
| Evaluator / Dataset              |                                        |

- You **version** design-plane entities (draft → published → version-pinned).
- You **never** version runtime artifacts; they're immutable and timestamped.
- Deleting a Conversation must not touch the Agent. Resetting an Agent must not
  delete its run history.

---

## 5. Runtime ownership (parentage)

Runtime artifacts form a strict ownership chain. This is what makes retention,
replay, and cascade-delete sane:

```text
Conversation
 └── Run                 (one execution of an agent/workflow)
      ├── Trace
      │    └── Event      (tool call, model call, memory write, …)
      └── Artifact[]      (generated outputs — see below)
```

- A **retention policy** set on Conversation cascades cleanly down the tree.
- **Artifact** is first-class, *not* buried inside Run. Generated outputs
  (`report.pdf`, `summary.md`, a generated dataset or code bundle) often outlive
  the run that produced them and become user-facing assets with their own
  lifecycle, sharing, and permissions. A Run *produces* Artifacts; deleting the
  Run can be configured to orphan rather than delete them.

---

## 6. Environments & deployments

The one layer that's painful to retrofit. Drafts and production config must not
coexist in the same execution path.

An **Environment** is a *named* first-class entity (not a fixed
Dev/Staging/Production enum) that freezes a set of resource versions:

```text
Environment "production"
 ├── AgentVersion       = agent:onboarding @ v12
 ├── WorkflowVersion    = workflow:triage  @ v7
 └── ToolVersion        = tool:search      @ v3
```

- Runs always execute **against an Environment**, never against loose drafts.
- Promotion = pointing an Environment at newer version snapshots.
- Rollback = pointing it back. No data migration, no risk to in-flight work.
- Names are free-form (`production`, `staging`, `eu-prod`, `pr-1234-preview`,
  `canary`) so teams aren't boxed into three fixed stages.

---

## 7. Memory: one answer

Pick one model and hold it. Recommended:

- **MemoryStore** is a design-plane container scoped at Workspace (or Org, for
  shared knowledge). It defines *where* memory lives and its policy (retention,
  dedup, embedding model).
- **MemoryRecord** is a runtime artifact written into a MemoryStore.
- An **Agent binds to one or more MemoryStores** (read and/or write). "Per-agent
  memory" = a MemoryStore scoped to that agent; "shared memory" = a
  Workspace-scoped MemoryStore that several agents bind to.

Same binding pattern as tools (§2): MemoryStore is to MemoryRecord as a database
is to its rows.

---

## 8. Versioning & templates

- Agents, Tools, Workflows, KnowledgeBases are **versioned**: `draft`,
  `published`, and immutable version snapshots. Bindings can pin a version or
  float to latest.
- A **Template** is a published, parameterized snapshot promoted to a library
  (Workspace, Org, or Global). Instantiating a template **copies** it into the
  target scope (this is the one place a copy is correct — the instance then
  diverges independently).

---

## 9. Scheduling & triggers

Reserved as first-class design-plane resources now, even ahead of implementation,
so automations don't get bolted on as a special case later:

- **Schedule** — time-based invocation (`every hour`, cron expression).
- **Trigger** — event-based invocation (webhook, file upload, memory update,
  upstream run completion).

Both target an Agent or Workflow **within a named Environment** (§6), so a
schedule fires against frozen, known versions.

---

## 10. Credentials & secrets

Secrets are **not** plain binding overrides — they need their own vaulted
resource type so they can be scoped, rotated, and audited without leaking into
config snapshots or version history.

```text
Credential
 ├── id
 ├── slug                (stable reference key)
 ├── scope               Org | Project | Workspace
 ├── secret_ref          → external vault / KMS handle (never the value)
 └── rotation_policy
```

- A Credential stores a **reference** to a secret in a vault/KMS, never the value
  itself. Version snapshots and templates capture the `slug`, so promoting a
  template across environments rebinds to the target scope's secret — no secret
  ever travels in config.
- Tools and Integrations bind to a Credential by `slug`, resolved with the same
  cascade as §3 (a Workspace `openai-key` shadows an Org-level one).
- Rotation updates the vaulted value behind a stable `slug`; nothing bound to it
  changes.

---

## 11. Evaluation

Once Agents/Workflows are versioned (§8), you need a first-class way to score a
version *before* promoting it into an Environment (§6).

```text
Dataset        design plane — a named set of test cases / golden examples
Evaluator      design plane — a scorer (assertion, LLM-judge, metric fn)
EvalRun        runtime plane — Evaluator applied to a target version over a Dataset
```

- An **EvalRun** targets a specific version snapshot (e.g. `agent:triage @ v13`)
  against a **Dataset**, producing scored results — the gate for promotion.
- Evaluators and Datasets are versioned design-plane resources and follow the
  binding + cascade rules, so a Global "faithfulness" judge can be reused across
  every workspace.
- EvalRuns slot into the runtime parentage model (§5) as a sibling of Run.

---

## 12. Recommended entity list

```text
Organization
  ├── User, Role, Membership          (who, what they can do)
  ├── Plan / Billing                  (tenant-level)
  └── Project
        ├── ProjectMembership         (coarse grants)
        └── Workspace
              ├── WorkspaceMembership  (fine grants)
              │
              ├── Agent          (+ AgentVersion)        ─┐
              ├── Tool           (+ ToolVersion)          │
              ├── KnowledgeBase  (+ Version)              │ design
              ├── Workflow       (+ WorkflowVersion)      │
              ├── MemoryStore                             │
              ├── Schedule / Trigger                      │
              ├── Credential     (vaulted secret ref)     │
              ├── Evaluator / Dataset                     │
              ├── AgentBinding   (agent ↔ resource refs) ─┘
              │
              ├── Environment    (frozen version sets)    ─ deployment
              │
              ├── Conversation                            ─┐
              │    └── Run                                 │
              │         ├── Trace → Event                  │
              │         └── Artifact                       │ runtime
              ├── EvalRun                                  │
              └── MemoryRecord                            ─┘

Global Library (platform-owned)
  ├── Model
  ├── Integration
  └── Template
```

---

## 13. Why this works

- **Unlimited everything** — workspaces, agents, and resources all grow
  independently; nothing is nested so deep that scale forces a redesign.
- **Sharing without duplication** — reference-not-own + slug-based cascade gives
  a single source of truth and deterministic resolution.
- **Safe to ship** — Environments separate drafts from production and rollback is
  a pointer move; EvalRuns gate promotion; secrets stay vaulted and never travel
  in config or version history.
- **Clean lifecycle** — design/runtime split + a strict runtime parentage chain
  means versioning, templating, retention, and resets each touch exactly one
  plane.
- **Multi-tenant from day one** — the Organization boundary means billing and
  cross-project users work without retrofitting; grants at both Project and
  Workspace cover team-level isolation.
- **Extensible** — new resource types (Evaluators, Connectors, …) drop into the
  Workspace design plane and inherit the binding + cascade + environment rules
  for free.
```
