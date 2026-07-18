import { T } from "@/styles/theme";
import { PageHeader } from "@/components/ui";
import UCIDashboard from "@/components/panels/UCIDashboard";
import RiskObservatoryPanel from "@/components/panels/RiskObservatoryPanel";
import EventLogPanel from "@/components/panels/EventLogPanel";
import PlanGraphPanel from "@/components/panels/PlanGraphPanel";
import InferenceCostPanel from "@/components/panels/InferenceCostPanel";

// ── Cognition dashboard (v1.4) ────────────────────────────────
// The "observability as hero" screen: the four system-health views — UCI,
// Risk, Events, Plan — composed into one responsive grid instead of four
// separate tabs. Each cell reuses its existing self-contained component
// (each fetches its own data), wrapped in a calm scrollable card so the grid
// reads as a single dashboard. The focused full-screen versions stay reachable
// from the Cognition sub-nav.

function Cell({ title, hint, children }) {
  return (
    <div className="lux-card" style={{
      display: "flex", flexDirection: "column",
      minWidth: 0, minHeight: 360, maxHeight: 560, overflow: "hidden",
    }}>
      <div style={{
        flexShrink: 0, display: "flex", alignItems: "baseline", gap: 8,
        padding: "13px 16px", borderBottom: `1px solid ${T.border}`,
      }}>
        <span style={{
          fontSize: 11, fontWeight: 700, color: T.mutedLt,
          letterSpacing: "0.1em", textTransform: "uppercase",
        }}>{title}</span>
        {hint && <span style={{ fontSize: 10, color: T.muted, letterSpacing: "0.02em" }}>{hint}</span>}
      </div>
      {/* Sections render content only (no header of their own) and own no
          padding, so the cell insets them. It clips and scrolls so one busy
          panel can't stretch the grid, and cog-cell-body flattens any nested
          lux-card so the cell is the ONLY card — no card-in-card nesting. */}
      <div className="cog-cell-body" style={{ flex: 1, overflow: "auto", minHeight: 0, padding: "12px 16px 16px" }}>
        {children}
      </div>
    </div>
  );
}

export default function CognitionView() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <PageHeader
        title="Cognition"
        subtitle="System health and reasoning at a glance — intelligence, risk, live events, and the active plan."
        gold
      />
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))",
        gap: 16,
        alignItems: "stretch",
      }}>
        <Cell title="Intelligence" hint="UCI"><UCIDashboard /></Cell>
        <Cell title="Risk" hint="Observatory"><RiskObservatoryPanel /></Cell>
        <Cell title="Events" hint="Live"><EventLogPanel /></Cell>
        <Cell title="Plan" hint="Active graph"><PlanGraphPanel /></Cell>
        <Cell title="Inference Cost" hint="Productivity"><InferenceCostPanel /></Cell>
      </div>
    </div>
  );
}
