import { useState } from "react";
import { PROMISES } from "./constants";
import { PageHeader } from "./ObsShared";

const T = {
  bg:      "#F4F0E8",
  surface: "#FAF7F2",
  surface2:"#F4F0E8",
  surface3:"#EDE6DA",
  border:  "#E0D6C4",
  accent:  "#C48808",
  text:    "#2E2010",
  mutedLt: "#5C4030",
  muted:   "#9A7A60",
  success: "#15803D",
  warn:    "#9A6C00",
  error:   "#B42318",
  purple:  "#6D4FA8",
};

const STATUS = {
  delivered: { label: "Delivered",    color: T.success, bg: `${T.success}12`, dot: "●", pulse: false },
  building:  { label: "Building now", color: T.warn,    bg: `${T.warn}12`,    dot: "●", pulse: true  },
  committed: { label: "Committed",    color: T.accent,  bg: `${T.accent}12`,  dot: "○", pulse: false },
};

const CATEGORY_COLOR = {
  Privacy:     "#0F766E",
  Platform:    T.purple,
  AI:          "#BE185D",
  Developer:   "#C48808",
  Performance: T.warn,
};

const CATEGORIES = ["All", "AI", "Developer", "Performance", "Platform", "Privacy"];
const STATUS_FILTER = ["All", "Delivered", "Building", "Committed"];

function PromiseCard({ p }) {
  const st  = STATUS[p.status] || STATUS.committed;
  const cat = CATEGORY_COLOR[p.category] || T.muted;
  const isDelivered = p.status === "delivered";
  const isBuilding  = p.status === "building";

  return (
    <div className="lux-card lux-card-i" style={{
      padding: "18px 20px",
      display: "flex", flexDirection: "column", gap: 10,
      position: "relative",
      overflow: "hidden",
      borderColor: isDelivered ? T.success + "55" : isBuilding ? T.warn + "44" : undefined,
    }}>

      {/* Delivered shimmer bar */}
      {isDelivered && (
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: 2,
          background: `linear-gradient(90deg, transparent, ${T.success}88, transparent)`,
        }} />
      )}

      {/* Header row */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div style={{
          width: 38, height: 38, borderRadius: 8, flexShrink: 0,
          background: `${cat}18`, border: `1px solid ${cat}33`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18,
        }}>
          {p.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 700, color: isDelivered ? T.text : T.mutedLt,
            lineHeight: 1.3, marginBottom: 4,
          }}>
            {p.title}
          </div>
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "center" }}>
            {/* Category */}
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "1px 7px", borderRadius: 10,
              background: `${cat}18`, color: cat, border: `1px solid ${cat}33`,
              letterSpacing: "0.06em", textTransform: "uppercase",
            }}>{p.category}</span>

            {/* Status */}
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "1px 7px", borderRadius: 10,
              background: st.bg, color: st.color, border: `1px solid ${st.color}44`,
              letterSpacing: "0.06em",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <span style={{
                animation: st.pulse ? "promisePulse 1.2s ease-in-out infinite" : "none",
                display: "inline-block",
              }}>{st.dot}</span>
              {st.label}
            </span>

            {/* Target */}
            {(p.target_quarter || p.delivered_on) && (
              <span style={{
                fontSize: 9, color: T.muted, fontVariantNumeric: "tabular-nums",
              }}>
                {p.status === "delivered"
                  ? `✓ ${p.delivered_on?.slice(0, 7)}`
                  : p.target_quarter}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Description */}
      <div style={{
        fontSize: 12, color: T.muted, lineHeight: 1.65,
      }}>
        {p.description}
      </div>

      {/* Version tag */}
      {p.target && p.status !== "delivered" && (
        <div style={{ marginTop: 2 }}>
          <span style={{
            fontSize: 9, fontFamily: "monospace", fontWeight: 700,
            padding: "2px 8px", borderRadius: 3,
            background: `${T.accent}14`, color: T.accent,
            border: `1px solid ${T.accent}33`,
          }}>{p.target}</span>
        </div>
      )}
    </div>
  );
}

function StatPill({ count, label, color }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
      padding: "10px 20px",
      background: `${color}10`,
      border: `1px solid ${color}33`,
      borderRadius: 8,
    }}>
      <span style={{ fontSize: 22, fontWeight: 800, color, fontVariantNumeric: "tabular-nums" }}>
        {count}
      </span>
      <span style={{ fontSize: 10, color: T.muted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em" }}>
        {label}
      </span>
    </div>
  );
}

export default function PromisesTab() {
  const [activeCat,    setActiveCat]    = useState("All");
  const [activeStatus, setActiveStatus] = useState("All");

  const delivered = PROMISES.filter(p => p.status === "delivered").length;
  const building  = PROMISES.filter(p => p.status === "building").length;
  const committed = PROMISES.filter(p => p.status === "committed").length;

  const visible = PROMISES.filter(p => {
    const catOk    = activeCat    === "All" || p.category === activeCat;
    const statusOk = activeStatus === "All"
      || (activeStatus === "Delivered" && p.status === "delivered")
      || (activeStatus === "Building"  && p.status === "building")
      || (activeStatus === "Committed" && p.status === "committed");
    return catOk && statusOk;
  });

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", paddingBottom: 40 }}>

      {/* Keyframes */}
      <style>{`@keyframes promisePulse { 0%,100%{opacity:1} 50%{opacity:.2} }`}</style>

      {/* ── Header ── */}
      <div style={{
        borderBottom: `1px solid ${T.border}`,
        paddingBottom: 28, marginBottom: 28,
      }}>
        <PageHeader
          title="Amagra Promises"
          subtitle="These are explicit commitments — not marketing copy. Each promise comes with a target version and a delivery date. Delivered items stay here so you can hold us accountable."
        />

        {/* Stats */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 18 }}>
          <StatPill count={delivered} label="Delivered"    color={T.success} />
          <StatPill count={building}  label="Building now" color={T.warn}    />
          <StatPill count={committed} label="Committed"    color={T.accent}  />
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
            padding: "10px 20px",
            background: T.surface2, border: `1px solid ${T.border}`,
            borderRadius: 8, marginLeft: "auto",
          }}>
            <span style={{ fontSize: 11, color: T.muted, lineHeight: 1.5, maxWidth: 180, textAlign: "center" }}>
              Published <span style={{ color: T.text, fontWeight: 600 }}>Jun 11, 2026</span>
              <br />Updated with every release
            </span>
          </div>
        </div>
      </div>

      {/* ── Filters ── */}
      <div style={{ display: "flex", gap: 24, marginBottom: 22, flexWrap: "wrap" }}>

        {/* Category */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {CATEGORIES.map(c => {
            const active = activeCat === c;
            const col = CATEGORY_COLOR[c] || T.accent;
            return (
              <button key={c} onClick={() => setActiveCat(c)} style={{
                padding: "4px 12px", borderRadius: 20, fontSize: 11,
                fontFamily: "inherit", cursor: "pointer", fontWeight: active ? 700 : 500,
                background: active ? `${col}22` : T.surface,
                border: `1px solid ${active ? col + "66" : T.border}`,
                color: active ? col : T.muted,
                transition: "all .12s",
              }}>{c}</button>
            );
          })}
        </div>

        <div style={{ width: 1, background: T.border, margin: "0 2px" }} />

        {/* Status */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {STATUS_FILTER.map(s => {
            const active = activeStatus === s;
            const col = s === "Delivered" ? T.success : s === "Building" ? T.warn : s === "Committed" ? T.accent : T.muted;
            return (
              <button key={s} onClick={() => setActiveStatus(s)} style={{
                padding: "4px 12px", borderRadius: 20, fontSize: 11,
                fontFamily: "inherit", cursor: "pointer", fontWeight: active ? 700 : 500,
                background: active ? `${col}22` : T.surface,
                border: `1px solid ${active ? col + "66" : T.border}`,
                color: active ? col : T.muted,
                transition: "all .12s",
              }}>{s}</button>
            );
          })}
        </div>
      </div>

      {/* ── Promise grid ── */}
      {visible.length === 0 ? (
        <div style={{ textAlign: "center", padding: "40px 0", fontSize: 13, color: T.muted }}>
          No promises match this filter.
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
          gap: 14,
        }}>
          {/* Delivered first, then building, then committed */}
          {["delivered", "building", "committed"].flatMap(status =>
            visible.filter(p => p.status === status)
          ).map(p => (
            <PromiseCard key={p.id} p={p} />
          ))}
        </div>
      )}

      {/* ── Footer note ── */}
      <div style={{
        marginTop: 36, padding: "16px 20px",
        background: T.surface, border: `1px solid ${T.border}`,
        borderRadius: 8, fontSize: 11, color: T.muted, lineHeight: 1.7,
      }}>
        <strong style={{ color: T.text }}>What "committed" means:</strong> These features are scheduled
        and scoped — they exist in the engineering roadmap with time estimates attached.
        They are not aspirational wishlist items.
        <span style={{ display: "block", marginTop: 6 }}>
          <strong style={{ color: T.text }}>What "building" means:</strong> Active development.
          The backend infrastructure is in place and the feature will ship in the next 1–2 releases.
        </span>
        <span style={{ display: "block", marginTop: 6 }}>
          If a committed feature slips its target version, it will be updated here with an explanation — not quietly removed.
        </span>
      </div>

    </div>
  );
}
