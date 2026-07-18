import {
  ObsPanel, MetricCard, EmptyState, Grid, Stack, Table, Inline,
} from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

// ── Step Verifier (Diagnostics section) ───────────────────────────
// The verifier scores every plan step before the system moves on
// (pass / retry / replan / abort → event_bus). It appears in every
// architecture diagram, and this is its observability surface:
// GET /verify/stats + GET /verify/recent.
//
// Section contract: content only — Diagnostics owns the header and refresh.
// This file used to return its own <Page> nested inside the tab's, plus a
// second PageHeader that retitled the page to "Step Verifier".

// Recommendation → tone (meaning, not decoration). Resolved by the kit.
const REC_TONE = { continue: "success", retry: "warn", replan: "warn", abort: "error" };

function prettyTs(ts) {
  return (ts || "").slice(5, 16).replace("T", " ");
}

function passRateTone(v) {
  if (v == null) return "muted";
  return v >= 0.9 ? "success" : v >= 0.7 ? "warn" : "error";
}

export default function VerifierPanel() {
  const { data: stats }  = usePoll("/verify/stats", { interval: 30_000 });
  const { data: recent } = usePoll("/verify/recent?n=40", { interval: 30_000 });

  const n         = stats?.n ?? 0;
  const passRate  = stats?.pass_rate;
  const meanScore = stats?.mean_score;
  const byRec     = stats?.by_recommendation || {};
  const rows      = recent?.verifications || [];

  const columns = [
    { key: "ts", width: 78, mono: true, tone: "muted", render: v => prettyTs(v.ts) },
    { key: "agent", width: 120, weight: 600, render: v => (v.agent || "?").replace(/_/g, " ") },
    { key: "score", width: 110, mono: true, render: v => (
      <>
        <Inline mono tone={v.passed ? "success" : "error"}>{v.raw_score?.toFixed(2)}</Inline>{" "}
        <Inline mono tone="muted">/ {v.threshold?.toFixed(2)} req</Inline>
      </>
    ) },
    { key: "recommendation", width: 72, weight: 700, tone: v => REC_TONE[v.recommendation] || "muted" },
    { key: "issues", grow: true, tone: "muted", render: v => v.issues || "—" },
  ];

  return (
    <Stack gap="md">
      {/* ── Stats row ── */}
      <Grid min={150} gap="sm">
        <MetricCard label="Pass rate" tone={passRateTone(passRate)}
          value={passRate != null ? `${(passRate * 100).toFixed(1)}%` : "—"}
          sub={`last ${n} verifications`} />
        <MetricCard label="Mean score"
          tone={meanScore == null ? "muted" : meanScore >= 0.8 ? "success" : "warn"}
          value={meanScore != null ? meanScore.toFixed(3) : "—"}
          sub="raw verifier score" />
        {Object.entries(byRec).map(([rec, rate]) => (
          <MetricCard key={rec} label={rec} tone={REC_TONE[rec] || "muted"}
            value={`${(rate * 100).toFixed(0)}%`}
            sub="of recent recommendations" />
        ))}
      </Grid>

      {/* ── Recent verifications ── */}
      <ObsPanel title="Recent verifications" icon="✓">
        {rows.length === 0 ? (
          <EmptyState msg="No verifications yet — ask something and each verified step lands here." />
        ) : (
          <Table columns={columns} rows={rows} rowKey={(v, i) => `${v.ts}-${i}`} />
        )}
      </ObsPanel>
    </Stack>
  );
}
