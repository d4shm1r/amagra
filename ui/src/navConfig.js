// ── 6-view navigation config (v1.4 Unified Workspace UI) ──────────────────────
// A single source of truth: each surface owns its sub-tabs. Everything else
// (the sidebar NAV, the SubNav dropdown, surface lookup, last-tab memory) is
// derived from this. `adv: true` hides a surface/sub-tab in Simple mode.
//
//   Workspace  = do work        Memory   = manage knowledge
//   Runs       = inspect runs    Research = experiment
//   Cognition  = monitor system  Setup    = configure
// Per-tab `sym` gives each tile its own mark for recognition; the surface `sym`
// stays the section signature (and the fallback). Glyphs stay in the geometric /
// serif language of the theme — never emoji, which ignore the palette.
export const SURFACES = [
  { id: "workspace", label: "Workspace", sym: "▸", desc: "Work with your project", tabs: [
    // Create tools stay ungrouped (the section's front door); planning tools
    // sit under a "Plan" sub-header — all adv, so Simple mode shows no header.
    { id: "chat",          label: "Chat",          sym: "⟡" },
    { id: "prompt",        label: "Prompt IDE",    sym: "✎" },
    { id: "consensus",     label: "Consensus",     sym: "⁂" },
    { id: "explain",       label: "Explain",       sym: "∵", adv: true },
    { id: "goals",         label: "Goals",         sym: "◎", adv: true, group: "Plan" },
    { id: "tasks",         label: "Tasks",         sym: "≣", adv: true, group: "Plan" },
    { id: "project-state", label: "Project State", sym: "⊡", adv: true, group: "Plan" },
  ]},
  { id: "runs", label: "Runs", sym: "⊙", desc: "Inspect agent executions", adv: true, tabs: [
    { id: "overview",  label: "Overview",  sym: "◉" },
    { id: "runs",      label: "All runs",  sym: "⊙" },  // "Runs" tile inside the Runs section read as a duplicate
    { id: "brain",     label: "Decisions", sym: "◬" },   // absorbs Trace (Live view) + Replay (inspector action)
    { id: "inspector", label: "Inspector", sym: "⊚" },
  ]},
  { id: "cognition", label: "Cognition", sym: "∴", desc: "Monitor system health and reasoning", adv: true, tabs: [
    // Dashboard = the at-a-glance health grid; Diagnostics folds the six focus
    // views (UCI/Risk/Verifier/Events/Plan/Policy) into one tab with internal sections.
    { id: "cog-dash",    label: "Dashboard",   sym: "▦", group: "Health" },
    { id: "diagnostics", label: "Diagnostics", sym: "✳", group: "Health" },
    { id: "cognitive",   label: "CogOS",       sym: "∞", group: "Advanced" },
    { id: "skills",      label: "Skills",      sym: "✦", group: "Advanced" },
    { id: "timeline",    label: "Timeline",    sym: "↺", group: "Advanced" },
  ]},
  { id: "memory", label: "Memory", sym: "◈", desc: "Explore stored knowledge and context", tabs: [
    // Library is the friendly front door; the technical views live under one
    // sub-header so the section leads with what most users came for.
    // Browser now hosts the old "Memory Map" as a Table|Map toggle (same
    // /memory/stats data — no reason to be two tabs). "Mind Map" was a live
    // agent-routing view, not memory — it moved to Analytics.
    { id: "library",   label: "Library",    sym: "❧" },
    { id: "memory",    label: "Browser",    sym: "◈", adv: true, group: "Under the hood" },
    { id: "knowledge", label: "Knowledge",  sym: "⊛", adv: true, group: "Under the hood" },
  ]},
  // "Analytics" (was "Research") — the surface now holds only live-data views.
  // The old "Lab" was static explainer prose, not an experiment; it moved to
  // Setup › Concepts. Mind Map (live routing network) joins Analysis here.
  { id: "research", label: "Analytics", sym: "⊹", desc: "Analyze routing, memory, and agent behavior", adv: true, tabs: [
    { id: "data",    label: "Analysis", sym: "∑" },
    { id: "mindmap", label: "Mind Map", sym: "✧" },
  ]},
  // "Setup" (was "Settings") — renamed so the surface stops colliding with the
  // Settings *modal* in the launcher's System section. Essentials (Guide, Model,
  // Releases) stay ungrouped; project-meta tabs sit under a "Project" sub-header.
  { id: "settings", label: "Setup", sym: "⚙", desc: "Configure Amagra", tabs: [
    { id: "guide",    label: "Guide",    sym: "§" },
    { id: "concepts", label: "Concepts", sym: "◇", adv: true },  // ex-"Research Lab" explainer prose (C(t), calibration, memory types…)
    { id: "model",    label: "Model",    sym: "⬡" },
    { id: "releases", label: "Releases", sym: "❖" },
    { id: "progress", label: "Progress", sym: "◐", adv: true, group: "Project" },
    { id: "promises", label: "Promises", sym: "✓", adv: true, group: "Project" },
    { id: "log",      label: "Log",      sym: "▤", adv: true, group: "Project" },
  ]},
];

// Derived lookups
export const NAV = SURFACES.map(({ id, label, sym, desc, adv }) => ({ id, label, sym, desc, adv }));
export const TABS_BY_SURFACE = Object.fromEntries(SURFACES.map(s => [s.id, s.tabs]));
export const SURFACE_BY_TAB  = Object.fromEntries(SURFACES.flatMap(s => s.tabs.map(t => [t.id, s.id])));
export const DEFAULT_TAB     = Object.fromEntries(SURFACES.map(s => [s.id, s.tabs[0].id]));
export const TAB_ALIASES     = {
  agents: "skills", history: "releases", traces: "brain", replay: "brain",
  // v1.6.4 consolidation: Memory Map folded into Browser; Research Lab → Setup › Concepts.
  map: "memory", research: "concepts",
  // Cognition consolidation (v1.6.2): the five focus tabs now live as sections
  // inside Diagnostics — redirect old ids so deep links / shortcuts still land.
  uci: "diagnostics", "risk-obs": "diagnostics", "event-log": "diagnostics",
  "plan-graph": "diagnostics", policy: "diagnostics",
};
export const VALID_TABS      = new Set(["home", ...Object.keys(SURFACE_BY_TAB)]);

// Map a raw activeTab to which top-level surface it belongs to.
export function surfaceOf(tab) {
  if (tab === "home") return "home";   // pre-nav landing, not one of the 6 views
  return SURFACE_BY_TAB[tab] || "workspace";
}

// First sub-tab of a surface that's visible in the current mode (avoids landing
// a Simple-mode user on a hidden Advanced tab).
export function firstVisibleTab(surfaceId, mode) {
  const tabs = TABS_BY_SURFACE[surfaceId] || [];
  const pick = mode === "simple" ? tabs.find(t => !t.adv) : tabs[0];
  return (pick || tabs[0])?.id;
}
