import { useState, useEffect, useCallback } from "react";
import {
  PageHeader, RefreshButton, EmptyState, StatStrip, Stack, Divider, Small, Pad,
} from "@/components/ui";

import { API } from "@/lib/api";

// ── Inference Cost (v1.5 Hybrid Inference) ───────────────────────────────────
// The Productivity cost axis: how much recent reasoning cost in cloud spend, and
// how often the hybrid policy escalated past the local default. In the default
// local-only posture this reads a truthful "$0.00 — fully local" — escalation is
// opt-in behind AMAGRA_HYBRID.

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
    <EmptyState msg={loading ? "Loading…" : "No run data yet"} />
  ) : (
    <Stack gap="md">
      <StatStrip items={[
        { label: "Total spend", value: usd(data.total_cost_usd), sub: `last ${data.runs} runs`, tone: local ? "success" : "gold" },
        { label: "Avg / run", value: usd(data.avg_cost_per_run_usd), tone: "default" },
        { label: "Escalated", value: `${(data.escalation_rate * 100).toFixed(0)}%`, sub: `${data.escalated_runs} / ${data.runs} runs`, tone: "default" },
        { label: "Tokens (in/out)", value: `${data.tokens_in}/${data.tokens_out}`, tone: "default" },
      ]} />
      <Divider />
      <Small tone={local ? "success" : "muted"}>
        {local
          ? "Fully local — no cloud inference cost. Escalation is opt-in (AMAGRA_HYBRID)."
          : "Hybrid inference active — hard or low-confidence routes escalated to a cloud model."}
      </Small>
    </Stack>
  );

  // Embedded in the Cognition dashboard cell, which owns no padding — inset it.
  if (embedded) return <Pad>{body}</Pad>;

  return (
    <div>
      <PageHeader title="Inference Cost"
                  subtitle="Cloud spend and escalation rate across recent runs." gold>
        <RefreshButton onClick={load} loading={loading} />
      </PageHeader>
      {body}
    </div>
  );
}
