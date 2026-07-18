// ── Coherence (Diagnostics section) ───────────────────────────────────────────
// C(t) — how consistently the system agrees with itself: routing (brain vs
// router), calibration (confidence vs outcome) and memory quality, averaged.
//
// Extracted from the retired CogOS tab, which owned the only good ideas on that
// screen — the inferred system MODE, the Δ²C bend indicator, and the slope-based
// health prediction — buried under a second copy of the event feed, a second
// routing inspector and a private mini design system. Those ideas live here, on
// the kit, next to the Intelligence section they were always describing.
//
// Section contract: content only. Diagnostics owns the header and refresh.
import { useState } from "react";
import {
  Stack, Row, Grid, Section, Well, Spacer, Small, Micro, Caption, Inline, Pill,
  MetricCard, HeroStat, ScoreBar, TrendChart, EmptyState, Notice, Button, SegmentedControl,
} from "@/components/ui";
import { usePoll } from "@/lib/usePoll";

const HEALTHY = 0.82;   // the C(t) line the system is expected to hold above

// C(t) in 0–1 → tone. Deliberately stricter than the generic probTone: this is
// a self-consistency score, and 0.70 is already a bad day for it.
function cohTone(v) {
  if (v == null) return "muted";
  return v >= HEALTHY ? "success" : v >= 0.70 ? "warn" : "error";
}

// ── System mode — the one-word read on what the runtime is doing ──────────────
// Ordered by urgency: a degraded system is degraded even if it is also learning.
function inferMode(coh, dynamics) {
  if (!coh) return { label: "Offline", tone: "muted", live: false };
  const C        = coh.C ?? 0;
  const conflict = coh.conflict_rate ?? 0;
  const gain     = coh.G_r_mean ?? 0;

  let rising = false, falling = false;
  if (dynamics?.length >= 3) {
    const tail = dynamics.slice(-3).map(d => d.C);
    rising  = tail[2] > tail[0] + 0.015;
    falling = tail[2] < tail[0] - 0.015;
  }

  if (C < 0.65)                   return { label: "Degraded",          tone: "error",   live: true };
  if (falling && C < 0.80)        return { label: "Recovering",        tone: "warn",    live: true };
  if (rising && gain > 0.01)      return { label: "Learning",          tone: "accent",  live: false };
  if (conflict > 0.20)            return { label: "Routing uncertain", tone: "warn",    live: true };
  if (C >= 0.88)                  return { label: "Stable",            tone: "success", live: false };
  return                                 { label: "Nominal",           tone: "success", live: false };
}

// ── Health prediction — least-squares slope over the recent window ────────────
function predictHealth(dynamics) {
  if (!dynamics || dynamics.length < 4) return null;
  const recent = dynamics.slice(-6).map(d => d.C);
  const n     = recent.length;
  const xMean = (n - 1) / 2;
  const yMean = recent.reduce((a, b) => a + b, 0) / n;
  const denom = recent.reduce((s, _, i) => s + (i - xMean) ** 2, 0) || 1;
  const slope = recent.reduce((s, y, i) => s + (i - xMean) * (y - yMean), 0) / denom;
  const cur   = recent[n - 1];
  const clamp = v => Math.min(1, Math.max(0, v));
  const p5    = clamp(cur + slope * 5);
  const p10   = clamp(cur + slope * 10);
  const variance = recent.reduce((s, y) => s + (y - yMean) ** 2, 0) / n;

  if (Math.abs(slope) < 0.003 || variance < 0.0005) {
    return { trend: "Stable", tone: "success", slope,
      msg: `Expected to hold near ${p5.toFixed(3)} over the next few windows.` };
  }
  if (slope > 0.003) {
    return { trend: "Rising", tone: "success", slope,
      msg: `Trending toward ${p10.toFixed(3)} — learning is active.` };
  }
  return { trend: "Declining", tone: "error", slope,
    msg: `Trending toward ${p10.toFixed(3)} — check routing conflicts and contradictions.` };
}

// Peak |Δ²C| over the window. Coherence bending sharply is a leading indicator:
// it turns before C(t) itself falls (see coherence.py / the OCAC notes).
function peakCurvature(dynamics) {
  let idx = -1, val = 0;
  (dynamics || []).forEach((d, i) => {
    if (d.C_curvature != null && Math.abs(d.C_curvature) > Math.abs(val)) { val = d.C_curvature; idx = i; }
  });
  const tone = Math.abs(val) > 0.05 ? "error" : Math.abs(val) > 0.025 ? "warn" : "success";
  const label = Math.abs(val) > 0.05 ? "bending" : Math.abs(val) > 0.025 ? "flexing" : "smooth";
  return { idx, val, tone, label };
}

// ── Why is C(t) not 1.000? ───────────────────────────────────────────────────
// Each component contributes a third of the total, so the gap each one costs is
// (1 − value) / 3. Naming the worst one is the whole point of the breakdown:
// "coherence is 0.79" is a fact, "calibration is costing you 0.06" is a task.
function Breakdown({ coh }) {
  const parts = [
    { label: "Routing",     val: coh?.c_routing, desc: "brain–router agreement" },
    { label: "Calibration", val: coh?.c_calib,   desc: "confidence vs outcome" },
    { label: "Memory",      val: coh?.c_quality, desc: "average knowledge quality" },
  ].filter(p => p.val != null);

  if (!parts.length) return <EmptyState msg="No coherence components reported yet." />;

  const worst = [...parts].sort((a, b) => a.val - b.val)[0];

  return (
    <Stack gap="sm">
      {parts.map(p => (
        <ScoreBar
          key={p.label}
          label={p.label === worst.label ? `${p.label} — bottleneck` : p.label}
          value={p.val * 100}
          sub={`${p.desc} · contributes ${(p.val / 3).toFixed(3)} of 0.333`}
        />
      ))}
      <Small tone="muted">
        <Inline weight={700} tone={cohTone(worst.val)}>{worst.label}</Inline>
        {" "}is costing{" "}
        <Inline weight={700} mono tone={cohTone(worst.val)}>{((1 - worst.val) / 3).toFixed(3)}</Inline>
        {" "}points from a perfect 1.000.
        {worst.val < 0.70 && " Worth acting on now."}
      </Small>
    </Stack>
  );
}

export default function CoherencePanel() {
  const [win, setWin]   = useState(50);
  const [why, setWhy]   = useState(false);

  const { data: coh, error: cohErr } = usePoll("/coherence", { interval: 30_000 });
  const { data: dynRaw }             = usePoll(`/coherence/dynamics?window=${win}`, { interval: 30_000 });

  const dyn = Array.isArray(dynRaw) ? dynRaw : (dynRaw?.history || []);

  const C     = coh?.C ?? null;
  const mode  = inferMode(coh, dyn);
  const bend  = peakCurvature(dyn);
  const pred  = predictHealth(dyn);

  // Direction of the last step — the arrow next to the hero number.
  const tail  = dyn.slice(-2);
  const trend = tail.length < 2 ? "→"
    : tail[1].C > tail[0].C + 0.001 ? "↑"
    : tail[1].C < tail[0].C - 0.001 ? "↓" : "→";
  const trendTone = trend === "↑" ? "success" : trend === "↓" ? "error" : "muted";

  const xLabels = dyn.length
    ? [`w${dyn[0].window_idx ?? 0}`,
       `w${dyn[Math.floor(dyn.length / 2)]?.window_idx ?? ""}`,
       `w${dyn[dyn.length - 1].window_idx ?? dyn.length - 1}`]
    : [];

  return (
    <Stack gap="lg">
      {cohErr && <Notice tone="error">Coherence unavailable: {cohErr}</Notice>}

      <HeroStat
        value={C != null ? C.toFixed(3) : "—"}
        tone={cohTone(C)}
        trend={trend}
        trendTone={trendTone}
        label="Global coherence — C(t) = (routing + calibration + memory) / 3"
        badges={
          <>
            <Pill tone={mode.tone} strong>{mode.label}</Pill>
            {bend.idx >= 0 && (
              <Pill tone={bend.tone}>
                Δ²C {bend.val >= 0 ? "+" : ""}{bend.val.toFixed(3)} · {bend.label}
              </Pill>
            )}
            {C != null && (
              <Button variant="quiet" size="sm" onClick={() => setWhy(w => !w)}>
                {why ? "Hide breakdown" : "Why?"}
              </Button>
            )}
          </>
        }
      />

      {why && (
        <Section title={`Why is C(t) ${C?.toFixed(3)} and not 1.000?`}>
          <Breakdown coh={coh} />
        </Section>
      )}

      <Section
        title="Coherence timeline"
        hint="C(t) with its three components — the dashed line is the healthy floor"
        action={
          <SegmentedControl
            label="Timeline window (samples)"
            options={[20, 50, 100].map(w => ({ val: w, label: `${w}` }))}
            value={win}
            onChange={setWin}
          />
        }
      >
        <TrendChart
          height={170}
          // Fixed, not data-fitted, so the slope means the same thing on every
          // refresh. 0.6 rather than 0.4 as the floor: a healthy system lives
          // between 0.82 and 1.0, and a domain twice that tall spent half the
          // chart on empty space below anything the system has ever reported.
          // Values under 0.6 clamp to the floor, where "pinned at the bottom"
          // is exactly the right read.
          domain={[0.6, 1]}
          grid={[0.7, 0.9, 1.0]}
          threshold={{ value: HEALTHY, label: "healthy" }}
          xLabels={xLabels}
          format={v => v.toFixed(2)}
          legend
          empty="Collecting data — the timeline needs at least two windows."
          marker={bend.idx >= 0 && Math.abs(bend.val) > 0.025
            ? { index: bend.idx, tone: bend.tone,
                title: `Sharpest bend: Δ²C = ${bend.val.toFixed(4)}` }
            : null}
          series={[
            { label: "C(t)",        values: dyn.map(d => d.C),         tone: cohTone(C), emphasis: true },
            { label: "routing",     values: dyn.map(d => d.c_routing), tone: "accent" },
            { label: "calibration", values: dyn.map(d => d.c_calib),   tone: "teal" },
            { label: "memory",      values: dyn.map(d => d.c_quality), tone: "purple" },
          ]}
        />
      </Section>

      <Grid min={220} gap="sm">
        <MetricCard
          label="Conflict rate" tone={(coh?.conflict_rate ?? 0) > 0.2 ? "warn" : "success"}
          value={coh?.conflict_rate != null ? `${(coh.conflict_rate * 100).toFixed(0)}%` : "—"}
          sub="brain and router disagreeing"
        />
        <MetricCard
          label="Reflection rate" tone="default"
          value={coh?.reflection_rate != null ? `${(coh.reflection_rate * 100).toFixed(0)}%` : "—"}
          sub={coh?.G_r_positive != null ? `${Math.round(coh.G_r_positive * 100)}% improved the answer` : "share of queries reflected"}
        />
        <MetricCard
          label="Reflection gain" tone={(coh?.G_r_mean ?? 0) > 0.02 ? "success" : "muted"}
          value={coh?.G_r_mean != null ? `${coh.G_r_mean >= 0 ? "+" : ""}${coh.G_r_mean.toFixed(4)}` : "—"}
          sub="mean quality delta when it reflects"
        />
        <MetricCard
          label="Memory" tone={coh?.mem_avg_quality >= 0.75 ? "success" : "warn"}
          value={coh?.mem_avg_quality != null ? coh.mem_avg_quality.toFixed(3) : "—"}
          sub={coh?.mem_n != null ? `${coh.mem_n} entries · average quality` : "average quality"}
        />
      </Grid>

      <Section title="Health prediction" hint="extrapolated from the recent slope">
        {pred ? (
          <Well tone={pred.tone}>
            <Row gap="sm">
              <Inline role="subtitle" weight={700} tone={pred.tone}>{pred.trend}</Inline>
              <Spacer />
              <Micro mono>slope {pred.slope >= 0 ? "+" : ""}{pred.slope.toFixed(5)} / window</Micro>
            </Row>
            <Caption>{pred.msg}</Caption>
          </Well>
        ) : (
          <EmptyState msg="Needs at least four dynamics windows before it can project a trend." />
        )}
      </Section>
    </Stack>
  );
}
