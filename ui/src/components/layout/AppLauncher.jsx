// ── AppLauncher ───────────────────────────────────────────────────────────────
// The single unified navigation surface. One ☰ button (in the TopBar) opens this
// full-screen, phone-launcher-style grid — replacing the old left sidebar, the top
// sub-nav, and the chat's Threads/Context/Advanced side rail.
//
// Design contract (docs/design/DESIGN_PRINCIPLES.md): chat is the clean home; navigation
// is summoned, not always-on. Gilded Calm — cream field, gold as the signature
// (never the hierarchy system), serif AMAGRA wordmark, calm ease-out motion.
import { Fragment, useEffect, useState, useCallback, useRef } from "react";
import { API } from "@/lib/api";
import { SURFACES, NAV, surfaceOf } from "@/config/navConfig";
import { loadTileMeta, markTabUsed } from "@/lib/launcherStats";
import { Icon } from "@/components/ui";
import { T, LUX, FONT_UI, FONT_DISPLAY, EASE, DUR, Z } from "@/styles/theme";

// Drive ChatTab (which owns the conversation state) from here via window events.
export const chatEvent = (name, detail) =>
  window.dispatchEvent(new CustomEvent(name, { detail }));

// One tile = icon chip + label + description, and every tile must be the SAME
// object wearing different words. Two things make that true:
//
//   · Fixed internal geometry. The chip, the label line, and a TWO-LINE
//     description box are each a fixed height, so a tile with a one-line
//     description and a tile with a two-line one occupy the identical box and
//     their bottoms line up. (Before, height was fixed but the text was
//     top-packed, so a ≤34-char description that wrapped in a narrow column but
//     not a wide one left a different bottom gap per tile — the unevenness.)
//   · One color ladder, from tokens. Idle: label T.mutedLt over description
//     T.muted (description always one step lighter). Hover: both warm one step
//     together (see .tile-label / .tile-sub in the CSS), so the whole button
//     responds as a unit, not just the chip.
//
// `primary` marks the menu's one anchor (New chat): double-width, icon beside
// text, gold chip worn permanently — the one deliberate exception.
// Geometry. Everything is border-box (styles/index.css), so TILE_H has to pay for
// the border and both pads as well as the content:
//
//   2 border + 14 pad + 32 chip + 10 gap
//     + 16.9 label (13px × 1.3) + 3 + 30 description + 3 + 14 metadata
//     + 14 pad                                                  = 138.9 → 140
//
// The ~1px of slack is deliberate but thin: if you add a row here, redo the sum.
// The old 124 predated the metadata row and was itself ~2px under (the border was
// missing from the tally) — invisible only because the reserved 2-line
// description box almost never fills to its last pixel. A clipped metadata line
// would not have been anywhere near as forgiving.
//
// `meta` is the contextual footer — "18 prompts", "3 running", "used 2h ago"
// (see lib/launcherStats.js). It is what makes the grid read as a command center
// rather than a menu: the tile reports the state of the thing it opens. It sits
// bottom-RIGHT, small and recessive, so it registers as instrument reading and
// never competes with the label. Its row is reserved on every tile whether or
// not that tile has anything to report — the same rule as the description box,
// for the same reason: tiles must stay one object wearing different words.
const TILE_H = 140;   // chip + label + reserved 2-line description + meta row + air
const SUB_H  = 30;    // 2 lines at 10.5px / 1.4 — reserved whether used or not
const META_H = 14;    // one 9.5px line — reserved whether used or not

// The active tile's face: a fade, not a panel. Three layers —
//   · a warm pool high-left and a fainter gold one low-right: the "dimmed
//     lights", placed off-centre so what light there is has a direction. Both
//     are wide and low-alpha; a tight or strong highlight reads as gloss.
//   · a barely-there wash underneath, near-white at the crown drifting to the
//     faintest honey at the base.
// Tuned DOWN twice. The first pass (base ending #F7E9C4, pools at .95/.20) read
// as a distinctly yellow card — you saw the gradient before you saw the tile.
// The target is that you should not be able to point at where the gold starts:
// the tile is just *warmer* than its neighbours, and the halo and border do the
// actual work of saying "you are here". If this ever stops registering, widen
// the halo before you deepen the fill — the fill is the thing that goes garish
// first. Dimming also bought back contrast: T.muted on the deepest tone here is
// 5.35:1, up from 4.61:1 when the base was #F7E9C4.
const ACTIVE_FACE = `
  radial-gradient(150px 90px at 20% 6%,   rgba(255,247,224,0.55), transparent 76%),
  radial-gradient(190px 110px at 90% 100%, rgba(222,184,56,0.07), transparent 78%),
  linear-gradient(168deg, #FFFEFA 0%, #FFFBF2 60%, #FDF6E8 100%)`;

// Hover on the tile you are already on: the same lamp, barely turned up. It must
// be its own rule because the generic hover sets a white face with !important,
// which would wipe the fade off the active tile entirely.
const ACTIVE_FACE_HOVER = `
  radial-gradient(150px 90px at 20% 6%,   rgba(255,250,235,0.70), transparent 76%),
  radial-gradient(190px 110px at 90% 100%, rgba(222,184,56,0.10), transparent 78%),
  linear-gradient(168deg, #FFFFFC 0%, #FFFDF7 60%, #FEF9EE 100%)`;

// The tile label's gilded ramp. It is NOT LUX.goldText: that ramp is built for
// the 26px AMAGRA wordmark and peaks at #DEB838, which measures ~2.2:1 on cream —
// fine for a display mark you recognise by shape, not for the 13px word that
// tells you where a tile goes. This ramp keeps the metallic top-lit read (light
// crown, deep base) while holding the body of every glyph in the deep golds that
// clear AA. The bright crown still dips under it; see the note on .tile-label.
const LABEL_GOLD = {
  background: "linear-gradient(180deg, #C89A3A 0%, #9A6C00 58%, #7A5200 100%)",
  WebkitBackgroundClip: "text",
  WebkitTextFillColor: "transparent",
  backgroundClip: "text",
};

function Tile({ label, icon, sub, meta, active, primary, onClick, ariaLabel }) {
  const gold = active || primary;
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel || label}
      className={`launch-tile${active ? " is-active" : ""}`}
      style={{
        display: "flex", flexDirection: primary ? "row" : "column",
        alignItems: primary ? "center" : undefined,
        gap: primary ? 13 : 10, textAlign: "left", userSelect: "none",
        gridColumn: primary ? "span 2" : undefined,
        padding: "14px 15px 14px", height: TILE_H, cursor: "pointer",
        position: "relative", overflow: "hidden",   // hosts the hover sheen sweep
        borderRadius: 14, fontFamily: FONT_UI,
        border: `1px solid ${gold ? T.accent : LUX.tileBorder}`,
        // Active is a lit gold panel. This reverses the tile's original rule
        // ("same white face as idle, never a tinted fill") — that rule existed
        // when active also owned a filled gold icon chip and hover owned a 3px
        // lift, so the three states were already separable without it. Both of
        // those are gone now, and border-alone left hover and active looking
        // nearly identical. The fill is what tells them apart again.
        background: active ? ACTIVE_FACE
          : primary ? T.surface
          : "linear-gradient(172deg, #FFFEFB 0%, #FBF6EE 100%)",
        // The inset glow is the light *inside* the panel; the outer halo is the
        // same light escaping past the border. They are one effect in two halves,
        // which is why the inset alpha and the halo alpha move together.
        boxShadow: active
          ? `inset 0 1px 0 rgba(255,255,255,0.95),
             inset 0 0 34px rgba(255,236,180,0.30),
             0 0 0 3px rgba(222,184,56,0.16),
             0 10px 30px rgba(140,105,35,0.12)`
          : primary ? "inset 0 1px 0 rgba(255,255,255,0.7)"
          : `${LUX.tileLift}, inset 0 1px 0 rgba(255,255,255,0.85)`,
        // No `transform` in the list on purpose — hover is gilding, not motion.
        // It stays only on :active, which sets its own 90ms duration.
        transition: `transform 90ms ${EASE.out}, border-color ${DUR.slow} ${EASE.out}, background ${DUR.slow} ${EASE.out}, box-shadow ${DUR.slow} ${EASE.out}`,
      }}
    >
      {/* The app icon — the bare drawn mark in gold, sitting straight on the tile
          face. It used to wear a chip (cream gradient panel + hairline ring +
          inset highlight, filled gold when active): a frame around a frame, since
          the tile is already a bordered card. Removing it leaves the icon itself
          as the only thing there is to look at.
          The 32px box STAYS — it is a layout slot, not a visual, and TILE_H's sum
          depends on it. What was removed is only paint: background, border,
          shadow, radius. Because the frame no longer supplies the optical mass,
          the mark grows into the freed space (17→24) or it reads as a small thing
          adrift in an empty square. 24 in a 32 slot leaves 4px a side, which is
          the floor — past this the icon needs a bigger slot, and the slot is in
          TILE_H's sum.
          Colour is the whole state ladder now: T.accent at rest, deepening to
          T.accent2 when the tile is active or hovered. */}
      <span aria-hidden className="tile-ico" style={{
        width: primary ? 38 : 32, height: primary ? 38 : 32, flexShrink: 0,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        color: gold ? T.accent2 : T.accent,
        transition: `color ${DUR.base} ${EASE.out}`,
      }}>
        <Icon name={icon} size={primary ? 28 : 24} />
      </span>
      <div style={{ minWidth: 0, width: "100%" }}>
        {/* Gilded on every tile, in every state, hover included. Because the fill
            is a clipped gradient there is no `color` left to animate, which is
            the point: the label is the one thing on the tile that never reacts.
            Current-ness is carried by weight (700) and the tile's gold border,
            not by the label changing colour under the cursor.
            Legibility note: the crown of the ramp (#C89A3A) sits near 3.4:1, under
            the AA floor the rest of the palette holds. It is the top ~2px of a
            13px glyph and the mass of the letterform is 4.5:1+, so the word stays
            readable — but this is the one place in the app where gold-as-text is
            not fully AA, and brightening the crown further would make it worse. */}
        <div className="tile-label" style={{
          fontSize: primary ? 14.5 : 13, fontWeight: active || primary ? 700 : 600,
          ...LABEL_GOLD, letterSpacing: "-0.01em",
          lineHeight: 1.3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{label}</div>
        {/* Reserved to a fixed two-line box, so a one-line and a two-line
            description occupy the same height and every tile's content ends on
            the same baseline. Clamps rather than cutting a word with an ellipsis. */}
        {sub && <div className="tile-sub" style={{
          fontSize: 10.5, color: T.muted, marginTop: 3, lineHeight: 1.4,
          ...(primary ? null : { height: SUB_H }),
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          overflow: "hidden", transition: `color ${DUR.base} ${EASE.out}`,
        }}>{sub}</div>}
        {/* Contextual footer. It has to sit BELOW the description in the reading
            order without going lighter than it: T.muted is already the last tier
            that clears AA on cream (see styles/theme.js), so recession here is
            bought with size (9.5 vs 10.5) and right-alignment instead of colour.
            The eye reads label → description → number, and can skip the number.
            `live` counts (something running right now) carry a slow gold pulse —
            a heartbeat every few seconds, not a blinking alert; a grid of 25
            constantly-animating dots would be the opposite of calm. */}
        {!primary && (
          <div className="tile-meta" style={{
            height: META_H, marginTop: 3, display: "flex", alignItems: "center",
            justifyContent: "flex-end", gap: 5,
            fontSize: 9.5, letterSpacing: "0.04em", color: T.muted,
            fontVariantNumeric: "tabular-nums", opacity: meta ? 1 : 0,
            transition: `color ${DUR.base} ${EASE.out}, opacity ${DUR.base} ${EASE.out}`,
          }}>
            {meta?.live && <span aria-hidden className="tile-pulse" style={{
              width: 5, height: 5, borderRadius: "50%", flexShrink: 0,
              background: T.accent,
            }} />}
            {meta?.label || ""}
          </div>
        )}
      </div>
    </button>
  );
}

function Section({ icon, title, desc, children, extra, delay = 0 }) {
  return (
    <section className="launch-sec" style={{ marginBottom: 48, animationDelay: `${delay}ms` }}>
      {/* alignItems: center, not baseline — an SVG has no baseline to sit on, so
          `baseline` dropped the section mark a couple of pixels below its label. */}
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 12, paddingLeft: 2, userSelect: "none" }}>
        <span aria-hidden style={{ color: T.accent, display: "inline-flex" }}>
          <Icon name={icon} size={15} />
        </span>
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
      {/* The last glyph in the menu, now drawn like the rest — a thread row used
          a bare ✎ that sat a pixel high and a shade heavier than the tile marks. */}
      <span aria-hidden style={{ color: T.accent2, display: "inline-flex", flexShrink: 0 }}>
        <Icon name="chat" size={13} />
      </span>
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
  const [tileMeta, setTileMeta] = useState({});
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

  // Tile metadata. Resolves in two beats by design: the local last-used map lands
  // synchronously-ish on the first tick, the live counts land when the fan-out
  // returns. `alive` guards a close mid-flight — the launcher unmounts freely and
  // a late stats response must not setState into a dead component.
  useEffect(() => {
    if (!open) return;
    let alive = true;
    loadTileMeta({ online }).then(m => { if (alive) setTileMeta(m); });
    return () => { alive = false; };
  }, [open, online]);

  const go = useCallback((tabId) => { markTabUsed(tabId); onNav(tabId); onClose(); }, [onNav, onClose]);
  const openChatPanel = useCallback((panel) => {
    markTabUsed("chat"); onNav("chat"); chatEvent("amagra:chat-panel", panel); onClose();
  }, [onNav, onClose]);
  const newChat = useCallback(() => {
    markTabUsed("chat"); onNav("chat"); chatEvent("amagra:new-thread"); onClose();
  }, [onNav, onClose]);
  const switchThread = useCallback((id) => {
    markTabUsed("chat"); onNav("chat"); chatEvent("amagra:switch-thread", id); onClose();
  }, [onNav, onClose]);

  if (!open) return null;

  // Search filters everything the launcher can reach. A live query deliberately
  // ignores Simple mode — typing a name is an explicit ask, so Advanced tools
  // are findable even when the grid hides them.
  const q = query.trim().toLowerCase();
  const hit = (label) => label.toLowerCase().includes(q);

  const actions = [
    { label: "New chat", icon: "plus",     sub: "start a fresh thread",  run: newChat, primary: true },
    { label: "Context",  icon: "context",  sub: "what the model sees",   run: () => openChatPanel("context") },
    { label: "Advanced", icon: "advanced", sub: "agent · reflect · pin", run: () => openChatPanel("advanced") },
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
        position: "fixed", inset: 0, zIndex: Z.overlay,
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
        /* Hover, without motion. The tile used to jump 3px and scale 1.012 — with
           25 of them in a grid that reads as the page twitching under the cursor,
           and "expensive" objects do not flinch when you approach them. What is
           left is the gilding coming up:
             · the hairline goes from a whisper of gold to the real thing
             · a second gold hairline blooms just outside it (the 0 0 0 1px ring),
               so the edge reads as two-part metal trim rather than one thicker
               line — the detail that separates a bezel from a border
             · the face brightens and the warm shadow deepens, so the card looks
               lit rather than moved
             · the sheen sweeps once (see ::after)
           No transform anywhere, so nothing reflows and nothing overlaps: the
           z-index that kept the lifted card's shadow out of the grid gap is gone
           with it. */
        .launch-tile:hover {
          border-color: ${T.accent} !important;
          background: linear-gradient(165deg, #FFFFFF 0%, #FFFBF2 100%) !important;
          box-shadow:
            0 0 0 1px rgba(222,184,56,0.22),
            0 10px 30px rgba(95,75,20,0.11),
            0 2px 8px rgba(95,75,20,0.05),
            inset 0 1px 0 rgba(255,255,255,0.98);
        }
        /* Hovering the tile you are already on must not blank its gilding, which
           the rule above would do (white face, !important). Same lamp, turned up:
           the inner glow strengthens and the halo widens a touch. */
        .launch-tile.is-active:hover {
          background: ${ACTIVE_FACE_HOVER} !important;
          box-shadow:
            inset 0 1px 0 rgba(255,255,255,1),
            inset 0 0 34px rgba(255,238,190,0.40),
            0 0 0 3px rgba(222,184,56,0.22),
            0 12px 34px rgba(140,105,35,0.15) !important;
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
        .tile-ico { transition: color ${DUR.base} ${EASE.out}; }
        /* The mark deepens and holds its place — no lift, no scale, no tilt. A
           24px icon that grows 6% is 1.4px of travel, which on a 1.6px stroke
           grid is a blur, not a gesture. Colour alone is the response. */
        .launch-tile:hover .tile-ico { color: ${T.accent2} !important; }
        /* The description warms one step on hover. The LABEL deliberately does
           not: it is a clipped gold gradient in every state, so there is no
           colour property left to override here — see the note on .tile-label.
           (No backticks in this block, ever — it is a JS template literal.) */
        .launch-tile:hover .tile-sub   { color: ${T.mutedLt} !important; }
        .launch-tile:hover .tile-meta  { color: ${T.accent2} !important; }
        /* A heartbeat, not a strobe: two seconds of visible pulse in a six-second
           cycle, so a grid with several live tiles still reads as still. */
        @keyframes metaPulse {
          0%, 66%, 100% { opacity: .45; transform: scale(1) }
          78%           { opacity: 1;   transform: scale(1.35) }
        }
        .tile-pulse {
          animation: metaPulse 6s ${EASE.out} infinite;
          box-shadow: 0 0 6px rgba(196,136,8,0.45);
        }
        /* The press is the only movement left on a tile, and it moves inward —
           a settle under the finger, not a hop. Kept because a click with no
           acknowledgement at all feels broken rather than calm. */
        .launch-tile:active { transform: scale(0.994); transition-duration: 90ms; }
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
          /* Hover is already motionless by design; only the press and the row
             nudge still need suppressing here. */
          .launch-tile:active, .launch-row:hover { transform: none; }
          .launch-tile::after, .launch-tile:hover::after { transition: none; transform: translateX(-130%) skewX(-16deg); }
          .launch-sec { animation: none; }
          .tile-pulse { animation: none; opacity: .7 }
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
            <Section icon="chat" title="Conversation" desc="your chat, threads & controls"
              extra={<RecentThreads threads={shownThreads} onSwitch={switchThread} />}>
              {actions.map(a => (
                <Tile key={a.label} label={a.label} icon={a.icon} sub={a.sub}
                  primary={a.primary} onClick={a.run} />
              ))}
            </Section>
          )}

          {/* One section per surface → its tab tiles. Tabs carrying a `group`
              (e.g. Cognition's Health/Advanced) get full-row sub-headers. */}
          {visibleSurfaces.map(([s, tabs], i) => {
            const tile = (t) => (
              <Tile key={t.id} label={t.label} icon={t.icon || s.icon} sub={t.desc}
                meta={tileMeta[t.id]}
                active={t.id === activeTab}
                onClick={() => go(t.id)} />
            );
            const groups = [...new Set(tabs.map(t => t.group).filter(Boolean))];
            return (
              <Section key={s.id} icon={s.icon} title={s.label} desc={s.desc} delay={(i + 1) * 45}>
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
