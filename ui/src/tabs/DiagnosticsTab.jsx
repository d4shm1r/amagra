import { useState } from "react";
import { T, GOLD, LUX, TYPE } from "@/styles/theme";
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
    <div style={{ animation: "fadeIn .2s" }}>
      {/* Segmented section nav — one decision, six calm options */}
      <div style={{ display: "flex", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
        {SECTIONS.map(s => {
          const on = s.id === sec;
          return (
            <button
              key={s.id}
              onClick={() => setSec(s.id)}
              className="nav-btn"
              style={{
                ...TYPE.small, fontWeight: on ? 700 : 500,
                padding: "7px 16px", borderRadius: 99,
                background: on ? LUX.goldTint : "transparent",
                border: `1px solid ${on ? GOLD.g2 + "66" : T.border}`,
                color: on ? T.accent2 : T.muted,
                cursor: "pointer", fontFamily: "inherit",
                transition: "background 0.12s, color 0.12s",
              }}
            >
              {s.label}
            </button>
          );
        })}
      </div>

      <Active />
    </div>
  );
}
