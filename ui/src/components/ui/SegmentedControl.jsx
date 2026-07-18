// SegmentedControl.jsx — a small set of mutually exclusive choices shown at
// once (Auto / Fast / Check / Deep). The selected segment carries a gold tint;
// the others recede. Use instead of a Select when there are ≤4 options and the
// options themselves are worth reading.
import { T, TYPE, RADIUS, DUR, EASE } from "@/styles/theme";

/** options: [{ val, label }]
 *
 *  `label` names the group ("Diagnostics section", "Event category"). It is not
 *  decoration: a page can hold several of these at once — the Diagnostics
 *  section nav sits directly above the Events panel's own category filter, and
 *  both offer a "Risk" and a "Plan". Without a group name, those are four
 *  identically-named buttons with nothing to tell them apart, by ear or by
 *  automation. Selection is carried on `aria-pressed`, since the gold tint that
 *  shows it is only available to people who can see it. */
export function SegmentedControl({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} style={{
      display: "inline-flex", gap: 2, padding: 2, background: T.surface2,
      border: `1px solid ${T.border}`, borderRadius: RADIUS.md,
    }}>
      {options.map(o => {
        const on = value === o.val;
        return (
          <button key={o.val} onClick={() => onChange(o.val)} aria-pressed={on} style={{
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
