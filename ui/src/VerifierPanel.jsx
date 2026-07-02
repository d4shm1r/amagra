import { useCallback, useEffect, useState } from "react";
import { T, FONT_MONO, TYPE } from "./theme";
import { PageHeader, ObsPanel, MetricCard } from "./ObsShared";
import { API } from "./api";

// ── Step Verifier (Diagnostics section) ───────────────────────────
// The verifier scores every plan step before the system moves on
// (pass / retry / replan / abort → event_bus). It appears in every
// architecture diagram, and this is its observability surface:
// GET /verify/stats + GET /verify/recent.

const REC_COLOR = {
  continue: T.success,
  retry:    T.warn,
  replan:   T.warn,
  abort:    T.error,
};

function prettyTs(ts) {
  return (ts || "").slice(5, 16).replace("T", " ");
}

export default function VerifierPanel() {
  const [stats,  setStats]  = useState(null);
  const [recent, setRecent] = useState(null);

  const load = useCallback(async () => {
    try {
      const [sR, rR] = await Promise.all([
        fetch(`${API}/verify/stats`),
        fetch(`${API}/verify/recent?n=40`),
      ]);
      setStats(sR.ok ? await sR.json() : null);
      const rec = rR.ok ? await rR.json() : null;
      setRecent(rec?.verifications || []);
    } catch {
      setStats(null); setRecent([]);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const n        = stats?.n ?? 0;
  const passRate = stats?.pass_rate;
  const meanScore = stats?.mean_score;
  const byRec    = stats?.by_recommendation || {};
  const rows     = recent || [];

  return (
    <div style={{ animation: "fadeIn .2s" }}>
      <PageHeader
        title="Step Verifier"
        subtitle="Every plan step is scored before the system moves on — pass, retry, replan, or abort."
      >
        <button onClick={load} className="nav-btn" style={{
          background: "transparent", border: `1px solid ${T.border}`,
          color: T.mutedLt, padding: "5px 15px", borderRadius: 16,
          fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
        }}>
          ↻ Refresh
        </button>
      </PageHeader>

      {/* ── Stats row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, marginBottom: 14 }}>
        <MetricCard label="Pass rate" mono
          value={passRate != null ? `${(passRate * 100).toFixed(1)}%` : "—"}
          color={passRate == null ? T.muted : passRate >= 0.9 ? T.success : passRate >= 0.7 ? T.warn : T.error}
          sub={`last ${n} verifications`} />
        <MetricCard label="Mean score" mono
          value={meanScore != null ? meanScore.toFixed(3) : "—"}
          color={meanScore == null ? T.muted : meanScore >= 0.8 ? T.success : T.warn}
          sub="raw verifier score" />
        {Object.entries(byRec).map(([rec, rate]) => (
          <MetricCard key={rec} label={rec} mono
            value={`${(rate * 100).toFixed(0)}%`}
            color={REC_COLOR[rec] || T.muted}
            sub="of recent recommendations" />
        ))}
      </div>

      {/* ── Recent verifications ── */}
      <ObsPanel title="Recent verifications" icon="✓">
        {rows.length === 0 ? (
          <div style={{ padding: "26px 0", textAlign: "center", color: T.muted, fontSize: 12.5, fontStyle: "italic" }}>
            No verifications yet — ask something and each verified step lands here.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            {rows.map((v, i) => {
              const color = v.passed ? T.success : T.error;
              return (
                <div key={`${v.ts}-${i}`} style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "7px 2px", borderBottom: i < rows.length - 1 ? `1px solid ${T.border}` : "none",
                }}>
                  <span style={{ ...TYPE.small, fontFamily: FONT_MONO, color: T.muted, minWidth: 78 }}>{prettyTs(v.ts)}</span>
                  <span style={{ ...TYPE.small, fontWeight: 600, color: T.text, minWidth: 120 }}>
                    {(v.agent || "?").replace(/_/g, " ")}
                  </span>
                  <span style={{ ...TYPE.small, fontFamily: FONT_MONO, color, minWidth: 110 }}>
                    {v.raw_score?.toFixed(2)} <span style={{ color: T.muted }}>/ {v.threshold?.toFixed(2)} req</span>
                  </span>
                  <span style={{
                    ...TYPE.small, fontWeight: 700, minWidth: 72,
                    color: REC_COLOR[v.recommendation] || T.muted,
                  }}>
                    {v.recommendation}
                  </span>
                  <span style={{ ...TYPE.small, color: T.muted, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                    title={v.issues}>
                    {v.issues || "—"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </ObsPanel>
    </div>
  );
}
