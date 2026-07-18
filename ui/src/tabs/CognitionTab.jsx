import {
  Page, PageHeader, Stack, Row, Grid, Section, Well, Spacer, Divider,
  Small, Micro, Caption, Inline, Pill, Dot, HeroStat, MetricCard, ScoreBar,
  TrendChart, EventRow, EmptyState, RefreshButton, Button, hScore, scoreTone,
} from "@/components/ui";
import { usePoll, refreshAll } from "@/lib/usePoll";

// ── Cognition Dashboard ───────────────────────────────────────────────────────
// The glance half of Cognition: "is it healthy?" in ten seconds, and a way in
// to "why?" for whatever looks wrong.
//
// It used to be a grid of five FULL PAGES shrunk into 420px scrollable cells —
// UCI, Risk, Events, Plan, Cost — each with its own header, its own filters and
// its own inner scrollbar. Reading it meant scrolling inside a cell inside a
// page, every panel showed its deepest detail at its smallest size, and the
// three richest views on the surface (Verifier, Policy, Feedback) were not on
// it at all. It also needed a CSS hack (.cog-cell-body) to flatten the cards
// that the embedded pages brought with them.
//
// So it is built the other way round now: ONE number that answers the question,
// a tile per domain carrying that domain's headline figure, its health tone and
// its shape, and a click straight into the matching Diagnostics section. Detail
// lives where there is room for it. Nothing here scrolls inside itself.

const HEALTHY_C = 0.82;

// Which Diagnostics section each tile opens. The ids are DiagnosticsTab's.
const OPENS = {
  intelligence: "uci", coherence: "coherence", risk: "risk", verifier: "verifier",
  plan: "plan", policy: "policy", cost: "uci", feedback: "feedback",
};

function cohTone(v) {
  if (v == null) return "muted";
  return v >= HEALTHY_C ? "success" : v >= 0.70 ? "warn" : "error";
}

// ── Policy: the tile must be coloured by the number it is showing ────────────
// A tile whose tone disagrees with its own figure is worse than no tone at all:
// this one printed a 99% acceptance rate in red, because the colour was taken
// from `marginal_value` while the number came from `acceptance_rate`. Nothing
// on screen explained the contradiction.
//
// Acceptance is judged against the same 70–95% band PolicyPanel uses. The band
// has an upper bound on purpose — a gate that accepts everything is not a gate,
// it is a rubber stamp — so "too high" is a real warning, and the sub-text now
// says which side of the band it fell on rather than leaving the colour to
// argue with the number.
const ACCEPT_BAND = { lo: 0.70, hi: 0.95 };

function policyValue(p) {
  return p?.acceptance_rate != null ? `${(p.acceptance_rate * 100).toFixed(0)}%` : "—";
}

function policyTone(p) {
  const r = p?.acceptance_rate;
  if (r == null) return "muted";
  if (r >= ACCEPT_BAND.lo && r <= ACCEPT_BAND.hi) return "success";
  return r < ACCEPT_BAND.lo * 0.6 || r > 1 ? "error" : "warn";
}

function policySub(p) {
  const r = p?.acceptance_rate;
  if (r == null) return "critic-gate acceptance";
  if (r > ACCEPT_BAND.hi) return "critic-gate accepts nearly everything";
  if (r < ACCEPT_BAND.lo) return "critic-gate rejecting heavily";
  return "critic-gate acceptance · in band";
}

// One-word read on the runtime, from coherence + its recent slope. Kept from
// the retired CogOS tab — it was the one thing on that screen that answered a
// question a person actually asks.
function inferMode(coh, dyn) {
  if (!coh) return { label: "Offline", tone: "muted", live: false };
  const C = coh.C ?? 0;
  let rising = false, falling = false;
  if (dyn?.length >= 3) {
    const tail = dyn.slice(-3).map(d => d.C);
    rising  = tail[2] > tail[0] + 0.015;
    falling = tail[2] < tail[0] - 0.015;
  }
  if (C < 0.65)                            return { label: "Degraded",          tone: "error",   live: true };
  if (falling && C < 0.80)                 return { label: "Recovering",        tone: "warn",    live: true };
  if (rising && (coh.G_r_mean ?? 0) > 0.01) return { label: "Learning",          tone: "accent",  live: false };
  if ((coh.conflict_rate ?? 0) > 0.20)     return { label: "Routing uncertain", tone: "warn",    live: true };
  if (C >= 0.88)                           return { label: "Stable",            tone: "success", live: false };
  return                                          { label: "Nominal",           tone: "success", live: false };
}

// ── The one health number ─────────────────────────────────────────────────────
// The surface used to carry TWO competing heroes that never appeared together:
// h_UCI (0–100) on the Dashboard and C(t) (0–1) on CogOS, each with its own Δ²
// "bending / flexing" badge on its own scale. A reader could not tell which was
// THE health number. h_UCI leads because it is the composite the whole system
// is scored on; C(t) sits beside it as one of the inputs, not a rival.
function HealthHero({ uci, traj, coh, dyn, health, onOpen }) {
  const hUCI   = uci?.h_uci;
  const mode   = inferMode(coh, dyn);
  const status = hUCI == null ? "Offline" : hUCI >= 80 ? "Healthy" : hUCI >= 60 ? "Nominal" : "Degraded";

  const hist  = (traj?.history || []).map(h => h.uci);
  const trend = hist.length > 1 ? hist[hist.length - 1] - hist[0] : 0;
  const arrow = hist.length < 2 ? "→" : trend > 0.05 ? "↑" : trend < -0.05 ? "↓" : "→";

  const curv    = traj?.curvature;
  const bending = curv?.bending;
  const peak    = curv?.peak_abs_curvature ?? 0;

  // Lower-case keys from the API; Title Case for display.
  const layers = Object.fromEntries(
    Object.entries(uci?.layers || {}).map(([k, v]) => [k.toLowerCase(), v])
  );

  return (
    <HeroStat
      value={hUCI != null ? hUCI.toFixed(1) : "—"}
      tone={scoreTone(hUCI)}
      trend={arrow}
      trendTone={arrow === "↑" ? "success" : arrow === "↓" ? "error" : "muted"}
      label="h_UCI — the composite the whole system is scored on"
      badges={
        <>
          <Pill tone={scoreTone(hUCI)} strong>{status}</Pill>
          <Pill tone={mode.tone}>{mode.label}</Pill>
          {curv?.n >= 3 && (
            <Pill tone={bending ? "error" : peak > 1 ? "warn" : "success"}>
              Δ² {peak.toFixed(1)} · {bending ? "bending" : peak > 1 ? "flexing" : "stable"}
            </Pill>
          )}
        </>
      }
    >
      <Divider />
      <Grid min={300} gap="lg">
        {/* The four layers h_UCI is made of — the first thing you want after
            the composite is which part of it is dragging. */}
        <div>
          {["Reliability", "Intelligence", "Adaptation", "Productivity"].map(name => (
            <ScoreBar key={name} label={name} value={layers[name.toLowerCase()]?.score} />
          ))}
        </div>

        {/* Coherence and liveness — inputs to the picture, sized as inputs. */}
        <Stack gap="sm">
          <Well tone={cohTone(coh?.C)} onClick={() => onOpen(OPENS.coherence)} interactive>
            <Row gap="sm">
              <Inline role="subtitle" weight={700} mono tone={cohTone(coh?.C)}>
                {coh?.C != null ? coh.C.toFixed(3) : "—"}
              </Inline>
              <Small tone="muted">C(t) coherence</Small>
              <Spacer />
              <Inline tone="muted">›</Inline>
            </Row>
            <Micro>routing, calibration and memory agreeing with each other</Micro>
          </Well>
          <Row gap="md" wrap>
            <Row gap="xs">
              <Dot tone={health?.ollama === "online" ? "success" : "error"} />
              <Micro>Ollama {health?.ollama === "online" ? "serving" : "offline"}</Micro>
            </Row>
            <Row gap="xs">
              <Dot tone={health?.memory?.backend ? "success" : "error"} />
              <Micro>{health?.memory?.total ?? "—"} memories</Micro>
            </Row>
          </Row>
        </Stack>
      </Grid>
    </HeroStat>
  );
}

export default function CognitionDashboard({ onOpenSection = () => {} }) {
  // Every one of these is a URL some Diagnostics section also reads, so the
  // cache is already warm when a tile is clicked — the detail view opens with
  // its numbers on screen instead of a spinner.
  const { data: uci }    = usePoll("/cos/uci/hierarchical",     { interval: 25_000 });
  const { data: traj }   = usePoll("/cos/uci/trajectory?n=100", { interval: 25_000 });
  const { data: health } = usePoll("/health",                   { interval: 25_000 });
  const { data: coh }    = usePoll("/coherence",                { interval: 30_000 });
  const { data: dynRaw } = usePoll("/coherence/dynamics?window=50", { interval: 30_000 });
  const { data: risk }   = usePoll("/risk/stats",               { interval: 30_000 });
  const { data: riskH }  = usePoll("/risk/history?n=100",       { interval: 30_000 });
  const { data: verify } = usePoll("/verify/stats",             { interval: 30_000 });
  const { data: plan }   = usePoll("/plan/graph",               { interval: 15_000 });
  const { data: policy } = usePoll("/policy/health?limit=200",  { interval: 30_000 });
  const { data: cost }   = usePoll("/runs/cost",                { interval: 60_000 });
  const { data: fb }     = usePoll("/feedback?limit=500",       { interval: 60_000 });
  const { data: evData } = usePoll("/cos/events?n=200",         { interval: 10_000 });

  const dyn      = Array.isArray(dynRaw) ? dynRaw : (dynRaw?.history || []);
  const events   = evData?.events || [];
  const riskHist = Array.isArray(riskH) ? [...riskH].reverse() : [];

  const planNodes  = plan?.nodes || [];
  const planDone   = planNodes.filter(n => n.status === "completed").length;
  const planFailed = planNodes.filter(n => n.status === "failed").length;

  const fbList = Array.isArray(fb) ? fb : [];
  const fbUp   = fbList.filter(f => f.rating === 1).length;
  const fbPct  = fbList.length ? Math.round((fbUp / fbList.length) * 100) : null;

  const localOnly = cost && cost.escalated_runs === 0;

  return (
    <Page>
      <PageHeader
        title="Cognition"
        subtitle="System health at a glance. Every tile opens the diagnostics behind its number."
      >
        <RefreshButton onClick={refreshAll} />
      </PageHeader>

      <Stack gap="lg">
        <HealthHero uci={uci} traj={traj} coh={coh} dyn={dyn} health={health}
                    onOpen={onOpenSection} />

        {/* One tile per domain: headline figure, health tone, shape, way in.
            Tiles are uniform — the eye compares tones across a row instead of
            re-learning a new layout in every cell. */}
        <Grid min={250} gap="sm">
          <MetricCard
            label="Intelligence" tone={scoreTone(uci?.h_uci)}
            value={uci?.h_uci != null ? uci.h_uci.toFixed(1) : "—"}
            sub="unified cognitive index"
            onClick={() => onOpenSection(OPENS.intelligence)}
          >
            <TrendChart bare height={26} domain={[0, 100]}
              series={[{ label: "h_UCI", values: (traj?.history || []).map(h => h.uci),
                         tone: hScore(uci?.h_uci), emphasis: true }]} />
          </MetricCard>

          <MetricCard
            label="Coherence" tone={cohTone(coh?.C)}
            value={coh?.C != null ? coh.C.toFixed(3) : "—"}
            sub={`${Math.round((coh?.conflict_rate ?? 0) * 100)}% routing conflict`}
            onClick={() => onOpenSection(OPENS.coherence)}
          >
            <TrendChart bare height={26} domain={[0.6, 1]}
              threshold={{ value: HEALTHY_C }}
              series={[{ label: "C(t)", values: dyn.map(d => d.C),
                         tone: cohTone(coh?.C), emphasis: true }]} />
          </MetricCard>

          <MetricCard
            label="Risk" tone={risk?.mean_risk == null ? "muted" : risk.mean_risk < 0.35 ? "success" : risk.mean_risk < 0.6 ? "warn" : "error"}
            value={risk?.mean_risk != null ? risk.mean_risk.toFixed(3) : "—"}
            sub={`${Math.round(((risk?.by_level?.light || 0) + (risk?.by_level?.full || 0)) * 100)}% reflect rate · n=${risk?.n ?? 0}`}
            onClick={() => onOpenSection(OPENS.risk)}
          >
            <TrendChart bare height={26} domain={[0, 1]}
              series={[{ label: "risk", values: riskHist.map(r => r.total_risk ?? 0),
                         tone: "warn", emphasis: true }]} />
          </MetricCard>

          <MetricCard
            label="Verifier"
            tone={verify?.pass_rate == null ? "muted" : verify.pass_rate >= 0.9 ? "success" : verify.pass_rate >= 0.7 ? "warn" : "error"}
            value={verify?.pass_rate != null ? `${(verify.pass_rate * 100).toFixed(0)}%` : "—"}
            sub={`step pass rate · last ${verify?.n ?? 0}`}
            onClick={() => onOpenSection(OPENS.verifier)}
          />

          <MetricCard
            label="Plan"
            tone={planFailed > 0 ? "error" : planNodes.length ? "success" : "muted"}
            value={planNodes.length ? `${planDone}/${planNodes.length}` : "Idle"}
            sub={planNodes.length
              ? `steps complete${planFailed ? ` · ${planFailed} failed` : ""}`
              : "no execution plan active"}
            onClick={() => onOpenSection(OPENS.plan)}
          />

          <MetricCard
            label="Policy" tone={policyTone(policy)} value={policyValue(policy)}
            sub={policySub(policy)}
            onClick={() => onOpenSection(OPENS.policy)}
          />

          <MetricCard
            label="Inference cost" tone={localOnly ? "success" : "gold"}
            value={cost ? `$${(cost.total_cost_usd ?? 0).toFixed(cost.total_cost_usd >= 1 ? 2 : 4)}` : "—"}
            sub={localOnly ? "fully local — no cloud spend" : `${((cost?.escalation_rate ?? 0) * 100).toFixed(0)}% escalated to cloud`}
            onClick={() => onOpenSection(OPENS.cost)}
          />

          <MetricCard
            label="Feedback"
            tone={fbPct == null ? "muted" : fbPct >= 70 ? "success" : fbPct >= 40 ? "warn" : "error"}
            value={fbPct != null ? `${fbPct}%` : "—"}
            sub={fbList.length ? `positive · ${fbList.length} ratings` : "no ratings yet"}
            onClick={() => onOpenSection(OPENS.feedback)}
          />
        </Grid>

        {/* A PREVIEW of the event stream, not a second copy of it: newest few,
            no filters, no search, no inner scrollbar. The full log — with all
            of that — is one click away. */}
        <Section
          title="Recent activity"
          hint="the newest events from the cognitive runtime"
          action={<Button variant="quiet" size="sm" onClick={() => onOpenSection("events")}>
            Open event log →
          </Button>}
        >
          {events.length === 0 ? (
            <EmptyState msg="No events yet — ask something in Chat and the runtime will start reporting." />
          ) : (
            <Stack gap="none">
              {events.slice(0, 8).map((e, i) => <EventRow key={i} event={e} compact />)}
            </Stack>
          )}
        </Section>
      </Stack>
    </Page>
  );
}
