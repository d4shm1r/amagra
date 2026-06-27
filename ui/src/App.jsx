import { useState, useEffect, useCallback, useRef, lazy, Suspense } from "react";
import { API } from "./api";
import Onboarding         from "./Onboarding";
import HomeTab            from "./HomeTab";
import ChatTab            from "./ChatTab";
import LogTab             from "./LogTab";
import RunsTab            from "./RunsTab";
import CognitionView      from "./CognitionView";
import ProgressTab        from "./ProgressTab";
import GuideTab           from "./GuideTab";
import TaskQueue          from "./TaskQueue";
import GoalTracker        from "./GoalTracker";
import MindMapInteractive from "./MindMapInteractive";
import KnowledgeGraph     from "./KnowledgeGraph";
import DecisionTimeline   from "./DecisionTimeline";
import TimelineTab        from "./TimelineTab";
import CognitiveMapTab    from "./CognitiveMapTab";
import DataTab            from "./DataTab";
import PolicyTab          from "./PolicyTab";
import CognitiveOSTab       from "./CognitiveOSTab";
import UCIDashboard         from "./UCIDashboard";
import ProjectStateTab      from "./ProjectStateTab";
import EventLogTab          from "./EventLogTab";
import RiskObservatoryTab   from "./RiskObservatoryTab";
import PlanGraphTab         from "./PlanGraphTab";
import MemoryBrowserTab     from "./MemoryBrowserTab";
import ContextInspectorTab from "./ContextInspectorTab";
import InspectOverviewTab  from "./InspectOverviewTab";
import LibraryTab          from "./LibraryTab";
import VersionHistoryTab   from "./VersionHistoryTab";
import ResearchTab         from "./ResearchTab";
import { BUILD_PHASES, VERSION } from "./constants";
// Lazy — pulls in Monaco (~3.7 MB) only when the Prompt IDE is first opened,
// keeping the initial dashboard bundle lean.
const PromptEditorTab = lazy(() => import("./PromptEditorTab"));
import ConsensusTab       from "./ConsensusTab";
import ExplainProjectTab  from "./ExplainProjectTab";
import SkillsTab          from "./SkillsTab";
import PromisesTab        from "./PromisesTab";
import ProviderSettingsTab from "./ProviderSettingsTab";
import { ApiOfflineBanner } from "./ObsShared";
import { SettingsModal, ShortcutsModal } from "./Modals";
import {
  NAV, TABS_BY_SURFACE, SURFACE_BY_TAB, DEFAULT_TAB,
  TAB_ALIASES, VALID_TABS, surfaceOf, firstVisibleTab,
} from "./navConfig";
import { T, LUX, GOLD, FONT_UI, FONT_DISPLAY } from "./theme";

// ── App-wide settings ─────────────────────────────────────────
const DEFAULT_SETTINGS = {
  defaultAgent:  "auto",   // "auto" | agent id
  reflectMode:   "",       // "" | "light" | "deep"
  temperature:   0.7,      // 0.1–1.0
  maxMemories:   5,        // 1–15
};

function loadSettings() {
  try { return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem("app_settings_v1") || "{}") }; }
  catch { return { ...DEFAULT_SETTINGS }; }
}

// ── Sidebar ───────────────────────────────────────────────────
// ── Agent mesh status display ─────────────────────────────────
const MESH_COLOR = { running: "#C48808", done: "#15803D", error: "#B42318", idle: "#D6C9B2" };

// Calm agent presence: one dot summarizing the swarm; details on click.
function AgentMesh({ mesh, collapsed }) {
  const [expanded, setExpanded] = useState(false);
  if (!mesh || !mesh.length) return null;

  const running  = mesh.filter(a => a.status === "running").length;
  const hasError = mesh.some(a => a.status === "error");
  const aggColor = hasError ? MESH_COLOR.error : running ? MESH_COLOR.running : MESH_COLOR.idle;
  const pulsing  = running > 0;

  const Dot = ({ size = 7, color = aggColor, pulse = pulsing }) => (
    <span style={{
      width: size, height: size, borderRadius: "50%", flexShrink: 0, display: "inline-block",
      background: color,
      boxShadow: pulse ? `0 0 5px ${color}88` : "none",
      animation: pulse ? "meshPulse 1.1s ease-in-out infinite" : "none",
    }} />
  );

  if (collapsed) {
    const title = hasError ? "Agent error" : running ? `${running} agent${running > 1 ? "s" : ""} working` : "Agents idle";
    return (
      <div title={title} style={{ display: "flex", justifyContent: "center", padding: "10px 0 6px", borderTop: `1px solid ${T.border}` }}>
        <Dot />
      </div>
    );
  }

  return (
    <div style={{ borderTop: `1px solid ${T.border}`, padding: "7px 8px 5px" }}>
      <button
        onClick={() => setExpanded(e => !e)}
        className="nav-btn"
        style={{
          display: "flex", alignItems: "center", gap: 8, width: "100%",
          padding: "5px 6px", border: "none", borderRadius: 6,
          background: "transparent", cursor: "pointer", fontFamily: "inherit",
        }}
      >
        <Dot />
        <span style={{ fontSize: 11, color: T.muted, flex: 1, textAlign: "left" }}>
          {hasError ? "Attention needed" : running ? `${running} working` : "Agents idle"}
        </span>
        <span style={{ fontSize: 8, color: T.muted, transform: expanded ? "rotate(180deg)" : "none", transition: "transform .15s" }}>▾</span>
      </button>

      {expanded && mesh.slice(0, 5).map((a, i) => {
        const col   = MESH_COLOR[a.status] || MESH_COLOR.idle;
        const label = a.agent.replace(/_/g, " ");
        const age   = a.age_s < 60 ? `${Math.round(a.age_s)}s` : `${Math.floor(a.age_s / 60)}m`;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 7, padding: "3px 6px 2px 8px" }}>
            <Dot size={6} color={col} pulse={a.status === "running"} />
            <span style={{ fontSize: 10.5, color: T.muted, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textTransform: "capitalize" }}>
              {label}
            </span>
            <span style={{ fontSize: 9, color: T.muted, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>{age}</span>
          </div>
        );
      })}
    </div>
  );
}

function Sidebar({ activeTab, onNav, collapsed, onToggle, apiStatus, coherence, totalQueries, agentMesh,
                   lastTabBySurface, mode, onModal, onAction, onToggleMode }) {
  const online  = apiStatus === "online";
  const surface = surfaceOf(activeTab);
  const navItems = mode === "simple" ? NAV.filter(item => !item.adv) : NAV;

  // Clicking a surface reopens the sub-tab you last used there (falling back to
  // its first visible sub-tab), so each view remembers where you left off.
  const handleNav = (surfaceId) => {
    const last = lastTabBySurface[surfaceId];
    const tabs = TABS_BY_SURFACE[surfaceId] || [];
    const lastHidden = mode === "simple" && tabs.find(t => t.id === last)?.adv;
    onNav((last && !lastHidden) ? last : firstVisibleTab(surfaceId, mode));
  };

  return (
    <aside style={{
      width: collapsed ? 52 : 168,
      minWidth: collapsed ? 52 : 168,
      height: "100%",
      background: T.surface,
      borderRight: `1px solid ${T.border}`,
      display: "flex",
      flexDirection: "column",
      transition: "width 0.2s ease, min-width 0.2s ease",
      overflow: "hidden",
      flexShrink: 0,
      userSelect: "none",
    }}>

      {/* ── Brand (rehomed from the removed top bar; click → Introduction) ── */}
      <button
        onClick={() => onNav("home")}
        title="Introduction"
        className="nav-btn"
        style={{
          display: "flex", alignItems: "center", gap: 8, width: "100%",
          padding: collapsed ? "13px 0" : "14px 14px",
          justifyContent: collapsed ? "center" : "flex-start",
          background: "transparent", border: "none",
          borderBottom: `1px solid ${T.border}`,
          cursor: "pointer", flexShrink: 0, outline: "none",
          fontFamily: "inherit",
        }}
      >
        {!collapsed && (
          <span style={{
            fontSize: 17, fontWeight: 600, letterSpacing: "0.12em",
            fontFamily: FONT_DISPLAY, whiteSpace: "nowrap", ...LUX.goldText,
          }}>
            AMAGRA
          </span>
        )}
      </button>

      {/* ── 6 primary surfaces ── */}
      <nav style={{ flex: 1, overflowY: "auto", overflowX: "hidden", padding: "8px 6px" }}>
        {navItems.map((item) => {
          const isActive = surface === item.id;
          return (
            <button
              key={item.id}
              onClick={() => handleNav(item.id)}
              title={item.desc}
              style={{
                display: "flex", alignItems: "center",
                gap: 10, width: "100%",
                padding: collapsed ? "11px 0" : "10px 10px",
                justifyContent: collapsed ? "center" : "flex-start",
                border: "none",
                background: isActive ? LUX.goldTint : "transparent",
                color: isActive ? T.text : T.muted,
                cursor: "pointer", fontFamily: "inherit",
                fontSize: 13, fontWeight: isActive ? 700 : 500,
                marginBottom: 3,
                transition: "background 0.1s, color 0.1s",
                outline: "none",
                borderRadius: 4,
                position: "relative",
              }}
              className="nav-btn"
            >
              {isActive && (
                <span style={{
                  position: "absolute", left: 0, top: "20%", bottom: "20%",
                  width: 2, background: T.accent, borderRadius: 1,
                }} />
              )}
              <span style={{
                fontSize: 14, flexShrink: 0, lineHeight: 1,
                fontFamily: "monospace",
                color: isActive ? T.accent : T.muted,
              }}>{item.sym}</span>
              {!collapsed && (
                <span style={{
                  whiteSpace: "nowrap", overflow: "hidden",
                  textOverflow: "ellipsis", flex: 1, textAlign: "left",
                }}>
                  {item.label}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Agent mesh ── */}
      <AgentMesh mesh={agentMesh} collapsed={collapsed} />

      {/* ── Footer ── */}
      <div style={{
        flexShrink: 0, borderTop: `1px solid ${T.border}`,
        padding: collapsed ? "10px 0" : "10px 12px",
      }}>
        {!collapsed && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                background: online ? T.success : T.error,
                boxShadow: online ? `0 0 6px ${T.success}88` : "none",
              }} />
              <span style={{ fontSize: 11, color: online ? T.success : T.error, fontWeight: 600 }}>
                {online ? "Connected" : apiStatus === "checking" ? "Connecting…" : "Offline"}
              </span>
              {totalQueries > 0 && (
                <span style={{ marginLeft: "auto", fontSize: 10, color: T.muted }}>
                  {totalQueries}
                </span>
              )}
            </div>
            {coherence && online && (
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ fontSize: 10, color: T.muted, letterSpacing: "0.02em" }}>C(t)</span>
                <span style={{
                  fontSize: 11, fontWeight: 700, fontVariantNumeric: "tabular-nums",
                  color: coherence.C >= 0.82 ? T.success : coherence.C >= 0.70 ? T.warn : T.error,
                }}>
                  {coherence.C?.toFixed(3)}
                </span>
              </div>
            )}
          </div>
        )}

        {/* ── Global actions (rehomed from the removed top bar) ── */}
        <SidebarActions
          collapsed={collapsed}
          mode={mode}
          onModal={onModal}
          onAction={onAction}
          onToggleMode={onToggleMode}
        />

        <button
          onClick={onToggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: "100%", padding: "6px 0", marginTop: 8,
            background: "transparent", border: `1px solid ${T.border}`,
            borderRadius: 3, cursor: "pointer", color: T.muted,
            fontSize: 11, fontFamily: "inherit",
            transition: "background 0.1s, color 0.1s",
          }}
          className="nav-btn"
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>
    </aside>
  );
}

// ── Sidebar global actions ─────────────────────────────────────
// The genuinely-unique items from the removed top MenuBar: quick Settings &
// Shortcuts modals, the Simple/Advanced toggle, and a "More" popover for the
// low-frequency long tail (About, Export, Clear Log, Docs viewers).
const DOC_ITEMS = [
  ["doc:querysignal", "QuerySignal"],
  ["doc:methodology", "Methodology"],
  ["doc:coherence",   "Coherence"],
  ["doc:memory",      "Memory"],
  ["doc:reflection",  "Reflection"],
];

function SidebarActions({ collapsed, mode, onModal, onAction, onToggleMode }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const [pos, setPos] = useState({ left: 0, bottom: 0 });
  const moreRef = useRef(null);

  useEffect(() => {
    if (!moreOpen) return;
    const close = (e) => { if (moreRef.current && !moreRef.current.contains(e.target)) setMoreOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [moreOpen]);

  const openMore = () => {
    const r = moreRef.current?.getBoundingClientRect();
    if (r) setPos({ left: r.left, bottom: window.innerHeight - r.top + 6 });
    setMoreOpen(o => !o);
  };

  const iconBtn = {
    display: "flex", alignItems: "center", justifyContent: "center",
    flex: 1, padding: "6px 0", background: "transparent",
    border: `1px solid ${T.border}`, borderRadius: 6, cursor: "pointer",
    color: T.muted, fontSize: 13, fontFamily: "inherit",
    transition: "background 0.1s, color 0.1s",
  };

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{
        display: "flex", flexDirection: collapsed ? "column" : "row", gap: 5,
      }}>
        <button className="nav-btn" style={iconBtn} title="Settings  (Ctrl+,)"
          onClick={() => onModal("settings")}>⚙</button>
        <button className="nav-btn" style={iconBtn} title="Keyboard shortcuts  (Ctrl+/)"
          onClick={() => onModal("shortcuts")}>⌨</button>
        <button ref={moreRef} className="nav-btn" style={iconBtn} title="More"
          onClick={openMore}>⋯</button>
      </div>

      {/* Simple / Advanced toggle */}
      <button
        onClick={onToggleMode}
        title={mode === "simple"
          ? "Simple mode — showing the essentials. Click for all tools."
          : "Advanced mode — all tools shown. Click to simplify."}
        className="nav-btn"
        style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          width: "100%", marginTop: 5, padding: "5px 0",
          background: "transparent", border: `1px solid ${T.border}`,
          borderRadius: 99, cursor: "pointer", fontFamily: "inherit",
          fontSize: 10.5, fontWeight: 600, color: T.accent2,
          transition: "background 0.1s",
        }}
      >
        <span style={{
          width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
          background: mode === "simple" ? T.success : T.accent,
        }} />
        {!collapsed && (mode === "simple" ? "Simple" : "Advanced")}
      </button>

      {moreOpen && (
        <div style={{
          position: "fixed", left: pos.left, bottom: pos.bottom, zIndex: 9999,
          minWidth: 188, background: "#FCFAF7", border: `1px solid ${T.border}`,
          borderRadius: 10, boxShadow: LUX.shadowMd, padding: "5px 0",
        }}>
          {[
            ["About AMAGRA",      () => onModal("about")],
            ["Export Memory…",    () => onAction("exportCsv")],
            ["Clear Session Log", () => onAction("clearLog")],
          ].map(([label, fn]) => (
            <button key={label} className="nav-btn"
              onClick={() => { fn(); setMoreOpen(false); }}
              style={moreItemStyle}>{label}</button>
          ))}
          <div style={{ height: 1, background: T.border, margin: "5px 10px" }} />
          <div style={{
            fontSize: 9, fontWeight: 700, color: T.muted, letterSpacing: "0.12em",
            textTransform: "uppercase", padding: "2px 14px 4px", userSelect: "none",
          }}>Docs</div>
          {DOC_ITEMS.map(([action, label]) => (
            <button key={action} className="nav-btn"
              onClick={() => { onAction(action); setMoreOpen(false); }}
              style={moreItemStyle}>{label}</button>
          ))}
        </div>
      )}
    </div>
  );
}

const moreItemStyle = {
  display: "block", width: "100%", textAlign: "left",
  padding: "6px 14px", border: "none", background: "transparent",
  cursor: "pointer", fontFamily: "inherit", fontSize: 12, color: T.mutedLt,
};

// ── Sub-navigation (any multi-tab surface) ────────────────────
// Calm selector: surface name + current view + one dropdown + the surface's
// one-line description, instead of a strip of always-visible tabs.
function SubNav({ surface, desc, tabs, activeTab, onNav }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const current = tabs.find(t => t.id === activeTab);

  // Group tabs into depth levels (Core / Advanced / Developer); ungrouped
  // tab sets (Settings) render as a single unlabeled column.
  const groups = [];
  tabs.forEach(t => {
    const name = t.group || "";
    let g = groups.find(x => x.name === name);
    if (!g) { g = { name, items: [] }; groups.push(g); }
    g.items.push(t);
  });

  return (
    <div style={{
      flexShrink: 0,
      display: "flex", alignItems: "center", gap: 10,
      padding: "9px 28px",
      borderBottom: `1px solid ${T.border}`,
      background: T.surface,
    }}>
      <span style={{
        fontSize: 10, fontWeight: 700, letterSpacing: "0.14em",
        textTransform: "uppercase", color: T.muted, userSelect: "none",
      }}>
        {surface}
      </span>
      <span style={{ color: T.border, userSelect: "none" }}>/</span>

      <div ref={ref} style={{ position: "relative" }}>
        <button
          onClick={() => setOpen(o => !o)}
          className="nav-btn"
          style={{
            display: "flex", alignItems: "center", gap: 7,
            padding: "4px 10px", border: `1px solid transparent`,
            borderRadius: 7, background: open ? LUX.hover : "transparent",
            cursor: "pointer", fontFamily: "inherit",
            fontSize: 12.5, fontWeight: 600, color: T.text,
          }}
        >
          {current?.label || "—"}
          <span style={{ fontSize: 9, color: T.muted, transform: open ? "rotate(180deg)" : "none", transition: "transform .15s" }}>▾</span>
        </button>

        {open && (
          <div style={{
            position: "absolute", top: "calc(100% + 6px)", left: 0,
            background: "#FCFAF7", border: `1px solid ${T.border}`,
            borderRadius: 10, boxShadow: LUX.shadowMd,
            padding: "10px 8px", zIndex: 5000,
            display: "flex", gap: 4,
          }}>
            {groups.map((g, gi) => (
              <div key={g.name || gi} style={{
                minWidth: 132,
                borderLeft: gi ? `1px solid ${T.border}66` : "none",
                paddingLeft: gi ? 10 : 2, paddingRight: 2,
              }}>
                {g.name && (
                  <div style={{
                    fontSize: 9, fontWeight: 700, color: T.muted,
                    letterSpacing: "0.12em", textTransform: "uppercase",
                    padding: "2px 12px 6px", userSelect: "none",
                  }}>
                    {g.name}
                  </div>
                )}
                {g.items.map(tab => {
                  const active = tab.id === activeTab;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => { onNav(tab.id); setOpen(false); }}
                      className="nav-btn"
                      style={{
                        display: "block", width: "100%",
                        textAlign: "left", padding: "5px 12px",
                        border: "none", borderRadius: 6, cursor: "pointer",
                        background: active ? T.surface2 : "transparent",
                        color: active ? T.text : T.mutedLt,
                        fontFamily: "inherit", fontSize: 12,
                        fontWeight: active ? 700 : 500,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      {desc && (
        <span style={{
          marginLeft: "auto", fontSize: 11, color: T.muted,
          fontStyle: "italic", userSelect: "none", whiteSpace: "nowrap",
          overflow: "hidden", textOverflow: "ellipsis",
        }}>
          {desc}
        </span>
      )}
    </div>
  );
}



// ── Root ──────────────────────────────────────────────────────
export default function App() {
  const [activeTab,    setActiveTab]    = useState("chat");
  const [researchDoc,  setResearchDoc]  = useState(null);
  const [apiStatus,    setApiStatus]    = useState("checking");
  const [activityPct,  setActivityPct]  = useState(0);
  const [litNode,      setLitNode]      = useState(null);
  const [sessionLog,   setSessionLog]   = useState([]);
  const [totalQueries, setTotalQueries] = useState(0);
  const [settings,         setSettings]         = useState(loadSettings);
  const [inspectContextId, setInspectContextId] = useState(null);
  // Per-surface "last visited sub-tab" so each view reopens where you left it.
  const [lastTabBySurface, setLastTabBySurface] = useState(() => ({ ...DEFAULT_TAB }));
  const [seedPrompt,       setSeedPrompt]       = useState(null);
  const [showOnboarding,   setShowOnboarding]   = useState(() => {
    try { return localStorage.getItem("onboarding_done_v1") !== "1"; } catch { return false; }
  });
  const dismissOnboarding = useCallback(() => {
    try { localStorage.setItem("onboarding_done_v1", "1"); } catch {}
    setShowOnboarding(false);
  }, []);

  // ── Simple / Advanced UI mode ──────────────────────────────────
  // "simple" trims the chrome to the first-run trust workflow (Chat,
  // Prompt IDE, Consensus, Library, Guide, Model); "advanced" reveals every
  // surface, menu, and diagnostic.
  // New users start simple; people who already finished onboarding keep the
  // full UI so we never hide tools out from under an existing workflow.
  const [mode, setMode] = useState(() => {
    try {
      const saved = localStorage.getItem("ui_mode_v1");
      if (saved) return saved;
      return localStorage.getItem("onboarding_done_v1") === "1" ? "advanced" : "simple";
    } catch { return "simple"; }
  });
  const setModePersisted = useCallback((next) => {
    setMode(next);
    try { localStorage.setItem("ui_mode_v1", next); } catch {}
  }, []);
  const toggleMode = useCallback(() => {
    setMode(prev => {
      const next = prev === "simple" ? "advanced" : "simple";
      try { localStorage.setItem("ui_mode_v1", next); } catch {}
      return next;
    });
  }, []);

  const updateSetting = useCallback((key, val) => {
    setSettings(prev => {
      const next = { ...prev, [key]: val };
      try { localStorage.setItem("app_settings_v1", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const [forcedAgent, setForcedAgent] = useState(() => {
    const s = loadSettings();
    return s.defaultAgent !== "auto" ? s.defaultAgent : null;
  });

  // Navigate to a tab, remembering it as the last-visited sub-tab of its surface.
  const navTo = useCallback((id) => {
    const tab = TAB_ALIASES[id] || id;
    const next = VALID_TABS.has(tab) ? tab : "chat";
    const s = SURFACE_BY_TAB[next];
    if (s) setLastTabBySurface(prev => (prev[s] === next ? prev : { ...prev, [s]: next }));
    setActiveTab(next);
  }, []);

  const handleInspect = useCallback((ctxId) => {
    setInspectContextId(ctxId);
    navTo("inspector");
  }, [navTo]);
  const [coherence,    setCoherence]    = useState(null);
  const [collapsed,    setCollapsed]    = useState(() => {
    try { return localStorage.getItem("sb_col") === "1"; } catch { return false; }
  });
  const [activeModal,  setActiveModal]  = useState(null);
  const [agentMesh,    setAgentMesh]    = useState([]);

  useEffect(() => {
    try {
      const s = localStorage.getItem("session_log_v1");
      if (s) setSessionLog(JSON.parse(s));
    } catch (_) {}
  }, []);

  useEffect(() => {
    try { localStorage.setItem("session_log_v1", JSON.stringify(sessionLog.slice(-50))); } catch (_) {}
  }, [sessionLog]);

  const checkHealth = useCallback(async () => {
    setApiStatus(prev => (prev === "online" ? prev : "checking"));
    try {
      const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(5000) });
      setApiStatus(r.ok ? "online" : "offline");
      if (r.ok) {
        try {
          const h = await fetch(`${API}/history`);
          if (h.ok) {
            const hd = await h.json();
            setTotalQueries((hd.history || hd || []).length);
          }
        } catch (_) {}
      }
    } catch { setApiStatus("offline"); }
  }, []);

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 30000);
    return () => clearInterval(id);
  }, [checkHealth]);

  useEffect(() => {
    if (apiStatus !== "online") return;
    const fn = () => {
      fetch(`${API}/agents/status`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.agents) setAgentMesh(d.agents); })
        .catch(() => {});
    };
    fn();
    const id = setInterval(fn, 4000);
    return () => clearInterval(id);
  }, [apiStatus]);

  const fetchCoherence = useCallback(() => {
    if (apiStatus !== "online") return;
    fetch(`${API}/coherence`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setCoherence(d); })
      .catch(() => {});
  }, [apiStatus]);

  useEffect(() => {
    fetchCoherence();
    const id = setInterval(fetchCoherence, 30000);
    return () => clearInterval(id);
  }, [fetchCoherence]);

  const addLog = (msg, color = T.success) => {
    const ts = new Date().toLocaleTimeString();
    setSessionLog(prev => [...prev.slice(-49), { ts, msg, color }]);
  };

  const toggleCollapsed = useCallback(() => {
    setCollapsed(c => {
      const next = !c;
      try { localStorage.setItem("sb_col", next ? "1" : "0"); } catch {}
      return next;
    });
  }, []);

  const handleMenuAction = (action) => {
    if (action === "clearLog") setSessionLog([]);
    else if (action === "toggleSidebar") toggleCollapsed();
    else if (action === "toggleMode") toggleMode();
    else if (action === "exportCsv") window.open(`${API}/memory/export.csv`, "_blank");
    else if (action.startsWith("doc:")) { setResearchDoc(action.slice(4)); navTo("research"); }
  };

  // In Simple mode, hidden surfaces/sub-tabs are unreachable from the chrome but
  // can still be hit via keyboard shortcuts — bounce off them to a visible view.
  useEffect(() => {
    if (mode !== "simple") return;
    const s = surfaceOf(activeTab);
    // Bounce off Advanced-only surfaces entirely…
    if (NAV.find(n => n.id === s)?.adv) { navTo("chat"); return; }
    // …and off Advanced sub-tabs of an otherwise-visible surface.
    if ((TABS_BY_SURFACE[s] || []).find(t => t.id === activeTab)?.adv) {
      navTo(firstVisibleTab(s, "simple"));
    }
  }, [mode, activeTab, navTo]);

  useEffect(() => {
    const handler = (e) => {
      const inInput = e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable;
      if (e.key === "Escape") { setActiveModal(null); return; }
      if (inInput) return;
      if (e.ctrlKey || e.metaKey) {
        if (e.shiftKey) {
          if (mode === "simple") return;
          switch (e.key.toLowerCase()) {
            case "e": e.preventDefault(); navTo("prompt");    break;
            case "d": e.preventDefault(); navTo("brain");     break;
            case "l": e.preventDefault(); navTo("timeline");  break;
            case "y": e.preventDefault(); navTo("policy");    break;
            case "r": e.preventDefault(); navTo("brain");     break;
            case "x": e.preventDefault(); navTo("cognitive"); break;
            case "a": e.preventDefault(); navTo("data");      break;
            case "m": e.preventDefault(); navTo("memory");    break;
            case "k": e.preventDefault(); navTo("knowledge"); break;
            case "h": e.preventDefault(); navTo("releases");  break;
            case "g": e.preventDefault(); navTo("goals");     break;
            case "q": e.preventDefault(); navTo("tasks");     break;
            case "p": e.preventDefault(); navTo("progress");  break;
            default: break;
          }
        } else {
          switch (e.key) {
            case "1": e.preventDefault(); navTo("home"); break;
            case "2": e.preventDefault(); navTo("chat"); break;
            case "3": e.preventDefault(); navTo(mode === "simple" ? "prompt" : "overview"); break;
            case "4": e.preventDefault(); navTo(mode === "simple" ? "consensus" : "cog-dash"); break;
            case "5": e.preventDefault(); navTo(mode === "simple" ? "library" : "memory"); break;
            case "6": e.preventDefault(); navTo(mode === "simple" ? "model" : "research"); break;
            case "7": e.preventDefault(); navTo("guide"); break;
            case ",": e.preventDefault(); setActiveModal("settings");  break;
            case "/": e.preventDefault(); setActiveModal("shortcuts"); break;
            case "b": case "B": e.preventDefault(); toggleCollapsed(); break;
            case "k": case "K":
              e.preventDefault();
              navTo("chat");
              setTimeout(() => document.querySelector("textarea")?.focus(), 80);
              break;
            default: break;
          }
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [mode, navTo, toggleCollapsed]);

  const MODAL_CONTENT = {
    settings: <SettingsModal settings={settings} onUpdate={updateSetting} coherence={coherence} apiStatus={apiStatus} mode={mode} onSetMode={setModePersisted} />,
    shortcuts: <ShortcutsModal mode={mode} />,
    about: (
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, fontFamily: FONT_DISPLAY, letterSpacing: "0.06em", ...LUX.goldText }}>AMAGRA</h2>
          <span style={{
            fontSize: 11, fontWeight: 700, color: T.accent,
            background: `${T.accent}18`, border: `1px solid ${T.accent}44`,
            borderRadius: 4, padding: "2px 8px", fontFamily: "monospace",
          }}>
            v{VERSION}
          </span>
          <span style={{ fontSize: 10, color: T.muted }}>
            Phase {BUILD_PHASES[BUILD_PHASES.length - 1].id} — {BUILD_PHASES[BUILD_PHASES.length - 1].title}
          </span>
        </div>
        <p style={{ margin: "0 0 8px", fontSize: 12, color: T.mutedLt, lineHeight: 1.6 }}>
          The AI you can trust with long-term work — it remembers what you've done, explains every
          decision, and runs entirely on your hardware.
        </p>
        <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px" }}>
          {[["Architecture","Signal-first routing"],["Memory","FAISS + LRU cache"],
            ["Agents","Specialist + Coordinator"],["Eval","Dual-trajectory critic"],
            ["UI","React + Vite"],["API","FastAPI / Python"]].map(([k,v]) => (
            <div key={k} style={{ fontSize: 11 }}>
              <span style={{ color: T.muted }}>{k}: </span>
              <span style={{ color: T.text }}>{v}</span>
            </div>
          ))}
        </div>
        {coherence && (
          <div style={{ marginTop: 16, padding: "10px 12px", background: T.surface, borderRadius: 4, fontSize: 11, fontFamily: "monospace", color: T.muted }}>
            C(t) = {coherence.C?.toFixed(4)} &nbsp;|&nbsp; mem = {coherence.mem_n} &nbsp;|&nbsp;
            routing = {coherence.c_routing?.toFixed(3)} &nbsp;|&nbsp;
            calib = {coherence.c_calib?.toFixed(3)}
          </div>
        )}
      </div>
    ),
  };

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden",
      background: T.bg,
      fontFamily: FONT_UI,
      color: T.text,
    }}>
      <style>{`
        @keyframes fadeIn    { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
        @keyframes dotPulse  { 0%,100%{box-shadow:0 0 0 1.5px rgba(138,99,36,0.18),0 0 8px rgba(196,136,8,0.28)} 50%{box-shadow:0 0 0 2px rgba(138,99,36,0.28),0 0 18px rgba(154,108,0,0.44),0 0 32px rgba(196,136,8,0.13)} }
        @keyframes livePulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        @keyframes dotBounce { 0%,80%,100%{transform:translateY(0);opacity:.4} 40%{transform:translateY(-5px);opacity:1} }
        @keyframes weightFade  { 0%{opacity:1;transform:scale(1.07)} 70%{opacity:1} 100%{opacity:0.45;transform:scale(1)} }
        @keyframes cursorBlink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes modalIn   { from{opacity:0;transform:scale(0.97)} to{opacity:1;transform:scale(1)} }
        @keyframes routeFadeIn { from{opacity:0;transform:translateX(-8px)} to{opacity:1;transform:translateX(0)} }
        @keyframes routePulse  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.35;transform:scale(0.85)} }
        @keyframes fbFadeOut   { 0%{opacity:1} 70%{opacity:1} 100%{opacity:0} }

        * { box-sizing: border-box; }

        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #D6C9B2; border-radius: 2px; }

        @keyframes meshPulse { 0%,100%{opacity:1} 50%{opacity:.25} }

        /* Landing-page primary gold button (ported from landing.html .btn-primary) */
        .btn-gold {
          position: relative; overflow: hidden;
          display: inline-flex; align-items: center; justify-content: center;
          background: linear-gradient(160deg, #FFE880 0%, #DEB838 25%, #C48808 60%, #9A6C00 100%);
          color: #F8F4EC; font-weight: 700; font-family: inherit; cursor: pointer;
          border: 1.5px solid rgba(242,216,155,0.28); border-radius: 40px;
          letter-spacing: -0.01em;
          box-shadow:
            5px 5px 14px rgba(72,52,28,0.22),
            -2px -2px 8px rgba(255,255,255,0.80),
            inset 0 1px 1px rgba(255,248,215,0.62),
            inset 0 -1px 2px rgba(138,99,36,0.20),
            0 0 32px rgba(196,136,8,0.13);
          text-shadow: 0 1px 2px rgba(70,44,8,0.22);
          will-change: transform;
          transition:
            transform 200ms cubic-bezier(0.34,1.56,0.64,1),
            box-shadow 200ms ease-out,
            background 160ms ease-in-out;
        }
        .btn-gold::before {
          content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 50%;
          background: linear-gradient(180deg, rgba(255,255,255,0.46) 0%, rgba(255,255,255,0) 100%);
          border-radius: 40px 40px 0 0; pointer-events: none;
        }
        .btn-gold:hover {
          background: linear-gradient(160deg, #FFE870 0%, #DDAF28 28%, #BF8400 60%, #986800 100%);
          box-shadow:
            7px 7px 18px rgba(72,52,28,0.26),
            -2px -2px 9px rgba(255,255,255,0.94),
            inset 0 1px 1px rgba(255,248,215,0.72),
            inset 0 -1px 2px rgba(138,99,36,0.24),
            0 0 44px rgba(196,136,8,0.28);
          transform: translateY(-2px);
        }
        .nav-btn:hover { background: rgba(72,52,28,0.05) !important; color: #2E2010 !important; }
        .copy-btn { opacity: 0; transition: opacity .15s; }
        .msg-wrap:hover .copy-btn { opacity: 1; }
        .agent-sel:hover { filter: brightness(0.97); }
        .card-hover:hover { border-color: rgba(196,136,8,0.45) !important; background: #FCFAF7 !important; }
        .run-row:hover { background: #F1EBE0 !important; }
      `}</style>

      {/* ── First-run onboarding overlay ── */}
      {showOnboarding && (
        <Onboarding
          onDismiss={dismissOnboarding}
          onStart={(p) => { setSeedPrompt(p); navTo("chat"); }}
          onMode={setModePersisted}
          mode={mode}
        />
      )}

      {/* ── Body row (top menu bar removed in v1.4.1; nav lives in the sidebar) ── */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <Sidebar
          activeTab={activeTab}
          onNav={navTo}
          collapsed={collapsed}
          onToggle={toggleCollapsed}
          apiStatus={apiStatus}
          coherence={coherence}
          totalQueries={totalQueries}
          agentMesh={agentMesh}
          lastTabBySurface={lastTabBySurface}
          mode={mode}
          onModal={setActiveModal}
          onAction={handleMenuAction}
          onToggleMode={toggleMode}
        />

        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
          {/* Progress bar */}
          <div style={{ height: 2, flexShrink: 0, background: T.border, position: "relative" }}>
            <div style={{
              position: "absolute", top: 0, left: 0, height: "100%",
              width: `${activityPct}%`,
              background: `linear-gradient(90deg, ${T.accent}, ${T.accent2})`,
              transition: "width 0.3s ease",
            }} />
          </div>

          {/* Calm sub-nav for any surface with more than one (visible) sub-tab */}
          {(() => {
            const s = surfaceOf(activeTab);
            const surf = NAV.find(n => n.id === s);
            if (!surf) return null;
            const tabs = (TABS_BY_SURFACE[s] || []).filter(t => mode !== "simple" || !t.adv);
            if (tabs.length <= 1) return null;
            return <SubNav surface={surf.label} desc={surf.desc} tabs={tabs} activeTab={activeTab} onNav={navTo} />;
          })()}

          {apiStatus !== "online" && (
            <div style={{ padding: "16px 28px 0", flexShrink: 0 }}>
              <ApiOfflineBanner onRetry={checkHealth} checking={apiStatus === "checking"} />
            </div>
          )}

          <div style={{
            flex: 1,
            overflow: activeTab === "chat" || activeTab === "prompt" ? "hidden" : "auto",
            padding: activeTab === "chat" || activeTab === "prompt" ? 0 : "24px 28px",
            display: activeTab === "chat" || activeTab === "prompt" ? "flex" : "block",
            flexDirection: activeTab === "chat" || activeTab === "prompt" ? "column" : undefined,
          }}>
            {activeTab === "chat"      && <ChatTab apiStatus={apiStatus} onLogAdd={addLog} onQueryComplete={() => setTotalQueries(q => q + 1)} onLitNode={setLitNode} onActivityChange={setActivityPct} onCoherenceUpdate={setCoherence} forcedAgent={forcedAgent} onForcedAgentChange={setForcedAgent} onInspect={handleInspect} defaultReflectMode={settings.reflectMode} seedPrompt={seedPrompt} onSeedConsumed={() => setSeedPrompt(null)} />}
            {activeTab === "prompt"    && (
              <Suspense fallback={
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
                              color: T.muted, fontSize: 13, fontFamily: FONT_DISPLAY, letterSpacing: "0.04em" }}>
                  Loading the Prompt IDE…
                </div>
              }>
                <PromptEditorTab />
              </Suspense>
            )}

            {/* All other tabs share one centered content column */}
            {activeTab !== "chat" && activeTab !== "prompt" && (
            <div style={{ maxWidth: 1020, margin: "0 auto", width: "100%" }}>
              {activeTab === "home"          && <HomeTab apiStatus={apiStatus} coherence={coherence} totalQueries={totalQueries} onNav={navTo} mode={mode} />}
              {activeTab === "research"      && <ResearchTab activeDoc={researchDoc} />}
              {activeTab === "knowledge"     && <KnowledgeGraph />}
              {activeTab === "mindmap"       && <MindMapInteractive litNode={litNode} onForceAgent={(id) => { setForcedAgent(id); navTo("chat"); }} />}
              {activeTab === "map"           && <CognitiveMapTab />}
              {activeTab === "library"       && <LibraryTab />}
              {activeTab === "memory"        && <MemoryBrowserTab />}
              {activeTab === "overview"      && <InspectOverviewTab onNav={navTo} />}
              {activeTab === "brain"         && <DecisionTimeline />}
              {activeTab === "runs"          && <RunsTab />}
              {activeTab === "timeline"      && <TimelineTab />}
              {activeTab === "event-log"     && <EventLogTab />}
              {activeTab === "data"          && <DataTab />}
              {activeTab === "cog-dash"      && <CognitionView />}
              {activeTab === "uci"           && <UCIDashboard />}
              {activeTab === "risk-obs"      && <RiskObservatoryTab />}
              {activeTab === "policy"        && <PolicyTab />}
              {activeTab === "cognitive"     && <CognitiveOSTab coherence={coherence} />}
              {activeTab === "inspector"     && <ContextInspectorTab contextId={inspectContextId} />}
              {activeTab === "project-state" && <ProjectStateTab />}
              {activeTab === "consensus"     && <ConsensusTab />}
              {activeTab === "explain"       && <ExplainProjectTab />}
              {activeTab === "plan-graph"    && <PlanGraphTab />}
              {activeTab === "skills"        && <SkillsTab />}
              {activeTab === "guide"         && <GuideTab />}
              {activeTab === "model"         && <ProviderSettingsTab />}
              {activeTab === "goals"         && <GoalTracker />}
              {activeTab === "tasks"         && <TaskQueue />}
              {activeTab === "log"           && <LogTab sessionLog={sessionLog} onClear={() => setSessionLog([])} />}
              {activeTab === "progress"      && <ProgressTab />}
              {activeTab === "promises"      && <PromisesTab />}
              {activeTab === "releases"      && <VersionHistoryTab />}
            </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Modal overlay ── */}
      {activeModal && MODAL_CONTENT[activeModal] && (
        <div
          onClick={() => setActiveModal(null)}
          style={{
            position: "fixed", inset: 0,
            background: "rgba(46, 32, 16, 0.30)",
            backdropFilter: "blur(3px)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 10000,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: T.surface,
              border: `1px solid ${T.border}`,
              borderRadius: 14,
              padding: "26px 30px",
              minWidth: activeModal === "shortcuts" ? 580 : 420,
              maxWidth: activeModal === "shortcuts" ? 680 : activeModal === "settings" ? 500 : 560,
              width: "92%",
              boxShadow: LUX.shadowLg,
              animation: "modalIn 0.15s ease",
              position: "relative",
            }}
          >
            <button
              onClick={() => setActiveModal(null)}
              style={{
                position: "absolute", top: 12, right: 14,
                background: "transparent", border: "none",
                color: T.muted, cursor: "pointer", fontSize: 18,
                lineHeight: 1, padding: "2px 6px",
              }}
              className="nav-btn"
            >
              ×
            </button>
            {MODAL_CONTENT[activeModal]}
          </div>
        </div>
      )}
    </div>
  );
}
