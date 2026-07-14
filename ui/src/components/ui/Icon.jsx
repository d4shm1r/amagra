// Icon.jsx — THE icon set.
//
// The menu used to draw its marks as unicode glyphs (⟡ ✎ ⁂ ∵ ◎ ≣ ⊡ ⊙ ◬ ▦ ✳ ∞ ✦
// ❧ ⊛ ∑ § ⬡ ❖ ▤ ✻ ⌘ ❋). They can never look like a set: each one is pulled from
// whatever font on the machine happens to contain it, so every tile got its own
// weight, size, baseline and optical center. Some sat high, some looked bold,
// some were tiny. No amount of CSS fixes that — the shapes themselves disagree.
//
// So they are drawn here instead. Every icon is:
//
//   · one 24×24 viewBox, artwork inset to ~3px so all have the same optical size
//   · stroke-only, strokeWidth 1.6, round caps and joins — one drawn line weight
//   · currentColor — the chip decides the color, the icon never does
//
// Adding one: draw it on the same grid, stroke only, no fill. If it needs a
// different weight to "read", it is drawn wrong, not weighted wrong.

const P = {
  // ── Surfaces ──────────────────────────────────────────────
  workspace: <><path d="M3 7.5 12 3l9 4.5-9 4.5z" /><path d="M3 12l9 4.5L21 12" /><path d="M3 16.5 12 21l9-4.5" /></>,
  runs:      <><circle cx="12" cy="12" r="8.5" /><path d="M10.5 8.5 15.5 12l-5 3.5z" /></>,
  cognition: <><path d="M12 4.5a3.5 3.5 0 0 0-3.5 3.5 3 3 0 0 0-1 5.8V16a3.5 3.5 0 0 0 4.5 3.4z" /><path d="M12 4.5A3.5 3.5 0 0 1 15.5 8a3 3 0 0 1 1 5.8V16a3.5 3.5 0 0 1-4.5 3.4z" /><path d="M12 4.5v15" /></>,
  memory:    <><ellipse cx="12" cy="6.5" rx="7" ry="3" /><path d="M5 6.5v11c0 1.7 3.1 3 7 3s7-1.3 7-3v-11" /><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></>,
  analytics: <><path d="M4 20V4" /><path d="M4 20h16" /><path d="M8 16.5V12" /><path d="M12.5 16.5V7.5" /><path d="M17 16.5v-6" /></>,
  setup:     <><circle cx="12" cy="12" r="3" /><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" /></>,
  system:    <><circle cx="12" cy="12" r="3.2" /><path d="M12 3.5v3.6M12 16.9v3.6M3.5 12h3.6M16.9 12h3.6" /><path d="M6.4 6.4l2.4 2.4M15.2 15.2l2.4 2.4M17.6 6.4l-2.4 2.4M8.8 15.2l-2.4 2.4" /></>,

  // ── Workspace ─────────────────────────────────────────────
  chat:      <><path d="M20.5 14.5a2 2 0 0 1-2 2H9l-4.5 4V5.5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z" /></>,
  prompt:    <><path d="M4 20.5l.9-3.6L15.5 6.3a2.1 2.1 0 0 1 3 3L7.9 19.9z" /><path d="M14.2 7.6l3 3" /></>,
  consensus: <><circle cx="9.2" cy="12" r="5.6" /><circle cx="14.8" cy="12" r="5.6" /></>,
  explain:   <><path d="M6.5 3.5h7l4.5 4.5v12h-11.5z" /><path d="M13.5 3.5V8h4.5" /><path d="M9 12.5h6M9 16h4" /></>,
  goals:     <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="1" /></>,
  tasks:     <><path d="M4 6.8l1.5 1.5L8.5 5" /><path d="M4 13.3l1.5 1.5L8.5 11.5" /><path d="M4 19.3l1.5 1.5L8.5 17.5" /><path d="M11.5 7h8.5M11.5 13.5h8.5M11.5 20h8.5" /></>,
  project:   <><rect x="3.5" y="3.5" width="17" height="17" rx="2.5" /><path d="M3.5 9.5h17" /><path d="M9.5 9.5v11" /></>,

  // ── Runs ──────────────────────────────────────────────────
  decisions: <><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="12" cy="18.5" r="2.5" /><path d="M6 8.5v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2" /><path d="M12 12.5V16" /></>,
  inspector: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="M15.3 15.3 20.5 20.5" /></>,

  // ── Cognition ─────────────────────────────────────────────
  dashboard:   <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></>,
  diagnostics: <><path d="M3 12.5h4l2.5-6.5 4.5 13 2.5-6.5h4.5" /></>,
  cogos:       <><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M10 3.5v3.5M14 3.5v3.5M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5" /></>,
  skills:      <><circle cx="12" cy="5.5" r="2.5" /><circle cx="5.5" cy="17.5" r="2.5" /><circle cx="18.5" cy="17.5" r="2.5" /><path d="M10.2 7 7.3 15.4M13.8 7l2.9 8.4M8 17.5h8" /></>,
  timeline:    <><path d="M3.8 12a8.2 8.2 0 1 0 2.6-6" /><path d="M3.5 3.5v3.8h3.8" /><path d="M12 8v4.4l3 1.8" /></>,

  // ── Memory ────────────────────────────────────────────────
  library:   <><path d="M4.5 4.5h9a2.5 2.5 0 0 1 2.5 2.5v13H7a2.5 2.5 0 0 1-2.5-2.5z" /><path d="M16 7a2.5 2.5 0 0 1 2.5-2.5h1v13a2.5 2.5 0 0 0-2.5 2.5" /><path d="M8 9h5" /></>,
  browser:   <><rect x="3.5" y="4.5" width="17" height="15" rx="2.5" /><path d="M3.5 9h17" /><path d="M7.5 13h9M7.5 16h5" /></>,
  knowledge: <><circle cx="6" cy="17.5" r="2.5" /><circle cx="18" cy="17.5" r="2.5" /><circle cx="12" cy="5.5" r="2.5" /><path d="M12 8v3.5M12 11.5 7.4 15.6M12 11.5l4.6 4.1" /></>,

  // ── Analytics ─────────────────────────────────────────────
  analysis: <><path d="M4 20V4" /><path d="M4 20h16" /><path d="M7.5 20v-5.5M12 20V9.5M16.5 20v-8" /></>,
  mindmap:  <><circle cx="12" cy="12" r="3" /><circle cx="12" cy="4" r="2" /><circle cx="4.5" cy="17" r="2" /><circle cx="19.5" cy="17" r="2" /><path d="M12 6v3M9.6 13.8 6.2 15.9M14.4 13.8l3.4 2.1" /></>,

  // ── Setup ─────────────────────────────────────────────────
  guide:    <><path d="M12 6.5C10.6 5.2 8.6 4.5 6 4.5H4v13h2c2.6 0 4.6.7 6 2z" /><path d="M12 6.5c1.4-1.3 3.4-2 6-2h2v13h-2c-2.6 0-4.6.7-6 2z" /><path d="M12 6.5v13" /></>,
  concepts: <><path d="M12 3.5 20.5 12 12 20.5 3.5 12z" /><path d="M12 8.2 15.8 12 12 15.8 8.2 12z" /></>,
  model:    <><path d="M12 3.2 20 7.6v8.8L12 20.8 4 16.4V7.6z" /><circle cx="12" cy="12" r="3" /></>,
  releases: <><path d="M12.6 3.5H20.5v7.9l-9 9-7.9-7.9z" /><circle cx="16.6" cy="7.4" r="1.6" /></>,
  log:      <><rect x="4.5" y="3.5" width="15" height="17" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" /></>,

  // ── System ────────────────────────────────────────────────
  settings:  <><circle cx="12" cy="12" r="3" /><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" /></>,
  shortcuts: <><rect x="2.5" y="6" width="19" height="12" rx="2.5" /><path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M6.5 14h11" /></>,
  about:     <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5.5" /><path d="M12 7.8h.01" /></>,

  // ── Launcher quick-actions ────────────────────────────────
  plus:     <><path d="M12 5v14M5 12h14" /></>,
  context:  <><path d="M3.5 8 12 3.5 20.5 8 12 12.5z" /><path d="M3.5 12.5 12 17l8.5-4.5" /><path d="M3.5 16.5 12 21l8.5-4.5" /></>,
  advanced: <><path d="M4 7h9M17 7h3M4 17h3M11 17h9" /><circle cx="15" cy="7" r="2.2" /><circle cx="9" cy="17" r="2.2" /></>,
};

/** One mark from the set. `name` must exist in the registry above — an unknown
 *  name renders nothing rather than a mystery box. */
export function Icon({ name, size = 18 }) {
  const art = P[name];
  if (!art) return null;
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden focusable="false"
      style={{ display: "block", flexShrink: 0 }}
    >
      {art}
    </svg>
  );
}

/** Names the set knows — used by a dev check that navConfig can't name a
 *  missing icon. */
export const ICON_NAMES = Object.keys(P);
