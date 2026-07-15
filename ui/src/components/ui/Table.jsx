// Table.jsx — the tabular readout. A log or list where every row is the same
// set of fields (the verifier log, run lists, decision tables).
//
// The point: a VIEW declares its columns — width, alignment, tone — and never
// writes `minWidth`/`style` at the call site. That per-cell inline style was the
// escape hatch that kept every log panel out of the design system.
//
//   columns: [{
//     key,        row[key] is the default cell value
//     header,     optional column label; omit on every column for a headerless log
//     width,      px min-width for a fixed column; omit on the ONE flexible column
//     grow,       this column takes the remaining space and ellipsizes (the message)
//     align,      "left" (default) | "right"
//     mono,       monospace the cell
//     weight,     font weight for the cell (bold a key column)
//     tone,       a tone name, or (row) => toneName for per-row semantic color
//     render,     (row) => node — full control; compose <Inline> for mixed tones
//   }]
import { T, TYPE, SPACE, FONT_MONO } from "@/styles/theme";
import { toneColor } from "./tone";

function cellStyle(col) {
  return {
    ...TYPE.small,
    textAlign: col.align || "left",
    ...(col.mono ? { fontFamily: FONT_MONO } : null),
    ...(col.weight ? { fontWeight: col.weight } : null),
    ...(col.grow
      ? { flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }
      : { flexShrink: 0, ...(col.width ? { minWidth: col.width } : null) }),
  };
}

const ROW = (divided) => ({
  display: "flex", alignItems: "center", gap: SPACE[3],
  padding: `${SPACE[2] - 1}px 2px`,
  ...(divided ? { borderBottom: `1px solid ${T.border}` } : null),
});

export function Table({ columns, rows, rowKey }) {
  const hasHeader = columns.some(c => c.header);
  return (
    <div style={{ overflowX: "auto" }}>
      {hasHeader && (
        <div style={ROW(true)}>
          {columns.map((c, j) => (
            <span key={j} style={{ ...cellStyle(c), ...TYPE.eyebrow, color: T.muted }}>
              {c.header}
            </span>
          ))}
        </div>
      )}
      {rows.map((row, i) => (
        <div key={rowKey ? rowKey(row, i) : i} style={ROW(i < rows.length - 1)}>
          {columns.map((c, j) => {
            const tone = typeof c.tone === "function" ? c.tone(row) : c.tone;
            const content = c.render ? c.render(row) : row[c.key];
            return (
              <span key={j} style={{ ...cellStyle(c), color: toneColor(tone || "default") }}>
                {content ?? "—"}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}
