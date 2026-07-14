// CommandList.jsx — a terminal recipe: `command → what it does`, aligned.
// items: [{ cmd, desc, tone? }]
import { T, TYPE, SPACE, RADIUS, FONT_MONO } from "@/styles/theme";
import { toneColor } from "./tone";

export function CommandList({ items }) {
  return (
    <div style={{
      background: T.surface2, border: `1px solid ${T.border}`,
      borderRadius: RADIUS.md, padding: `${SPACE[3]}px ${SPACE[4]}px`,
      ...TYPE.caption, fontFamily: FONT_MONO,
    }}>
      {items.map(({ cmd, desc, tone = "gold" }) => (
        <div key={cmd} style={{ display: "flex", gap: SPACE[3], alignItems: "baseline", marginBottom: 6 }}>
          <span style={{ color: toneColor(tone), minWidth: 80 }}>{cmd}</span>
          <span style={{ color: T.muted }}>→</span>
          <span style={{ color: T.muted }}>{desc}</span>
        </div>
      ))}
    </div>
  );
}
