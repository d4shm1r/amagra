// ── AppLauncher ───────────────────────────────────────────────────────────────
// The single unified navigation surface. One ☰ button (in the TopBar) opens this
// full-screen, phone-launcher-style grid — replacing the old left sidebar, the top
// sub-nav, and the chat's Threads/Context/Advanced side rail.
//
// Design contract (docs/design/DESIGN_PRINCIPLES.md): chat is the clean home; navigation
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
        gap: primary ? 13 : 11, textAlign: "left", userSelect: "none",
        gridColumn: primary ? "span 2" : undefined,
        padding: "15px 15px", minHeight: 96, cursor: "pointer",
        position: "relative", overflow: "hidden",   // hosts the hover sheen sweep
        borderRadius: 14, fontFamily: FONT_UI,
        border: `1px solid ${gold ? T.accent : LUX.tileBorder}`,
        // Active keeps the same white face as idle — "current" is marked by the
        // gold border + soft halo + gold label, never a tinted fill.
        background: primary ? T.surface
          : "linear-gradient(172deg, #FFFEFB 0%, #FBF6EE 100%)",
        boxShadow: active
          ? `${LUX.tileLift}, 0 0 0 3px rgba(222,184,56,0.16), inset 0 1px 0 rgba(255,255,255,0.85)`
          : primary ? "inset 0 1px 0 rgba(255,255,255,0.7)"
          : `${LUX.tileLift}, inset 0 1px 0 rgba(255,255,255,0.85)`,
        transition: `transform 260ms ${EASE.out}, border-color ${DUR.slow} ${EASE.out}, background ${DUR.slow} ${EASE.out}, box-shadow 260ms ${EASE.out}`,
      }}
    >
      {/* app-icon-style chip — idle: cream face + gold hairline ring (the
          menu-fab / app-icon language); active/primary: filled gold. */}
      <span aria-hidden className="tile-ico" style={{
        width: primary ? 38 : 30, height: primary ? 38 : 30, borderRadius: primary ? 11 : 9, flexShrink: 0,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: primary ? 19 : 15, lineHeight: 1, fontFamily: FONT_DISPLAY,
        color: gold ? "#6C4C00" : "#8A5A00",
        background: gold ? "linear-gradient(135deg,#FFE880 0%,#DEB838 55%,#C48808 100%)"
                         : "linear-gradient(160deg,#FFFDF6 0%,#F6EEDC 100%)",
        border: `1px solid ${gold ? "transparent" : "rgba(196,136,8,0.32)"}`,
        boxShadow: gold ? "inset 0 1px 1px rgba(255,248,215,0.6)"
                        : "inset 0 1px 1px rgba(255,255,255,0.9), 0 1px 3px rgba(95,75,20,0.08)",
      }}>{sym}</span>
      <div style={{ minWidth: 0, width: "100%" }}>
        <div className="tile-label" style={{
          fontSize: primary ? 14.5 : 13, fontWeight: active || primary ? 700 : 600,
          color: active ? "#8A5A00" : primary ? T.text : "#4A3A22", letterSpacing: "-0.01em",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          transition: `color ${DUR.base} ${EASE.out}`,
        }}>{label}</div>
        {sub && <div style={{ fontSize: 10.5, color: T.muted, marginTop: 3, lineHeight: 1.3,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sub}</div>}
      </div>
    </button>
  );
}

function Section({ sym, title, desc, children, extra, delay = 0 }) {
  return (
    <section className="launch-sec" style={{ marginBottom: 48, animationDelay: `${delay}ms` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 9, marginBottom: 12, paddingLeft: 2, userSelect: "none" }}>
        <span aria-hidden style={{ fontSize: 14, color: T.accent, fontFamily: FONT_DISPLAY }}>{sym}</span>
        <h3 style={{ margin: 0, fontSize: 12, fontWeight: 700, letterSpacing: "0.14em",
          textTransform: "uppercase", color: T.muted, fontFamily: FONT_UI }}>{title}</h3>
        {desc && <span style={{ fontSize: 11, color: T.mutedLt }}>· {desc}</span>}
        {/* Gold hairline rule — the SectionLabel convention, carried into the menu. */}
        <span aria-hidden style={{ flex: 1, alignSelf: "center", height: 1, marginLeft: 6,
          background: `linear-gradient(90deg, ${T.accent}3D 0%, ${T.accent}14 45%, transparent 100%)` }} />
      </div>
      <div style={{
        display: "grid", gap: 12,
        gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
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
  // "Earlier" history is intentionally dropped from the launcher — it reads as
  // stale clutter; only recent (Today/Yesterday) threads stay surfaced here.
  return Object.entries(groups)
    .filter(([label]) => label !== "Earlier")
    .filter(([, items]) => items.length);
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
        transition: `background ${DUR.base} ${EASE.out}, border-color ${DUR.base} ${EASE.out}, transform ${DUR.base} ${EASE.out}, box-shadow ${DUR.base} ${EASE.out}`,
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
  open, onClose, activeTab, onNav, apiStatus,
  searchSignal = 0,
}) {
  const [threads, setThreads] = useState([]);
  const [query, setQuery] = useState("");
  const searchRef = useRef(null);
  const online = apiStatus === "online";
  const currentSurface = surfaceOf(activeTab);

  // Esc clears the search first; a second Esc closes the launcher.
  // Typing any printable character routes into the search field — the field is
  // never focused on open (calm by default), but responds the moment you type.
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (query) setQuery(""); else onClose();
        return;
      }
      if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey
          && document.activeElement !== searchRef.current) {
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, query]);

  // Fresh query every time the launcher opens — but no autofocus: the ☰ path
  // opens a quiet grid. Only an explicit ⌘K (searchSignal bump) focuses search.
  useEffect(() => {
    if (open) setQuery("");
  }, [open]);
  const seenSignal = useRef(searchSignal);
  useEffect(() => {
    if (!open || searchSignal === seenSignal.current) return;
    seenSignal.current = searchSignal;
    const t = setTimeout(() => searchRef.current?.focus(), 60);
    return () => clearTimeout(t);
  }, [open, searchSignal]);

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
    : SURFACES.map(s => [s, s.tabs])
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
        background: `
          radial-gradient(1100px 460px at 50% -8%, rgba(222,184,56,0.11), transparent 62%),
          radial-gradient(900px 520px at 88% 110%, rgba(196,136,8,0.06), transparent 58%),
          rgba(243,237,228,0.82)`,
        backdropFilter: "blur(14px) saturate(1.12)",
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
          z-index: 2;   /* lift above siblings so the spread shadow isn't cut in the grid gap */
          transform: translateY(-3px) scale(1.012);
          border-color: rgba(182,138,50,0.48) !important;
          background: linear-gradient(165deg, rgba(255,255,255,0.92) 0%, rgba(253,247,236,0.82) 100%) !important;
          box-shadow:
            0 18px 42px rgba(95,75,20,0.13),
            0 4px 12px rgba(95,75,20,0.06),
            0 0 0 1px rgba(222,184,56,0.10),
            inset 0 1px 0 rgba(255,255,255,0.95);
        }
        /* Gold sheen — a soft gilded light band sweeps across the tile once on
           hover-in, then rests off-canvas. Snaps back invisibly on hover-out. */
        .launch-tile::after {
          content: ''; position: absolute; top: -20%; bottom: -20%; left: 0; width: 55%;
          background: linear-gradient(100deg,
            transparent 0%, rgba(255,244,200,0.0) 18%,
            rgba(255,240,190,0.38) 50%,
            rgba(222,184,56,0.10) 66%, transparent 100%);
          transform: translateX(-130%) skewX(-16deg);
          pointer-events: none;
        }
        .launch-tile:hover::after {
          transform: translateX(310%) skewX(-16deg);
          transition: transform 780ms cubic-bezier(0.33, 0.7, 0.3, 1);
        }
        .tile-ico { transition: transform 300ms ${EASE.out}, background ${DUR.base} ${EASE.out}, box-shadow 300ms ${EASE.out}, color ${DUR.base} ${EASE.out}; }
        .launch-tile:hover .tile-ico {
          transform: translateY(-1px) scale(1.1) rotate(-3deg);
          background: linear-gradient(135deg,#FFF3C4,#EACB62) !important; color: #6C4C00 !important;
          box-shadow: 0 4px 12px rgba(196,136,8,0.30), 0 0 18px rgba(222,184,56,0.20), inset 0 1px 1px rgba(255,248,215,0.8);
        }
        .launch-tile:hover .tile-label { color: #6C4C00 !important; }
        .launch-tile:active { transform: translateY(-1px) scale(0.99); transition-duration: 90ms; }
        .launch-tile:focus-visible { outline: 2px solid ${T.accent}; outline-offset: 2px; }
        .launch-row:hover {
          background: #FFFEFA !important; border-color: rgba(196,136,8,0.30) !important;
          transform: translateX(3px); box-shadow: 0 2px 10px rgba(72,52,28,0.06);
        }
        .launch-row:focus-visible { outline: 2px solid ${T.accent}; outline-offset: 1px; }
        .launch-search::placeholder { color: ${T.muted}; }
        .launch-search:focus { border-color: ${T.accent} !important; box-shadow: 0 0 0 4px ${T.accent}1F; }
        /* Scroll surface — soft edge fades so content dissolves at the
           boundaries instead of clipping. The gold scrollbar itself is the
           app-wide one from index.css — menu and tabs scroll identically. */
        .launch-scroll {
          overscroll-behavior: contain;
          -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 18px, #000 calc(100% - 30px), transparent 100%);
          mask-image: linear-gradient(to bottom, transparent 0, #000 18px, #000 calc(100% - 30px), transparent 100%);
        }
        @media (prefers-reduced-motion: reduce) {
          .launch-tile:hover, .launch-tile:active, .launch-row:hover, .launch-tile:hover .tile-ico { transform: none; }
          .launch-tile::after, .launch-tile:hover::after { transition: none; transform: translateX(-130%) skewX(-16deg); }
          .launch-sec { animation: none; }
          [role=dialog] { animation: none !important; }
        }
      `}</style>

      {/* Panel — full viewport width; sections breathe with fluid side padding */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%", height: "100%",
          display: "flex", flexDirection: "column",
          padding: "20px clamp(20px, 4vw, 56px) 0", animation: `launchRise ${DUR.slow} ${EASE.out}`,
        }}
      >
        {/* Header: wordmark · status — the ☰/✕ toggle in the app chrome
            (top-left, same spot) is the single open/close control. */}
        <header style={{ display: "flex", alignItems: "center", gap: 16, flexShrink: 0, marginBottom: 22 }}>
          <button onClick={() => go("home")} aria-label="AMAGRA home"
            className="nav-btn"
            style={{ background: "transparent", border: "none", cursor: "pointer", padding: "2px 4px",
              marginLeft: 48,
              fontFamily: FONT_DISPLAY, fontSize: 26, fontWeight: 600, letterSpacing: "0.08em", ...LUX.goldText }}>
            AMAGRA
          </button>

          <div style={{ flex: 1 }} />
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
              borderRadius: 12, border: `1px solid ${LUX.tileBorder}`, background: LUX.tileFace,
              fontFamily: FONT_UI, fontSize: 13.5, color: T.text, outline: "none",
              transition: `border-color ${DUR.base} ${EASE.out}, box-shadow ${DUR.base} ${EASE.out}`,
            }}
          />
          <kbd aria-hidden style={{
            position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
            fontFamily: FONT_UI, fontSize: 10.5, fontWeight: 600, color: T.muted,
            padding: "2px 7px", borderRadius: 6, border: `1px solid ${LUX.tileBorder}`,
            background: "transparent", pointerEvents: "none",
          }}>{isMac ? "⌘K" : "Ctrl K"}</kbd>
        </div>

        {/* Scrollable grid — spans the full panel width */}
        <div className="launch-scroll" style={{ flex: 1, overflowY: "auto", paddingTop: 4, paddingBottom: 34 }}>
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
              <Tile key={t.id} label={t.label} sym={t.sym || s.sym} sub={t.desc}
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
        </div>
      </div>
    </div>
  );
}
