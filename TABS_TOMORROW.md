# Tabs — Tomorrow's UI Pass (TEMPORARY)

> **Temporary handoff note.** Created 2026-07-11. Delete once the pending tabs
> below are worked through. This is a scratch checklist, not a durable record —
> the durable UI decisions live in `docs/design/` and the memory index.

## Purpose

Today's session polished a first batch of tabs to a shared, calm, gold-forward
pattern. The remaining tabs still carry the old look and — more importantly —
**need careful verification of what they actually are and how they should
behave** before restyling. Several are dense, data-driven, or ambiguous in
purpose. Do **not** blindly reskin them; understand each one first.

---

## The pattern established today (apply to pending tabs)

Every tab that was upgraded now shares this contract:

1. **Centered gold `PageHeader`** — `<PageHeader center title="…" subtitle="…" />`
   (the `center` prop clears the fixed ☰ menu button and keeps titles constant).
2. **Gilded-Calm theme via tokens** — `T`, `LUX`, `TYPE`, `EASE`, `DUR`,
   `RADIUS`, `FONT_MONO`/`FONT_DISPLAY` from `theme.js`. No ad-hoc hex.
3. **Frosted `lux-card` surfaces** (`LUX.tileFace` + `LUX.tileBorder`), soft hover
   lift, hairline dividers — not grey boxes.
4. **Single-gold accents** for decorative marks; keep *semantic* colors
   (agent identity, status green/red, per-event log colors) as real signal.
5. **Controls**: gold/white sliders (no black track), gold/white toggles with a
   defined knob border, gold key-caps. Numerals in `T.accentText`.
6. Shared content column is `maxWidth: 1020` (App.jsx wraps every non-chat tab).

Reference implementations from today: `VersionHistoryTab.jsx`, `Modals.jsx`
(Settings/About/Shortcuts), `LogTab.jsx`, `MindMapInteractive.jsx`.

---

## DONE this session ✅

| Tab (label) | id | Component |
|---|---|---|
| Releases | `releases` | `VersionHistoryTab.jsx` |
| Settings | `prefs` | `Modals.jsx › SettingsModal` |
| About | `about` | `Modals.jsx › AboutView` |
| Shortcuts | `shortcuts` | `Modals.jsx › ShortcutsModal` |
| Log | `log` | `LogTab.jsx` |
| Mind Map | `mindmap` | `MindMapInteractive.jsx` |
| Knowledge | `knowledge` | `KnowledgeGraph.jsx` |
| Model | `model` | `ProviderSettingsTab.jsx` |
| Guide | `guide` | `GuideTab.jsx` |

(Also: AppLauncher trims, Chat toggles for send-on-Enter / timestamps / reduce-motion.)

---

## PENDING — need work + verification 🔎

Grouped by nav surface (`ui/src/navConfig.js`). "Analysis", "Dashboard" and
"Coherence" the user called out are mapped below.

### Cognition surface (densest — most care needed)
| Tab (label) | id | Component | Notes / to verify |
|---|---|---|---|
| **Dashboard** | `cog-dash` | `CognitionView.jsx` | The at-a-glance health grid. Called out. Verify which metrics are live vs placeholder. |
| Diagnostics | `diagnostics` | `DiagnosticsTab.jsx` | Folds six focus views (UCI / Risk / Verifier / Events / Plan / Policy) into internal sections — big surface, check each section. |
| CogOS | `cognitive` | `CognitiveOSTab.jsx` | Self-analysis, 30s refresh. Large. |
| Skills | `skills` | `SkillsTab.jsx` | Skill graph. |
| **Timeline** | `timeline` | `TimelineTab.jsx` | Subtitle = "Coherence dynamics, drift health…". **Likely what the user means by "Coherence."** Confirm. |

> ⚠️ **"Coherence" is not a literal tab label.** Best candidates: `timeline`
> (coherence dynamics) or the C(t) panel inside `cog-dash`. **Confirm with the
> user tomorrow which surface they mean** before touching it.

### Runs surface
| Tab (label) | id | Component | Notes |
|---|---|---|---|
| Overview | `overview` | `InspectOverviewTab.jsx` | Live snapshot. |
| All runs | `runs` | `RunsTab.jsx` | |
| Decisions | `brain` | `DecisionTimeline.jsx` | Absorbs Trace (Live) + Replay. |
| Inspector | `inspector` | `ContextInspectorTab.jsx` | Context inspector. |

### Analytics surface
| Tab (label) | id | Component | Notes |
|---|---|---|---|
| **Analysis** | `data` | `DataTab.jsx` | Called out. Data-analysis views — verify charts/data before restyle (see `dataviz` skill). |

### Workspace surface
| Tab (label) | id | Component | Notes |
|---|---|---|---|
| Consensus | `consensus` | `ConsensusTab.jsx` | |
| Explain | `explain` | `ExplainProjectTab.jsx` | |
| Goals | `goals` | `GoalTracker.jsx` | |
| Tasks | `tasks` | `TaskQueue.jsx` | |
| Project State | `project-state` | `ProjectStateTab.jsx` | Live world model. |

### Memory surface
| Tab (label) | id | Component | Notes |
|---|---|---|---|
| Library | `library` | `LibraryTab.jsx` | Front door for saved docs. |
| Browser | `memory` | `MemoryBrowserTab.jsx` | Has Table\|Map toggle. |

### Setup / Home
| Tab (label) | id | Component | Notes |
|---|---|---|---|
| Concepts | `concepts` | `ResearchTab.jsx` | Static explainer prose (C(t), calibration, memory types). |
| Home / Intro | `home` | `HomeTab.jsx` | Landing view — verify separately; not a standard tab. |

### Special (not standard tabs — treat with extra care)
- **Chat** (`chat`, `ChatTab.jsx`) — full-width, its own layout. Only touched
  today for the 3 new settings toggles.
- **Prompt IDE** (`prompt`, `PromptEditorTab.jsx`) — Monaco editor, full-width.

---

## Suggested order for tomorrow
1. **Confirm "Coherence"** = which tab (ask user).
2. Start with the simpler content tabs (Consensus, Explain, Project State,
   Library) to extend the pattern low-risk.
3. Then the dense Cognition tabs (Dashboard, Diagnostics, CogOS, Timeline) —
   these need real analysis of live vs placeholder data and likely the
   `dataviz` skill for any charts.
4. Analysis (`data`) last — most data-heavy, verify every chart.
