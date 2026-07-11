import { useState, useEffect, useCallback, useRef, lazy, Suspense, startTransition } from "react";
import { API } from "./api";
// Eager: the landing tabs (Chat is the default view, Home the pre-nav landing)
// plus first-run onboarding — these must paint immediately with no chunk fetch.
import Onboarding         from "./Onboarding";
import HomeTab            from "./HomeTab";
import ChatTab            from "./ChatTab";
// Lazy: every other tab is its own chunk, fetched on first visit. This keeps the
// initial bundle to Chat/Home instead of parsing ~30 heavy tab trees (charts,
// graphs, Monaco) up front, and — with startTransition in navTo + the Suspense
// boundary below — makes tab switches non-blocking instead of janking on a big
// synchronous mount. Monaco (~3.7 MB) rides in PromptEditorTab.
const LogTab             = lazy(() => import("./LogTab"));
const RunsTab            = lazy(() => import("./RunsTab"));
const CognitionView      = lazy(() => import("./CognitionView"));
const GuideTab           = lazy(() => import("./GuideTab"));
const TaskQueue          = lazy(() => import("./TaskQueue"));
const GoalTracker        = lazy(() => import("./GoalTracker"));
const MindMapInteractive = lazy(() => import("./MindMapInteractive"));
const KnowledgeGraph     = lazy(() => import("./KnowledgeGraph"));
const DecisionTimeline   = lazy(() => import("./DecisionTimeline"));
const TimelineTab        = lazy(() => import("./TimelineTab"));
const DataTab            = lazy(() => import("./DataTab"));
const CognitiveOSTab     = lazy(() => import("./CognitiveOSTab"));
const DiagnosticsTab     = lazy(() => import("./DiagnosticsTab"));
const ProjectStateTab    = lazy(() => import("./ProjectStateTab"));
const MemoryBrowserTab   = lazy(() => import("./MemoryBrowserTab"));
const ContextInspectorTab = lazy(() => import("./ContextInspectorTab"));
const InspectOverviewTab = lazy(() => import("./InspectOverviewTab"));
const LibraryTab         = lazy(() => import("./LibraryTab"));
const VersionHistoryTab  = lazy(() => import("./VersionHistoryTab"));
const ResearchTab        = lazy(() => import("./ResearchTab"));
const PromptEditorTab    = lazy(() => import("./PromptEditorTab"));
const ConsensusTab       = lazy(() => import("./ConsensusTab"));
const ExplainProjectTab  = lazy(() => import("./ExplainProjectTab"));
const SkillsTab          = lazy(() => import("./SkillsTab"));
const ProviderSettingsTab = lazy(() => import("./ProviderSettingsTab"));
import { ApiOfflineBanner } from "./ObsShared";
import { SettingsModal, ShortcutsModal, AboutView } from "./Modals";
import AppLauncher from "./AppLauncher";
import {
  SURFACE_BY_TAB, DEFAULT_TAB, TAB_ALIASES, VALID_TABS,
} from "./navConfig";
import { T, GOLD, TYPE, FONT_UI, FONT_DISPLAY } from "./theme";

// ── App-wide settings ─────────────────────────────────────────
const DEFAULT_SETTINGS = {
  defaultAgent:   "auto",  // "auto" | agent id
  reflectMode:    "",      // "" | "light" | "deep"
  temperature:    0.7,     // 0.1–1.0
  maxMemories:    5,       // 1–15
  enterToSend:    true,    // Enter sends (Shift+Enter newline) vs Ctrl+Enter sends
  showTimestamps: true,    // show per-message timestamps in chat
  reduceMotion:   false,   // near-instant animations/transitions app-wide
};

function loadSettings() {
  try { return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem("app_settings_v1") || "{}") }; }
  catch { return { ...DEFAULT_SETTINGS }; }
}




// ── Root ──────────────────────────────────────────────────────
export default function App() {
  const [activeTab,    setActiveTab]    = useState("chat");
  const [launcherOpen, setLauncherOpen] = useState(false);   // the unified ☰ app-grid menu
  const [launcherSearchSignal, setLauncherSearchSignal] = useState(0); // bumped by ⌘K → launcher focuses its search
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

  // The Simple/Advanced toggle was removed — every surface, menu, and diagnostic
  // is always shown. `mode` is pinned to "advanced" so the handful of components
  // that still branch on it render the full experience.
  const mode = "advanced";

  const updateSetting = useCallback((key, val) => {
    setSettings(prev => {
      const next = { ...prev, [key]: val };
      try { localStorage.setItem("app_settings_v1", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  // Reduce-motion preference — inject a global stylesheet that collapses every
  // animation/transition to near-zero. Isolated: no component needs to know.
  useEffect(() => {
    const id = "amagra-reduce-motion";
    let el = document.getElementById(id);
    if (settings.reduceMotion) {
      if (!el) { el = document.createElement("style"); el.id = id; document.head.appendChild(el); }
      el.textContent = "*,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important;}";
    } else if (el) {
      el.remove();
    }
  }, [settings.reduceMotion]);

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
    setLauncherOpen(false);   // urgent: the menu dismisses instantly
    // Heavy tab trees (charts, graphs) can take several frames to mount. Mark the
    // switch as a transition so React keeps the current view interactive and swaps
    // in the new tab when it's ready, rather than blocking the click on a big
    // synchronous render. Pairs with the lazy() chunks + Suspense boundary.
    startTransition(() => setActiveTab(next));
  }, []);

  const handleInspect = useCallback((ctxId) => {
    setInspectContextId(ctxId);
    navTo("inspector");
  }, [navTo]);
  const [coherence,    setCoherence]    = useState(null);

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


  const handleMenuAction = (action) => {
    if (action === "clearLog") setSessionLog([]);
    else if (action === "toggleSidebar") setLauncherOpen(o => !o);
    else if (action === "exportCsv") window.open(`${API}/memory/export.csv`, "_blank");
    else if (action.startsWith("doc:")) { setResearchDoc(action.slice(4)); navTo("concepts"); }
  };

  useEffect(() => {
    const handler = (e) => {
      const inInput = e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable;
      if (e.key === "Escape") return;
      if (inInput) return;
      if (e.ctrlKey || e.metaKey) {
        if (e.shiftKey) {
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
            case "s": e.preventDefault(); navTo("skills");    break;
            case "v": e.preventDefault(); navTo("consensus"); break;
            case "p": e.preventDefault(); navTo("model");     break;
            case "n": e.preventDefault(); navTo("chat"); window.dispatchEvent(new CustomEvent("amagra:new-thread")); break;
            default: break;
          }
        } else {
          switch (e.key) {
            case "1": e.preventDefault(); navTo("home"); break;
            case "2": e.preventDefault(); navTo("chat"); break;
            case "3": e.preventDefault(); navTo("overview"); break;
            case "4": e.preventDefault(); navTo("cog-dash"); break;
            case "5": e.preventDefault(); navTo("memory"); break;
            case "6": e.preventDefault(); navTo("data"); break;
            case "7": e.preventDefault(); navTo("guide"); break;
            case ",": e.preventDefault(); navTo("prefs");     break;
            case "/": e.preventDefault(); navTo("shortcuts"); break;
            case "b": case "B": e.preventDefault(); setLauncherOpen(o => !o); break;
            // Command-palette convention: ⌘/Ctrl+K summons the launcher with
            // search focused — the ☰ path opens it calm, no field activated.
            case "k": case "K": e.preventDefault(); setLauncherOpen(true); setLauncherSearchSignal(n => n + 1); break;
            default: break;
          }
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navTo]);

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden",
      background: T.bg,
      fontFamily: FONT_UI,
      color: T.text,
    }}>
      <style>{`
        @keyframes fadeIn    { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
        @keyframes spin      { to{transform:rotate(360deg)} }
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
            transform 200ms cubic-bezier(0.22,1,0.36,1),
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
        /* Menu launcher (☰) — a calm cream squircle with a gold hairline ring
           and gold bars, not a filled gold pill. Matches the app-icon look:
           soft-embossed white face + luminous gold border. */
        .menu-fab {
          display: inline-flex; align-items: center; justify-content: center;
          cursor: pointer; font-family: inherit;
          background: linear-gradient(155deg, #FFFEFA 0%, #FBF6EC 100%);
          border: 1.5px solid rgba(196,136,8,0.55);
          box-shadow:
            0 4px 14px rgba(72,52,28,0.10),
            0 1px 3px rgba(72,52,28,0.07),
            inset 0 1px 1px rgba(255,255,255,0.90),
            inset 0 -1px 2px rgba(196,136,8,0.07);
          transition:
            transform 200ms cubic-bezier(0.22,1,0.36,1),
            box-shadow 200ms ease-out,
            border-color 200ms ease-out;
        }
        .menu-fab:hover {
          border-color: #C48808;
          box-shadow:
            0 6px 18px rgba(72,52,28,0.14),
            0 0 22px rgba(196,136,8,0.18),
            inset 0 1px 1px rgba(255,255,255,0.95),
            inset 0 -1px 2px rgba(196,136,8,0.10);
          transform: translateY(-1px);
        }
        /* Ghost button — cream fill + luminous gold gradient border (mirrors
           landing .btn-ghost / the GitHub button). For secondary CTAs. */
        .btn-ghost {
          position: relative; overflow: hidden;
          display: inline-flex; align-items: center; justify-content: center;
          color: #9A6C00; font-weight: 700; font-family: inherit; cursor: pointer;
          letter-spacing: -0.01em; border-radius: 40px;
          background:
            linear-gradient(#FBF8F3, #FBF8F3) padding-box,
            linear-gradient(145deg, #FFE880, #DEB838, #C48808) border-box;
          border: 2px solid transparent;
          box-shadow:
            4px 4px 10px rgba(72,52,28,0.10),
            -2px -2px 7px rgba(255,255,255,0.80),
            inset 0 1px 1px rgba(255,255,255,0.92),
            inset 0 -1px 2px rgba(138,99,36,0.06);
          will-change: transform;
          transition:
            transform 200ms cubic-bezier(0.22,1,0.36,1),
            box-shadow 200ms ease-out,
            color 140ms ease;
        }
        .btn-ghost::before {
          content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 50%;
          background: linear-gradient(180deg, rgba(255,255,255,0.46) 0%, rgba(255,255,255,0) 100%);
          border-radius: 40px 40px 0 0; pointer-events: none;
        }
        .btn-ghost:hover {
          color: #6C4C00;
          box-shadow:
            6px 6px 16px rgba(72,52,28,0.14),
            -2px -2px 8px rgba(255,255,255,0.92),
            inset 0 1px 1px rgba(255,255,255,0.92),
            inset 0 -1px 2px rgba(138,99,36,0.10),
            0 0 24px rgba(196,136,8,0.13);
          transform: translateY(-1px);
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
        />
      )}

      {/* ── Body (v1.6.3: sidebar + sub-nav + brand collapsed into one ☰ menu → AppLauncher) ── */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{ position: "relative", flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
          {/* The only chrome: a single floating luxurious gold ☰ (top-left, over the content).
              No bar, no labels, no sub-nav — everything lives in the AppLauncher it opens. */}
          <button onClick={() => setLauncherOpen(o => !o)}
            aria-label={launcherOpen ? "Close menu" : "Open menu"}
            title={launcherOpen ? "Close menu  (Ctrl+B)" : "Menu  (Ctrl+B)"}
            className="menu-fab"
            style={{ position: launcherOpen ? "fixed" : "absolute", top: 13, left: 15,
              zIndex: launcherOpen ? 9010 : 50,
              width: 44, height: 44, borderRadius: 14, padding: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C48808"
              strokeWidth="2.4" strokeLinecap="round" aria-hidden
              style={{ transition: "transform 240ms cubic-bezier(0.22,1,0.36,1)",
                transform: launcherOpen ? "rotate(90deg)" : "none" }}>
              {launcherOpen
                ? <><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></>
                : <><line x1="3.5" y1="7" x2="20.5" y2="7" /><line x1="3.5" y1="12" x2="20.5" y2="12" /><line x1="3.5" y1="17" x2="20.5" y2="17" /></>}
            </svg>
          </button>

          {/* Progress bar */}
          <div style={{ height: 2, flexShrink: 0, background: T.border, position: "relative" }}>
            <div style={{
              position: "absolute", top: 0, left: 0, height: "100%",
              width: `${activityPct}%`,
              background: `linear-gradient(90deg, ${T.accent}, ${T.accent2})`,
              transition: "width 0.3s ease",
            }} />
          </div>

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
            {activeTab === "chat"      && <ChatTab apiStatus={apiStatus} onLogAdd={addLog} onQueryComplete={() => setTotalQueries(q => q + 1)} onLitNode={setLitNode} onActivityChange={setActivityPct} onCoherenceUpdate={setCoherence} forcedAgent={forcedAgent} onForcedAgentChange={setForcedAgent} onInspect={handleInspect} defaultReflectMode={settings.reflectMode} seedPrompt={seedPrompt} onSeedConsumed={() => setSeedPrompt(null)} enterToSend={settings.enterToSend} showTimestamps={settings.showTimestamps} />}
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

            {/* All other tabs share one centered content column. One Suspense
                boundary covers every lazy tab chunk (Home stays eager, so no
                fallback flash on the landing view). */}
            {activeTab !== "chat" && activeTab !== "prompt" && (
            <div style={{ maxWidth: 1020, margin: "0 auto", width: "100%" }}>
              <Suspense fallback={
                <div style={{ padding: "48px 0", textAlign: "center",
                              color: T.muted, fontSize: 13, fontFamily: FONT_DISPLAY, letterSpacing: "0.04em" }}>
                  Loading…
                </div>
              }>
              {activeTab === "home"          && <HomeTab apiStatus={apiStatus} coherence={coherence} totalQueries={totalQueries} onNav={navTo} mode={mode} />}
              {activeTab === "concepts"      && <ResearchTab activeDoc={researchDoc} />}
              {activeTab === "knowledge"     && <KnowledgeGraph />}
              {activeTab === "mindmap"       && <MindMapInteractive litNode={litNode} onForceAgent={(id) => { setForcedAgent(id); navTo("chat"); }} />}
              {activeTab === "library"       && <LibraryTab />}
              {activeTab === "memory"        && <MemoryBrowserTab />}
              {activeTab === "overview"      && <InspectOverviewTab onNav={navTo} />}
              {activeTab === "brain"         && <DecisionTimeline />}
              {activeTab === "runs"          && <RunsTab />}
              {activeTab === "timeline"      && <TimelineTab />}
              {activeTab === "data"          && <DataTab />}
              {activeTab === "cog-dash"      && <CognitionView />}
              {activeTab === "diagnostics"   && <DiagnosticsTab />}
              {activeTab === "cognitive"     && <CognitiveOSTab coherence={coherence} />}
              {activeTab === "inspector"     && <ContextInspectorTab contextId={inspectContextId} />}
              {activeTab === "project-state" && <ProjectStateTab />}
              {activeTab === "consensus"     && <ConsensusTab />}
              {activeTab === "explain"       && <ExplainProjectTab />}
              {activeTab === "skills"        && <SkillsTab />}
              {activeTab === "guide"         && <GuideTab />}
              {activeTab === "model"         && <ProviderSettingsTab />}
              {activeTab === "goals"         && <GoalTracker />}
              {activeTab === "tasks"         && <TaskQueue />}
              {activeTab === "log"           && <LogTab sessionLog={sessionLog} onClear={() => setSessionLog([])} />}
              {activeTab === "releases"      && <VersionHistoryTab />}
              {activeTab === "prefs"         && <SettingsModal settings={settings} onUpdate={updateSetting} coherence={coherence} apiStatus={apiStatus} />}
              {activeTab === "shortcuts"     && <ShortcutsModal />}
              {activeTab === "about"         && <AboutView coherence={coherence} apiStatus={apiStatus} />}
              </Suspense>
            </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Unified app-grid launcher (the ☰ menu) ── */}
      <AppLauncher
        open={launcherOpen}
        onClose={() => setLauncherOpen(false)}
        activeTab={activeTab}
        onNav={navTo}
        apiStatus={apiStatus}
        coherence={coherence}
        searchSignal={launcherSearchSignal}
      />
    </div>
  );
}
