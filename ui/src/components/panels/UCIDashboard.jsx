import { T, FONT_MONO } from "@/styles/theme";
import { ObsPanel, EventRow, EmptyState, hScore, TrendChart, Notice } from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

// ── Cognitive Index (Diagnostics section) ─────────────────────────
// Section contract: content only — the host owns the header and refresh.

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

// ── UCI trajectory + curvature ────────────────────────────────
// The shared TrendChart owns the drawing; this owns the reading of it — a
// fixed 0–100 domain so the slope stays honest across refreshes, the 80/60
// Healthy/Nominal grid, and a ring on the sharpest Δ² bend.
function UCITrajectory({ traj }) {
  const hist = traj?.history || [];
  if (hist.length < 2) {
    return <EmptyState msg="Not enough UCI samples yet — trajectory builds as metrics recompute." />;
  }

  const vals = hist.map(h => h.uci);
  const curv = traj?.curvature?.curvature || [];   // aligns to interior points

  const last  = vals[vals.length - 1];
  const trend = last - vals[0];

  // Peak |Δ²|. curvature[k] describes vals[k+1], so the index shifts by one.
  let peakIdx = -1, peakVal = 0;
  curv.forEach((c, k) => { if (Math.abs(c) > Math.abs(peakVal)) { peakVal = c; peakIdx = k + 1; } });

  return (
    <div>
      <TrendChart
        height={110}
        domain={[0, 100]}
        grid={[60, 80]}
        format={v => v.toFixed(0)}
        series={[{ label: "h_UCI", values: vals, tone: hScore(last), emphasis: true }]}
        marker={peakIdx >= 0 && Math.abs(peakVal) > 1
          ? { index: peakIdx, tone: Math.abs(peakVal) > 2 ? "error" : "warn",
              title: `Sharpest bend: Δ² = ${peakVal.toFixed(2)} UCI pts` }
          : null}
      />
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
// How a number came to exist. Three states, and the badge says which one it
// actually is rather than collapsing them into measured/not: a `proxy` is a
// stand-in the system computed, an `assumed` is a static snapshot nobody
// re-measured. Reporting a proxy as "assumed" understates it, and reporting it
// as measured would be a lie — this surface's whole claim is that it shows its
// own uncertainty honestly.
const SOURCE_META = {
  measured: { tone: T.success, hint: "Measured live from the most recent run." },
  proxy:    { tone: T.warn,    hint: "Derived from a stand-in signal, not measured directly." },
  assumed:  { tone: T.muted,   hint: "Static snapshot — nothing on record re-measured this." },
};

function SourceBadge({ source }) {
  if (!source) return null;
  const meta = SOURCE_META[source] || SOURCE_META.assumed;
  return (
    <span
      title={meta.hint}
      style={{
        fontSize: 8, fontWeight: 700, fontFamily: FONT_MONO, letterSpacing: 0.4,
        color: meta.tone, background: `${meta.tone}14`, border: `1px solid ${meta.tone}40`,
        borderRadius: 3, padding: "0 4px", textTransform: "uppercase",
      }}>
      {source}
    </span>
  );
}

// ── Layer component formatting ────────────────────────────────
// A layer mixes three kinds of number and they cannot be rendered by one rule.

// Counts, not percentages. "342 completed tasks" rendered as "342.00" reads
// like a score that overflowed its scale.
const COUNT_KEY = /(_tasks|_sessions|_count)$/;

// Metrics where LOW is good. Everything else in a layer is "higher is better",
// so the shared score coloring works — but abort_rate 0.0, a perfect result,
// came out red, which is the panel reporting success as failure.
const INVERTED_KEY = /^(abort_rate)$/;

function fmtComponent(k, v) {
  if (typeof v !== "number") return String(v ?? "—");
  if (COUNT_KEY.test(k) || v > 100) return v.toLocaleString();
  return `${v.toFixed(1)}%`;
}

function componentTone(k, v) {
  if (typeof v !== "number") return T.text;
  if (COUNT_KEY.test(k) || v > 100) return T.text;   // a count has no health
  return hScore(INVERTED_KEY.test(k) ? 100 - v : v);
}

// ── Layer detail grid ─────────────────────────────────────────
function LayerDetail({ name, layer }) {
  if (!layer) return null;
  const comps = { ...layer };
  delete comps.score;
  delete comps.weight;

  // Every metric ships a sibling `<metric>_source` telling you whether it was
  // measured or assumed. Those are ANNOTATIONS on their metric, not metrics —
  // pull them all out and render each as a badge on the card it describes.
  // This used to special-case `routing_accuracy_source` alone, which was
  // invisibly fine only because the whole grid was rendering empty; with the
  // layer lookup fixed, the other five would have shown up as their own cells
  // reading "measured".
  const sources = {};
  for (const k of Object.keys(comps)) {
    if (k.endsWith("_source")) {
      sources[k.slice(0, -"_source".length)] = comps[k];
      delete comps[k];
    }
  }

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
              {sources[k] && <SourceBadge source={sources[k]} />}
            </div>
            <div style={{
              fontSize: 13, fontWeight: 700, fontFamily: FONT_MONO,
              color: componentTone(k, v), marginTop: 2,
            }}>
              {fmtComponent(k, v)}
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
  mechanical:  T.muted,
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
          {["transparent", "partial", "opaque", "mechanical", "unobserved"].map(s => (
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
              : c.status === "mechanical"
                ? c.rationale || "Deterministic reduction over fully-disclosed inputs"
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
export default function UCIDashboard() {
  const { data: uci, error, loading } = usePoll("/cos/uci/hierarchical", { interval: 25_000 });
  const { data: cos }    = usePoll("/cos/state",               { interval: 25_000 });
  const { data: health } = usePoll("/health",                  { interval: 25_000 });
  const { data: transp } = usePoll("/cos/transparency",        { interval: 25_000 });
  const { data: traj }   = usePoll("/cos/uci/trajectory?n=100",{ interval: 25_000 });
  // Shares the Events section's subscription — same URL, one request between
  // them. This panel used to fetch `?n=30` alongside it on a different clock,
  // so the surface polled the event bus twice and the two feeds disagreed.
  const { data: evData } = usePoll("/cos/events?n=200",        { interval: 25_000 });

  const events = evData?.events || [];
  // GET /cos/uci/hierarchical keys its layers in lower case ("reliability"),
  // and this panel had always looked them up in Title Case ("Reliability") —
  // so every lookup returned undefined and the four summary bars and the whole
  // Layer Components panel rendered empty, under a hero number that worked
  // fine. Silent, because a missing key is not an error: it just draws "—".
  // Match on the lower-cased key and keep Title Case for display.
  const layers = Object.fromEntries(
    Object.entries(uci?.layers || {}).map(([k, v]) => [k.toLowerCase(), v])
  );
  const layer = (name) => layers[name.toLowerCase()];
  const hUCI   = uci?.h_uci;
  const legacy = uci?.legacy_uci;
  const risk   = cos?.risk;

  const delta = hUCI != null ? hUCI - BASELINE_HUCI : null;

  return (
    <div>
      {/* System health strip */}
      <HealthStrip health={health} />

      {error && <Notice tone="error">Backend unavailable: {error}</Notice>}

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
                        width: `${Math.min(100, layer(name)?.score ?? 0)}%`, height: "100%",
                        background: hScore(layer(name)?.score), borderRadius: 2,
                        transition: "width 0.5s ease",
                      }} />
                    </div>
                    <div style={{ fontSize: 10, fontFamily: FONT_MONO, color: hScore(layer(name)?.score), minWidth: 34, textAlign: "right" }}>
                      {layer(name)?.score?.toFixed(1) ?? "—"}
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
                <LayerDetail name="Reliability"  layer={layer("Reliability")} />
                <LayerDetail name="Intelligence" layer={layer("Intelligence")} />
                <LayerDetail name="Adaptation"   layer={layer("Adaptation")} />
                <LayerDetail name="Productivity" layer={layer("Productivity")} />
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
