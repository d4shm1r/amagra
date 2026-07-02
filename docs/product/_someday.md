# Someday — frozen until there are real users

> This file holds work that was promoted to the roadmap **before** the product
> had a single external user. None of it is necessarily *wrong*. It is premature.
>
> **Unfreeze rule:** nothing here moves back into [`ROADMAP.md`](../ROADMAP.md)
> until the wedge has drawn a real external signal (strangers running tasks,
> inbound issues, the first non-founder user). The *State of the AI Economy 2026*
> analysis is the reason for the freeze: AI revenue is still ~0.4% of US GDP — a
> rounding error — so designing pricing tiers, marketplaces, and enterprise
> governance at user #0 is building the top floors of a building with no door.

---

## Premature monetization (was in `revenueGPT.md`)

Designing five pricing tiers and a marketplace for a product with zero users.
Kept here as a record; revisit only after sustained organic usage.

### Tiers (frozen)

| Tier | Price | What's included |
|------|-------|-----------------|
| Self-host Free | $0, MIT | Everything, single-user, full source, unlimited locally |
| Pro | $39/mo | Managed hosting · encrypted memory sync · hosted dashboard · weekly digest |
| Team | $249/mo | Shared team memory · workspaces · RBAC · admin console · analytics · SLA alerts |
| Cognitive Ops | $499–999/mo | Risk observatory · decision audit trail · verification reports · replay |
| Enterprise | $2k–10k/mo | SSO/SAML · CoA audit trail · SOC2 · air-gapped installer · signed MSA/SLA |

### Cognitive Marketplace (frozen)

- Skill Packs ($99–499): DevOps · Security · Legal · Finance · Data Science
- Verification Packs ($49–199): Python · Kubernetes · Security · SQL
- Planner Packs ($99–299): Software Sprint · Incident Response · Research · DevOps Migration
- World Models ($199+): Software · Legal · Healthcare · Financial

### Revenue projection (frozen — this was fiction)

The original projection assumed a launch that never happened (Month 1 = "launch
build", but the Show HN post was never sent). Kept here only as a cautionary
record, **not a forecast.**

| Month | MRR | Driver |
|-------|-----|--------|
| 1 | $0 | Launch build |
| 2 | $39 | First managed-hosting customer |
| 3 | $200 | ~5 Pro (organic GitHub) |
| 6 | $1,200 | 20 Pro + 2 Team + marketplace |
| 12 | $10k–15k | 50 Pro + 8 Team + 3 CogOps + 1 Enterprise |

---

## Far-future milestones (frozen)

### Workspaces & RBAC
Multiple isolated projects per user, role-based access, custom agent builder,
per-workspace memory namespace. Build the single-user wedge first.

### Team Memory & Governance (was v1.7)
Shared FAISS index per workspace, admin console, encrypted sync, audit log
export, SSO/SAML, data-retention policies, air-gapped installer. Category-defining
*if* there is ever a team using it.

### Agent Registry & Marketplace (was v2.0)
Agent SDK (manifest-declared community agents), importable agent packs, curated
registry, execution-graph interface. Only after the runtime is excellent *and*
has users.

### Platformization
Generalize from agent extensibility to a unified contribution model
(`PLUGIN_ARCHITECTURE.md`). **Hard boundary:** a third-party marketplace is a
*security* boundary (extensions reach prompts, memory, keys); ship it only on a
real out-of-process isolation model, never folded into the contribution model.

### Long-term bets
Multi-agent pipeline UI, decision replay as shareable artifact, edge deployment
(Pi/NAS), and the "AI operating layer" vision seeds (Consensus/Trust/Executive
modes, memory vaults, cross-device memory) in [`VISION.md`](VISION.md).
