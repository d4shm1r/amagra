import { useState } from "react";
import { Page, Stack, SegmentedControl, PageHeader, RefreshButton } from "@/components/ui";
import { refreshAll } from "@/lib/usePoll";
import UCIDashboard         from "@/components/panels/UCIDashboard";
import CoherencePanel       from "@/components/panels/CoherencePanel";
import RiskObservatoryPanel from "@/components/panels/RiskObservatoryPanel";
import EventLogPanel        from "@/components/panels/EventLogPanel";
import PlanGraphPanel       from "@/components/panels/PlanGraphPanel";
import PolicyPanel          from "@/components/panels/PolicyPanel";
import VerifierPanel        from "@/components/panels/VerifierPanel";
import { FeedbackLoopPanel } from "@/components/panels/SystemPanels";

// ── Diagnostics — the deep-dive half of Cognition ─────────────────
// Dashboard answers "is it healthy?"; this answers "why?". One section is
// visible at a time, chosen by the segmented control.
//
// THE SECTION CONTRACT: a section renders CONTENT ONLY — no <Page>, no
// PageHeader, no refresh button of its own. The tab owns all three.
//
// It earned that rule the hard way. Every section used to carry its own
// PageHeader, so the page re-titled itself under the nav on each switch
// ("Diagnostics" → "Step Verifier" → "Risk Observatory"), and VerifierPanel
// returned its own <Page> nested inside this one's. Two headers, two enter
// animations, and a title that argued with the tab you were on.
const SECTIONS = [
  { id: "uci",       label: "Intelligence", Comp: UCIDashboard,
    desc: "Unified Cognitive Index · 30% Reliability · 30% Intelligence · 25% Adaptation · 15% Productivity" },
  { id: "coherence", label: "Coherence",    Comp: CoherencePanel,
    desc: "C(t) — how consistently routing, calibration and memory agree over time" },
  { id: "risk",      label: "Risk",         Comp: RiskObservatoryPanel,
    desc: "Reflection gate signals · risk score distribution · per-action breakdown" },
  { id: "verifier",  label: "Verifier",     Comp: VerifierPanel,
    desc: "Every plan step is scored before the system moves on — pass, retry, replan, or abort" },
  { id: "events",    label: "Events",       Comp: EventLogPanel,
    desc: "Typed event stream from the cognitive runtime" },
  { id: "plan",      label: "Plan",         Comp: PlanGraphPanel,
    desc: "The active plan graph — steps, dependencies and where execution is now" },
  { id: "policy",    label: "Policy",       Comp: PolicyPanel,
    desc: "Escalation thresholds and how often each gate fires" },
  { id: "feedback",  label: "Feedback",     Comp: FeedbackLoopPanel,
    desc: "Thumbs ratings rolled up by agent — the human signal on answer quality" },
];

const valid = (id) => (SECTIONS.some(s => s.id === id) ? id : "uci");

export default function DiagnosticsTab({ initialSection = "uci" }) {
  const [sec, setSec] = useState(() => valid(initialSection));

  // A deep link must win even if this tab is already mounted. Reading the prop
  // only in the useState initializer would make "open the Risk diagnostics"
  // silently do nothing whenever the tab happened to still be alive — a bug
  // that hides until someone changes how tabs unmount.
  const [seenProp, setSeenProp] = useState(initialSection);
  if (initialSection !== seenProp) {
    setSeenProp(initialSection);
    setSec(valid(initialSection));
  }

  const active = SECTIONS.find(s => s.id === sec) || SECTIONS[0];
  const Active = active.Comp;

  return (
    <Page>
      {/* One header for the whole tab. The subtitle tracks the active section,
          so the page says what you are looking at without re-titling itself. */}
      <PageHeader title="Diagnostics" subtitle={active.desc}>
        <RefreshButton onClick={refreshAll} />
      </PageHeader>

      <Stack gap="lg">
        <SegmentedControl
          label="Diagnostics section"
          options={SECTIONS.map(s => ({ val: s.id, label: s.label }))}
          value={sec}
          onChange={setSec}
        />
        <Active />
      </Stack>
    </Page>
  );
}
