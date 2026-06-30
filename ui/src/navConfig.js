// ── 6-view navigation config (v1.4 Unified Workspace UI) ──────────────────────
// A single source of truth: each surface owns its sub-tabs. Everything else
// (the sidebar NAV, the SubNav dropdown, surface lookup, last-tab memory) is
// derived from this. `adv: true` hides a surface/sub-tab in Simple mode.
//
//   Workspace  = do work        Memory   = manage knowledge
//   Runs       = inspect runs    Research = experiment
//   Cognition  = monitor system  Settings = configure
export const SURFACES = [
  { id: "workspace", label: "Workspace", sym: "▸", desc: "Work with your project", tabs: [
    { id: "chat",          label: "Chat" },
    { id: "prompt",        label: "Prompt IDE" },
    { id: "consensus",     label: "Consensus" },
    { id: "explain",       label: "Explain",       adv: true },
    { id: "goals",         label: "Goals",         adv: true },
    { id: "tasks",         label: "Tasks",         adv: true },
    { id: "project-state", label: "Project State", adv: true },
  ]},
  { id: "runs", label: "Runs", sym: "⊙", desc: "Inspect agent executions", adv: true, tabs: [
    { id: "overview",  label: "Overview"  },
    { id: "runs",      label: "Runs"      },
    { id: "brain",     label: "Decisions" },   // absorbs Trace (Live view) + Replay (inspector action)
    { id: "inspector", label: "Inspector" },
  ]},
  { id: "cognition", label: "Cognition", sym: "∴", desc: "Monitor system health and reasoning", adv: true, tabs: [
    // Dashboard = the at-a-glance health grid; Diagnostics folds the five focus
    // views (UCI/Risk/Events/Plan/Policy) into one tab with internal sections.
    { id: "cog-dash",    label: "Dashboard",   group: "Health" },
    { id: "diagnostics", label: "Diagnostics", group: "Health" },
    { id: "cognitive",   label: "CogOS",       group: "Advanced" },
    { id: "skills",      label: "Skills",      group: "Advanced" },
    { id: "timeline",    label: "Timeline",    group: "Advanced" },
  ]},
  { id: "memory", label: "Memory", sym: "◈", desc: "Explore stored knowledge and context", tabs: [
    { id: "library",   label: "Library" },
    { id: "memory",    label: "Browser",    adv: true },
    { id: "knowledge", label: "Knowledge",  adv: true },
    { id: "map",       label: "Memory Map", adv: true },
    { id: "mindmap",   label: "Mind Map",   adv: true },
  ]},
  { id: "research", label: "Research", sym: "⊹", desc: "Experiment, analyze, and compare", adv: true, tabs: [
    { id: "research", label: "Lab" },
    { id: "data",     label: "Analysis" },
  ]},
  { id: "settings", label: "Settings", sym: "⚙", desc: "Configure Amagra", tabs: [
    { id: "guide",    label: "Guide" },
    { id: "model",    label: "Model" },
    { id: "progress", label: "Progress", adv: true },
    { id: "promises", label: "Promises", adv: true },
    { id: "log",      label: "Log",      adv: true },
    { id: "releases", label: "Releases" },
  ]},
];

// Derived lookups
export const NAV = SURFACES.map(({ id, label, sym, desc, adv }) => ({ id, label, sym, desc, adv }));
export const TABS_BY_SURFACE = Object.fromEntries(SURFACES.map(s => [s.id, s.tabs]));
export const SURFACE_BY_TAB  = Object.fromEntries(SURFACES.flatMap(s => s.tabs.map(t => [t.id, s.id])));
export const DEFAULT_TAB     = Object.fromEntries(SURFACES.map(s => [s.id, s.tabs[0].id]));
export const TAB_ALIASES     = {
  agents: "skills", history: "releases", traces: "brain", replay: "brain",
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
