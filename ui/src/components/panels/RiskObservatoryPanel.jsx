import { T, FONT_MONO } from "@/styles/theme";
import { ObsPanel, MetricCard, EmptyState, hScore, TrendChart, Notice } from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

// ── Risk Observatory (Diagnostics section) ────────────────────────
// Section contract: content only — the host owns the header and refresh.

const LEVEL_COLOR = { none: T.success, light: T.warn, full: T.error };
const LEVEL_LABEL = { none: "None", light: "Light", full: "Full" };
const LEVEL_TONE  = { none: "success", light: "warn", full: "error" };

// ── Reflect-level distribution bar ───────────────────────────
function LevelDistribution({ byLevel, total }) {
  if (!byLevel || !total) return <EmptyState msg="No risk data yet." />;

  const order  = ["none", "light", "full"];
  const values = order.map(k => ({ level: k, pct: (byLevel[k] || 0) }));

  return (
    <div>
      {/* Stacked bar */}
      <div style={{ display: "flex", height: 14, borderRadius: 99, overflow: "hidden", marginBottom: 12 }}>
        {values.map(({ level, pct }) => pct > 0 && (
          <div key={level} style={{
            width: `${pct * 100}%`, background: LEVEL_COLOR[level],
            transition: "width 0.5s ease",
          }} title={`${level}: ${(pct * 100).toFixed(1)}%`} />
        ))}
      </div>
      {/* Legend */}
      <div style={{ display: "flex", gap: 16 }}>
        {values.map(({ level, pct }) => (
          <div key={level} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: LEVEL_COLOR[level] }} />
            <span style={{ fontSize: 11, color: T.mutedLt }}>{LEVEL_LABEL[level]}</span>
            <span style={{ fontSize: 11, fontFamily: FONT_MONO, color: LEVEL_COLOR[level] }}>
              {(pct * 100).toFixed(0)}%
            </span>
          </div>
        ))}
        <span style={{ fontSize: 11, color: T.muted, marginLeft: "auto" }}>n={total}</span>
      </div>
    </div>
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
        dots: history.map((r, i) => ({ index: i, tone: LEVEL_TONE[r.reflect_level] || "muted" })),
      }]}
    />
  );
}

// ── By-action breakdown ───────────────────────────────────────
function ActionBreakdown({ byAction }) {
  if (!byAction || !Object.keys(byAction).length) return null;
  const total  = Object.values(byAction).reduce((s, n) => s + n, 0);
  const sorted = Object.entries(byAction).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      {sorted.map(([action, n]) => {
        const pct = n / total;
        return (
          <div key={action} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 11, color: T.mutedLt, minWidth: 80 }}>{action}</span>
            <div style={{ flex: 1, background: T.surface2, borderRadius: 2, height: 6 }}>
              <div style={{
                width: `${pct * 100}%`, height: "100%",
                background: T.accent, borderRadius: 2,
              }} />
            </div>
            <span style={{ fontSize: 10, fontFamily: FONT_MONO, color: T.muted, minWidth: 30, textAlign: "right" }}>
              {n}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Recent risk events ────────────────────────────────────────
function RecentRiskRows({ history }) {
  if (!history?.length) return <EmptyState msg="No risk events." />;
  return (
    <div style={{ maxHeight: 280, overflowY: "auto" }}>
      {history.slice(0, 40).map((r, i) => (
        <div key={i} style={{
          display: "flex", gap: 10, alignItems: "center",
          padding: "5px 0", borderBottom: `1px solid ${T.border}`,
          fontSize: 11,
        }}>
          <span style={{
            minWidth: 52, fontFamily: FONT_MONO, fontSize: 10,
            color: LEVEL_COLOR[r.reflect_level] || T.muted,
            background: (LEVEL_COLOR[r.reflect_level] || T.muted) + "18",
            border: `1px solid ${(LEVEL_COLOR[r.reflect_level] || T.muted)}44`,
            borderRadius: 99, padding: "2px 7px", textAlign: "center",
          }}>{r.reflect_level || "—"}</span>
          <span style={{ color: T.mutedLt, minWidth: 60 }}>{r.action || "—"}</span>
          <span style={{ color: T.muted, minWidth: 64 }}>{r.agent?.replace(/_/g, " ") || "—"}</span>
          <span style={{ color: T.text, minWidth: 50 }}>{r.complexity || "—"}</span>
          <span style={{ fontFamily: FONT_MONO, color: hScore((1 - (r.total_risk ?? 0)) * 100), marginLeft: "auto" }}>
            {r.total_risk?.toFixed(3) ?? "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────
export default function RiskObservatoryPanel() {
  const { data: stats, error, loading } = usePoll("/risk/stats", { interval: 30_000 });
  const { data: histRaw }               = usePoll("/risk/history?n=100", { interval: 30_000 });

  // The API returns newest-first; the chart reads left-to-right in time.
  const history = Array.isArray(histRaw) ? [...histRaw].reverse() : [];

  const reflectPct = stats
    ? Math.round(((stats.by_level?.light || 0) + (stats.by_level?.full || 0)) * 100)
    : null;

  return (
    <div>
      {error && <Notice tone="error">Backend unavailable: {error}</Notice>}

      {loading && !stats ? (
        <EmptyState msg="Loading…" />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
            <MetricCard
              label="Mean Risk"
              value={stats?.mean_risk?.toFixed(3) ?? "—"}
              color={hScore((1 - (stats?.mean_risk || 0)) * 100)}
              sub="0 = safe · 1 = abort"
            />
            <MetricCard
              label="Reflect Rate"
              value={reflectPct != null ? `${reflectPct}%` : "—"}
              color={reflectPct > 40 ? T.warn : T.success}
              sub="light + full triggers"
            />
            <MetricCard
              label="Samples"
              value={stats?.n ?? "—"}
              color={T.accent}
              sub="from risk_gate.db"
            />
            <MetricCard
              label="Full Reflect"
              value={stats?.by_level?.full != null ? `${((stats.by_level.full) * 100).toFixed(0)}%` : "—"}
              color={(stats?.by_level?.full || 0) > 0.2 ? T.error : T.success}
              sub="highest cost level"
            />
          </div>

          {/* Reflect-level distribution */}
          <ObsPanel title="Reflect-Level Distribution" icon="⌇">
            <LevelDistribution byLevel={stats?.by_level} total={stats?.n} />
          </ObsPanel>

          {/* Risk trend */}
          <ObsPanel title="Risk Score Timeline" icon="△"
            hint="each sample dotted in the level the gate chose">
            <RiskTimeline history={history} />
          </ObsPanel>

          {/* By-action breakdown */}
          {stats?.by_action && Object.keys(stats.by_action).length > 0 && (
            <ObsPanel title="Triggers by Action" icon="◉">
              <ActionBreakdown byAction={stats.by_action} />
            </ObsPanel>
          )}

          {/* Recent events */}
          <ObsPanel title="Recent Risk Events" icon="⚑"
            action={
              <span style={{ fontSize: 10, color: T.muted }}>
                {["none", "light", "full"].map(l => (
                  <span key={l} style={{ marginLeft: 8 }}>
                    <span style={{ color: LEVEL_COLOR[l] }}>●</span> {l}
                  </span>
                ))}
              </span>
            }
          >
            <RecentRiskRows history={history} />
          </ObsPanel>

        </div>
      )}
    </div>
  );
}
