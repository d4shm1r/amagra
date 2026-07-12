import { useState, useEffect } from "react";
import { T, FONT_MONO } from "./theme";
import { ObsPanel, MetricCard, RefreshBtn, EmptyState, hScore, PageHeader } from "./ObsShared";

import { API } from "./api";

const LEVEL_COLOR = { none: T.success, light: T.warn, full: T.error };
const LEVEL_LABEL = { none: "None", light: "Light", full: "Full" };

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

// ── Risk score sparkline (SVG) ────────────────────────────────
function RiskSparkline({ history }) {
  if (!history?.length) return <EmptyState msg="No risk history." />;

  const vals  = history.map(r => r.total_risk ?? 0);
  const W = 560, H = 80, PX = 8, PY = 8;
  const iW = W - 2 * PX, iH = H - 2 * PY;
  const xs = i => PX + (i / Math.max(1, vals.length - 1)) * iW;
  const ys = v => PY + (1 - Math.max(0, Math.min(1, v))) * iH;
  const pts = vals.map((v, i) => `${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(" ");

  // Color segments by reflect level
  const levelPath = (level) => {
    const filtered = history.map((r, i) => ({ ...r, i })).filter(r => r.reflect_level === level);
    if (!filtered.length) return null;
    return filtered.map(r => (
      <circle key={r.i} cx={xs(r.i)} cy={ys(r.total_risk ?? 0)}
        r={3} fill={LEVEL_COLOR[level]} opacity={0.8} />
    ));
  };

  const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
  const meanY = ys(mean);

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block", overflow: "visible" }}>
        {/* Mean line */}
        <line x1={PX} y1={meanY} x2={W - PX} y2={meanY}
          stroke={T.border} strokeWidth={1} strokeDasharray="4 3" />
        {/* Risk line */}
        <polyline points={pts} fill="none" stroke={T.warn} strokeWidth={1.5}
          strokeLinejoin="round" strokeLinecap="round" opacity={0.6} />
        {/* Dots colored by level */}
        {["none", "light", "full"].map(l => levelPath(l))}
        {/* Mean label */}
        <text x={W - PX + 2} y={meanY + 4} fill={T.muted} fontSize={9}>
          {mean.toFixed(2)}
        </text>
      </svg>
      <div style={{ display: "flex", gap: 12, marginTop: 6 }}>
        {["none", "light", "full"].map(l => (
          <span key={l} style={{ fontSize: 10, color: T.muted }}>
            <span style={{ color: LEVEL_COLOR[l] }}>●</span> {l}
          </span>
        ))}
      </div>
    </div>
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
export default function RiskObservatoryTab({ embedded = false } = {}) {
  const [stats,   setStats]   = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/risk/stats`).then(r => r.json()).catch(() => null),
      fetch(`${API}/risk/history?n=100`).then(r => r.json()).catch(() => []),
    ]).then(([s, h]) => {
      setStats(s);
      setHistory(Array.isArray(h) ? h.reverse() : []);
      setError(null);
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); const id = setInterval(load, 30_000); return () => clearInterval(id); }, []);

  const reflectPct = stats
    ? Math.round(((stats.by_level?.light || 0) + (stats.by_level?.full || 0)) * 100)
    : null;

  return (
    <div style={{ maxWidth: embedded ? "none" : 860, margin: embedded ? 0 : "0 auto", padding: embedded ? "10px 14px 14px" : 0 }}>

      {/* Header (suppressed when embedded — the dashboard cell carries the title) */}
      {!embedded && (
      <PageHeader
        sticky={false}
        title="Risk Observatory"
        subtitle="Reflection gate signals · risk score distribution · per-action breakdown"
      >
        <RefreshBtn onClick={load} />
      </PageHeader>
      )}

      {error && (
        <div style={{ color: T.error, background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 10, padding: "8px 14px", marginBottom: 14, fontSize: 12 }}>
          Backend unavailable: {error}
        </div>
      )}

      {loading && !stats ? (
        <div style={{ color: T.muted, fontSize: 12, padding: 40, textAlign: "center" }}>Loading…</div>
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

          {/* Risk trend sparkline */}
          <ObsPanel title="Risk Score Timeline" icon="△">
            <RiskSparkline history={history} />
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
