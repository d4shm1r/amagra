// DataRow.jsx — "label ………… value", the readout row.
// Consecutive rows divide themselves with a hairline (.set-row). Used wherever
// the app states a fact about itself: the About system readout, run metadata,
// memory stats.
import { T, TYPE, SPACE, FONT_MONO } from "@/styles/theme";
import { toneColor } from "./tone";

export function DataRow({ label, value, tone = "default", mono = false, children }) {
  return (
    <div className="set-row" style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      gap: SPACE[3], padding: `${SPACE[2] + 2}px 0`,
    }}>
      <span style={{ ...TYPE.small, color: T.muted }}>{label}</span>
      <span style={{
        ...TYPE.small, color: toneColor(tone), textAlign: "right",
        minWidth: 0, overflow: "hidden", textOverflow: "ellipsis",
        ...(mono ? { fontFamily: FONT_MONO } : null),
      }}>
        {children ?? value ?? "—"}
      </span>
    </div>
  );
}
