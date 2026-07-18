// Stat.jsx — how the app shows a number.
//
// HeroStat    — THE number a page is about, at hero scale
// StatStrip   — headline numbers as one hairline-divided row (preferred)
// MetricCard  — a single stat as its own small card
// ScoreBar    — a 0–100 score with a bar, colored by health
import { T, TYPE, FONT_MONO, DUR } from "@/styles/theme";
import { toneColor, scoreTone } from "./tone";

/** The one number a page is about — the health figure at the top of Dashboard
 *  and Coherence. Big, monospaced (so digits don't jitter as it refreshes),
 *  with its trend arrow inline and status badges pushed to the right.
 *
 *  Two panels had grown their own 52px and 56px hero blocks with different
 *  weights and label placement, which is why the surface had two competing
 *  "main numbers" that didn't even look like siblings. This is that block,
 *  once — so a second hero is a prop, not a copy. */
export function HeroStat({ value, label, tone = "default", trend, trendTone = "muted", badges, children }) {
  const color = toneColor(tone);
  return (
    <div className="lux-card" style={{ padding: "22px 24px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 20, flexWrap: "wrap" }}>
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 52, lineHeight: 1, fontWeight: 700, color,
            fontFamily: FONT_MONO, letterSpacing: "-0.03em",
            fontVariantNumeric: "tabular-nums",
          }}>
            {value ?? "—"}
            {trend && (
              <span style={{ fontSize: 26, marginLeft: 10, color: toneColor(trendTone) }}>{trend}</span>
            )}
          </div>
          {label && <div style={{ ...TYPE.caption, color: T.muted, marginTop: 8 }}>{label}</div>}
        </div>
        {badges && (
          <div style={{
            marginLeft: "auto", display: "flex", flexDirection: "column",
            alignItems: "flex-end", gap: 8,
          }}>
            {badges}
          </div>
        )}
      </div>
      {children}
    </div>
  );
}

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

/** A single stat as its own small card — label / big value / sub-text.
 *
 *  `onClick` turns it into a way IN: the card becomes a button, gains a chevron
 *  and announces itself as a link to wherever the number is explained in full.
 *  A dashboard tile that shows a worrying number and offers no route to the
 *  detail behind it makes the reader hunt through a menu for it.
 *  `children` is a slot under the sub-text — a sparkline, usually. */
export function MetricCard({ label, value, sub, tone = "default", color, onClick, children }) {
  const interactive = typeof onClick === "function";
  return (
    <div
      className={`lux-card${interactive ? " lux-card-i" : ""}`}
      onClick={onClick}
      {...(interactive ? {
        role: "button", tabIndex: 0,
        onKeyDown: (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(e); }
        },
        "aria-label": `${label}${value != null ? `: ${value}` : ""} — open details`,
      } : null)}
      style={{ padding: "14px 16px", ...(interactive ? { cursor: "pointer" } : null) }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <div style={{ ...TYPE.metric, color: color ?? toneColor(tone), fontFamily: "inherit" }}>
          {value ?? "—"}
        </div>
        {interactive && (
          <span aria-hidden style={{ ...TYPE.caption, color: T.muted, marginLeft: "auto" }}>›</span>
        )}
      </div>
      <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.08em", color: T.muted, marginTop: 5 }}>
        {label}
      </div>
      {sub && <div style={{ ...TYPE.micro, color: T.muted, marginTop: 3 }}>{sub}</div>}
      {children && <div style={{ marginTop: 10 }}>{children}</div>}
    </div>
  );
}

/** A proportion split across categories, as one bar.
 *
 *  segments: [{ label, value (0–1), tone }]. For "94% none / 6% light / 0% full"
 *  — a whole divided into parts, which is a different question from ScoreBar's
 *  "how far along one thing is", and was being hand-rolled as a flex row of
 *  divs wherever it came up. */
export function StackedBar({ segments = [], height = 14 }) {
  const live = segments.filter(s => s.value > 0);
  if (!live.length) return null;
  return (
    <div style={{ display: "flex", height, borderRadius: 999, overflow: "hidden" }}>
      {live.map(s => (
        <div
          key={s.label}
          title={`${s.label}: ${(s.value * 100).toFixed(1)}%`}
          style={{
            width: `${s.value * 100}%`, background: toneColor(s.tone),
            transition: `width ${DUR.slower} ease`,
          }}
        />
      ))}
    </div>
  );
}

/** One labelled bar in a ranked list — label, proportional bar, raw value.
 *
 *  ScoreBar answers "what score is this out of 100"; this answers "how big is
 *  this next to its siblings", where the number on the right is a COUNT, not a
 *  percentage. Used for per-action and per-agent breakdowns. */
export function BarRow({ label, fraction = 0, value, tone = "accent", labelWidth = 90 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
      <span style={{ ...TYPE.caption, color: T.mutedLt, minWidth: labelWidth }}>{label}</span>
      <div style={{ flex: 1, background: T.surface2, borderRadius: 3, height: 6, overflow: "hidden" }}>
        <div style={{
          width: `${Math.min(100, Math.max(0, fraction * 100))}%`, height: "100%",
          background: toneColor(tone), borderRadius: 3, transition: `width ${DUR.slower} ease`,
        }} />
      </div>
      <span style={{
        ...TYPE.micro, fontFamily: FONT_MONO, color: T.muted,
        minWidth: 34, textAlign: "right",
      }}>
        {value}
      </span>
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
