import {
  ObsPanel, MetricCard, EmptyState, TrendChart, Notice, Table, Grid, Stack,
  Row, Spacer, Dot, Micro, Inline, StackedBar, BarRow, Scroll, scoreTone,
} from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

// ── Risk Observatory (Diagnostics section) ────────────────────────
// Section contract: content only — the host owns the header and refresh.
//
// The reflect level is the gate's verdict on a query, and it is the one piece
// of vocabulary this whole panel is built from: the distribution bar, the dots
// on the timeline and the rows below all encode the same three states in the
// same three tones, so a colour means the same thing everywhere on screen.
const LEVELS = [
  { id: "none",  label: "None",  tone: "success" },
  { id: "light", label: "Light", tone: "warn" },
  { id: "full",  label: "Full",  tone: "error" },
];
const toneOf = (level) => LEVELS.find(l => l.id === level)?.tone || "muted";

// Risk runs backwards from every other score here: 0 is safe, 1 is abort. The
// shared scoreTone expects "higher is better", so the value is inverted before
// it is coloured — otherwise a perfectly safe 0.0 would render as a failure.
const riskTone = (v) => (v == null ? "muted" : scoreTone((1 - v) * 100));

// ── Reflect-level distribution ────────────────────────────────
function LevelDistribution({ byLevel, total }) {
  if (!byLevel || !total) return <EmptyState msg="No risk data yet." />;

  return (
    <Stack gap="sm">
      <StackedBar segments={LEVELS.map(l => ({ ...l, value: byLevel[l.id] || 0 }))} />
      <Row gap="md" wrap>
        {LEVELS.map(l => (
          <Row key={l.id} gap="xs">
            <Dot tone={l.tone} />
            <Micro tone="subtle">{l.label}</Micro>
            <Micro mono tone={l.tone}>{((byLevel[l.id] || 0) * 100).toFixed(0)}%</Micro>
          </Row>
        ))}
        <Spacer />
        <Micro>n={total}</Micro>
      </Row>
    </Stack>
  );
}

// ── Risk score timeline ───────────────────────────────────────
// The shared TrendChart draws the line, the mean and the axis; this only
// decides MEANING — each sample is dotted in its reflect-level tone, so the
// chart shows both how risky recent work was and what the gate did about it.
function RiskTimeline({ history }) {
  if (!history?.length) return <EmptyState msg="No risk history." />;

  const vals = history.map(r => r.total_risk ?? 0);
  const mean = vals.reduce((s, v) => s + v, 0) / vals.length;

  return (
    <TrendChart
      height={110}
      domain={[0, 1]}
      grid={[0.25, 0.5, 0.75]}
      mean={mean}
      empty="No risk history."
      series={[{
        label: "total risk",
        values: vals,
        tone: "warn",
        emphasis: true,
        dots: history.map((r, i) => ({ index: i, tone: toneOf(r.reflect_level) })),
      }]}
    />
  );
}

// ── By-action breakdown ───────────────────────────────────────
function ActionBreakdown({ byAction }) {
  if (!byAction || !Object.keys(byAction).length) return null;
  const total = Object.values(byAction).reduce((s, n) => s + n, 0);

  return (
    <div>
      {Object.entries(byAction)
        .sort((a, b) => b[1] - a[1])
        .map(([action, n]) => (
          <BarRow key={action} label={action} fraction={n / total} value={n} />
        ))}
    </div>
  );
}

// ── Recent risk events ────────────────────────────────────────
// The same Table the Verifier section uses: two lists of scored events on one
// surface should not be two different kinds of list.
const COLUMNS = [
  { key: "reflect_level", width: 58, weight: 700,
    tone: r => toneOf(r.reflect_level),
    render: r => r.reflect_level || "—" },
  { key: "action",     width: 74, tone: "subtle", render: r => r.action || "—" },
  { key: "agent",      width: 108, tone: "muted", render: r => r.agent?.replace(/_/g, " ") || "—" },
  { key: "complexity", width: 70, render: r => r.complexity || "—" },
  { key: "total_risk", grow: true, mono: true, align: "right",
    tone: r => riskTone(r.total_risk),
    render: r => r.total_risk?.toFixed(3) ?? "—" },
];

function RecentRiskRows({ history }) {
  if (!history?.length) return <EmptyState msg="No risk events." />;
  return (
    <Scroll max="280px">
      <Table columns={COLUMNS} rows={history.slice(0, 40)} rowKey={(r, i) => `${r.timestamp}-${i}`} />
    </Scroll>
  );
}

// ── Main component ────────────────────────────────────────────
export default function RiskObservatoryPanel() {
  const { data: stats, error, loading } = usePoll("/risk/stats", { interval: 30_000 });
  const { data: histRaw }               = usePoll("/risk/history?n=100", { interval: 30_000 });

  // The API returns newest-first; the chart reads left-to-right in time.
  const history = Array.isArray(histRaw) ? [...histRaw].reverse() : [];

  const light = stats?.by_level?.light || 0;
  const full  = stats?.by_level?.full  || 0;
  const reflectPct = stats ? Math.round((light + full) * 100) : null;

  if (loading && !stats) return <EmptyState msg="Loading…" />;

  return (
    <Stack gap="md">
      {error && <Notice tone="error">Backend unavailable: {error}</Notice>}

      <Grid min={150} gap="sm">
        <MetricCard label="Mean risk" tone={riskTone(stats?.mean_risk)}
          value={stats?.mean_risk?.toFixed(3) ?? "—"}
          sub="0 = safe · 1 = abort" />
        <MetricCard label="Reflect rate" tone={reflectPct > 40 ? "warn" : "success"}
          value={reflectPct != null ? `${reflectPct}%` : "—"}
          sub="light + full triggers" />
        <MetricCard label="Samples" tone="gold"
          value={stats?.n ?? "—"}
          sub="from risk_gate.db" />
        <MetricCard label="Full reflect" tone={full > 0.2 ? "error" : "success"}
          // 0 is a real answer here, and the panel used to print "—" for it
          // because the key is simply absent when the gate never escalated.
          value={stats ? `${(full * 100).toFixed(0)}%` : "—"}
          sub="highest cost level" />
      </Grid>

      <ObsPanel title="Reflect-level distribution" icon="⌇">
        <LevelDistribution byLevel={stats?.by_level} total={stats?.n} />
      </ObsPanel>

      <ObsPanel title="Risk score timeline" icon="△"
        hint="each sample dotted in the level the gate chose">
        <RiskTimeline history={history} />
      </ObsPanel>

      {stats?.by_action && Object.keys(stats.by_action).length > 0 && (
        <ObsPanel title="Triggers by action" icon="◉">
          <ActionBreakdown byAction={stats.by_action} />
        </ObsPanel>
      )}

      <ObsPanel title="Recent risk events" icon="⚑"
        action={
          <Row gap="sm">
            {LEVELS.map(l => (
              <Row key={l.id} gap="xs">
                <Dot tone={l.tone} />
                <Micro>{l.id}</Micro>
              </Row>
            ))}
          </Row>
        }
      >
        <RecentRiskRows history={history} />
      </ObsPanel>
    </Stack>
  );
}
