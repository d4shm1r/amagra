import { useState, useEffect, useRef } from "react";
import { LUX, GOLD, FONT_DISPLAY } from "./theme";

const T = {
  surface2:  "#FCFAF7",
  border:    "#E0D6C4",
  text:      "#5C4030",
  muted:     "#9A7A60",
  menuBg:    "rgba(240, 235, 226, 0.92)",
  selection: "rgba(196, 136, 8, 0.14)",
};

// ── Menu structure ─────────────────────────────────────────────
// Rules enforced here:
//   1. Every tab in App.js NAV has exactly ONE menu entry.
//   2. No two items in different menus share the same action.
//   3. "Help > Release Notes" is the only intentional alias (links to Version History
//      as a discovery path — acceptable UX convention, not a navigation duplicate).

// Menus/items marked `advanced: true` (whole menu) or `adv: true` (single item)
// are hidden in Simple mode, leaving a newcomer with just Go / Docs / View / Help.
const MENUS = [
  {
    label: "Go",
    items: [
      { label: "Introduction",      action: "tab:home",         hint: "Ctrl+1" },
      { label: "Workspace",         action: "tab:chat",         hint: "Ctrl+2" },
      { label: "Runs",              action: "tab:overview",     hint: "Ctrl+3", adv: true },
      { label: "Cognition",         action: "tab:cog-dash",     hint: "Ctrl+4", adv: true },
      { label: "Memory",            action: "tab:memory",       hint: "Ctrl+5", adv: true },
      { label: "Research",          action: "tab:research",     hint: "Ctrl+6" },
      { label: "Settings",          action: "tab:guide",        hint: "Ctrl+7" },
    ],
  },
  {
    label: "Debug",
    advanced: true,
    items: [
      { label: "Routing Decisions", action: "tab:brain",        hint: "Ctrl+Shift+D" },
      { label: "Learning Timeline", action: "tab:timeline",     hint: "Ctrl+Shift+L" },
      { label: "Policy Gate",       action: "tab:policy",       hint: "Ctrl+Shift+Y" },
      { label: "Decision Replay",   action: "tab:replay",       hint: "Ctrl+Shift+R" },
    ],
  },
  {
    label: "Observe",
    advanced: true,
    items: [
      { label: "Cognitive OS",      action: "tab:cognitive",    hint: "Ctrl+Shift+X" },
      { label: "Project State",     action: "tab:project-state" },
      { label: "Event Log",         action: "tab:event-log" },
      { type: "sep" },
      { label: "Risk Observatory",  action: "tab:risk-obs" },
      { label: "Plan Graph",        action: "tab:plan-graph" },
    ],
  },
  {
    label: "Explore",
    advanced: true,
    items: [
      { label: "Memory Browser",    action: "tab:memory",       hint: "Ctrl+Shift+M" },
      { label: "Memory Map",        action: "tab:map" },
      { label: "Knowledge Graph",   action: "tab:knowledge",    hint: "Ctrl+Shift+K" },
      { label: "Mind Map",          action: "tab:mindmap" },
      { type: "sep" },
      { label: "Skills",            action: "tab:skills" },
      { label: "Data Analysis",     action: "tab:data",         hint: "Ctrl+Shift+A" },
    ],
  },
  {
    label: "Tools",
    advanced: true,
    items: [
      { label: "Prompt Editor",     action: "tab:prompt",       hint: "Ctrl+Shift+E" },
      { label: "Task Queue",        action: "tab:tasks",        hint: "Ctrl+Shift+Q" },
      { label: "Goals",             action: "tab:goals",        hint: "Ctrl+Shift+G" },
      { type: "sep" },
      { label: "Traces",            action: "tab:traces" },
      { label: "Session Log",       action: "tab:log" },
      { type: "sep" },
      { label: "Progress",          action: "tab:progress",     hint: "Ctrl+Shift+P" },
      { label: "Promises",          action: "tab:promises" },
      { label: "Version History",   action: "tab:releases",     hint: "Ctrl+Shift+H" },
    ],
  },
  {
    label: "Docs",
    items: [
      { label: "Guide",             action: "tab:guide" },
      { type: "sep", adv: true },
      { label: "QuerySignal",       action: "doc:querysignal", adv: true },
      { label: "Methodology",       action: "doc:methodology", adv: true },
      { label: "Coherence",         action: "doc:coherence",   adv: true },
      { label: "Memory",            action: "doc:memory",      adv: true },
      { label: "Reflection",        action: "doc:reflection",  adv: true },
    ],
  },
  {
    label: "View",
    items: [
      { label: "Toggle Sidebar",    action: "fn:toggleSidebar", hint: "Ctrl+B" },
      { type: "sep" },
      { label: "Settings",          action: "modal:settings",   hint: "Ctrl+," },
      { type: "sep" },
      { label: "Clear Session Log", action: "fn:clearLog", adv: true },
      { label: "Export Memory…",    action: "fn:exportCsv", adv: true },
    ],
  },
  {
    label: "Help",
    items: [
      { label: "Keyboard Shortcuts",action: "modal:shortcuts",  hint: "Ctrl+/" },
      { label: "About AMAGRA",      action: "modal:about" },
      { type: "sep" },
      { label: "Release Notes",     action: "tab:releases" },
    ],
  },
];

// Drop advanced entries in Simple mode, then collapse any separators left
// stranded at the edges or doubled up by the removal.
function visibleMenus(mode) {
  if (mode !== "simple") return MENUS;
  return MENUS
    .filter(menu => !menu.advanced)
    .map(menu => {
      const items = [];
      for (const it of menu.items) {
        if (it.adv) continue;
        if (it.type === "sep" && (!items.length || items[items.length - 1].type === "sep")) continue;
        items.push(it);
      }
      while (items.length && items[items.length - 1].type === "sep") items.pop();
      return { ...menu, items };
    })
    .filter(menu => menu.items.length);
}

const accent  = "#C4880A";
const accent2 = "#E8C040";

export default function MenuBar({ onNav, onAction, onModal, mode = "advanced", onToggleMode }) {
  const [open, setOpen]           = useState(null);
  const [hoveredTop, setHoveredTop] = useState(null);
  const ref = useRef(null);
  const menus = visibleMenus(mode);

  useEffect(() => {
    const close = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(null);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const handleItem = (action) => {
    setOpen(null);
    if (!action) return;
    if      (action.startsWith("tab:"))   onNav(action.slice(4));
    else if (action.startsWith("modal:")) onModal(action.slice(6));
    else if (action.startsWith("fn:"))    onAction(action.slice(3));
    else if (action.startsWith("doc:"))   { onNav("research"); onAction(action); }
  };

  return (
    <div ref={ref} style={{
      height: 52,
      background: "rgba(240, 235, 226, 0.86)",
      backdropFilter: "blur(32px) saturate(1.4)",
      WebkitBackdropFilter: "blur(32px) saturate(1.4)",
      borderBottom: "none",
      boxShadow: "0 1px 0 rgba(199, 154, 67, 0.18), 0 4px 20px rgba(72, 52, 28, 0.07)",
      display: "flex",
      alignItems: "stretch",
      flexShrink: 0,
      userSelect: "none",
      zIndex: 1000,
      position: "relative",
      padding: "0 10px",
    }}>
      <style>{`
        .menu-item-btn:hover { background: rgba(196,136,8,0.12) !important; color: #2E2010 !important; }
        .menu-item-btn:hover .menu-hint { opacity: 1 !important; }
        @keyframes dotPulse {
          0%, 100% { box-shadow: 0 0 0 1.5px rgba(138,99,36,0.18), 0 0 8px rgba(196,136,8,0.28); }
          50%      { box-shadow: 0 0 0 2px rgba(138,99,36,0.28), 0 0 18px rgba(154,108,0,0.44), 0 0 32px rgba(196,136,8,0.13); }
        }
      `}</style>

      {/* ── Logo / brand ── */}
      <button
        onClick={() => onNav("home")}
        title="Introduction"
        onMouseEnter={(e) => e.currentTarget.style.background = LUX.hover}
        onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
        style={{
          height: "100%",
          padding: "0 14px 0 10px",
          display: "flex", alignItems: "center", gap: 8,
          background: "transparent",
          border: "none", borderRight: `1px solid ${T.border}`,
          cursor: "pointer",
          flexShrink: 0,
          outline: "none",
          marginRight: 2,
        }}
      >
        <span style={{
          width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
          background: `radial-gradient(circle at 35% 30%, ${GOLD.g1}, ${GOLD.g5})`,
          animation: "dotPulse 4s ease-in-out infinite",
        }} />
        <span style={{
          fontSize: 19, fontWeight: 600, letterSpacing: "0.10em", whiteSpace: "nowrap",
          fontFamily: FONT_DISPLAY,
          background: `linear-gradient(135deg, ${GOLD.g5} 0%, ${GOLD.g4} 18%, ${GOLD.g3} 36%, ${GOLD.g2} 52%, ${GOLD.g3} 68%, ${GOLD.g4} 84%, ${GOLD.g5} 100%)`,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}>
          AMAGRA
        </span>
      </button>

      {menus.map((menu) => (
        <div key={menu.label} style={{ position: "relative" }}>
          <button
            onClick={() => setOpen(open === menu.label ? null : menu.label)}
            onMouseEnter={() => { setHoveredTop(menu.label); if (open !== null) setOpen(menu.label); }}
            onMouseLeave={() => setHoveredTop(null)}
            style={{
              height: "100%",
              padding: "0 14px",
              background: open === menu.label ? T.selection : "transparent",
              border: "none",
              color: (open === menu.label || hoveredTop === menu.label) ? "#6C4C00" : T.text,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500,
              letterSpacing: "-0.01em",
              fontFamily: "inherit",
              outline: "none",
              display: "flex",
              alignItems: "center",
              whiteSpace: "nowrap",
              transition: "color 160ms ease, background 160ms ease",
            }}
          >
            {menu.label}
          </button>

          {open === menu.label && (
            <div style={{
              position: "absolute",
              top: "100%",
              left: 0,
              minWidth: 230,
              background: T.surface2,
              border: `1px solid ${T.border}`,
              borderRadius: 8,
              boxShadow: "0 10px 32px rgba(62, 44, 20, 0.16)",
              zIndex: 9999,
              padding: "4px 0",
              overflow: "hidden",
            }}>
              {menu.items.map((item, i) => {
                if (item.type === "sep") {
                  return <div key={i} style={{ height: 1, background: T.border, margin: "4px 0" }} />;
                }
                return (
                  <button
                    key={i}
                    onClick={() => handleItem(item.action)}
                    className="menu-item-btn"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      width: "100%",
                      padding: "6px 14px",
                      background: "transparent",
                      border: "none",
                      color: T.text,
                      cursor: "pointer",
                      fontSize: 12,
                      fontFamily: "inherit",
                      textAlign: "left",
                      outline: "none",
                      transition: "background 0.08s",
                    }}
                  >
                    <span style={{ flex: 1 }}>{item.label}</span>
                    {item.hint && (
                      <span
                        className="menu-hint"
                        style={{
                          fontSize: 10,
                          color: T.muted,
                          fontFamily: "monospace",
                          flexShrink: 0,
                          opacity: 0.6,
                          paddingLeft: 16,
                        }}
                      >
                        {item.hint}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ))}

      {/* ── Simple / Advanced mode toggle (right-aligned) ── */}
      {onToggleMode && (
        <button
          onClick={onToggleMode}
          title={mode === "simple"
            ? "Simple mode — showing the essentials. Click for all tools."
            : "Advanced mode — all tools shown. Click to simplify."}
          onMouseEnter={(e) => e.currentTarget.style.background = "rgba(196,136,8,0.12)"}
          onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
          style={{
            marginLeft: "auto",
            alignSelf: "center",
            display: "flex", alignItems: "center", gap: 6,
            padding: "4px 12px",
            background: "transparent",
            border: `1px solid ${T.border}`,
            borderRadius: 99,
            cursor: "pointer",
            fontFamily: "inherit",
            fontSize: 11, fontWeight: 600,
            color: accent2,
            outline: "none",
            transition: "background 160ms ease",
            whiteSpace: "nowrap",
          }}
        >
          <span style={{
            width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
            background: mode === "simple" ? "#15803D" : accent,
          }} />
          {mode === "simple" ? "Simple" : "Advanced"}
        </button>
      )}
    </div>
  );
}
