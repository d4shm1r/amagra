import { useState } from "react";
import { Page, Stack, SegmentedControl } from "@/components/ui";
import UCIDashboard      from "@/components/panels/UCIDashboard";
import RiskObservatoryPanel from "@/components/panels/RiskObservatoryPanel";
import EventLogPanel       from "@/components/panels/EventLogPanel";
import PlanGraphPanel      from "@/components/panels/PlanGraphPanel";
import PolicyPanel         from "@/components/panels/PolicyPanel";
import VerifierPanel     from "@/components/panels/VerifierPanel";
import { FeedbackLoopPanel } from "@/components/panels/SystemPanels";

// ── Diagnostics (v1.6.2 IA restraint) ─────────────────────────────
// The focused system-health views (UCI, Risk, Verifier, Events, Plan, Policy)
// used to be peer tabs under Cognition — most of which already appear as cells
// on the Dashboard "at a glance" grid. They collapse into ONE tab here, with a
// calm segmented control, so Cognition reads as Dashboard + Diagnostics + the
// three Advanced views instead of many peers. Each section reuses its existing
// full-screen component unchanged (each fetches its own data).
const SECTIONS = [
  { id: "uci",      label: "Intelligence", Comp: UCIDashboard },
  { id: "risk",     label: "Risk",         Comp: RiskObservatoryPanel },
  { id: "verifier", label: "Verifier",     Comp: VerifierPanel },
  { id: "events",   label: "Events",       Comp: EventLogPanel },
  { id: "plan",     label: "Plan",         Comp: PlanGraphPanel },
  { id: "policy",   label: "Policy",       Comp: PolicyPanel },
  { id: "feedback", label: "Feedback",     Comp: FeedbackLoopPanel },  // folded in from the retired Progress tab
];

export default function DiagnosticsTab({ initialSection = "uci" }) {
  const [sec, setSec] = useState(
    SECTIONS.some(s => s.id === initialSection) ? initialSection : "uci"
  );
  const Active = (SECTIONS.find(s => s.id === sec) || SECTIONS[0]).Comp;

  return (
    <Page>
      <Stack gap="lg">
        {/* Segmented section nav — one decision, seven calm options */}
        <SegmentedControl
          options={SECTIONS.map(s => ({ val: s.id, label: s.label }))}
          value={sec}
          onChange={setSec}
        />
        <Active />
      </Stack>
    </Page>
  );
}
