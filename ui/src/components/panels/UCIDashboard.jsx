import {
  ObsPanel, EventRow, EmptyState, TrendChart, Notice, HeroStat, ScoreBar,
  Grid, Split, Stack, Row, Spacer, Scroll, Well, Tile, Pill, Dot,
  Micro, Small, Caption, Inline, scoreTone, hScore,
} from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

// ── Cognitive Index (Diagnostics section) ─────────────────────────
// Section contract: content only — the host owns the header and refresh.

const BASELINE_HUCI = 75.1;   // h_UCI before Phase 37 fixes

const LEVEL_TONE = { none: "success", light: "warn", full: "error" };

// Risk runs backwards from every other score here — 0 is safe, 1 is abort — so
// it is inverted before being coloured.
const riskTone = (v) => (v == null ? "muted" : scoreTone((1 - v) * 100));

// ── System health strip ────────────────────────────────────────
function HealthStrip({ health }) {
  if (!health) return null;

  const ollamaOk = health.ollama === "online";
  const memOk    = health.memory?.backend != null;
  const degraded = health.status === "degraded";

  return (
    <Well tone={degraded ? "warn" : undefined}>
      <Row gap="lg" wrap>
        <Caption>System</Caption>
        <Row gap="xs">
          <Dot tone={ollamaOk ? "success" : "error"} />
          <Small tone={ollamaOk ? "subtle" : "error"}>Ollama</Small>
          <Micro>{ollamaOk ? "serving" : "offline"}</Micro>
        </Row>
        <Row gap="xs">
          <Dot tone={memOk ? "success" : "error"} />
          <Small tone={memOk ? "subtle" : "error"}>Memory</Small>
          <Micro>{memOk ? `${health.memory.backend} · ${health.memory.total ?? "?"}` : "unavailable"}</Micro>
        </Row>
        <Row gap="xs">
          <Dot tone={degraded ? "warn" : "success"} />
          <Small tone={degraded ? "warn" : "subtle"}>API</Small>
          <Micro>{degraded ? "degraded" : "healthy"}</Micro>
        </Row>
        <Spacer />
        {health.uci?.h_uci != null && (
          <Micro>
            live h_UCI{" "}
            <Inline role="micro" mono weight={700} tone={scoreTone(health.uci.h_uci)}>
              {health.uci.h_uci.toFixed(1)}
            </Inline>
          </Micro>
        )}
      </Row>
    </Well>
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
    <Stack gap="xs">
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
      <Row gap="md" wrap>
        <Micro>{vals.length} samples</Micro>
        <Micro mono>range {Math.min(...vals).toFixed(1)}–{Math.max(...vals).toFixed(1)}</Micro>
        <Micro tone={trend >= 0 ? "success" : "error"}>
          {trend >= 0 ? "↑" : "↓"} {trend >= 0 ? "+" : ""}{trend.toFixed(1)} over window
        </Micro>
      </Row>
    </Stack>
  );
}

// ── Layer component formatting ────────────────────────────────
// A layer mixes three kinds of number and they cannot be rendered by one rule.

// Counts, not percentages. "342 completed tasks" rendered as "342.00" reads
// like a score that overflowed its scale.
const COUNT_KEY = /(_tasks|_sessions|_count)$/;

// Metrics where LOW is good. Everything else in a layer is "higher is better",
// so the shared score colouring works — but abort_rate 0.0, a perfect result,
// came out red, which is the panel reporting success as failure.
const INVERTED_KEY = /^(abort_rate)$/;

function fmtComponent(k, v) {
  if (typeof v !== "number") return String(v ?? "—");
  if (COUNT_KEY.test(k) || v > 100) return v.toLocaleString();
  return `${v.toFixed(1)}%`;
}

function componentTone(k, v) {
  if (typeof v !== "number") return "default";
  if (COUNT_KEY.test(k) || v > 100) return "default";   // a count has no health
  return scoreTone(INVERTED_KEY.test(k) ? 100 - v : v);
}

// How a number came to exist. Three states, and the badge says which one it
// actually is rather than collapsing them into measured/not: a `proxy` is a
// stand-in the system computed, an `assumed` is a static snapshot nobody
// re-measured. Reporting a proxy as "assumed" understates it, and reporting it
// as measured would be a lie — this surface's whole claim is that it shows its
// own uncertainty honestly.
const SOURCE_TONE = { measured: "success", proxy: "warn", assumed: "muted" };
const SOURCE_HINT = {
  measured: "Measured live from the most recent run.",
  proxy:    "Derived from a stand-in signal, not measured directly.",
  assumed:  "Static snapshot — nothing on record re-measured this.",
};

// ── Layer detail grid ─────────────────────────────────────────
function LayerDetail({ name, layer }) {
  if (!layer) return null;
  const comps = { ...layer };
  delete comps.score;
  delete comps.weight;

  // Every metric ships a sibling `<metric>_source` telling you whether it was
  // measured or assumed. Those are ANNOTATIONS on their metric, not metrics —
  // pull them all out and render each as a badge on the card it describes.
  const sources = {};
  for (const k of Object.keys(comps)) {
    if (k.endsWith("_source")) {
      sources[k.slice(0, -"_source".length)] = comps[k];
      delete comps[k];
    }
  }

  return (
    <Stack gap="xs">
      <Row gap="sm">
        <Small weight={600} tone="subtle">{name}</Small>
        <Inline role="caption" mono tone={scoreTone(layer.score)}>{layer.score?.toFixed(1)}</Inline>
        {layer.weight != null && <Micro>{(layer.weight * 100).toFixed(0)}% weight</Micro>}
      </Row>
      <Grid min={140} gap="xs">
        {Object.entries(comps).map(([k, v]) => (
          <Tile
            key={k}
            label={
              <Row gap="xs">
                <Micro>{k.replace(/_/g, " ")}</Micro>
                {sources[k] && (
                  <span title={SOURCE_HINT[sources[k]] || SOURCE_HINT.assumed}>
                    <Pill tone={SOURCE_TONE[sources[k]] || "muted"}>{sources[k]}</Pill>
                  </span>
                )}
              </Row>
            }
            value={fmtComponent(k, v)}
            tone={componentTone(k, v)}
          />
        ))}
      </Grid>
    </Stack>
  );
}

// ── Risk signal strip ─────────────────────────────────────────
function RiskStrip({ risk }) {
  if (!risk) return <EmptyState msg="No risk signal yet — run a query to populate." />;

  return (
    <Well tone={LEVEL_TONE[risk.reflect_level] || "muted"}>
      <Row gap="lg" wrap>
        <Tile label="Reflect level" value={risk.reflect_level ?? "—"}
              tone={LEVEL_TONE[risk.reflect_level] || "muted"} />
        <Tile label="Total risk" tone={riskTone(risk.total_risk)}
              value={risk.total_risk != null ? risk.total_risk.toFixed(3) : "—"} />
        {risk.reflect_type && <Tile label="Type" value={risk.reflect_type} mono={false} tone="subtle" />}
      </Row>
    </Well>
  );
}

// ── Component transparency ────────────────────────────────────
const TP_TONE = {
  transparent: "success", partial: "warn", opaque: "error",
  unobserved: "muted", mechanical: "muted",
};

function TransparencyPanel({ data }) {
  if (!data) return <EmptyState msg="No transparency signal yet." />;

  const { summary = {}, transparency_score = 0, components = [] } = data;
  const pct = Math.round(transparency_score * 100);

  return (
    <Stack gap="sm">
      <Row gap="sm" wrap>
        <Inline role="metric" mono tone={scoreTone(pct)}>{pct}%</Inline>
        <Micro>transparent</Micro>
        <Spacer />
        <Row gap="xs" wrap>
          {["transparent", "partial", "opaque", "mechanical", "unobserved"].map(s => (
            summary[s]
              ? <Pill key={s} tone={TP_TONE[s]}>{summary[s]} {s}</Pill>
              : null
          ))}
        </Row>
      </Row>

      <Scroll max="220px">
        {components.map(c => (
          <div key={c.component} title={
            c.status === "unobserved"
              ? "Emitted no events in the observation window"
              : c.status === "mechanical"
                ? c.rationale || "Deterministic reduction over fully-disclosed inputs"
                : `confidence: ${c.confidence_keys.join(", ") || "none"}\nevidence: ${c.evidence_keys.join(", ") || "none"}`
          }>
            <Row gap="sm">
              <Dot tone={TP_TONE[c.status] || "muted"} />
              <Small weight={600} tone="subtle">{c.component}</Small>
              <Spacer />
              {/* Whether the component discloses its own confidence and
                  evidence — the two things this score is actually measuring. */}
              <Micro tone={c.has_confidence ? "success" : "muted"}>conf</Micro>
              <Micro tone={c.has_evidence   ? "success" : "muted"}>evid</Micro>
              <Micro mono>{c.events > 0 ? c.events : "—"}</Micro>
            </Row>
          </div>
        ))}
      </Scroll>
    </Stack>
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
  const layers = Object.fromEntries(
    Object.entries(uci?.layers || {}).map(([k, v]) => [k.toLowerCase(), v])
  );
  const layer = (name) => layers[name.toLowerCase()];

  const hUCI   = uci?.h_uci;
  const legacy = uci?.legacy_uci;
  const delta  = hUCI != null ? hUCI - BASELINE_HUCI : null;
  const curv   = traj?.curvature;
  const peak   = curv?.peak_abs_curvature ?? 0;

  const LAYERS = ["Reliability", "Intelligence", "Adaptation", "Productivity"];

  return (
    <Stack gap="md">
      <HealthStrip health={health} />
      {error && <Notice tone="error">Backend unavailable: {error}</Notice>}

      <Split side={320}>
        {/* MAIN — the scores */}
        <Stack gap="md">
          <HeroStat
            value={hUCI != null ? hUCI.toFixed(1) : "—"}
            tone={scoreTone(hUCI)}
            label="h_UCI — 30% Reliability · 30% Intelligence · 25% Adaptation · 15% Productivity"
            badges={
              <>
                <Pill tone={scoreTone(hUCI)} strong>
                  {hUCI == null ? "Offline" : hUCI >= 80 ? "Healthy" : hUCI >= 60 ? "Nominal" : "Degraded"}
                </Pill>
                {delta != null && (
                  <span title={`Baseline ${BASELINE_HUCI.toFixed(1)} (pre-Phase 37)`}>
                    <Pill tone={delta >= 0 ? "success" : "error"}>
                      {delta >= 0 ? "↑ +" : "↓ "}{delta.toFixed(1)} vs baseline
                    </Pill>
                  </span>
                )}
                {curv?.n >= 3 && (
                  <span title={`Δ² leading indicator — peak |curvature| = ${peak.toFixed(2)} UCI pts.\n>2 pts signals an accelerating downturn before the level drops (OCAC).`}>
                    <Pill tone={curv.bending ? "error" : peak > 1 ? "warn" : "success"}>
                      Δ² {peak.toFixed(1)} · {curv.bending ? "bending" : peak > 1 ? "flexing" : "stable"}
                    </Pill>
                  </span>
                )}
              </>
            }
          >
            <Row gap="md" wrap>
              <Micro>
                legacy UCI{" "}
                <Inline role="micro" mono tone={scoreTone(legacy)}>
                  {legacy != null ? legacy.toFixed(1) : "—"}
                </Inline>
              </Micro>
            </Row>
            {LAYERS.map(name => (
              <ScoreBar key={name} label={name} value={layer(name)?.score} />
            ))}
          </HeroStat>

          <ObsPanel title="UCI trajectory" icon="∿">
            <UCITrajectory traj={traj} />
          </ObsPanel>

          <ObsPanel title="Layer components" icon="◑">
            {loading && !uci ? (
              <EmptyState msg="Loading…" />
            ) : (
              <Stack gap="md">
                {LAYERS.map(name => (
                  <LayerDetail key={name} name={name} layer={layer(name)} />
                ))}
              </Stack>
            )}
          </ObsPanel>
        </Stack>

        {/* RAIL — the live signal */}
        <Stack gap="md">
          <ObsPanel title="Last risk signal" icon="⚑">
            <RiskStrip risk={cos?.risk} />
          </ObsPanel>

          <ObsPanel title="Component transparency" icon="◇">
            <TransparencyPanel data={transp} />
          </ObsPanel>

          <ObsPanel title="Recent events" icon="≡">
            {events.length === 0 ? (
              <EmptyState msg="No events yet." />
            ) : (
              <Scroll max="260px">
                {events.slice(0, 20).map((e, i) => <EventRow key={i} event={e} compact />)}
              </Scroll>
            )}
          </ObsPanel>
        </Stack>
      </Split>
    </Stack>
  );
}
