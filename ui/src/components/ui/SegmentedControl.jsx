// SegmentedControl.jsx — a small set of mutually exclusive choices shown at
// once (Auto / Fast / Check / Deep). The selected segment carries a gold tint;
// the others recede. Use instead of a Select when there are ≤4 options and the
// options themselves are worth reading.
import { T, TYPE, RADIUS, DUR, EASE } from "@/styles/theme";

/** options: [{ val, label }] */
export function SegmentedControl({ options, value, onChange }) {
  return (
    <div style={{
      display: "inline-flex", gap: 2, padding: 2, background: T.surface2,
      border: `1px solid ${T.border}`, borderRadius: RADIUS.md,
    }}>
      {options.map(o => {
        const on = value === o.val;
        return (
          <button key={o.val} onClick={() => onChange(o.val)} style={{
            ...TYPE.micro, fontSize: 11, fontWeight: on ? 700 : 500, fontFamily: "inherit",
            padding: "5px 13px", border: "none", borderRadius: RADIUS.sm, cursor: "pointer",
            background: on ? `${T.accent}22` : "transparent",
            color: on ? T.accentText : T.muted,
            transition: `background ${DUR.fast} ${EASE.out}, color ${DUR.fast} ${EASE.out}`,
          }}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
