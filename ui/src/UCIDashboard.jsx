import { useState, useEffect } from "react";
import { T, FONT_MONO } from "./theme";
import { ObsPanel, EventRow, RefreshBtn, EmptyState, hScore, PageHeader } from "./ObsShared";

const API = "http://localhost:8000";
const BASELINE_HUCI = 75.1;   // h_UCI before Phase 37 fixes

// ── System health strip ────────────────────────────────────────
function HealthStrip({ health }) {
  if (!health) return null;

  const ollamaOk  = health.ollama === "online";
  const memOk     = health.memory?.backend != null;
  const degraded  = health.status === "degraded";

  const Dot = ({ ok, label, sub }) => (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <span style={{
        width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
        background: ok ? T.success : T.error,
        boxShadow: ok ? `0 0 5px ${T.success}88` : "none",
      }} />
      <div>
        <div style={{ fontSize: 11, color: ok ? T.mutedLt : T.error, fontWeight: 600 }}>{label}</div>
        {sub && <div style={{ fontSize: 9, color: T.muted }}>{sub}</div>}
      </div>
    </div>
  );

  return (
    <div style={{
      display: "flex", gap: 20, padding: "8px 14px",
      background: T.surface, border: `1px solid ${degraded ? T.warn + "55" : T.border}`,
      borderRadius: 5, marginBottom: 16, flexWrap: "wrap", alignItems: "center",
    }}>
      <span style={{ fontSize: 9, color: T.muted, fontWeight: 700, letterSpacing: "0.1em",
                     textTransform: "uppercase", flexShrink: 0 }}>System</span>
      <Dot ok={ollamaOk}  label="Ollama"  sub={ollamaOk ? "serving" : "offline"} />
      <Dot ok={memOk}     label="Memory"  sub={memOk ? `${health.memory.backend} · ${health.memory.total ?? "?"}` : "unavailable"} />
      <Dot ok={!degraded} label="API"     sub={degraded ? "degraded" : "healthy"} />
      {health.uci?.h_uci != null && (
        <div style={{ marginLeft: "auto", fontSize: 10, color: T.muted, fontFamily: FONT_MONO }}>
          live h_UCI <span style={{ color: hScore(health.uci.h_uci), fontWeight: 700 }}>{health.uci.h_uci.toFixed(1)}</span>
        </div>
      )}
    </div>
  );
}

// ── UCI trajectory + curvature sparkline ──────────────────────
function UCITrajectory({ traj }) {
  const hist = traj?.history || [];
  if (hist.length < 2) {
    return <EmptyState msg="Not enough UCI samples yet — trajectory builds as metrics recompute." />;
  }

  const vals = hist.map(h => h.uci);
  const curv = traj?.curvature?.curvature || [];   // aligns to interior points
  const W = 560, H = 90, PX = 8, PY = 10;
  const iW = W - 2 * PX, iH = H - 2 * PY;
  // Fixed 0–100 UCI scale so the slope is honest across refreshes.
  const xs = i => PX + (i / Math.max(1, vals.length - 1)) * iW;
  const ys = v => PY + (1 - Math.max(0, Math.min(100, v)) / 100) * iH;
  const pts = vals.map((v, i) => `${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(" ");

  const last  = vals[vals.length - 1];
  const first = vals[0];
  const trend = last - first;

  // Mark the sharpest bend (peak |Δ²|). curvature[k] corresponds to vals[k+1].
  let peakIdx = -1, peakVal = 0;
  curv.forEach((c, k) => { if (Math.abs(c) > Math.abs(peakVal)) { peakVal = c; peakIdx = k + 1; } });

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block", overflow: "visible" }}>
        {/* 80 / 60 reference grid (Healthy / Nominal thresholds) */}
        {[80, 60].map(g => (
          <line key={g} x1={PX} y1={ys(g)} x2={W - PX} y2={ys(g)}
            stroke={T.border} strokeWidth={1} strokeDasharray="3 4" />
        ))}
        {/* UCI line */}
        <polyline points={pts} fill="none" stroke={hScore(last)} strokeWidth={1.8}
          strokeLinejoin="round" strokeLinecap="round" />
        {/* Sharpest-bend marker */}
        {peakIdx >= 0 && Math.abs(peakVal) > 1 && (
          <circle cx={xs(peakIdx)} cy={ys(vals[peakIdx])} r={3.5}
            fill="none" stroke={Math.abs(peakVal) > 2 ? T.error : T.warn} strokeWidth={1.5} />
        )}
        {/* Latest point */}
        <circle cx={xs(vals.length - 1)} cy={ys(last)} r={3} fill={hScore(last)} />
      </svg>
      <div style={{ display: "flex", gap: 14, marginTop: 6, fontSize: 10, color: T.muted, flexWrap: "wrap" }}>
        <span>{vals.length} samples</span>
        <span>range <span style={{ fontFamily: FONT_MONO }}>{Math.min(...vals).toFixed(1)}–{Math.max(...vals).toFixed(1)}</span></span>
        <span style={{ color: trend >= 0 ? T.success : T.error }}>
          {trend >= 0 ? "↑" : "↓"} {trend >= 0 ? "+" : ""}{trend.toFixed(1)} over window
        </span>
      </div>
    </div>
  );
}

// ── Curvature "bend alarm" badge (OCAC Δ² leading indicator) ───
function CurvatureBadge({ curvature }) {
  if (!curvature || curvature.n < 3) return null;
  const peak = curvature.peak_abs_curvature ?? 0;
  const bending = curvature.bending;
  const col = bending ? T.error : peak > 1 ? T.warn : T.success;
  const label = bending ? "bending" : peak > 1 ? "flexing" : "stable";
  return (
    <span
      title={`Δ² leading indicator — peak |curvature| = ${peak.toFixed(2)} UCI pts.\n>2 pts signals an accelerating downturn before the level drops (OCAC).`}
      style={{
        fontSize: 9, fontWeight: 700, fontFamily: FONT_MONO,
        color: col, background: `${col}18`, border: `1px solid ${col}44`,
        borderRadius: 3, padding: "1px 5px", whiteSpace: "nowrap",
      }}>
      Δ² {peak.toFixed(1)} · {label}
    </span>
  );
}

// ── Routing-accuracy source badge (measured vs assumed) ───────
function SourceBadge({ source }) {
  if (!source) return null;
  const measured = source === "measured";
  const col = measured ? T.success : T.muted;
  return (
    <span
      title={measured
        ? "Routing accuracy measured live from the most recent agent_arena run."
        : "No agent_arena run on record — showing the static ablation snapshot, not a live measurement."}
      style={{
        fontSize: 8, fontWeight: 700, fontFamily: FONT_MONO, letterSpacing: 0.4,
        color: col, background: `${col}14`, border: `1px solid ${col}40`,
        borderRadius: 3, padding: "0 4px", textTransform: "uppercase",
      }}>
      {measured ? "measured" : "assumed"}
    </span>
  );
}

// ── Layer detail grid ─────────────────────────────────────────
function LayerDetail({ name, layer }) {
  if (!layer) return null;
  const comps = { ...layer };
  delete comps.score;
  delete comps.weight;
  // Rendered inline on the routing_accuracy card, not as its own cell.
  const routingSource = comps.routing_accuracy_source;
  delete comps.routing_accuracy_source;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: T.mutedLt }}>{name}</span>
        <span style={{ fontSize: 11, fontFamily: FONT_MONO, color: hScore(layer.score) }}>
          {layer.score?.toFixed(1)}
        </span>
        {layer.weight != null && (
          <span style={{ fontSize: 10, color: T.muted }}>
            {((layer.weight) * 100).toFixed(0)}% weight
          </span>
        )}
      </div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
        gap: 6,
      }}>
        {Object.entries(comps).map(([k, v]) => (
          <div key={k} style={{
            background: T.surface2, borderRadius: 4, padding: "6px 10px",
            border: `1px solid ${T.border}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: 0.8 }}>
                {k.replace(/_/g, " ")}
              </div>
              {k === "routing_accuracy" && <SourceBadge source={routingSource} />}
            </div>
            <div style={{
              fontSize: 13, fontWeight: 700, fontFamily: FONT_MONO,
              color: typeof v === "number" && v <= 100 ? hScore(v) : T.text,
              marginTop: 2,
            }}>
              {typeof v === "number"
                ? (v > 1 && v <= 100 ? v.toFixed(1) + "%" : v.toFixed(2))
                : String(v ?? "—")}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Risk signal strip ─────────────────────────────────────────
function RiskStrip({ risk }) {
  if (!risk) return (
    <div style={{ fontSize: 11, color: T.muted, padding: "8px 0" }}>
      No risk signal yet — run a query to populate.
    </div>
  );

  const levelColor = {
    none:  T.success,
    light: T.warn,
    full:  T.error,
  }[risk.reflect_level] || T.muted;

  return (
    <div style={{
      background: T.surface2, borderRadius: 4, padding: "10px 12px",
      border: `1px solid ${levelColor}44`,
      display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-start",
    }}>
      <div>
        <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: 0.8 }}>Reflect level</div>
        <div style={{ fontSize: 14, fontWeight: 700, color: levelColor, fontFamily: FONT_MONO }}>
          {risk.reflect_level ?? "—"}
        </div>
      </div>
      <div>
        <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: 0.8 }}>Total risk</div>
        <div style={{ fontSize: 14, fontWeight: 700, color: hScore((1 - (risk.total_risk ?? 0.5)) * 100), fontFamily: FONT_MONO }}>
          {risk.total_risk != null ? risk.total_risk.toFixed(3) : "—"}
        </div>
      </div>
      {risk.reflect_type && (
        <div>
          <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: 0.8 }}>Type</div>
          <div style={{ fontSize: 13, color: T.mutedLt }}>{risk.reflect_type}</div>
        </div>
      )}
    </div>
  );
}

// ── Component transparency ────────────────────────────────────
const TP_COLOR = {
  transparent: T.success,
  partial:     T.warn,
  opaque:      T.error,
  unobserved:  T.muted,
};

function TransparencyPanel({ data }) {
  if (!data) return <EmptyState msg="No transparency signal yet." />;

  const { summary = {}, transparency_score = 0, components = [] } = data;
  const pct = Math.round(transparency_score * 100);

  return (
    <div>
      {/* Score + summary chips */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10, flexWrap: "wrap" }}>
        <div style={{ textAlign: "center", minWidth: 54 }}>
          <div style={{ fontFamily: FONT_MONO, fontSize: 22, fontWeight: 700, color: hScore(pct), lineHeight: 1 }}>
            {pct}%
          </div>
          <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>transparent</div>
        </div>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap", flex: 1 }}>
          {["transparent", "partial", "opaque", "unobserved"].map(s => (
            summary[s] ? (
              <span key={s} title={s} style={{
                fontSize: 9, fontFamily: FONT_MONO, fontWeight: 700,
                color: TP_COLOR[s], background: `${TP_COLOR[s]}18`,
                border: `1px solid ${TP_COLOR[s]}44`, borderRadius: 3, padding: "1px 5px",
              }}>
                {summary[s]} {s}
              </span>
            ) : null
          ))}
        </div>
      </div>

      {/* Per-component rows */}
      <div style={{ maxHeight: 220, overflowY: "auto" }}>
        {components.map((c) => (
          <div key={c.component} title={
            c.status === "unobserved"
              ? "Emitted no events in the observation window"
              : `confidence: ${c.confidence_keys.join(", ") || "none"}\nevidence: ${c.evidence_keys.join(", ") || "none"}`
          } style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "5px 0", borderBottom: `1px solid ${T.border}`,
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
              background: TP_COLOR[c.status] || T.muted,
              boxShadow: c.status === "transparent" ? `0 0 5px ${T.success}88` : "none",
            }} />
            <span style={{ fontSize: 11, color: T.mutedLt, fontWeight: 600, flex: 1 }}>
              {c.component}
            </span>
            {/* confidence / evidence presence ticks */}
            <span style={{ display: "flex", gap: 4, fontSize: 8, fontFamily: FONT_MONO }}>
              <span title="discloses confidence" style={{ color: c.has_confidence ? T.success : T.muted + "66" }}>◆conf</span>
              <span title="discloses evidence"   style={{ color: c.has_evidence   ? T.success : T.muted + "66" }}>◆evid</span>
            </span>
            <span style={{ fontSize: 9, fontFamily: FONT_MONO, color: T.muted, minWidth: 30, textAlign: "right" }}>
              {c.events > 0 ? c.events : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Mini event feed ───────────────────────────────────────────
function MiniEventFeed({ events }) {
  if (!events?.length) return <EmptyState msg="No events yet." />;
  return (
    <div style={{ maxHeight: 260, overflowY: "auto" }}>
      {events.slice(0, 20).map((e, i) => (
        <EventRow key={i} event={e} compact />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────
export default function UCIDashboard({ embedded = false } = {}) {
  const [uci,     setUCI]     = useState(null);
  const [cos,     setCos]     = useState(null);
  const [events,  setEvents]  = useState([]);
  const [health,  setHealth]  = useState(null);
  const [transp,  setTransp]  = useState(null);
  const [traj,    setTraj]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/cos/uci/hierarchical`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/state`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/events?n=30`).then(r => r.json()).catch(() => null),
      fetch(`${API}/health`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/transparency`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/uci/trajectory?n=100`).then(r => r.json()).catch(() => null),
    ]).then(([u, s, ev, h, tp, tj]) => {
      setUCI(u);
      setCos(s);
      setEvents(ev?.events || []);
      setHealth(h);
      setTransp(tp);
      setTraj(tj);
      setError(null);
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); const id = setInterval(load, 25_000); return () => clearInterval(id); }, []);

  const layers = uci?.layers || {};
  const hUCI   = uci?.h_uci;
  const legacy = uci?.legacy_uci;
  const risk   = cos?.risk;

  const delta = hUCI != null ? hUCI - BASELINE_HUCI : null;

  return (
    <div style={{ padding: embedded ? "10px 14px 14px" : 0 }}>

      {/* Header (suppressed when embedded — the dashboard cell carries the title) */}
      {!embedded && (
      <PageHeader
        title="Cognitive Index"
        subtitle="Unified Cognitive Index · 30% Reliability · 30% Intelligence · 25% Adaptation · 15% Productivity"
      >
        <RefreshBtn onClick={load} />
      </PageHeader>
      )}

      {/* System health strip */}
      <HealthStrip health={health} />

      {error && (
        <div style={{ color: T.error, background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 5, padding: "8px 14px", marginBottom: 16, fontSize: 12 }}>
          Backend unavailable: {error}
        </div>
      )}

      {/* Main layout: left = scores, right = live signal */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16, alignItems: "start" }}>

        {/* LEFT — scores */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* h_UCI hero + legacy side-by-side */}
          <ObsPanel>
            <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ textAlign: "center", minWidth: 80 }}>
                <div style={{
                  fontFamily: FONT_MONO, fontSize: 52, fontWeight: 700,
                  color: hScore(hUCI), lineHeight: 1,
                }}>
                  {hUCI != null ? hUCI.toFixed(1) : "—"}
                </div>
                <div style={{ fontSize: 10, color: T.muted, marginTop: 3, display: "flex", gap: 5, justifyContent: "center", alignItems: "center", flexWrap: "wrap" }}>
                  <span>h_UCI</span>
                  {delta != null && (
                    <span style={{
                      fontSize: 9, fontWeight: 700, fontFamily: FONT_MONO,
                      color: delta >= 0 ? T.success : T.error,
                      background: delta >= 0 ? `${T.success}18` : `${T.error}18`,
                      border: `1px solid ${delta >= 0 ? T.success : T.error}44`,
                      borderRadius: 3, padding: "1px 5px",
                    }}
                    title={`Baseline ${BASELINE_HUCI.toFixed(1)} (pre-Phase 37)`}>
                      {delta >= 0 ? "↑" : "↓"} {delta >= 0 ? "+" : ""}{delta.toFixed(1)}
                    </span>
                  )}
                  <CurvatureBadge curvature={traj?.curvature} />
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", gap: 16, marginBottom: 8, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontSize: 10, color: T.muted }}>Legacy UCI</div>
                    <div style={{ fontFamily: FONT_MONO, fontSize: 16, color: hScore(legacy) }}>
                      {legacy != null ? legacy.toFixed(1) : "—"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: T.muted }}>Status</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: hScore(hUCI) }}>
                      {hUCI == null ? "Offline" : hUCI >= 80 ? "Healthy" : hUCI >= 60 ? "Nominal" : "Degraded"}
                    </div>
                  </div>
                </div>
                {/* 4 layer summary bars */}
                {["Reliability", "Intelligence", "Adaptation", "Productivity"].map(name => (
                  <div key={name} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                    <div style={{ fontSize: 11, color: T.muted, minWidth: 88 }}>{name}</div>
                    <div style={{ flex: 1, background: T.surface2, borderRadius: 2, height: 5 }}>
                      <div style={{
                        width: `${Math.min(100, layers[name]?.score ?? 0)}%`, height: "100%",
                        background: hScore(layers[name]?.score), borderRadius: 2,
                        transition: "width 0.5s ease",
                      }} />
                    </div>
                    <div style={{ fontSize: 10, fontFamily: FONT_MONO, color: hScore(layers[name]?.score), minWidth: 34, textAlign: "right" }}>
                      {layers[name]?.score?.toFixed(1) ?? "—"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </ObsPanel>

          {/* UCI trajectory + Δ² curvature */}
          <ObsPanel title="UCI Trajectory" icon="∿">
            <UCITrajectory traj={traj} />
          </ObsPanel>

          {/* Layer detail cards */}
          <ObsPanel title="Layer Components" icon="◑">
            {loading && !uci ? (
              <div style={{ color: T.muted, fontSize: 12 }}>Loading…</div>
            ) : (
              <>
                <LayerDetail name="Reliability"  layer={layers.Reliability} />
                <LayerDetail name="Intelligence" layer={layers.Intelligence} />
                <LayerDetail name="Adaptation"   layer={layers.Adaptation} />
                <LayerDetail name="Productivity" layer={layers.Productivity} />
              </>
            )}
          </ObsPanel>
        </div>

        {/* RIGHT — live signal */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Risk signal */}
          <ObsPanel title="Last Risk Signal" icon="⚑">
            <RiskStrip risk={risk} />
          </ObsPanel>

          {/* Component transparency */}
          <ObsPanel title="Component Transparency" icon="◇">
            <TransparencyPanel data={transp} />
          </ObsPanel>

          {/* Live event feed */}
          <ObsPanel title="Recent Events" icon="≡" style={{ flex: 1 }}>
            <MiniEventFeed events={events} />
          </ObsPanel>

        </div>
      </div>
    </div>
  );
}
