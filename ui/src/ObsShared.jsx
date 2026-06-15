/**
 * ObsShared.jsx — shared primitives for all observability tabs
 *
 * Import: import { ObsPanel, MetricCard, ScoreBar, EventIcon, hScore } from "./ObsShared";
 */
import { T, LUX, FONT_DISPLAY } from "./theme";

// ── Page header ───────────────────────────────────────────────

/** Serif display header used by every tab — matches Library and landing.html */
export function PageHeader({ title, subtitle, children, gold }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 18 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{
          // gold variant mirrors the AMAGRA / Library display title exactly
          margin: 0, fontFamily: FONT_DISPLAY, fontWeight: 600,
          fontSize: gold ? 26 : 24, letterSpacing: "0.02em", lineHeight: 1.2,
          ...(gold ? { ...LUX.goldText, display: "inline-block" } : { color: T.text }),
        }}>
          {title}
        </h1>
        {subtitle && <div style={{ fontSize: 12, color: T.muted, marginTop: 3 }}>{subtitle}</div>}
      </div>
      {children}
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
              fontSize: 11, fontWeight: 700, color: T.mutedLt,
              letterSpacing: "0.1em", textTransform: "uppercase",
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
  return (
    <div className="lux-card lux-card-i" style={{ padding: "14px 16px" }}>
      <div style={{
        fontSize: 22, fontWeight: 700, color: color ?? T.text,
        fontFamily: mono ? "'Consolas','Cascadia Code',monospace" : "inherit",
        fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em",
        lineHeight: 1.1,
      }}>
        {value ?? "—"}
      </div>
      <div style={{ fontSize: 10, fontWeight: 600, color: T.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 5 }}>
        {label}
      </div>
      {sub && (
        <div style={{ fontSize: 10, color: T.muted, marginTop: 3 }}>{sub}</div>
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
        <span style={{ fontSize: 12, fontWeight: 600, color: T.mutedLt }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: "'Consolas',monospace" }}>
          {value == null ? "—" : value.toFixed(1)}
        </span>
      </div>
      <div style={{ background: "#EDE6DA", borderRadius: 3, height: 6, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%", background: color, borderRadius: 3,
          transition: "width 0.5s ease",
        }} />
      </div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 3 }}>{sub}</div>}
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
        <span style={{ fontSize: 11, color: T.muted, minWidth: 44 }}>{ts}</span>
        <span style={{ fontSize: 11, color: T.text, flex: 1 }}>{label}</span>
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
          <span style={{ fontSize: 12, color: T.text, fontWeight: 500 }}>{label}</span>
          <span style={{ fontSize: 10, color: T.muted }}>{ts}</span>
        </div>
        {event.payload && Object.keys(event.payload).length > 0 && (
          <div style={{ fontSize: 10, color: T.muted, marginTop: 2 }}>
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
      background: "transparent", color: T.muted, border: `1px solid ${T.border}`,
      borderRadius: 7, padding: "4px 10px", cursor: "pointer", fontSize: 11,
      fontFamily: "inherit",
    }}>↻</button>
  );
}

// ── Empty state ───────────────────────────────────────────────

export function EmptyState({ msg = "No data yet — run a query to populate this view." }) {
  return (
    <div style={{ padding: "24px 0", textAlign: "center", color: T.muted, fontSize: 12.5, fontStyle: "italic" }}>
      {msg}
    </div>
  );
}
