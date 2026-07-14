// ── 6-view navigation config (v1.4 Unified Workspace UI) ──────────────────────
// A single source of truth: each surface owns its sub-tabs. Everything else
// (the launcher grid, surface lookup, last-tab memory) is derived from this.
// `adv: true` hides a surface/sub-tab in Simple mode.
//
//   Workspace  = do work         Memory   = manage knowledge
//   Runs       = inspect runs     Research = experiment
//   Cognition  = monitor system   Setup    = configure
//
// Two rules, so the menu reads as one set instead of a bag of parts:
//
//   `icon` — a name from components/ui/Icon.jsx. NEVER a character. The glyphs
//     this replaced (⟡ ✎ ⁂ ∵ ◎ ≣ ⊡ ⊙ ◬ ▦ ✳ ∞ ✦ ❧ ⊛ ∑ § ⬡ ❖ ▤ ✻ ⌘ ❋) each came
//     from whatever font on the machine happened to contain them, so every tile
//     had its own weight, size and baseline. Drawn icons share one grid and one
//     line weight, so they cannot drift.
//
//   `desc` — EVERY destination has one. Sixteen of them used to be blank, so the
//     grid was a mix of two-line and one-line tiles that never settled. It says
//     what the thing is FOR: lower case, no full stop — a subtitle, not a
//     sentence.
export const SURFACES = [
  { id: "workspace", label: "Workspace", icon: "workspace", desc: "Work with your project", tabs: [
    // Create tools stay ungrouped (the section's front door); planning tools
    // sit under a "Plan" sub-header — all adv, so Simple mode shows no header.
    { id: "chat",          label: "Chat",          icon: "chat",      desc: "talk to your agents" },
    { id: "prompt",        label: "Prompt IDE",    icon: "prompt",    desc: "write and test prompts" },
    { id: "consensus",     label: "Consensus",     icon: "consensus", desc: "where models agree" },
    { id: "explain",       label: "Explain",       icon: "explain",   desc: "a briefing from your decisions", adv: true },
    { id: "goals",         label: "Goals",         icon: "goals",     desc: "multi-step agent plans", adv: true, group: "Plan" },
    { id: "tasks",         label: "Tasks",         icon: "tasks",     desc: "the background work queue", adv: true, group: "Plan" },
    { id: "project-state", label: "Project State", icon: "project",   desc: "what Amagra knows about the repo", adv: true, group: "Plan" },
  ]},
  { id: "runs", label: "Runs", icon: "runs", desc: "Inspect agent executions", adv: true, tabs: [
    { id: "runs",      label: "All runs",  icon: "runs",      desc: "every execution, newest first" },
    { id: "brain",     label: "Decisions", icon: "decisions", desc: "why each agent was chosen" },   // absorbs Trace + Replay
    { id: "inspector", label: "Inspector", icon: "inspector", desc: "the context behind one answer" },
  ]},
  { id: "cognition", label: "Cognition", icon: "cognition", desc: "Monitor system health and reasoning", adv: true, tabs: [
    // Dashboard = the at-a-glance health grid; Diagnostics folds the six focus
    // views (UCI/Risk/Verifier/Events/Plan/Policy) into one tab with sections.
    { id: "cog-dash",    label: "Dashboard",   icon: "dashboard",   desc: "system health at a glance", group: "Health" },
    { id: "diagnostics", label: "Diagnostics", icon: "diagnostics", desc: "risk, events, plans, policy", group: "Health" },
    { id: "cognitive",   label: "CogOS",       icon: "cogos",       desc: "the cognitive runtime", group: "Advanced" },
    { id: "skills",      label: "Skills",      icon: "skills",      desc: "the routing skill graph", group: "Advanced" },
    { id: "timeline",    label: "Timeline",    icon: "timeline",    desc: "how the system learned", group: "Advanced" },
  ]},
  { id: "memory", label: "Memory", icon: "memory", desc: "Explore stored knowledge and context", tabs: [
    // Library is the friendly front door; the technical views live under one
    // sub-header so the section leads with what most users came for.
    { id: "library",   label: "Library",   icon: "library",   desc: "documents Amagra has read" },
    { id: "memory",    label: "Browser",   icon: "browser",   desc: "every memory it has kept", adv: true, group: "Under the hood" },
    { id: "knowledge", label: "Knowledge", icon: "knowledge", desc: "how the memories connect", adv: true, group: "Under the hood" },
  ]},
  // "Analytics" (was "Research") — the surface now holds only live-data views.
  { id: "research", label: "Analytics", icon: "analytics", desc: "Analyze routing, memory, and agent behavior", adv: true, tabs: [
    { id: "data",    label: "Analysis", icon: "analysis", desc: "routing and memory in numbers" },
    { id: "mindmap", label: "Mind Map", icon: "mindmap",  desc: "the live routing network" },
  ]},
  // "Setup" (was "Settings") — renamed so the surface stops colliding with the
  // Settings destination in the System section.
  { id: "settings", label: "Setup", icon: "setup", desc: "Configure Amagra", tabs: [
    { id: "guide",    label: "Guide",    icon: "guide",    desc: "how to use Amagra" },
    { id: "concepts", label: "Concepts", icon: "concepts", desc: "the ideas behind the engine", adv: true },
    { id: "model",    label: "Model",    icon: "model",    desc: "choose which model answers" },
    { id: "releases", label: "Releases", icon: "releases", desc: "the full build history" },
    { id: "log",      label: "Log",      icon: "log",      desc: "this session's activity", adv: true },
  ]},
  // App chrome as first-class surfaces (v1.7.1) — Settings/Shortcuts/About are
  // normal destinations, so everything in the menu behaves the same way.
  { id: "system", label: "System", icon: "system", desc: "Preferences & app info", tabs: [
    { id: "prefs",     label: "Settings",  icon: "settings",  desc: "tune behavior & interface" },
    { id: "shortcuts", label: "Shortcuts", icon: "shortcuts", desc: "every keyboard binding" },
    { id: "about",     label: "About",     icon: "about",     desc: "identity & live engine state" },
  ]},
];

// Derived lookups
export const NAV = SURFACES.map(({ id, label, icon, desc, adv }) => ({ id, label, icon, desc, adv }));
export const TABS_BY_SURFACE = Object.fromEntries(SURFACES.map(s => [s.id, s.tabs]));
export const SURFACE_BY_TAB  = Object.fromEntries(SURFACES.flatMap(s => s.tabs.map(t => [t.id, s.id])));
export const DEFAULT_TAB     = Object.fromEntries(SURFACES.map(s => [s.id, s.tabs[0].id]));
export const TAB_ALIASES     = {
  agents: "skills", history: "releases", traces: "brain", replay: "brain",
  // v1.7.x consolidation: the Runs › Overview live snapshot folded into System › About.
  overview: "about",
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
