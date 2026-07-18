import { EmptyState, StatStrip, Stack, Divider, Small } from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

// ── Inference Cost (v1.5 Hybrid Inference) ───────────────────────────────────
// The Productivity cost axis: how much recent reasoning cost in cloud spend, and
// how often the hybrid policy escalated past the local default. In the default
// local-only posture this reads a truthful "$0.00 — fully local" — escalation is
// opt-in behind AMAGRA_HYBRID.
//
// Section contract: content only — the host owns the header and refresh.

export default function InferenceCostPanel() {
  const { data, loading } = usePoll("/runs/cost", { interval: 60_000 });

  const usd   = (n) => `$${(n ?? 0).toFixed(n >= 1 ? 2 : 4)}`;
  const local = data && data.escalated_runs === 0;

  if (!data) return <EmptyState msg={loading ? "Loading…" : "No run data yet"} />;

  return (
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
}
