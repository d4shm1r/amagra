import { useState, useEffect, useCallback } from "react";
import { PageHeader, MetricCard, ObsPanel, RefreshBtn } from "./ObsShared";

const API = "http://localhost:8000";

// ── Colour helpers ────────────────────────────────────────────
function rateColor(rate, lo, hi) {
  if (rate >= lo && rate <= hi) return "#15803D";
  if (rate < lo * 0.6 || rate > hi * 1.4) return "#B42318";
  return "#9A6C00";
}

// ── Inline SVG histogram ──────────────────────────────────────
function Histogram({ buckets, color = "#15803D", overlayBuckets, overlayColor = "#0F766E",
                     threshold, width = 180, height = 52 }) {
  if (!buckets) return null;
  const all  = overlayBuckets ? buckets.map((v, i) => Math.max(v, overlayBuckets[i] || 0)) : buckets;
  const peak = Math.max(...all, 1);
  const bw   = width / buckets.length;
  const thX  = threshold != null ? threshold * width : null;

  return (
    <svg width={width} height={height} style={{ display: "block", overflow: "visible" }}>
      {buckets.map((v, i) => {
        const bh = (v / peak) * (height - 4);
        return <rect key={i} x={i * bw + 1} y={height - bh - 2} width={bw - 2} height={bh}
          fill={color} opacity={0.65} />;
      })}
      {overlayBuckets && overlayBuckets.map((v, i) => {
        const bh = (v / peak) * (height - 4);
        return <rect key={`o${i}`} x={i * bw + 1} y={height - bh - 2} width={bw - 2} height={bh}
          fill={overlayColor} opacity={0.4} />;
      })}
      {thX != null && (
        <line x1={thX} y1={0} x2={thX} y2={height}
          stroke="#B42318" strokeWidth={1.5} strokeDasharray="3,3" opacity={0.7} />
      )}
      {/* x-axis labels: 0.0, 0.5, 1.0 */}
      {[0, 0.5, 1.0].map(v => (
        <text key={v} x={v * width} y={height + 11} fontSize={9} fill="#9A7A60" textAnchor="middle">
          {v.toFixed(1)}
        </text>
      ))}
    </svg>
  );
}

// ── Recent events timeline ────────────────────────────────────
function EventDots({ events }) {
  if (!events?.length) return <div style={{ color: "#9A7A60", fontSize: 12 }}>No data yet</div>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
      {events.slice(-40).map((ev, i) => {
        const accepted = ev.accepted_on_first === 1;
        const improved = ev.retry_improved === 1;
        const bg = accepted ? "#15803D" : improved ? "#9A6C00" : "#B42318";
        const title = accepted
          ? `Accepted · score ${ev.score_initial?.toFixed(2)}`
          : `Retry · ${ev.score_initial?.toFixed(2)} → ${ev.score_retry?.toFixed(2)} · ${ev.agent}`;
        return (
          <div key={i} title={title} style={{
            width: 10, height: 10, borderRadius: "50%", background: bg,
            opacity: 0.85, cursor: "default", flexShrink: 0,
          }} />
        );
      })}
      <div style={{ fontSize: 10, color: "#9A7A60", marginLeft: 4, alignSelf: "center" }}>
        latest →
      </div>
    </div>
  );
}

// ── Panel wrapper — shared luxe card (ObsPanel) ───────────────
function Panel({ title, children }) {
  return <ObsPanel title={title}>{children}</ObsPanel>;
}

// ── Entropy of bucketed distribution (0–1 normalized) ────────
function entropy(buckets) {
  const total = buckets.reduce((a, b) => a + b, 0);
  if (!total) return 0;
  const H = -buckets
    .filter(b => b > 0)
    .reduce((s, b) => s + (b / total) * Math.log2(b / total), 0);
  return H / Math.log2(buckets.length);
}

// ── Main component ────────────────────────────────────────────
export default function PolicyTab() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/policy/health?limit=200`)
      .then(r => r.json())
      .then(d => { setData(d); setError(null); })
      .catch(() => setError("API unreachable"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); const id = setInterval(load, 30000); return () => clearInterval(id); }, [load]);

  if (loading && !data) {
    return <div style={{ padding: 24, color: "#9A7A60" }}>Loading policy metrics…</div>;
  }
  if (error) {
    return <div style={{ padding: 24, color: "#B42318" }}>{error}</div>;
  }
  if (!data || data.no_data) {
    return (
      <div style={{ padding: 24, color: "#9A7A60", maxWidth: 600 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: "#5C4030", marginBottom: 8 }}>
          No gate data yet
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.6 }}>
          The critic gate logs outcomes as requests pass through. Send a query via Chat
          and this panel will populate.
        </div>
      </div>
    );
  }

  const {
    total, acceptance_rate, retry_rate, mean_uplift,
    negative_retry_pct, separation_power, marginal_value,
    avg_score_initial, avg_score_retry,
    score_distribution, retry_score_distribution,
    recent_events, by_agent, threshold,
  } = data;

  const scoreEntropy   = score_distribution ? entropy(score_distribution) : 0;
  const entropyColor   = scoreEntropy > 0.55 ? "#15803D" : scoreEntropy > 0.30 ? "#9A6C00" : "#B42318";
  const entropyLabel   = scoreEntropy > 0.55 ? "Discriminating" : scoreEntropy > 0.30 ? "Low spread" : "Collapsed";

  const acceptColor    = rateColor(acceptance_rate, 0.70, 0.95);
  const upliftColor    = mean_uplift > 0.04 ? "#15803D" : mean_uplift > 0.005 ? "#9A6C00" : "#B42318";
  const mvColor        = marginal_value > 0.03 ? "#15803D" : marginal_value > 0.005 ? "#9A6C00" : "#B42318";
  const negRetryColor  = negative_retry_pct < 0.10 ? "#15803D" : negative_retry_pct < 0.25 ? "#9A6C00" : "#B42318";

  const mvVerdict = marginal_value < 0.005
    ? "Remove retry — no gain"
    : marginal_value < 0.02
    ? "Marginal — monitor"
    : "Retry earning its cost";

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      {/* ── Header ── */}
      <PageHeader
        title="Policy"
        subtitle="Critic-gate health · acceptance, uplift, calibration, marginal value"
      >
        <RefreshBtn onClick={load} />
      </PageHeader>

      {/* ── Headline row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 20 }}>
        <MetricCard label="Acceptance Rate" mono
          value={`${(acceptance_rate * 100).toFixed(1)}%`}
          color={acceptColor}
          sub={`${total} scored total`} />
        <MetricCard label="Gate Pressure" mono
          value={`${(retry_rate * 100).toFixed(1)}%`}
          color={retry_rate > 0.25 ? "#B42318" : retry_rate > 0.05 ? "#9A6C00" : "#15803D"}
          sub="% requests retried" />
        <MetricCard label="Mean Uplift ΔC" mono
          value={mean_uplift >= 0 ? `+${mean_uplift.toFixed(3)}` : mean_uplift.toFixed(3)}
          color={upliftColor}
          sub={avg_score_retry != null ? `retry avg ${avg_score_retry.toFixed(2)}` : "no retries yet"} />
        <MetricCard label="Marginal Value" mono
          value={marginal_value.toFixed(4)}
          color={mvColor}
          sub={mvVerdict} />
      </div>

      {/* ── Panels row 1 ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>

        {/* Panel A — System Flow */}
        <Panel title="A · SYSTEM FLOW">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
            <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "8px 12px" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: acceptColor, fontFamily: "monospace" }}>
                {(acceptance_rate * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: 10, color: "#9A7A60" }}>first-pass accept</div>
            </div>
            <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "8px 12px" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#9A6C00", fontFamily: "monospace" }}>
                {(retry_rate * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: 10, color: "#9A7A60" }}>retry triggered</div>
            </div>
          </div>
          <div style={{ fontSize: 11, color: "#9A7A60", marginBottom: 6 }}>
            Recent {Math.min(recent_events?.length || 0, 40)} requests
            &nbsp;<span style={{ color: "#15803D" }}>●</span> accepted
            &nbsp;<span style={{ color: "#9A6C00" }}>●</span> retry improved
            &nbsp;<span style={{ color: "#B42318" }}>●</span> retry no gain
          </div>
          <EventDots events={recent_events} />
          {acceptance_rate > 0.95 && (
            <div style={{ marginTop: 10, fontSize: 11, color: "#9A6C00",
              background: "#9A6C0011", borderRadius: 8, padding: "6px 10px" }}>
              Gate may be too lenient — consider raising threshold above {threshold}
            </div>
          )}
          {retry_rate > 0.30 && (
            <div style={{ marginTop: 10, fontSize: 11, color: "#B42318",
              background: "#B4231811", borderRadius: 8, padding: "6px 10px" }}>
              High gate pressure — generator may be degrading or threshold too strict
            </div>
          )}
        </Panel>

        {/* Panel B — Quality Dynamics */}
        <Panel title="B · QUALITY DYNAMICS">
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start", marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 11, color: "#9A7A60", marginBottom: 6 }}>
                Score distribution
                {retry_score_distribution && (
                  <span style={{ marginLeft: 6, color: "#0F766E" }}>
                    <span style={{ opacity: 0.6 }}>■</span> retry
                  </span>
                )}
              </div>
              <Histogram
                buckets={score_distribution}
                color="#15803D"
                overlayBuckets={retry_score_distribution}
                overlayColor="#0F766E"
                threshold={threshold}
                width={190}
                height={56}
              />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "7px 12px" }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#15803D", fontFamily: "monospace" }}>
                  {avg_score_initial?.toFixed(3)}
                </div>
                <div style={{ fontSize: 10, color: "#9A7A60" }}>avg C(G₁)</div>
              </div>
              {avg_score_retry != null && (
                <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "7px 12px" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#0F766E", fontFamily: "monospace" }}>
                    {avg_score_retry?.toFixed(3)}
                  </div>
                  <div style={{ fontSize: 10, color: "#9A7A60" }}>avg C(G₂)</div>
                </div>
              )}
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "7px 10px" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: upliftColor, fontFamily: "monospace" }}>
                {mean_uplift >= 0 ? "+" : ""}{mean_uplift.toFixed(3)}
              </div>
              <div style={{ fontSize: 10, color: "#9A7A60" }}>mean ΔC on retry</div>
            </div>
            <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "7px 10px" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: negRetryColor, fontFamily: "monospace" }}>
                {(negative_retry_pct * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: 10, color: "#9A7A60" }}>negative retries</div>
            </div>
          </div>
        </Panel>
      </div>

      {/* ── Panels row 2 ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>

        {/* Panel C — Critic Calibration */}
        <Panel title="C · CRITIC CALIBRATION">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
            <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "8px 12px" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#1E5A8A", fontFamily: "monospace" }}>
                {separation_power >= 0 ? "+" : ""}{separation_power.toFixed(3)}
              </div>
              <div style={{ fontSize: 10, color: "#9A7A60" }}>separation power</div>
              <div style={{ fontSize: 9, color: "#9A7A60", marginTop: 2 }}>E[C(y₂) – C(y₁)]</div>
            </div>
            <div style={{ background: "#F4F0E8", borderRadius: 10, padding: "8px 12px" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: entropyColor, fontFamily: "monospace" }}>
                {scoreEntropy.toFixed(2)}
              </div>
              <div style={{ fontSize: 10, color: "#9A7A60" }}>score entropy</div>
              <div style={{ fontSize: 9, color: entropyColor, marginTop: 2 }}>{entropyLabel}</div>
            </div>
          </div>

          {scoreEntropy < 0.25 && (
            <div style={{ fontSize: 11, color: "#B42318", background: "#B4231811",
              borderRadius: 8, padding: "6px 10px", marginBottom: 10 }}>
              Score collapse — critic is not discriminating. Most responses score the same.
            </div>
          )}
          {separation_power < 0.01 && retry_rate > 0.03 && (
            <div style={{ fontSize: 11, color: "#B42318", background: "#B4231811",
              borderRadius: 8, padding: "6px 10px", marginBottom: 10 }}>
              Near-zero separation — gate is selecting noise, not quality.
            </div>
          )}

          <div style={{ fontSize: 11, color: "#9A7A60", marginBottom: 6 }}>
            Score distribution (τ = {threshold} cutoff)
          </div>
          <Histogram
            buckets={score_distribution}
            color="#1E5A8A"
            threshold={threshold}
            width={220}
            height={50}
          />
        </Panel>

        {/* Panel D — Efficiency Frontier */}
        <Panel title="D · EFFICIENCY FRONTIER">
          <div style={{ background: "#F4F0E8", borderRadius: 12, padding: "12px 16px", marginBottom: 14,
            border: `1px solid ${mvColor}22` }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: mvColor, fontFamily: "monospace" }}>
              MV = {marginal_value.toFixed(4)}
            </div>
            <div style={{ fontSize: 11, color: "#9A7A60", marginTop: 4 }}>
              marginal value of critique — avg quality gain per request
            </div>
            <div style={{ fontSize: 11, color: mvColor, marginTop: 6, fontWeight: 600 }}>
              {mvVerdict}
            </div>
            {marginal_value < 0.005 && (
              <div style={{ fontSize: 11, color: "#9A7A60", marginTop: 4 }}>
                If MV → 0 consistently, the generator is saturated and the retry should be removed.
              </div>
            )}
          </div>

          {Object.keys(by_agent || {}).length > 0 && (
            <>
              <div style={{ fontSize: 11, color: "#9A7A60", marginBottom: 6 }}>Per-agent breakdown</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                <thead>
                  <tr>
                    {["Agent", "Total", "Retry %", "Avg C(y)"].map(h => (
                      <th key={h} style={{ textAlign: "left", color: "#9A7A60",
                        padding: "3px 0", borderBottom: "1px solid #E0D6C4", fontWeight: 600 }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(by_agent)
                    .sort((a, b) => b[1].retry_rate - a[1].retry_rate)
                    .map(([ag, st]) => {
                      const rateC = rateColor(1 - st.retry_rate, 0.70, 0.95);
                      return (
                        <tr key={ag}>
                          <td style={{ padding: "4px 0", color: "#2E2010", fontFamily: "monospace" }}>{ag}</td>
                          <td style={{ padding: "4px 0", color: "#9A7A60" }}>{st.total}</td>
                          <td style={{ padding: "4px 0", color: rateC, fontFamily: "monospace" }}>
                            {(st.retry_rate * 100).toFixed(1)}%
                          </td>
                          <td style={{ padding: "4px 0", color: "#1E5A8A", fontFamily: "monospace" }}>
                            {st.avg_score.toFixed(3)}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </>
          )}
        </Panel>
      </div>

      {/* ── Refresh hint ── */}
      <div style={{ marginTop: 14, textAlign: "right", fontSize: 10, color: "#9A7A60" }}>
        Auto-refresh every 30s ·{" "}
        <button onClick={load} style={{ background: "none", border: "none", color: "#0F766E",
          cursor: "pointer", fontSize: 10, fontFamily: "inherit", padding: 0 }}>
          refresh now
        </button>
      </div>
    </div>
  );
}
