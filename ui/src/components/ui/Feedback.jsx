// Feedback.jsx — the states that aren't content: loading, empty, transient
// notices, and the engine-offline banner. A tab should never hand-write
// "Loading…" in an italic div again.
import { T, LUX, TYPE, FONT_DISPLAY, SPACE } from "@/styles/theme";
import { toneColor } from "./tone";
import { Button } from "./Button";

/** Quiet inline loading line — for a panel whose data hasn't landed yet. */
export function Loading({ msg = "Loading…" }) {
  return (
    <div style={{ ...TYPE.small, padding: `${SPACE[6]}px 0`, textAlign: "center",
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

/** A transient message — a failed upload, a backend that went away mid-action. */
export function Notice({ tone = "error", children }) {
  const color = toneColor(tone);
  return (
    <div style={{
      marginBottom: SPACE[3], padding: `${SPACE[2]}px ${SPACE[3]}px`, borderRadius: 8,
      background: `${color}12`, border: `1px solid ${color}33`,
      ...TYPE.caption, color,
    }}>
      {children}
    </div>
  );
}

/** Shown app-wide when the local backend is unreachable. Non-blocking (static
 *  tabs still render), with the exact fix spelled out. */
export function ApiOfflineBanner({ onRetry, checking = false }) {
  const dot = toneColor(checking ? "warn" : "error");
  return (
    <div style={{
      margin: "0 0 18px",
      display: "flex", alignItems: "center", gap: 16,
      padding: "15px 20px", borderRadius: 14,
      background: LUX.cardBg,
      border: `1px solid ${T.accent}33`,
      boxShadow: LUX.cardShadow,
    }}>
      <span style={{
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
