import { useState, useEffect, useCallback } from "react";
import { T, FONT_MONO } from "@/styles/theme";
import { PageHeader, RefreshButton, EmptyState } from "@/components/ui";

import { API } from "@/lib/api";

// ── Inference Cost (v1.5 Hybrid Inference) ───────────────────────────────────
// The Productivity cost axis: how much recent reasoning cost in cloud spend, and
// how often the hybrid policy escalated past the local default. In the default
// local-only posture this reads a truthful "$0.00 — fully local" — escalation is
// opt-in behind AMAGRA_HYBRID.

function Stat({ label, value, sub, accent }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{
        fontSize: 9, color: T.muted, fontWeight: 700,
        letterSpacing: "0.1em", textTransform: "uppercase",
      }}>{label}</div>
      <div style={{
        fontSize: 22, fontWeight: 700, fontFamily: FONT_MONO,
        color: accent || T.text, marginTop: 2, lineHeight: 1.1,
      }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export default function InferenceCostPanel({ embedded = false }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/runs/cost`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const usd = (n) => `$${(n ?? 0).toFixed(n >= 1 ? 2 : 4)}`;
  const local = data && data.escalated_runs === 0;

  const body = !data ? (
    <EmptyState label={loading ? "Loading…" : "No run data yet"} />
  ) : (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: embedded ? 14 : 0 }}>
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 16,
      }}>
        <Stat label="Total spend" value={usd(data.total_cost_usd)}
              sub={`last ${data.runs} runs`} accent={local ? T.success : T.gold} />
        <Stat label="Avg / run" value={usd(data.avg_cost_per_run_usd)} />
        <Stat label="Escalated" value={`${(data.escalation_rate * 100).toFixed(0)}%`}
              sub={`${data.escalated_runs} / ${data.runs} runs`} />
        <Stat label="Tokens (in/out)"
              value={`${data.tokens_in}/${data.tokens_out}`} />
      </div>
      <div style={{
        fontSize: 11, color: local ? T.success : T.muted,
        borderTop: `1px solid ${T.border}`, paddingTop: 10,
      }}>
        {local
          ? "Fully local — no cloud inference cost. Escalation is opt-in (AMAGRA_HYBRID)."
          : "Hybrid inference active — hard or low-confidence routes escalated to a cloud model."}
      </div>
    </div>
  );

  if (embedded) return body;

  return (
    <div>
      <PageHeader title="Inference Cost"
                  subtitle="Cloud spend and escalation rate across recent runs." gold />
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <RefreshButton onClick={load} loading={loading} />
      </div>
      {body}
    </div>
  );
}
