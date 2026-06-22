import { useState, useEffect, useCallback } from "react";
import { AGENTS } from "./constants";
import { T } from "./theme";
import { PageHeader } from "./ObsShared";

const API = "http://localhost:8000";

function hc(v, good, warn) {
  return v == null ? T.muted : v >= good ? T.success : v >= warn ? T.warn : T.error;
}

// ── System mode from coherence + dynamics trend ───────────────
function inferMode(coh, dynamics) {
  if (!coh) return { label: "Offline", color: T.muted, pulse: false };
  const C          = coh.C              ?? 0;
  const conflict_r = coh.conflict_rate  ?? 0;
  const G_r_mean   = coh.G_r_mean       ?? 0;

  let rising = false, falling = false;
  if (dynamics && dynamics.length >= 3) {
    const tail = dynamics.slice(-3).map(d => d.C);
    rising  = tail[2] > tail[0] + 0.015;
    falling = tail[2] < tail[0] - 0.015;
  }

  if (C < 0.65)                                return { label: "Degraded",          color: T.error,   pulse: true  };
  if (falling && C < 0.80)                     return { label: "Recovering",         color: T.warn,    pulse: true  };
  if (rising  && G_r_mean > 0.01)              return { label: "Learning",           color: T.accent2, pulse: false };
  if (conflict_r > 0.20)                       return { label: "Routing Uncertain",  color: T.warn,    pulse: true  };
  if (C >= 0.88)                               return { label: "Stable",             color: T.success, pulse: false };
  return                                              { label: "Nominal",            color: T.success, pulse: false };
}

// ── Health prediction from dynamics slope ─────────────────────
function predictHealth(dynamics) {
  if (!dynamics || dynamics.length < 4) return null;
  const recent = dynamics.slice(-6).map(d => d.C);
  const n = recent.length;
  const xMean = (n - 1) / 2;
  const yMean = recent.reduce((a, b) => a + b, 0) / n;
  const denom = recent.reduce((s, _, i) => s + (i - xMean) ** 2, 0) || 1;
  const slope = recent.reduce((s, y, i) => s + (i - xMean) * (y - yMean), 0) / denom;
  const cur   = recent[n - 1];
  const p5    = Math.min(1, Math.max(0, cur + slope * 5));
  const p10   = Math.min(1, Math.max(0, cur + slope * 10));
  const variance = recent.reduce((s, y) => s + (y - yMean) ** 2, 0) / n;

  if (Math.abs(slope) < 0.003 || variance < 0.0005) {
    return { trend: "Stable →", color: T.success, slope,
      msg: `Expected ${(p5 - 0.01).toFixed(3)}–${(p5 + 0.01).toFixed(3)} over next windows` };
  }
  if (slope > 0.003) {
    return { trend: "Rising ↑", color: T.success, slope,
      msg: `Trending toward ${p10.toFixed(3)} — learning active` };
  }
  return { trend: "Declining ↓", color: T.error, slope,
    msg: `Trending toward ${p10.toFixed(3)} — check routing & contradictions` };
}

// ── Event synthesis from decisions + contradictions + dynamics ─
function synthesizeEvents(decisions, contras, dynamics) {
  const events = [];

  (decisions || []).slice(0, 40).forEach((d, i) => {
    const time = d.timestamp ? d.timestamp.slice(11, 16) : null;
    const ord  = d.id != null ? d.id : 1_000_000 - i;
    if (d.conflict) {
      const ba = (d.brain_agent  || "?").replace(/_/g, " ");
      const ra = (d.router_agent || "?").replace(/_/g, " ");
      events.push({ key: `c${i}`, icon: "◉", color: T.warn,    time, ord,
        msg: `Routing conflict — brain:${ba} vs router:${ra}` });
    }
    if (d.reflect) {
      events.push({ key: `r${i}`, icon: "⌇", color: T.accent,  time, ord: ord - 0.1,
        msg: `Reflection triggered (conf ${(d.confidence || 0).toFixed(2)})` });
    }
    if ((d.regret || 0) > 0.20) {
      events.push({ key: `g${i}`, icon: "⚡", color: T.warn,    time, ord: ord - 0.2,
        msg: `High regret ${(d.regret).toFixed(3)} — ${(d.task || d.query || "").slice(0, 36)}` });
    }
  });

  (contras || []).slice(0, 12).forEach((c, i) => {
    const time = (c.timestamp || "").slice(11, 16) || null;
    events.push({ key: `ct${i}`, icon: "⊗", color: T.error, time, ord: 999_000 - i,
      msg: `Contradiction detected — ${(c.query || "").slice(0, 42)}` });
  });

  if (dynamics && dynamics.length >= 2) {
    for (let i = 1; i < dynamics.length; i++) {
      const delta = (dynamics[i].C || 0) - (dynamics[i - 1].C || 0);
      if (Math.abs(delta) > 0.03) {
        const up = delta > 0;
        events.push({ key: `dyn${i}`, icon: up ? "⊕" : "⊟",
          color: up ? T.success : T.error, time: `w${dynamics[i].window_idx ?? i}`,
          ord: 500_000 + i,
          msg: `Coherence ${up ? "recovered" : "declined"} ${delta >= 0 ? "+" : ""}${delta.toFixed(3)}` });
      }
    }
  }

  return events.sort((a, b) => b.ord - a.ord).slice(0, 22);
}

// ── CoherenceHero ─────────────────────────────────────────────
function CoherenceHero({ coh, dynamics }) {
  const [showWhy, setShowWhy] = useState(false);

  const C_val     = coh?.C          ?? null;
  const C_routing = coh?.c_routing  ?? null;
  const C_calib   = coh?.c_calib    ?? null;
  const C_quality = coh?.c_quality  ?? null;

  const color = hc(C_val, 0.82, 0.70);
  const mode  = inferMode(coh, dynamics);

  const tail   = dynamics?.slice(-2) || [];
  const trend  = tail.length < 2  ? "→"
    : tail[1].C > tail[0].C + 0.001  ? "↑"
    : tail[1].C < tail[0].C - 0.001  ? "↓" : "→";
  const trendColor = trend === "↑" ? T.success : trend === "↓" ? T.error : T.muted;

  // OCAC Δ²C leading indicator: acceleration of coherence change. Peak |Δ²C|
  // over 0.05 flags a sharp bend before C(t) itself drops (see coherence.py).
  const curvs   = (dynamics || []).map(d => d.C_curvature).filter(v => v != null);
  const peakD2C = curvs.reduce((m, v) => Math.abs(v) > Math.abs(m) ? v : m, 0);
  const bending = Math.abs(peakD2C) > 0.05;
  const d2cCol  = bending ? T.error : Math.abs(peakD2C) > 0.025 ? T.warn : T.success;

  const components = [
    { label: "Routing",     val: C_routing, desc: "brain–router consistency" },
    { label: "Memory",      val: C_quality, desc: "avg knowledge quality" },
    { label: "Calibration", val: C_calib,   desc: "confidence accuracy" },
  ].filter(c => c.val != null);

  const bottleneck = components.length
    ? [...components].sort((a, b) => a.val - b.val)[0]
    : null;

  return (
    <div className="lux-card" style={{
      padding: "24px 26px", marginBottom: 14,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 20 }}>
        {/* Big number */}
        <div>
          <div style={{
            fontSize: 56, fontWeight: 900, color,
            fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace",
            lineHeight: 1, letterSpacing: "-0.03em",
          }}>
            {C_val != null ? C_val.toFixed(3) : "—"}
            <span style={{ fontSize: 28, marginLeft: 10, color: trendColor }}>{trend}</span>
          </div>
          <div style={{ fontSize: 12, color: T.muted, marginTop: 6 }}>
            Global Coherence — C(t) = ( C_routing + C_calib + C_quality ) / 3
          </div>
        </div>

        <div style={{ flex: 1 }} />

        {/* Mode badge + Why? */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 7,
            background: `${mode.color}15`, border: `1px solid ${mode.color}40`,
            borderRadius: 20, padding: "7px 16px",
          }}>
            {mode.pulse && (
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: mode.color, animation: "livePulse 1.5s infinite",
              }} />
            )}
            <span style={{
              fontSize: 13, fontWeight: 700, color: mode.color, letterSpacing: "0.06em",
            }}>
              {mode.label}
            </span>
          </div>
          {curvs.length > 0 && (
            <span
              title={`Δ²C leading indicator — peak |curvature| = ${peakD2C.toFixed(4)}.\n>0.05 signals coherence bending sharply before C(t) drops (OCAC).`}
              style={{
                fontSize: 10, fontWeight: 700,
                fontFamily: "'Consolas', 'Cascadia Code', monospace",
                color: d2cCol, background: `${d2cCol}15`, border: `1px solid ${d2cCol}40`,
                borderRadius: 12, padding: "3px 10px", whiteSpace: "nowrap",
              }}>
              Δ²C {peakD2C >= 0 ? "+" : ""}{peakD2C.toFixed(3)} · {bending ? "bending" : Math.abs(peakD2C) > 0.025 ? "flexing" : "smooth"}
            </span>
          )}
          {components.length > 0 && (
            <button onClick={() => setShowWhy(!showWhy)} style={{
              background: showWhy ? `${T.accent}20` : "transparent",
              border: `1px solid ${showWhy ? T.accent : T.border}`,
              color: showWhy ? T.accent : T.mutedLt,
              borderRadius: 3, padding: "5px 14px",
              fontSize: 12, fontWeight: 600, cursor: "pointer",
              fontFamily: "inherit", transition: "all .15s",
            }}>
              {showWhy ? "▴ Why?" : "▾ Why?"}
            </button>
          )}
        </div>
      </div>

      {/* Why? — Coherence breakdown */}
      {showWhy && components.length > 0 && (
        <div style={{
          marginTop: 18, background: T.surface2, borderRadius: 4,
          border: `1px solid ${T.border}`, padding: "14px 16px",
          animation: "fadeIn .15s",
        }}>
          <div style={{
            fontSize: 10, fontWeight: 700, color: T.muted,
            textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: 12,
          }}>
            Why is C(t) {C_val?.toFixed(3)} and not 1.000?
          </div>
          {components.map(({ label, val, desc }) => {
            const contrib = val / 3;
            const isBlock = bottleneck?.label === label;
            const col     = hc(val, 0.82, 0.70);
            return (
              <div key={label} style={{
                display: "flex", alignItems: "center", gap: 10, marginBottom: 9,
              }}>
                <span style={{
                  width: 84, fontSize: 12, color: isBlock ? col : T.mutedLt,
                  fontWeight: isBlock ? 700 : 400,
                }}>
                  {label}
                </span>
                <span style={{
                  width: 48, fontSize: 13, fontWeight: 700, color: col,
                  fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace",
                }}>
                  {val.toFixed(3)}
                </span>
                <div style={{
                  flex: 1, height: 5, background: T.border, borderRadius: 3, overflow: "hidden",
                }}>
                  <div style={{ width: `${val * 100}%`, height: "100%", background: col, borderRadius: 3 }} />
                </div>
                <span style={{
                  width: 52, fontSize: 11, color: col,
                  fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace", textAlign: "right",
                }}>
                  +{contrib.toFixed(3)}
                </span>
                {isBlock && (
                  <span style={{
                    fontSize: 10, color: col, fontWeight: 700, whiteSpace: "nowrap",
                  }}>
                    ← bottleneck
                  </span>
                )}
              </div>
            );
          })}
          <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 10, marginTop: 4 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: T.mutedLt }}>Total</span>
              <span style={{
                fontSize: 14, fontWeight: 800, color,
                fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace",
              }}>
                C(t) = {C_val.toFixed(3)}
              </span>
            </div>
            {bottleneck && (
              <div style={{ fontSize: 11, color: T.muted, lineHeight: 1.55 }}>
                <span style={{ fontWeight: 700, color: hc(bottleneck.val, 0.82, 0.70) }}>
                  {bottleneck.label}
                </span>{" "}is costing{" "}
                <span style={{ fontWeight: 700, color: hc(bottleneck.val, 0.82, 0.70) }}>
                  {((1 - bottleneck.val) / 3).toFixed(3)} points
                </span>{" "}from a perfect 1.000.
                {bottleneck.val < 0.70 && " Immediate action recommended."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Coherence Timeline ────────────────────────────────────────
function CoherenceTimeline({ dynamics, onWindowChange, window: win }) {
  if (!dynamics || dynamics.length < 2) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: T.muted, fontSize: 12 }}>
        Collecting data — needs 2+ windows
      </div>
    );
  }

  const W = 500, H = 150, PX = 32, PY = 16;
  const IW = W - 2 * PX, IH = H - 2 * PY;
  const n  = dynamics.length;
  const xs = i => PX + (i / (n - 1)) * IW;
  const ys = v => PY + (1 - Math.max(0, Math.min(1, v))) * IH;

  const polyline = (key, col, w = 1.8) => {
    const pts = dynamics
      .map((d, i) => d[key] != null ? `${xs(i).toFixed(1)},${ys(d[key]).toFixed(1)}` : null)
      .filter(Boolean)
      .join(" ");
    return pts
      ? <polyline key={key} points={pts} fill="none" stroke={col} strokeWidth={w}
          strokeLinejoin="round" strokeLinecap="round" />
      : null;
  };

  const lastC = dynamics[n - 1].C;
  const lastX = xs(n - 1), lastY = ys(lastC);
  const gridTicks = [0.5, 0.6, 0.7, 0.82, 0.9, 1.0];

  // Sharpest Δ²C bend — ring it as an instability leading indicator.
  let bendIdx = -1, bendVal = 0;
  dynamics.forEach((d, i) => {
    if (d.C_curvature != null && Math.abs(d.C_curvature) > Math.abs(bendVal)) {
      bendVal = d.C_curvature; bendIdx = i;
    }
  });
  const bendCol = Math.abs(bendVal) > 0.05 ? T.error : T.warn;

  return (
    <div>
      {/* Window selector */}
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        {[20, 50, 100].map(w => (
          <button key={w} onClick={() => onWindowChange(w)} style={{
            background: win === w ? `${T.accent}22` : "transparent",
            border: `1px solid ${win === w ? T.accent : T.border}`,
            color: win === w ? T.accent : T.muted,
            borderRadius: 3, padding: "3px 10px", fontSize: 10,
            cursor: "pointer", fontFamily: "inherit", fontWeight: 600,
          }}>
            {w} windows
          </button>
        ))}
      </div>

      <svg width="100%" viewBox={`0 0 ${W} ${H + 16}`} style={{ display: "block" }}>
        {/* Grid lines */}
        {gridTicks.map(t => (
          <g key={t}>
            <line x1={PX} y1={ys(t)} x2={W - PX} y2={ys(t)}
              stroke={t === 0.82 ? T.border + "aa" : T.border}
              strokeDasharray={t === 0.82 ? "4,2" : "2,4"} />
            <text x={PX - 4} y={ys(t) + 3.5} fill={T.muted} fontSize={8}
              textAnchor="end" fontFamily="monospace">{t.toFixed(2)}</text>
          </g>
        ))}
        {/* Threshold label */}
        <text x={W - PX + 2} y={ys(0.82) + 3} fill={T.muted} fontSize={7}>healthy</text>

        {/* Sub-component lines (faint) */}
        {polyline("c_routing", T.accent  + "77", 1.2)}
        {polyline("c_quality", "#7E3F8F77", 1.2)}
        {polyline("c_calib",   T.accent2 + "77", 1.2)}

        {/* C(t) main line */}
        {polyline("C", T.success, 2.5)}

        {/* Sharpest Δ²C bend marker */}
        {bendIdx >= 0 && Math.abs(bendVal) > 0.025 && (
          <circle cx={xs(bendIdx)} cy={ys(dynamics[bendIdx].C)} r={4.5}
            fill="none" stroke={bendCol} strokeWidth={1.6}>
            <title>{`Sharpest bend: Δ²C = ${bendVal.toFixed(4)} at w${dynamics[bendIdx].window_idx ?? bendIdx}`}</title>
          </circle>
        )}

        {/* Latest point dot */}
        <circle cx={lastX} cy={lastY} r={4} fill={hc(lastC, 0.82, 0.70)} />
        <text x={lastX + 6} y={lastY + 4} fill={hc(lastC, 0.82, 0.70)}
          fontSize={9} fontFamily="monospace" fontWeight="bold">
          {lastC.toFixed(3)}
        </text>

        {/* Axes */}
        <line x1={PX} y1={PY} x2={PX} y2={H - PY} stroke={T.border} />
        <line x1={PX} y1={H - PY} x2={W - PX} y2={H - PY} stroke={T.border} />

        {/* X ticks */}
        {[0, Math.floor(n / 2), n - 1].map(i => (
          <text key={i} x={xs(i)} y={H - PY + 12} fill={T.muted}
            fontSize={8} textAnchor="middle" fontFamily="monospace">
            w{dynamics[i]?.window_idx ?? i}
          </text>
        ))}

        {/* Legend */}
        {[["C(t)", T.success, 2.5], ["routing", T.accent, 1.2], ["memory", "#7E3F8F", 1.2], ["calib", T.accent2, 1.2]].map(([l, c, sw], li) => (
          <g key={l} transform={`translate(${PX + li * 100}, ${PY - 8})`}>
            <line x1={0} y1={0} x2={14} y2={0} stroke={c} strokeWidth={sw} />
            <text x={17} y={4} fill={T.muted} fontSize={8}>{l}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

// ── Cognitive Events Feed ─────────────────────────────────────
function CognitiveEventsFeed({ events }) {
  if (!events?.length) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: T.muted, fontSize: 12 }}>
        No events yet — send a message to see the live feed.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 320, overflowY: "auto" }}>
      {events.map(ev => (
        <div key={ev.key} style={{
          display: "flex", alignItems: "flex-start", gap: 10,
          padding: "7px 10px", borderRadius: 3,
          background: `${ev.color}08`,
          border: `1px solid ${ev.color}20`,
        }}>
          <span style={{
            fontFamily: "monospace", fontSize: 13, color: ev.color,
            flexShrink: 0, lineHeight: 1.4,
          }}>
            {ev.icon}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            {ev.time && (
              <span style={{
                fontSize: 10, color: T.muted, fontFamily: "monospace",
                marginRight: 7,
              }}>
                {ev.time}
              </span>
            )}
            <span style={{ fontSize: 11, color: ev.color === T.success ? ev.color : T.mutedLt }}>
              {ev.msg}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Routing Inspector ─────────────────────────────────────────
function RoutingInspector({ lastDecision, agents }) {
  if (!lastDecision) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: T.muted, fontSize: 12 }}>
        No decisions yet — routing inspector appears after first query.
      </div>
    );
  }

  const d        = lastDecision;
  const ag = AGENTS.find(a => a.id === d.brain_agent);

  // Use count-based routing distribution (weight is a Bayesian quality score, not probability)
  const totalCount = Object.values(agents || {}).reduce((s, a) => s + (a.count || 0), 0);
  const weights = Object.entries(agents || {})
    .map(([id, s]) => ({ id, w: (s.count || 0) / (totalCount || 1), count: s.count || 0, quality: s.weight || 0 }))
    .filter(a => a.count > 0)
    .sort((a, b) => b.w - a.w)
    .slice(0, 6);
  const wMax = weights[0]?.w || 1;

  return (
    <div>
      {/* Query */}
      <div style={{
        fontSize: 11, color: T.muted, marginBottom: 12, lineHeight: 1.5,
        background: T.surface2, borderRadius: 3, padding: "8px 10px",
        fontStyle: "italic",
      }}>
        "{(d.task || d.query || "—").slice(0, 90)}{(d.task || d.query || "").length > 90 ? "…" : ""}"
      </div>

      {/* Execution path */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        {["Query", "Signal", "Brain", "Route", "Memory", "Answer"].map((step, i, arr) => (
          <span key={step} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{
              fontSize: 10, color: step === "Route" ? T.accent : T.muted,
              fontWeight: step === "Route" ? 700 : 400,
              background: step === "Route" ? `${T.accent}18` : "transparent",
              border: step === "Route" ? `1px solid ${T.accent}33` : "none",
              borderRadius: 4, padding: step === "Route" ? "2px 6px" : "0",
            }}>
              {step}
            </span>
            {i < arr.length - 1 && <span style={{ fontSize: 9, color: T.muted }}>→</span>}
          </span>
        ))}
        {d.reflect && (
          <>
            <span style={{ fontSize: 9, color: T.muted }}>→</span>
            <span style={{
              fontSize: 10, color: T.accent, fontWeight: 700,
              background: `${T.accent}18`, border: `1px solid ${T.accent}33`,
              borderRadius: 4, padding: "2px 6px",
            }}>
              Reflect
            </span>
          </>
        )}
      </div>

      {/* Key metrics row */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {[
          { label: "Selected", value: ag ? `${ag.icon} ${ag.label.split(" ")[0]}` : (d.brain_agent || "—"),
            color: ag?.color || T.muted },
          { label: "Confidence", value: `${((d.confidence || 0) * 100).toFixed(0)}%`,
            color: hc(d.confidence, 0.75, 0.55) },
          { label: "Status", value: d.conflict ? "Conflict" : "Agreed",
            color: d.conflict ? T.warn : T.success },
        ].map(m => (
          <div key={m.label} style={{
            flex: 1, background: T.surface2, borderRadius: 3,
            padding: "8px 10px", border: `1px solid ${T.border}`,
          }}>
            <div style={{ fontSize: 9, color: T.muted, marginBottom: 3 }}>{m.label}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: m.color, fontFamily: "monospace" }}>
              {m.value}
            </div>
          </div>
        ))}
      </div>

      {/* Routing candidates */}
      {weights.length > 0 && (
        <div>
          <div style={{
            fontSize: 10, color: T.muted, textTransform: "uppercase",
            letterSpacing: "0.08em", marginBottom: 7,
          }}>
            Routing Tendencies
          </div>
          {weights.map(({ id, w, count, quality }) => {
            const a        = AGENTS.find(ag => ag.id === id);
            const col      = a?.color || T.muted;
            const selected = id === d.brain_agent;
            const label    = (a?.label || id)
              .replace("IT & Networking", "IT & Net")
              .replace("Knowledge & Learning", "Knowledge")
              .replace(" Dev", "").replace("AI & ML", "AI/ML");
            return (
              <div key={id} style={{ marginBottom: 5 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                  <span style={{
                    fontSize: 11, color: selected ? col : T.mutedLt,
                    fontWeight: selected ? 700 : 400,
                  }}>
                    {a?.icon} {label}{selected && " ←"}
                  </span>
                  <span style={{ fontSize: 11, color: col, fontFamily: "monospace", fontWeight: 600 }}>
                    {Math.round(w * 100)}%
                    <span style={{ color: T.muted, fontWeight: 400, fontSize: 9, marginLeft: 4 }}>
                      q:{quality.toFixed(2)}
                    </span>
                  </span>
                </div>
                <div style={{ height: 4, background: T.border, borderRadius: 2, overflow: "hidden" }}>
                  <div style={{
                    width: `${(w / wMax) * 100}%`, height: "100%",
                    background: selected ? col : col + "55", borderRadius: 2,
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Panel wrapper ─────────────────────────────────────────────
function Panel({ title, icon, children, action }) {
  return (
    <div className="lux-card" style={{
      padding: "16px 18px",
    }}>
      <div style={{
        fontSize: 10, fontWeight: 700, color: T.muted,
        textTransform: "uppercase", letterSpacing: "0.1em",
        marginBottom: 14, display: "flex", gap: 6, alignItems: "center",
      }}>
        {icon && <span style={{ fontFamily: "monospace" }}>{icon}</span>}
        <span>{title}</span>
        {action && <span style={{ marginLeft: "auto" }}>{action}</span>}
      </div>
      {children}
    </div>
  );
}

// ── Sub-metric card (C(t) children) ──────────────────────────
function SubCard({ label, value, unit = "", color, sub, icon }) {
  return (
    <div className="lux-card lux-card-i" style={{
      flex: 1, minWidth: 130, padding: "13px 15px",
    }}>
      <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 5 }}>
        {icon && <span style={{ marginRight: 4 }}>{icon}</span>}
        {label}
      </div>
      <div style={{
        fontSize: 20, fontWeight: 800, color,
        fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace", lineHeight: 1,
      }}>
        {value != null ? `${value}${unit}` : "—"}
      </div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 4, lineHeight: 1.3 }}>{sub}</div>}
    </div>
  );
}

// ── ContradictionsPanel ───────────────────────────────────────
function ContradictionsPanel({ items }) {
  const [expanded, setExpanded] = useState(null);
  const [resolving, setResolving] = useState(false);
  const [resolveResult, setResolveResult] = useState(null);
  const [resolveError, setResolveError] = useState(null);

  const rows = Array.isArray(items) ? items : [];

  async function handleAutoResolve() {
    setResolving(true);
    setResolveResult(null);
    setResolveError(null);
    try {
      const res = await fetch(`${API}/memory/auto-resolve?threshold=0.90`, { method: "POST" });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setResolveResult(data);
    } catch (e) {
      setResolveError(e.message);
    } finally {
      setResolving(false);
    }
  }

  if (rows.length === 0) return null;

  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.error}30`,
      borderRadius: 3, padding: "16px 18px", marginTop: 14,
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: T.error, letterSpacing: "0.06em" }}>
          ⊗ CONTRADICTIONS — {rows.length} event{rows.length !== 1 ? "s" : ""}
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={handleAutoResolve}
          disabled={resolving}
          style={{
            background: resolving ? T.surface2 : `${T.error}18`,
            border: `1px solid ${T.error}55`,
            color: resolving ? T.muted : T.error,
            borderRadius: 3, padding: "5px 14px",
            fontSize: 11, fontWeight: 600, cursor: resolving ? "default" : "pointer",
            transition: "background 0.15s",
          }}
        >
          {resolving ? "Resolving…" : "Auto-Resolve (cos > 0.90)"}
        </button>
      </div>

      {/* Resolve result banner */}
      {resolveResult && (
        <div style={{
          background: `${T.success}12`, border: `1px solid ${T.success}40`,
          borderRadius: 3, padding: "8px 12px", marginBottom: 10, fontSize: 11, color: T.success,
        }}>
          Resolved {resolveResult.resolved} pair{resolveResult.resolved !== 1 ? "s" : ""}
          {" "}— {resolveResult.remaining} memories remaining
          {resolveResult.dry_run && " (dry run — no changes made)"}
        </div>
      )}
      {resolveError && (
        <div style={{
          background: `${T.error}12`, border: `1px solid ${T.error}40`,
          borderRadius: 3, padding: "8px 12px", marginBottom: 10, fontSize: 11, color: T.error,
        }}>
          Error: {resolveError}
        </div>
      )}

      {/* Event rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {rows.map((c) => {
          const isOpen = expanded === c.id;
          const snip   = (c.response_snip || "").slice(0, 120);
          const query  = (c.query || "").slice(0, 90);
          const ts     = (c.timestamp || "").slice(0, 16).replace("T", " ");
          return (
            <div key={c.id} style={{ border: `1px solid ${T.border}`, borderRadius: 3 }}>
              {/* Row header — click to expand */}
              <div
                onClick={() => setExpanded(isOpen ? null : c.id)}
                style={{
                  display: "flex", alignItems: "center", gap: 9,
                  padding: "8px 11px", cursor: "pointer",
                  background: isOpen ? T.surface2 : "transparent",
                  borderRadius: isOpen ? "3px 3px 0 0" : 3,
                }}
              >
                <span style={{ fontSize: 10, color: T.muted, fontFamily: "monospace", flexShrink: 0 }}>
                  #{c.id}
                </span>
                <span style={{ fontSize: 10, color: T.muted, flexShrink: 0 }}>{ts}</span>
                <span style={{ fontSize: 10, color: T.accent2, fontWeight: 600, flexShrink: 0 }}>
                  {(c.agent || "unknown").replace(/_/g, " ")}
                </span>
                <span style={{
                  flex: 1, fontSize: 11, color: T.mutedLt,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {query}{(c.query || "").length > 90 ? "…" : ""}
                </span>
                {c.reflect_level && (
                  <span style={{
                    fontSize: 9, color: T.warn, fontWeight: 700, flexShrink: 0,
                    background: `${T.warn}15`, border: `1px solid ${T.warn}30`,
                    borderRadius: 10, padding: "2px 6px",
                  }}>
                    {c.reflect_level}
                  </span>
                )}
                <span style={{ fontSize: 10, color: T.muted, flexShrink: 0 }}>
                  {isOpen ? "▲" : "▼"}
                </span>
              </div>

              {/* Expanded diff view */}
              {isOpen && (
                <div style={{
                  borderTop: `1px solid ${T.border}`,
                  padding: "10px 12px",
                  display: "flex", flexDirection: "column", gap: 8,
                }}>
                  <div>
                    <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                      Query
                    </div>
                    <div style={{
                      fontSize: 11, color: T.text, background: T.surface2,
                      borderRadius: 3, padding: "6px 9px", fontStyle: "italic", lineHeight: 1.5,
                    }}>
                      "{c.query || "—"}"
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                      Response (self-corrected excerpt)
                    </div>
                    <div style={{
                      fontSize: 11, color: T.error, background: `${T.error}08`,
                      border: `1px solid ${T.error}25`,
                      borderRadius: 3, padding: "6px 9px", lineHeight: 1.5,
                      fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace",
                    }}>
                      {snip || "—"}{(c.response_snip || "").length > 120 ? "…" : ""}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────
export default function CognitiveOSTab({ coherence: cohProp = null }) {
  const [coh,     setCoh]     = useState(cohProp);
  const [dec,     setDec]     = useState(null);
  const [mem,     setMem]     = useState(null);
  const [contras, setContras] = useState(null);
  const [dyn,     setDyn]     = useState(null);
  const [dynWin,  setDynWin]  = useState(50);
  const [loading, setLoading] = useState(true);

  // Sync coherence from parent (App.js already polls /coherence every 30s)
  useEffect(() => { if (cohProp) setCoh(cohProp); }, [cohProp]);

  const load = useCallback(async () => {
    try {
      const [dR, mR, ctR, dynR] = await Promise.all([
        fetch(`${API}/decisions?limit=50`),
        fetch(`${API}/memory/stats`),
        fetch(`${API}/contradictions?limit=30`),
        fetch(`${API}/coherence/dynamics?window=${dynWin}`),
      ]);
      setDec(dR.ok     ? await dR.json()  : null);
      setMem(mR.ok     ? await mR.json()  : null);
      setContras(ctR.ok ? await ctR.json() : []);
      const dynData = dynR.ok ? await dynR.json() : [];
      setDyn(Array.isArray(dynData) ? dynData : (dynData?.history || []));
    } catch {}
    setLoading(false);
  }, [dynWin]);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  // ── Derived ───────────────────────────────────────────────
  const agents    = dec?.agents    || {};
  const decStats  = dec?.stats     || {};
  const decisions = dec?.decisions || [];

  const C         = coh?.C              ?? null;
  const C_routing = coh?.c_routing      ?? null;
  const C_quality = coh?.c_quality      ?? null;
  const G_r_mean  = coh?.G_r_mean       ?? null;
  const G_r_pos   = coh?.G_r_positive   ?? 0;
  const reflect_r = coh?.reflection_rate ?? 0;
  const conflict_r= coh?.conflict_rate   ?? 0;
  const mem_avg_q = coh?.mem_avg_quality ?? null;
  const mem_n     = coh?.mem_n           ?? (mem?.total ?? null);

  const total_dec = decStats.total || 0;
  const conflicts = decStats.conflicts || 0;
  const contrasArr = Array.isArray(contras) ? contras : [];
  const contrasN   = contrasArr.length;

  const prediction  = predictHealth(dyn);
  const events      = synthesizeEvents(decisions, contrasArr, dyn);
  const lastDecision = decisions[0] ?? null;
  // Misroutes: brain–router conflict with low routing confidence (regret rarely exceeds 0.10 in practice)
  const misroutes    = decisions.filter(d => d.conflict && (d.confidence || 1) < 0.50);

  if (loading && !coh && !dec) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: T.muted, fontSize: 13 }}>
        Loading Cognitive OS…
      </div>
    );
  }

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      {/* ── Header row ── */}
      <PageHeader title="Cognitive OS" subtitle="Self-analysis · refreshes every 30s">
        <button onClick={load} className="nav-btn" style={{
          background: "transparent", border: `1px solid ${T.border}`,
          color: T.mutedLt, padding: "5px 15px", borderRadius: 16,
          fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
        }}>
          ↻ Refresh
        </button>
      </PageHeader>

      {/* ── C(t) Hero ── */}
      <CoherenceHero coh={coh} dynamics={dyn} />

      {/* ── Sub-metrics row — C(t) children ── */}
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <SubCard
          label="Routing"  icon="◉"
          value={C_routing != null ? `${((1 - conflict_r) * 100).toFixed(1)}` : null}
          unit="%"
          color={hc(C_routing, 0.82, 0.70)}
          sub={`${conflicts} conflicts · C_routing ${C_routing?.toFixed(3) ?? "–"}`}
        />
        <SubCard
          label="Memory"   icon="◎"
          value={mem_avg_q?.toFixed(3)}
          color={hc(mem_avg_q, 0.75, 0.60)}
          sub={`${mem_n ?? "—"} entries · C_quality ${C_quality?.toFixed(3) ?? "–"}`}
        />
        <SubCard
          label="Reflection" icon="⌇"
          value={G_r_mean != null ? `${G_r_mean >= 0 ? "+" : ""}${G_r_mean.toFixed(4)}` : null}
          color={hc(G_r_mean, 0.02, 0.005)}
          sub={`${Math.round(reflect_r * 100)}% rate · ${Math.round(G_r_pos * 100)}% positive`}
        />
        <SubCard
          label="Contradictions" icon="⊗"
          value={contrasN === 0 ? "None" : contrasN < 3 ? `${contrasN} low` : `${contrasN} high`}
          color={contrasN === 0 ? T.success : contrasN < 3 ? T.warn : T.error}
          sub={`${total_dec} decisions · ${contrasN} events`}
        />
      </div>

      {/* ── Timeline + Events ── */}
      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 14, marginBottom: 14 }}>
        <Panel title="Coherence Timeline" icon="⌇">
          <CoherenceTimeline
            dynamics={dyn}
            window={dynWin}
            onWindowChange={w => { setDynWin(w); }}
          />
        </Panel>

        <Panel title="Live Cognitive Events" icon="≡">
          <CognitiveEventsFeed events={events} />
        </Panel>
      </div>

      {/* ── Routing Inspector + Health Prediction ── */}
      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 14, marginBottom: 14 }}>
        <Panel title="Last Decision Inspector" icon="◉">
          <RoutingInspector lastDecision={lastDecision} agents={agents} />
        </Panel>

        <Panel title="Health Prediction" icon="△">
          {prediction ? (
            <div>
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 }}>
                  Current C(t)
                </div>
                <div style={{
                  fontSize: 28, fontWeight: 900, color: hc(C, 0.82, 0.70),
                  fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace",
                }}>
                  {C?.toFixed(3) ?? "—"}
                </div>
              </div>
              <div style={{
                background: `${prediction.color}10`,
                border: `1px solid ${prediction.color}30`,
                borderRadius: 4, padding: "12px 14px",
              }}>
                <div style={{ fontSize: 9, color: T.muted, marginBottom: 5, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Prediction
                </div>
                <div style={{
                  fontSize: 17, fontWeight: 800, color: prediction.color,
                  fontFamily: "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace", marginBottom: 6,
                }}>
                  {prediction.trend}
                </div>
                <div style={{ fontSize: 11, color: T.muted, lineHeight: 1.55 }}>
                  {prediction.msg}
                </div>
                <div style={{ fontSize: 9, color: T.muted, marginTop: 8 }}>
                  slope {prediction.slope >= 0 ? "+" : ""}{prediction.slope.toFixed(5)} / window
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: 20, textAlign: "center", color: T.muted, fontSize: 12 }}>
              Need 4+ dynamics windows for prediction.
            </div>
          )}
        </Panel>
      </div>

      {/* ── Misroute Candidates ── */}
      {misroutes.length > 0 && (
        <Panel title={`Uncertain Routes — ${misroutes.length} flagged`} icon="⚡">
          <div style={{ fontSize: 11, color: T.muted, marginBottom: 10 }}>
            Brain–router conflict with confidence &lt; 50% — uncertain routing decisions worth reviewing.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {misroutes.slice(0, 6).map((d, i) => {
              const brain  = AGENTS.find(a => a.id === d.brain_agent);
              const router = AGENTS.find(a => a.id === d.router_agent);
              return (
                <div key={i} style={{
                  background: T.surface2, border: `1px solid ${T.error}20`,
                  borderRadius: 3, padding: "8px 12px",
                  display: "flex", alignItems: "center", gap: 10,
                }}>
                  <span style={{ fontSize: 10, color: T.muted, fontFamily: "monospace", flexShrink: 0 }}>
                    #{d.id}
                  </span>
                  <span style={{ fontSize: 11, color: brain?.color || T.muted, fontWeight: 700, flexShrink: 0 }}>
                    {brain?.icon} {(d.brain_agent || "—").replace(/_/g, " ")}
                  </span>
                  <span style={{ fontSize: 10, color: T.muted, flexShrink: 0 }}>vs</span>
                  <span style={{ fontSize: 11, color: router?.color || T.muted, flexShrink: 0 }}>
                    {router?.icon} {(d.router_agent || "none").replace(/_/g, " ")}
                  </span>
                  <span style={{
                    fontSize: 10, color: T.error, fontFamily: "monospace", flexShrink: 0,
                  }}>
                    regret {(d.regret || 0).toFixed(3)}
                  </span>
                  <span style={{
                    flex: 1, fontSize: 11, color: T.muted,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {(d.task || d.query || "").slice(0, 80)}
                  </span>
                </div>
              );
            })}
          </div>
        </Panel>
      )}

      {/* ── Contradictions ── */}
      <ContradictionsPanel items={contrasArr} />
    </div>
  );
}
