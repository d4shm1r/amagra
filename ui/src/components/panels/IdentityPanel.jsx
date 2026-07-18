// ── Identity (About section) ──────────────────────────────────────────────────
// The identity contract (models/identity.py, docs/design/IDENTITY.md): who this
// system is = intrinsic state (yours, changed only when you change it) plus
// learned state (earned from real outcomes). The fingerprint hashes the whole
// snapshot, so it moves when durable state moves and never on a restart.
//
// Rehomed from the retired CogOS tab. It belongs here: About is the surface the
// nav describes as "identity and engine state", and this was the only place in
// the app that rendered the contract at all.
import { Section, Grid, Stack, Row, Spacer, DataRow, Small, Micro, Caption, Inline, ScoreBar, EmptyState } from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

export default function IdentityPanel() {
  const { data: identity } = usePoll("/identity",             { interval: 60_000 });
  const { data: fp }       = usePoll("/identity/fingerprint", { interval: 60_000 });

  if (!identity) return null;

  const intrinsic = identity.intrinsic || {};
  const learned   = identity.learned   || {};
  const weights   = learned.decision_weights || {};
  const hash      = fp?.fingerprint || "";

  const weightRows = Object.entries(weights).sort((a, b) => a[0].localeCompare(b[0]));
  const memories   = learned.memory?.total ?? learned.memory?.count ?? null;

  return (
    <Section
      title="Identity"
      hint="who this instance is — what you declared, and what it earned"
      action={
        <Micro mono title={hash}>
          {hash ? `${hash.slice(0, 12)}…` : "—"} · schema v{fp?.schema_version ?? "?"}
        </Micro>
      }
    >
      <Grid min={260} gap="lg">
        {/* Intrinsic — declared by the owner, mutated only by explicit action. */}
        <Stack gap="xs">
          <Caption>Intrinsic — yours</Caption>
          <DataRow label="Profile" value={Object.keys(intrinsic.profile || {}).length > 0 ? "set" : "not set"} />
          <DataRow label="Goals"       mono tone="gold" value={intrinsic.goals?.count ?? 0} />
          <DataRow label="Active keys" mono tone="gold" value={intrinsic.permissions?.active_keys ?? 0} />
          <Micro>
            Intrinsic state changes only when you change it. Learned state moves with
            every interaction{memories != null ? ` — ${memories} memories so far` : ""}.
          </Micro>
        </Stack>

        {/* Learned — per-agent routing weight earned from real outcomes. */}
        <Stack gap="xs">
          <Caption>Learned — earned per agent</Caption>
          {weightRows.length === 0 ? (
            <EmptyState msg="No learned weights yet — routing earns these from outcomes." />
          ) : weightRows.map(([agent, w]) => (
            <ScoreBar
              key={agent}
              label={agent.replace(/_/g, " ")}
              value={typeof w === "number" ? w * 100 : null}
            />
          ))}
        </Stack>
      </Grid>
    </Section>
  );
}
