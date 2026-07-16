// Feedback.jsx — the states that aren't content: loading, empty, transient
// notices, and the engine-offline banner. A tab should never hand-write
// "Loading…" in an italic div again.
import { T, LUX, TYPE, FONT_DISPLAY, SPACE, LAYOUT, Z } from "@/styles/theme";
import { toneColor } from "./tone";
import { Button } from "./Button";

/** Quiet inline loading line — for a panel whose data hasn't landed yet.
 *
 *  `role="status"` (an implicit polite live region) so the wait is announced
 *  rather than being a silent pause: a sighted user sees the panel is busy, and
 *  without this a screen-reader user gets nothing at all until the data lands. */
export function Loading({ msg = "Loading…" }) {
  return (
    <div role="status" style={{ ...TYPE.small, padding: `${SPACE[6]}px 0`, textAlign: "center",
                                color: T.muted, fontStyle: "italic" }}>
      {msg}
    </div>
  );
}

/** "There's nothing here" — the quiet variant, for inside a panel. */
export function EmptyState({ msg = "No data yet — run a query to populate this view." }) {
  return (
    <div style={{ ...TYPE.small, padding: `${SPACE[6]}px 0`, textAlign: "center",
                  color: T.muted, fontStyle: "italic" }}>
      {msg}
    </div>
  );
}

/** The generous variant — a whole tab with no content yet. Serif headline, a
 *  line of prose, one CTA, one hint. This is a first impression, so it gets
 *  room to breathe. */
export function EmptyPage({ title, children, action, hint }) {
  return (
    <div style={{ padding: "70px 0 60px", textAlign: "center" }}>
      <div style={{ ...TYPE.title, fontFamily: FONT_DISPLAY, fontSize: 24, color: T.text, marginBottom: SPACE[2] }}>
        {title}
      </div>
      {children && (
        <div style={{ ...TYPE.small, color: T.muted, maxWidth: 420,
                      margin: `0 auto ${SPACE[6]}px`, lineHeight: 1.6 }}>
          {children}
        </div>
      )}
      {action}
      {hint && <div style={{ ...TYPE.micro, color: T.muted, marginTop: SPACE[3] }}>{hint}</div>}
    </div>
  );
}

/** A transient message — a failed upload, a backend that went away mid-action.
 *
 *  A Notice always appears in reaction to something, so it is always a live
 *  region. Which kind depends on the tone, because urgency is not decoration:
 *  a failure interrupts (`alert`, assertive), anything else waits its turn
 *  (`status`, polite). Getting this backwards means either a user misses that
 *  their upload died, or every routine success barges into what they were doing. */
export function Notice({ tone = "error", children }) {
  const color = toneColor(tone);
  return (
    <div role={tone === "error" || tone === "warn" ? "alert" : "status"} style={{
      marginBottom: SPACE[3], padding: `${SPACE[2]}px ${SPACE[3]}px`, borderRadius: 8,
      background: `${color}12`, border: `1px solid ${color}33`,
      ...TYPE.caption, color,
    }}>
      {children}
    </div>
  );
}

/** The floating alert layer — an overlay pinned over the top of the content.
 *
 *  An alert is not part of the page. It must not take a row in the layout and
 *  shove every card down by its own height; it appears *over* the work, like a
 *  popup, and when it goes the page doesn't jump. So: absolutely positioned (it
 *  anchors to the shell's relative container), the layer itself is
 *  pointer-transparent so it never steals a click meant for the content beneath,
 *  and only the alert inside it is clickable.
 *
 *  z-index sits above the sticky PageHeader (30) but below the ☰ launcher (50),
 *  so the menu button stays reachable while an alert is up.
 *
 *  It is also the app's LIVE REGION, and that is why it renders even with no
 *  children. A screen reader only reliably announces content inserted into a
 *  region that was ALREADY in the document; mounting the region together with
 *  its message — `{offline && <Toast>…}` — is the standard way to ship an alert
 *  that stays silent for exactly the people who need it read aloud. So the layer
 *  is permanent and only its children come and go. An empty one is inert: it has
 *  no height, so it intercepts nothing.
 *
 *  Polite, not assertive: the banner persists on screen, so it does not need to
 *  cut into whatever the user is doing — it needs to be heard at the next pause. */
export function Toast({ children }) {
  return (
    <div role="status" aria-live="polite" style={{
      position: "absolute", top: 12, left: LAYOUT.gutter, right: LAYOUT.gutter,
      zIndex: Z.toast, display: "flex", justifyContent: "center",
      pointerEvents: "none",
    }}>
      <div style={{ pointerEvents: "auto", width: "100%", maxWidth: LAYOUT.content }}>
        {children}
      </div>
    </div>
  );
}

/** Shown app-wide when the local backend is unreachable. Non-blocking (static
 *  tabs still render), with the exact fix spelled out. Carries no outer margin:
 *  where it sits is the caller's business (it rides in a <Toast>). */
export function ApiOfflineBanner({ onRetry, checking = false }) {
  const dot = toneColor(checking ? "warn" : "error");
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 16,
      padding: "15px 20px", borderRadius: 14,
      background: LUX.cardBg,
      border: `1px solid ${T.accent}33`,
      boxShadow: LUX.cardShadow,
    }}>
      {/* Decorative: the headline beside it already says "offline"/"connecting",
          so an accessible name here would only stutter it. */}
      <span aria-hidden style={{
        width: 9, height: 9, borderRadius: "50%", flexShrink: 0,
        background: dot, boxShadow: `0 0 8px ${dot}66`,
        animation: "dotPulse 1.6s ease-in-out infinite",
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ ...TYPE.subtitle, fontFamily: FONT_DISPLAY, lineHeight: 1.2, color: T.text }}>
          {checking ? "Connecting to the engine…" : "The engine is offline"}
        </div>
        <div style={{ ...TYPE.caption, color: T.muted, marginTop: 4, lineHeight: 1.5 }}>
          Amagra runs entirely on your hardware. Start the local engine to bring the workspace online —{" "}
          <code style={{
            fontFamily: "monospace", fontSize: 11.5, color: T.accent2,
            background: T.surface2, border: `1px solid ${T.border}`,
            borderRadius: 5, padding: "1px 7px",
          }}>./start-agents.sh</code>
        </div>
      </div>
      <Button variant="quiet" onClick={onRetry} disabled={checking}>
        {checking ? "Checking…" : "Retry"}
      </Button>
    </div>
  );
}
