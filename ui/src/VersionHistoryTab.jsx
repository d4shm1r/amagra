import { useMemo, useState } from "react";
import { BUILD_PHASES, VERSION_EPOCHS } from "./constants";
import { T, TYPE, EASE, DUR, RADIUS, FONT_MONO } from "./theme";
import { PageHeader } from "./ObsShared";

// Single-color system: one gold for decoration, a deeper gold for text on cream.
const GOLD    = T.accent;      // #C48808 — hairlines, chevron
const GOLD_TX = T.accentText;  // #8A5A00 — legible gold for text/numerals

// ── Phase card ─────────────────────────────────────────────────
// The epoch header above already carries the version + label, so the card
// holds only its unique content: the summary and (on expand) the steps.
function PhaseCard({ phase }) {
  const [open, setOpen] = useState(false);
  const steps = phase.steps || phase.items || [];
  const isNow = phase.status === "next";

  return (
    <div
      // The app-wide card. Clickable, so it takes the interactive variant (lift
      // + gold ring on hover); the current phase holds the gold edge on.
      className="lux-card lux-card-i"
      onClick={() => setOpen(o => !o)}
      style={{
        display: "flex", flexDirection: "column",
        ...(isNow ? { borderColor: GOLD + "4A" } : null),
        padding: "12px 15px",
        cursor: "pointer",
        marginBottom: 7,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        {/* NOW badge */}
        {isNow && (
          <span style={{
            fontSize: 8, fontWeight: 800, letterSpacing: "0.1em",
            padding: "2px 6px", borderRadius: RADIUS.sm - 3, flexShrink: 0, marginTop: 1,
            background: `${GOLD}22`, color: GOLD_TX,
            border: `1px solid ${GOLD}55`,
          }}>NOW</span>
        )}

        {/* Summary — the card's identifying line */}
        <span style={{ ...TYPE.caption, color: T.mutedLt, lineHeight: 1.55, flex: 1 }}>
          {phase.summary}
        </span>

        {/* Steps count (collapsed only) */}
        {!open && steps.length > 0 && (
          <span style={{ fontSize: 10, color: T.muted, flexShrink: 0, fontFamily: FONT_MONO, marginTop: 1 }}>
            {steps.length}
          </span>
        )}

        {/* Date */}
        {phase.date && (
          <span style={{ fontSize: 10, color: T.muted, flexShrink: 0, fontVariantNumeric: "tabular-nums", marginTop: 1 }}>
            {phase.date}
          </span>
        )}

        {/* Chevron */}
        <span style={{
          fontSize: 9, color: GOLD, opacity: .55, flexShrink: 0, marginTop: 2,
          transition: `transform ${DUR.base} ${EASE.out}`, display: "inline-block",
          transform: open ? "rotate(180deg)" : "none",
        }}>▼</span>
      </div>

      {/* Expanded steps */}
      {open && steps.length > 0 && (
        <div style={{ marginTop: 11, display: "flex", flexDirection: "column", gap: 6 }}>
          {steps.map((step, i) => {
            const text = step.replace(/\s*✅$/, "").replace(" ✅", "");
            return (
              <div key={i} style={{ ...TYPE.caption, color: T.muted, lineHeight: 1.55 }}>
                {text}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────
export default function VersionHistoryTab() {
  const phaseMap = useMemo(() => Object.fromEntries(BUILD_PHASES.map(p => [p.id, p])), []);

  const shipped    = BUILD_PHASES.filter(p => p.status === "done");
  const latest     = shipped[shipped.length - 1] || BUILD_PHASES[BUILD_PHASES.length - 1];
  const totalSteps = BUILD_PHASES.reduce((s, p) => s + (p.steps?.length || 0), 0);
  const startDate  = BUILD_PHASES[0].date;
  const endDate    = latest.date;

  const semverDesc = (a, b) => {
    const parts = v => (v || "").replace(/^v/, "").split(".").map(n => parseInt(n, 10) || 0);
    const [a0,a1,a2] = parts(a.version), [b0,b1,b2] = parts(b.version);
    return (b0 - a0) || (b1 - a1) || (b2 - a2);
  };

  return (
    <div style={{ animation: `fadeIn ${DUR.base} ${EASE.out}` }}>
      <PageHeader center title="Releases" subtitle="Every shipped phase and version epoch — the full build history." />

      {/* ── Stats bar ── */}
      <div className="lux-card" style={{
        display: "flex", gap: 0, overflow: "hidden", marginBottom: 26,
      }}>
        {[
          { label: "Phases",  value: BUILD_PHASES.length },
          { label: "Version", value: latest.version },
          { label: "Steps",   value: totalSteps },
          { label: "Epochs",  value: VERSION_EPOCHS.filter(e => e.phases.some(id => phaseMap[id])).length },
          { label: "Started", value: startDate },
          { label: "Latest",  value: endDate },
        ].map((s, i, arr) => (
          <div key={s.label} style={{
            flex: 1, padding: "15px 16px", textAlign: "center",
            borderRight: i < arr.length - 1 ? `1px solid ${T.border}` : "none",
          }}>
            <div style={{ ...TYPE.metric, fontSize: 18, color: GOLD_TX, lineHeight: 1.1 }}>
              {s.value}
            </div>
            <div style={{ ...TYPE.eyebrow, fontSize: 9.5, color: T.muted, marginTop: 5 }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* ── Release epochs ── */}
      <div>
        {VERSION_EPOCHS.map((epoch) => {
          const phases = epoch.phases
            .map(id => phaseMap[id])
            .filter(Boolean)
            .slice()
            .sort(semverDesc);

          if (phases.length === 0) return null;

          // Date range from phases
          const dates  = epoch.phases.map(id => phaseMap[id]?.date).filter(Boolean);
          const first  = dates[0];
          const last   = dates[dates.length - 1];
          const range  = first && last && first !== last ? `${first} — ${last}` : first || "";

          const stepCount = phases.reduce((s, p) => s + (p.steps?.length || 0), 0);

          return (
            <div key={epoch.version} style={{ marginBottom: 30 }}>
              {/* Epoch header */}
              <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 12, paddingBottom: 8, borderBottom: `1px solid ${GOLD}2A` }}>
                <span style={{
                  ...TYPE.subtitle, fontSize: 15, fontWeight: 800, color: GOLD_TX,
                  fontFamily: FONT_MONO, letterSpacing: "-0.01em",
                }}>
                  {epoch.version}
                </span>
                <span style={{ ...TYPE.caption, fontWeight: 700, color: T.text }}>
                  {epoch.label}
                </span>
                <div style={{ flex: 1 }} />
                {range && <span style={{ fontSize: 10, color: T.muted }}>{range}</span>}
                <span style={{ fontSize: 10, color: T.muted, fontFamily: FONT_MONO }}>
                  {phases.length}p · {stepCount}s
                </span>
              </div>

              {/* Phase cards */}
              <div>
                {phases.map(phase => (
                  <PhaseCard key={phase.id} phase={phase} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
