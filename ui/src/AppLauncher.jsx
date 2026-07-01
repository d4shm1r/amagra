// ── AppLauncher ───────────────────────────────────────────────────────────────
// The single unified navigation surface. One ☰ button (in the TopBar) opens this
// full-screen, phone-launcher-style grid — replacing the old left sidebar, the top
// sub-nav, and the chat's Threads/Context/Advanced side rail.
//
// Design contract (docs/DESIGN_PRINCIPLES.md): chat is the clean home; navigation
// is summoned, not always-on. Gilded Calm — cream field, gold as the signature
// (never the hierarchy system), serif AMAGRA wordmark, calm ease-out motion.
import { useEffect, useState, useCallback } from "react";
import { API } from "./api";
import { SURFACES, NAV, surfaceOf } from "./navConfig";
import { T, LUX, FONT_UI, FONT_DISPLAY, EASE, DUR } from "./theme";

// Drive ChatTab (which owns the conversation state) from here via window events.
export const chatEvent = (name, detail) =>
  window.dispatchEvent(new CustomEvent(name, { detail }));

function Tile({ label, sym, sub, active, onClick, ariaLabel }) {
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel || label}
      className="launch-tile"
      style={{
        display: "flex", flexDirection: "column", gap: 11, textAlign: "left",
        padding: "15px 15px", minHeight: 96, cursor: "pointer",
        borderRadius: 14, fontFamily: FONT_UI,
        border: `1px solid ${active ? T.accent : T.border}`,
        background: active ? `${T.accent}0E` : T.surface,
        transition: `transform ${DUR.base} ${EASE.out}, border-color ${DUR.base} ${EASE.out}, background ${DUR.base} ${EASE.out}, box-shadow ${DUR.base} ${EASE.out}`,
      }}
    >
      {/* app-icon-style chip */}
      <span aria-hidden className="tile-ico" style={{
        width: 30, height: 30, borderRadius: 9, flexShrink: 0,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: 15, lineHeight: 1, fontFamily: FONT_DISPLAY,
        color: active ? "#6C4C00" : T.accent2,
        background: active ? "linear-gradient(135deg,#FFE880 0%,#DEB838 55%,#C48808 100%)" : `${T.accent}14`,
        border: `1px solid ${active ? "transparent" : "rgba(196,136,8,0.20)"}`,
        boxShadow: active ? "inset 0 1px 1px rgba(255,248,215,0.6)" : "none",
      }}>{sym}</span>
      <div style={{ minWidth: 0, width: "100%" }}>
        <div style={{
          fontSize: 13, fontWeight: active ? 700 : 600,
          color: active ? T.text : T.mutedLt, letterSpacing: "-0.01em",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{label}</div>
        {sub && <div style={{ fontSize: 10.5, color: T.muted, marginTop: 3, lineHeight: 1.3,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sub}</div>}
      </div>
    </button>
  );
}

function Section({ sym, title, desc, children, delay = 0 }) {
  return (
    <section className="launch-sec" style={{ marginBottom: 30, animationDelay: `${delay}ms` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 9, marginBottom: 12, paddingLeft: 2 }}>
        <span aria-hidden style={{ fontSize: 14, color: T.accent, fontFamily: FONT_DISPLAY }}>{sym}</span>
        <h3 style={{ margin: 0, fontSize: 12, fontWeight: 700, letterSpacing: "0.14em",
          textTransform: "uppercase", color: T.muted, fontFamily: FONT_UI }}>{title}</h3>
        {desc && <span style={{ fontSize: 11, color: T.mutedLt }}>· {desc}</span>}
      </div>
      <div style={{
        display: "grid", gap: 10,
        gridTemplateColumns: "repeat(auto-fill, minmax(148px, 1fr))",
      }}>
        {children}
      </div>
    </section>
  );
}

export default function AppLauncher({
  open, onClose, activeTab, onNav, mode, onToggleMode, apiStatus, coherence, onModal,
}) {
  const [threads, setThreads] = useState([]);
  const online = apiStatus === "online";
  const currentSurface = surfaceOf(activeTab);

  // Esc to close.
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); onClose(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Pull recent threads when the launcher opens.
  useEffect(() => {
    if (!open || !online) return;
    fetch(`${API}/threads?limit=8`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.threads) setThreads(d.threads); })
      .catch(() => {});
  }, [open, online]);

  const go = useCallback((tabId) => { onNav(tabId); onClose(); }, [onNav, onClose]);
  const openChatPanel = useCallback((panel) => {
    onNav("chat"); chatEvent("amagra:chat-panel", panel); onClose();
  }, [onNav, onClose]);
  const newChat = useCallback(() => {
    onNav("chat"); chatEvent("amagra:new-thread"); onClose();
  }, [onNav, onClose]);
  const switchThread = useCallback((id) => {
    onNav("chat"); chatEvent("amagra:switch-thread", id); onClose();
  }, [onNav, onClose]);

  if (!open) return null;

  const surfaces = SURFACES.filter(s => mode !== "simple" || !s.adv);

  return (
    <div
      role="dialog" aria-modal="true" aria-label="AMAGRA menu"
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 9000,
        background: "rgba(240,233,223,0.72)", backdropFilter: "blur(10px)",
        animation: `launchFade ${DUR.base} ${EASE.out}`,
        display: "flex", flexDirection: "column",
      }}
    >
      <style>{`
        @keyframes launchFade { from { opacity: 0 } to { opacity: 1 } }
        @keyframes launchRise { from { opacity: 0; transform: translateY(10px) } to { opacity: 1; transform: none } }
        @keyframes tileIn { from { opacity: 0; transform: translateY(8px) } to { opacity: 1; transform: none } }
        .launch-sec { animation: tileIn ${DUR.slow} ${EASE.out} both; }
        .launch-tile:hover {
          transform: translateY(-2px);
          border-color: ${T.accent} !important; background: #FCFAF7 !important;
          box-shadow: 0 8px 22px rgba(72,52,28,0.10);
        }
        .launch-tile:hover .tile-ico { background: linear-gradient(135deg,#FFF3C4,#EACB62) !important; color: #6C4C00 !important; }
        .launch-tile:focus-visible { outline: 2px solid ${T.accent}; outline-offset: 2px; }
        .launch-pill:hover { background: ${T.surface} !important; }
        @media (prefers-reduced-motion: reduce) {
          .launch-tile:hover { transform: none; }
          .launch-sec { animation: none; }
          [role=dialog] { animation: none !important; }
        }
      `}</style>

      {/* Panel */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          margin: "0 auto", width: "100%", maxWidth: 1080, height: "100%",
          display: "flex", flexDirection: "column",
          padding: "22px 28px 0", animation: `launchRise ${DUR.slow} ${EASE.out}`,
        }}
      >
        {/* Header: wordmark · mode toggle · status · close */}
        <header style={{ display: "flex", alignItems: "center", gap: 16, flexShrink: 0, marginBottom: 22 }}>
          <button onClick={() => go("home")} aria-label="AMAGRA home"
            className="nav-btn"
            style={{ background: "transparent", border: "none", cursor: "pointer", padding: "2px 4px",
              fontFamily: FONT_DISPLAY, fontSize: 26, fontWeight: 600, letterSpacing: "0.08em", ...LUX.goldText }}>
            AMAGRA
          </button>

          <div style={{ flex: 1 }} />

          {/* Simple / Advanced */}
          <button onClick={onToggleMode} className="launch-pill"
            title={mode === "simple" ? "Simple mode — showing the essentials. Click for all tools." : "Advanced mode — every tool shown."}
            style={{
              display: "inline-flex", alignItems: "center", gap: 7, cursor: "pointer",
              padding: "6px 12px", borderRadius: 20, fontFamily: FONT_UI, fontSize: 12, fontWeight: 600,
              border: `1px solid ${T.border}`, background: "transparent", color: T.muted,
              transition: `background ${DUR.base} ${EASE.out}`,
            }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%",
              background: mode === "simple" ? T.success : T.accent }} />
            {mode === "simple" ? "Simple" : "Advanced"}
          </button>

          {/* Connection */}
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12, color: T.muted, fontFamily: FONT_UI }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%",
              background: online ? T.success : apiStatus === "checking" ? T.warn : T.error }} />
            {online ? "Connected" : apiStatus === "checking" ? "Connecting…" : "Offline"}
            {coherence && online && (
              <span style={{ fontFamily: "monospace", fontSize: 11,
                color: coherence.C >= 0.82 ? T.success : coherence.C >= 0.70 ? T.warn : T.error }}>
                · C {coherence.C?.toFixed(2)}
              </span>
            )}
          </div>

          <button onClick={onClose} aria-label="Close menu" className="nav-btn"
            style={{ background: "transparent", border: "none", cursor: "pointer",
              fontSize: 22, lineHeight: 1, color: T.muted, padding: "4px 8px", borderRadius: 8 }}>
            ✕
          </button>
        </header>

        {/* Scrollable grid */}
        <div style={{ flex: 1, overflowY: "auto", paddingBottom: 28 }}>
          {/* Conversation — the rehomed chat side rail (Threads / Context / Advanced) */}
          <Section sym="⟡" title="Conversation" desc="your chat, threads & controls">
            <Tile label="New chat" sym="＋" sub="start a fresh thread" onClick={newChat} />
            <Tile label="Context"  sym="◈" sub="what the model sees"  onClick={() => openChatPanel("context")} />
            <Tile label="Advanced" sym="⚙" sub="agent · reflect · pin" onClick={() => openChatPanel("advanced")} />
            {threads.map(t => (
              <Tile key={t.id}
                label={t.title || "Untitled"}
                sym="✎"
                sub={`${t.turn_count || 0} turn${t.turn_count === 1 ? "" : "s"}`}
                onClick={() => switchThread(t.id)}
                ariaLabel={`Open thread: ${t.title || "Untitled"}`}
              />
            ))}
          </Section>

          {/* One section per surface → its tab tiles */}
          {surfaces.map((s, i) => {
            const tabs = s.tabs.filter(t => mode !== "simple" || !t.adv);
            if (!tabs.length) return null;
            return (
              <Section key={s.id} sym={s.sym} title={s.label} desc={s.desc} delay={(i + 1) * 45}>
                {tabs.map(t => (
                  <Tile key={t.id} label={t.label} sym={s.sym}
                    active={t.id === activeTab}
                    onClick={() => go(t.id)} />
                ))}
              </Section>
            );
          })}

          {/* Global actions */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, paddingTop: 6,
            borderTop: `1px solid ${T.border}`, marginTop: 6 }}>
            {[["Settings", () => { onModal("settings"); onClose(); }],
              ["Shortcuts", () => { onModal("shortcuts"); onClose(); }],
              ["About AMAGRA", () => { onModal("about"); onClose(); }]].map(([label, fn]) => (
              <button key={label} onClick={fn} className="launch-pill"
                style={{ padding: "8px 14px", borderRadius: 20, cursor: "pointer",
                  border: `1px solid ${T.border}`, background: "transparent",
                  color: T.muted, fontFamily: FONT_UI, fontSize: 12, fontWeight: 600,
                  transition: `background ${DUR.base} ${EASE.out}` }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
