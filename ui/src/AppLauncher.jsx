// ── AppLauncher ───────────────────────────────────────────────────────────────
// The single unified navigation surface. One ☰ button (in the TopBar) opens this
// full-screen, phone-launcher-style grid — replacing the old left sidebar, the top
// sub-nav, and the chat's Threads/Context/Advanced side rail.
//
// Design contract (docs/DESIGN_PRINCIPLES.md): chat is the clean home; navigation
// is summoned, not always-on. Gilded Calm — cream field, gold as the signature
// (never the hierarchy system), serif AMAGRA wordmark, calm ease-out motion.
import { Fragment, useEffect, useState, useCallback, useRef } from "react";
import { API } from "./api";
import { SURFACES, NAV, surfaceOf } from "./navConfig";
import { T, LUX, FONT_UI, FONT_DISPLAY, EASE, DUR } from "./theme";

// Drive ChatTab (which owns the conversation state) from here via window events.
export const chatEvent = (name, detail) =>
  window.dispatchEvent(new CustomEvent(name, { detail }));

// `primary` marks the menu's one visual anchor (New chat): a double-width tile
// with icon-beside-text and the gold chip worn permanently — everything else
// stays a quiet square, so the eye has a landing point.
function Tile({ label, sym, sub, active, primary, onClick, ariaLabel }) {
  const gold = active || primary;
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel || label}
      className="launch-tile"
      style={{
        display: "flex", flexDirection: primary ? "row" : "column",
        alignItems: primary ? "center" : undefined,
        gap: primary ? 13 : 11, textAlign: "left",
        gridColumn: primary ? "span 2" : undefined,
        padding: "15px 15px", minHeight: 96, cursor: "pointer",
        borderRadius: 14, fontFamily: FONT_UI,
        border: `1px solid ${gold ? T.accent : T.border}`,
        background: active ? `${T.accent}0E` : T.surface,
        transition: `transform ${DUR.base} ${EASE.out}, border-color ${DUR.base} ${EASE.out}, background ${DUR.base} ${EASE.out}, box-shadow ${DUR.base} ${EASE.out}`,
      }}
    >
      {/* app-icon-style chip */}
      <span aria-hidden className="tile-ico" style={{
        width: primary ? 38 : 30, height: primary ? 38 : 30, borderRadius: primary ? 11 : 9, flexShrink: 0,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: primary ? 19 : 15, lineHeight: 1, fontFamily: FONT_DISPLAY,
        color: gold ? "#6C4C00" : T.accent2,
        background: gold ? "linear-gradient(135deg,#FFE880 0%,#DEB838 55%,#C48808 100%)" : `${T.accent}14`,
        border: `1px solid ${gold ? "transparent" : "rgba(196,136,8,0.20)"}`,
        boxShadow: gold ? "inset 0 1px 1px rgba(255,248,215,0.6)" : "none",
      }}>{sym}</span>
      <div style={{ minWidth: 0, width: "100%" }}>
        <div style={{
          fontSize: primary ? 14.5 : 13, fontWeight: active || primary ? 700 : 600,
          color: active || primary ? T.text : T.mutedLt, letterSpacing: "-0.01em",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{label}</div>
        {sub && <div style={{ fontSize: 10.5, color: T.muted, marginTop: 3, lineHeight: 1.3,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sub}</div>}
      </div>
    </button>
  );
}

function Section({ sym, title, desc, children, extra, delay = 0 }) {
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
      {extra}
    </section>
  );
}

// ── Recent threads: compact time-grouped rows (not app tiles) ─────────────────
// Threads are history objects, not destinations — they read as a list, grouped
// by recency, so the eye separates "where can I go" (tiles) from "what was I
// doing" (rows).
function relTime(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)}d`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function threadGroups(threads) {
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 864e5).toDateString();
  const groups = { Today: [], Yesterday: [], Earlier: [] };
  for (const t of threads) {
    const d = new Date(t.updated_at || t.created_at);
    const key = isNaN(d) ? "Earlier"
      : d.toDateString() === today ? "Today"
      : d.toDateString() === yesterday ? "Yesterday" : "Earlier";
    groups[key].push(t);
  }
  return Object.entries(groups).filter(([, items]) => items.length);
}

function ThreadRow({ thread, onClick }) {
  const title = thread.title || "Untitled";
  const turns = thread.turn_count || 0;
  return (
    <button
      onClick={onClick}
      className="launch-row"
      aria-label={`Open thread: ${title}`}
      title={`${title} — ${turns} turn${turns === 1 ? "" : "s"}`}
      style={{
        display: "flex", alignItems: "center", gap: 10, width: "100%",
        padding: "8px 12px", borderRadius: 10, cursor: "pointer", textAlign: "left",
        border: "1px solid transparent", background: "transparent", fontFamily: FONT_UI,
        transition: `background ${DUR.base} ${EASE.out}, border-color ${DUR.base} ${EASE.out}`,
      }}
    >
      <span aria-hidden style={{ fontSize: 12, lineHeight: 1, color: T.accent2, fontFamily: FONT_DISPLAY, flexShrink: 0 }}>✎</span>
      <span style={{
        flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 600, color: T.mutedLt,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>{title}</span>
      <span style={{ fontSize: 10.5, color: T.muted, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
        {relTime(thread.updated_at || thread.created_at)}
      </span>
    </button>
  );
}

function RecentThreads({ threads, onSwitch }) {
  if (!threads.length) return null;
  return (
    <div style={{ marginTop: 16 }}>
      {threadGroups(threads).map(([label, items]) => (
        <div key={label} style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
            textTransform: "uppercase", color: T.muted, padding: "0 2px 5px", fontFamily: FONT_UI }}>
            {label}
          </div>
          <div style={{ display: "grid", gap: 2, gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
            {items.map(t => <ThreadRow key={t.id} thread={t} onClick={() => onSwitch(t.id)} />)}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AppLauncher({
  open, onClose, activeTab, onNav, mode, onToggleMode, apiStatus, coherence, onModal,
}) {
  const [threads, setThreads] = useState([]);
  const [query, setQuery] = useState("");
  const searchRef = useRef(null);
  const online = apiStatus === "online";
  const currentSurface = surfaceOf(activeTab);

  // Esc clears the search first; a second Esc closes the launcher.
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (query) setQuery(""); else onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, query]);

  // Fresh query + focused search every time the launcher opens (⌘K-style).
  useEffect(() => {
    if (!open) return;
    setQuery("");
    const t = setTimeout(() => searchRef.current?.focus(), 60);
    return () => clearTimeout(t);
  }, [open]);

  // Pull recent threads when the launcher opens.
  useEffect(() => {
    if (!open || !online) return;
    fetch(`${API}/threads?limit=12`)
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

  // Search filters everything the launcher can reach. A live query deliberately
  // ignores Simple mode — typing a name is an explicit ask, so Advanced tools
  // are findable even when the grid hides them.
  const q = query.trim().toLowerCase();
  const hit = (label) => label.toLowerCase().includes(q);

  const actions = [
    { label: "New chat", sym: "＋", sub: "start a fresh thread",  run: newChat, primary: true },
    { label: "Context",  sym: "◈", sub: "what the model sees",   run: () => openChatPanel("context") },
    { label: "Advanced", sym: "⚙", sub: "agent · reflect · pin", run: () => openChatPanel("advanced") },
  ].filter(a => !q || hit(a.label));

  const visibleSurfaces = (q
    ? SURFACES.map(s => [s, s.tabs.filter(t => hit(t.label) || hit(s.label))])
    : SURFACES.filter(s => mode !== "simple" || !s.adv)
        .map(s => [s, s.tabs.filter(t => mode !== "simple" || !t.adv)])
  ).filter(([, tabs]) => tabs.length);

  const shownThreads = q ? threads.filter(t => hit(t.title || "Untitled")) : threads;
  const noResults = q && !actions.length && !visibleSurfaces.length && !shownThreads.length;

  // Enter opens the top match: conversation action → first tab → first thread.
  const firstHit = !q ? null
    : actions[0] ? actions[0].run
    : visibleSurfaces[0] ? () => go(visibleSurfaces[0][1][0].id)
    : shownThreads[0] ? () => switchThread(shownThreads[0].id)
    : null;

  const isMac = /Mac/i.test(navigator.platform);

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
        .launch-tile:active { transform: scale(0.98); }
        .launch-tile:focus-visible { outline: 2px solid ${T.accent}; outline-offset: 2px; }
        .launch-pill:hover { background: ${T.surface} !important; }
        .launch-row:hover { background: ${T.surface} !important; border-color: ${T.border} !important; }
        .launch-row:focus-visible { outline: 2px solid ${T.accent}; outline-offset: 1px; }
        .launch-search::placeholder { color: ${T.muted}; }
        .launch-search:focus { border-color: ${T.accent} !important; box-shadow: 0 0 0 4px ${T.accent}1F; }
        @media (prefers-reduced-motion: reduce) {
          .launch-tile:hover, .launch-tile:active { transform: none; }
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

        {/* Search — filters tabs & threads; Enter opens the top match */}
        <div style={{ flexShrink: 0, marginBottom: 20, position: "relative", maxWidth: 560, width: "100%", alignSelf: "center" }}>
          <input
            ref={searchRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && firstHit) { e.preventDefault(); firstHit(); } }}
            placeholder="Search apps & threads…"
            aria-label="Search apps and threads"
            className="launch-search"
            style={{
              width: "100%", boxSizing: "border-box", padding: "10px 64px 10px 16px",
              borderRadius: 12, border: `1px solid ${T.border}`, background: T.surface,
              fontFamily: FONT_UI, fontSize: 13.5, color: T.text, outline: "none",
              transition: `border-color ${DUR.base} ${EASE.out}, box-shadow ${DUR.base} ${EASE.out}`,
            }}
          />
          <kbd aria-hidden style={{
            position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
            fontFamily: FONT_UI, fontSize: 10.5, fontWeight: 600, color: T.muted,
            padding: "2px 7px", borderRadius: 6, border: `1px solid ${T.border}`,
            background: "transparent", pointerEvents: "none",
          }}>{isMac ? "⌘K" : "Ctrl K"}</kbd>
        </div>

        {/* Scrollable grid */}
        <div style={{ flex: 1, overflowY: "auto", paddingBottom: 28 }}>
          {/* Conversation — the rehomed chat side rail (Threads / Context / Advanced) */}
          {(actions.length > 0 || shownThreads.length > 0) && (
            <Section sym="⟡" title="Conversation" desc="your chat, threads & controls"
              extra={<RecentThreads threads={shownThreads} onSwitch={switchThread} />}>
              {actions.map(a => (
                <Tile key={a.label} label={a.label} sym={a.sym} sub={a.sub}
                  primary={a.primary} onClick={a.run} />
              ))}
            </Section>
          )}

          {/* One section per surface → its tab tiles. Tabs carrying a `group`
              (e.g. Cognition's Health/Advanced) get full-row sub-headers. */}
          {visibleSurfaces.map(([s, tabs], i) => {
            const tile = (t) => (
              <Tile key={t.id} label={t.label} sym={t.sym || s.sym}
                active={t.id === activeTab}
                onClick={() => go(t.id)} />
            );
            const groups = [...new Set(tabs.map(t => t.group).filter(Boolean))];
            return (
              <Section key={s.id} sym={s.sym} title={s.label} desc={s.desc} delay={(i + 1) * 45}>
                {tabs.filter(t => !t.group).map(tile)}
                {groups.map(g => (
                  <Fragment key={g}>
                    <div style={{ gridColumn: "1 / -1", fontSize: 10, fontWeight: 700,
                      letterSpacing: "0.12em", textTransform: "uppercase", color: T.muted,
                      fontFamily: FONT_UI, padding: "4px 2px 0" }}>{g}</div>
                    {tabs.filter(t => t.group === g).map(tile)}
                  </Fragment>
                ))}
              </Section>
            );
          })}

          {noResults && (
            <div style={{ textAlign: "center", padding: "48px 0", color: T.muted,
              fontFamily: FONT_UI, fontSize: 13 }}>
              Nothing matches “{query.trim()}”
            </div>
          )}

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
