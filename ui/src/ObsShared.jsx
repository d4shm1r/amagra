/**
 * ObsShared.jsx — shared primitives for all observability tabs
 *
 * Import: import { ObsPanel, MetricCard, ScoreBar, EventIcon, hScore } from "./ObsShared";
 */
import { T, LUX, TYPE, DUR, FONT_DISPLAY } from "./theme";

// ── Page header ───────────────────────────────────────────────

/** Serif display header used by every tab — matches Library and landing.html.
 *  Gold gradient wordmark by default (the AMAGRA / Memory / Chat treatment);
 *  pass gold={false} to opt a title out. */
// Consistent header rule: an elegant gold serif title, then everything else —
// description, then any actions/buttons/forms — stacked on new lines below it.
export function PageHeader({ title, subtitle, children, gold = true }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h1 style={{
        // Elegant serif display (Cormorant Garamond), gold gradient — the
        // AMAGRA / Memory wordmark treatment.
        ...TYPE.display, margin: 0,
        ...(gold ? { ...LUX.goldText, display: "inline-block" } : { color: T.text }),
      }}>
        {title}
      </h1>
      {subtitle && (
        <div style={{ ...TYPE.caption, color: T.muted, marginTop: 6, maxWidth: 680 }}>
          {subtitle}
        </div>
      )}
      {children && (
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginTop: 13 }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ── Color helpers ─────────────────────────────────────────────

/** Return color for a 0–100 score (green ≥80, amber 60–80, red <60) */
export function hScore(v) {
  if (v == null) return T.muted;
  return v >= 80 ? T.success : v >= 60 ? T.warn : T.error;
}

/** Return color for a 0–1 probability (green ≥0.80, amber 0.65–0.80, red <0.65) */
export function hProb(v) {
  if (v == null) return T.muted;
  return v >= 0.80 ? T.success : v >= 0.65 ? T.warn : T.error;
}

// ── Layout ────────────────────────────────────────────────────

/** Standard section container used by every observability tab — landing card style */
export function ObsPanel({ title, icon, children, action, style = {} }) {
  return (
    <div className="lux-card" style={{ padding: "16px 20px", ...style }}>
      {(title || action) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          {title && (
            <div style={{
              ...TYPE.eyebrow, fontWeight: 700, color: T.mutedLt, letterSpacing: "0.1em",
            }}>
              {icon && <span style={{ marginRight: 6, opacity: 0.7 }}>{icon}</span>}
              {title}
            </div>
          )}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

// ── Metric card ───────────────────────────────────────────────

/** Small stat card — label / big value / sub-text (matches Overview Stat cards) */
export function MetricCard({ label, value, sub, color, mono = false }) {
  // `mono` is accepted for call-site compatibility but no longer forces a
  // code font — luxury numbers use the UI typeface with tabular figures.
  void mono;
  return (
    <div className="lux-card lux-card-i" style={{ padding: "14px 16px" }}>
      <div style={{ ...TYPE.metric, color: color ?? T.text, fontFamily: "inherit" }}>
        {value ?? "—"}
      </div>
      <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.08em", color: T.muted, marginTop: 5 }}>
        {label}
      </div>
      {sub && (
        <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 3 }}>{sub}</div>
      )}
    </div>
  );
}

// ── Score bar ─────────────────────────────────────────────────

/** Horizontal bar for a 0–100 score with label and value */
export function ScoreBar({ label, value, sub, style = {} }) {
  const pct   = value == null ? 0 : Math.min(100, Math.max(0, value));
  const color = hScore(value);
  return (
    <div style={{ marginBottom: 14, ...style }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ ...TYPE.caption, fontWeight: 600, color: T.mutedLt }}>{label}</span>
        <span style={{ ...TYPE.caption, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
          {value == null ? "—" : value.toFixed(1)}
        </span>
      </div>
      <div style={{ background: "#EDE6DA", borderRadius: 3, height: 6, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%", background: color, borderRadius: 3,
          transition: `width ${DUR.slower} ease`,
        }} />
      </div>
      {sub && <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

// ── Event icon + color ────────────────────────────────────────

const EVENT_META = {
  "plan.created":           { icon: "◈", color: T.accent },
  "plan.step.started":      { icon: "▷", color: T.accent },
  "plan.step.completed":    { icon: "✓", color: T.success },
  "plan.step.failed":       { icon: "✗", color: T.error },
  "plan.step.retry":        { icon: "↺", color: T.warn },
  "plan.aborted":           { icon: "⊗", color: T.error },
  "plan.completed":         { icon: "◆", color: T.success },
  "query.received":         { icon: "→", color: T.accent2 },
  "agent.selected":         { icon: "◉", color: T.accent2 },
  "response.generated":     { icon: "◎", color: T.success },
  "step.verified.pass":     { icon: "✓", color: T.success },
  "step.verified.fail":     { icon: "✗", color: T.error },
  "risk.computed":          { icon: "⚑", color: T.warn },
  "reflection.triggered":   { icon: "⌇", color: T.warn },
  "reflection.completed":   { icon: "⌇", color: T.success },
  "memory.retrieved":       { icon: "◎", color: "#1E5A8A" },
  "memory.stored":          { icon: "◎", color: "#1E5A8A" },
  "contradiction.detected": { icon: "⊗", color: T.error },
  "routing.weight.changed": { icon: "△", color: T.accent2 },
  "session.started":        { icon: "◦", color: T.muted },
  "session.ended":          { icon: "◦", color: T.muted },
};

export function eventMeta(type) {
  return EVENT_META[type] || { icon: "·", color: T.muted };
}

/** Compact event row used by EventLogTab and inline event feeds */
export function EventRow({ event, compact = false }) {
  const meta = eventMeta(event.event_type || event.type || "");
  const ts   = event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString() : "";
  const label = (event.event_type || event.type || "event").replace(/\./g, " ");

  if (compact) {
    return (
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "3px 0",
        borderBottom: `1px solid ${T.border}20` }}>
        <span style={{ color: meta.color, fontSize: 12, minWidth: 16 }}>{meta.icon}</span>
        <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, minWidth: 44 }}>{ts}</span>
        <span style={{ ...TYPE.caption, color: T.text, flex: 1 }}>{label}</span>
      </div>
    );
  }

  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0",
      borderBottom: `1px solid ${T.border}`,
    }}>
      <span style={{ color: meta.color, fontSize: 14, minWidth: 18, paddingTop: 1 }}>{meta.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
          <span style={{ ...TYPE.caption, color: T.text, fontWeight: 500 }}>{label}</span>
          <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted }}>{ts}</span>
        </div>
        {event.payload && Object.keys(event.payload).length > 0 && (
          <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 2 }}>
            {Object.entries(event.payload)
              .filter(([k]) => !["session_id", "run_id"].includes(k))
              .slice(0, 4)
              .map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed ? v.toFixed(2) : v : v}`)
              .join(" · ")}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Refresh button ────────────────────────────────────────────

export function RefreshBtn({ onClick }) {
  return (
    <button onClick={onClick} className="nav-btn" style={{
      ...TYPE.micro, fontWeight: 400, background: "transparent", color: T.muted, border: `1px solid ${T.border}`,
      borderRadius: 7, padding: "4px 10px", cursor: "pointer",
      fontFamily: "inherit",
    }}>↻</button>
  );
}

// ── Empty state ───────────────────────────────────────────────

export function EmptyState({ msg = "No data yet — run a query to populate this view." }) {
  return (
    <div style={{ ...TYPE.small, padding: "24px 0", textAlign: "center", color: T.muted, fontStyle: "italic" }}>
      {msg}
    </div>
  );
}

// ── API-offline banner ────────────────────────────────────────
// Calm, premium signal shown when the local backend is unreachable. Every data
// tab fetches the API; without this they fail silently and the dashboard reads
// as broken. Non-blocking (static tabs still render), with the exact fix.
export function ApiOfflineBanner({ onRetry, checking = false }) {
  return (
    <div style={{
      margin: "0 0 18px",
      display: "flex", alignItems: "center", gap: 16,
      padding: "15px 20px", borderRadius: 14,
      background: "linear-gradient(180deg, rgba(255,255,255,0.5) 0%, rgba(255,255,255,0) 46%), #FBF7F1",
      border: `1px solid ${T.accent}33`,
      boxShadow: LUX.cardShadow,
    }}>
      <span style={{
        width: 9, height: 9, borderRadius: "50%", flexShrink: 0,
        background: checking ? T.warn : T.error,
        boxShadow: `0 0 8px ${(checking ? T.warn : T.error)}66`,
        animation: "dotPulse 1.6s ease-in-out infinite",
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          ...TYPE.subtitle, fontFamily: FONT_DISPLAY, lineHeight: 1.2,
          color: T.text,
        }}>
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
      <button
        onClick={onRetry}
        disabled={checking}
        className="nav-btn"
        style={{
          ...TYPE.caption, fontWeight: 600, flexShrink: 0, padding: "7px 18px", borderRadius: 20,
          background: "transparent", border: `1px solid ${T.border}`,
          color: T.mutedLt,
          fontFamily: "inherit", cursor: checking ? "default" : "pointer",
        }}
      >
        {checking ? "Checking…" : "Retry"}
      </button>
    </div>
  );
}
