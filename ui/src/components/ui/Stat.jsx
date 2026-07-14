// Stat.jsx — how the app shows a number.
//
// StatStrip   — headline numbers as one hairline-divided row (preferred)
// MetricCard  — a single stat as its own small card
// ScoreBar    — a 0–100 score with a bar, colored by health
import { T, TYPE, DUR } from "@/styles/theme";
import { toneColor, scoreTone } from "./tone";

/** Headline numbers as one hairline-divided row, not floating mini-cards.
 *  Items: { label, value, sub?, tone? }. Wraps cleanly — every cell carries a
 *  left divider and the row is nudged 1px out of a clipping wrapper, so no row
 *  ever starts with a dangling line. */
export function StatStrip({ items }) {
  return (
    <div style={{ overflow: "hidden" }}>
      <div style={{ display: "flex", flexWrap: "wrap", marginLeft: -1, rowGap: 18 }}>
        {items.map(({ label, value, sub, tone = "gold" }) => (
          <div key={label} style={{
            flex: "1 1 130px", padding: "2px 20px",
            borderLeft: `1px solid ${T.border}`,
          }}>
            <div style={{ ...TYPE.metric, color: toneColor(tone) }}>{value ?? "—"}</div>
            <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.08em", color: T.muted, marginTop: 6 }}>{label}</div>
            {sub && <div style={{ ...TYPE.micro, color: T.muted, marginTop: 3 }}>{sub}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

/** A single stat as its own small card — label / big value / sub-text. */
export function MetricCard({ label, value, sub, tone = "default", color }) {
  return (
    <div className="lux-card lux-card-i" style={{ padding: "14px 16px" }}>
      <div style={{ ...TYPE.metric, color: color ?? toneColor(tone), fontFamily: "inherit" }}>
        {value ?? "—"}
      </div>
      <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.08em", color: T.muted, marginTop: 5 }}>
        {label}
      </div>
      {sub && <div style={{ ...TYPE.micro, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

/** Horizontal bar for a 0–100 score. The bar colors itself from the score. */
export function ScoreBar({ label, value, sub, style = {} }) {
  const pct   = value == null ? 0 : Math.min(100, Math.max(0, value));
  const color = toneColor(scoreTone(value));
  return (
    <div style={{ marginBottom: 14, ...style }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ ...TYPE.caption, fontWeight: 600, color: T.mutedLt }}>{label}</span>
        <span style={{ ...TYPE.caption, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
          {value == null ? "—" : value.toFixed(1)}
        </span>
      </div>
      <div style={{ background: T.surface2, borderRadius: 3, height: 6, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%", background: color, borderRadius: 3,
          transition: `width ${DUR.slower} ease`,
        }} />
      </div>
      {sub && <div style={{ ...TYPE.micro, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}
