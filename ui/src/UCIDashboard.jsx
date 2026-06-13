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

// ── Layer detail grid ─────────────────────────────────────────
function LayerDetail({ name, layer }) {
  if (!layer) return null;
  const comps = { ...layer };
  delete comps.score;
  delete comps.weight;

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
            <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: 0.8 }}>
              {k.replace(/_/g, " ")}
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
export default function UCIDashboard() {
  const [uci,     setUCI]     = useState(null);
  const [cos,     setCos]     = useState(null);
  const [events,  setEvents]  = useState([]);
  const [health,  setHealth]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/cos/uci/hierarchical`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/state`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/events?n=30`).then(r => r.json()).catch(() => null),
      fetch(`${API}/health`).then(r => r.json()).catch(() => null),
    ]).then(([u, s, ev, h]) => {
      setUCI(u);
      setCos(s);
      setEvents(ev?.events || []);
      setHealth(h);
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
    <div>

      {/* Header */}
      <PageHeader
        title="Cognitive Index"
        subtitle="Unified Cognitive Index · 30% Reliability · 30% Intelligence · 25% Adaptation · 15% Productivity"
      >
        <RefreshBtn onClick={load} />
      </PageHeader>

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
                <div style={{ fontSize: 10, color: T.muted, marginTop: 3, display: "flex", gap: 5, justifyContent: "center", alignItems: "center" }}>
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

          {/* Live event feed */}
          <ObsPanel title="Recent Events" icon="≡" style={{ flex: 1 }}>
            <MiniEventFeed events={events} />
          </ObsPanel>

        </div>
      </div>
    </div>
  );
}
