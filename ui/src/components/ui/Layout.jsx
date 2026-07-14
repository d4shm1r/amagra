// Layout.jsx — the spatial vocabulary.
//
// Tabs describe structure ("a column with medium gaps", "a 4-up grid"), never
// geometry. Every gap here lands on the 4px SPACE scale, so vertical rhythm is
// a property of the system instead of a per-tab guess.
import { Children } from "react";
import { SPACE, DUR, EASE, T, LAYOUT } from "@/styles/theme";

const GAP = { none: 0, xs: SPACE[1], sm: SPACE[2], md: SPACE[3], lg: SPACE[4], xl: SPACE[6], xxl: SPACE[7] };
const gapOf = (g) => (typeof g === "number" ? g : GAP[g] ?? GAP.md);

/** The centered content column — the ONE thing that decides how wide the body
 *  of a tab is. Both widths come from LAYOUT in styles/theme.js:
 *
 *    <Column>                  the dashboard measure (LAYOUT.content)
 *    <Column measure="reading">  the prose measure   (LAYOUT.reading)
 *
 *  A view must never center itself with its own maxWidth + `margin: 0 auto`.
 *  That is how the app ended up with five competing widths the last time. The
 *  shell owns the column; the view fills whatever it is given. */
export function Column({ measure = "content", children }) {
  return (
    <div style={{ maxWidth: LAYOUT[measure] ?? measure, margin: "0 auto", width: "100%" }}>
      {children}
    </div>
  );
}

/** The tab shell. Every routed view is wrapped in exactly one of these — it
 *  owns the enter animation so no tab hand-rolls `animation: fadeIn`. */
export function Page({ children }) {
  return <div style={{ animation: `fadeIn ${DUR.base} ${EASE.out}` }}>{children}</div>;
}

/** Vertical flow. The default way to stack anything. */
export function Stack({ gap = "md", align, children, grow = false }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", gap: gapOf(gap),
      alignItems: align, ...(grow ? { flex: 1, minHeight: 0 } : null),
    }}>
      {children}
    </div>
  );
}

/** Horizontal flow. `wrap` for chip/tag runs, `spread` to push the last child right. */
export function Row({ gap = "sm", align = "center", wrap = false, spread = false, children }) {
  return (
    <div style={{
      display: "flex", alignItems: align, gap: gapOf(gap),
      flexWrap: wrap ? "wrap" : "nowrap",
      justifyContent: spread ? "space-between" : undefined,
    }}>
      {children}
    </div>
  );
}

/** Fixed-column or auto-filling grid. `cols={4}` for a 4-up; `min={218}` for a
 *  responsive card wall that reflows on its own.
 *  `divided` separates the columns with a gold hairline instead of a gap — for
 *  dense reference lists (the shortcut sheet) where whitespace would be noise. */
export function Grid({ cols = 2, min, gap = "md", divided = false, children }) {
  const style = {
    display: "grid",
    gap: divided ? 0 : gapOf(gap),
    gridTemplateColumns: min
      ? `repeat(auto-fill, minmax(${min}px, 1fr))`
      : `repeat(${cols}, 1fr)`,
  };
  if (!divided) return <div style={style}>{children}</div>;

  return (
    <div style={style}>
      {Children.map(children, (child, i) => {
        const col = i % cols;
        return (
          <div style={{
            padding: `${SPACE[2]}px 0`,
            paddingLeft:  col === 0 ? 0 : SPACE[6],
            paddingRight: col === cols - 1 ? 0 : SPACE[6],
            borderLeft:   col === 0 ? "none" : `1px solid ${T.accent}22`,
          }}>
            {child}
          </div>
        );
      })}
    </div>
  );
}

/** Push subsequent siblings to the far edge of a Row. */
export function Spacer() {
  return <div style={{ marginLeft: "auto" }} />;
}

/** A hairline. The only horizontal rule in the app. */
export function Divider({ inset = 0 }) {
  return <div style={{ height: 1, background: T.border, margin: `${SPACE[1]}px ${inset}px` }} />;
}

/** Full-width cell inside a Grid — for the "nothing matched" row under a wall. */
export function GridSpan({ children }) {
  return <div style={{ gridColumn: "1 / -1" }}>{children}</div>;
}
