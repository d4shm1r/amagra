import { T } from "./theme";
import { PageHeader } from "./ObsShared";
import UCIDashboard from "./UCIDashboard";
import RiskObservatoryTab from "./RiskObservatoryTab";
import EventLogTab from "./EventLogTab";
import PlanGraphTab from "./PlanGraphTab";

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
      {/* The embedded tab components carry their own padding/headers; clip and
          scroll within the cell so one busy panel can't stretch the grid. The
          cog-cell-body class flattens any nested lux-cards so the cell is the
          ONLY card — content inside reads flat, no card-in-card nesting. */}
      <div className="cog-cell-body" style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
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
        <Cell title="Intelligence" hint="UCI"><UCIDashboard embedded /></Cell>
        <Cell title="Risk" hint="Observatory"><RiskObservatoryTab embedded /></Cell>
        <Cell title="Events" hint="Live"><EventLogTab embedded /></Cell>
        <Cell title="Plan" hint="Active graph"><PlanGraphTab embedded /></Cell>
      </div>
    </div>
  );
}
