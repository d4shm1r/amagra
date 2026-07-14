// Pill.jsx — the single badge shape (verdicts, statuses, tags, keywords).
// One radius, one weight, one way of tinting from a tone. If a tab wants a
// "small coloured label", it is this, always.
import { T, TYPE, FONT_MONO } from "@/styles/theme";
import { toneColor } from "./tone";

export function Pill({ tone = "muted", strong = false, children }) {
  const color = toneColor(tone);
  return (
    <span style={{
      ...TYPE.micro, fontWeight: 700, whiteSpace: "nowrap",
      padding: "3px 10px", borderRadius: 999,
      background: `${color}${strong ? "1F" : "14"}`,
      color, border: `1px solid ${color}3D`,
    }}>
      {children}
    </span>
  );
}

/** A keyword chip — monospace, gold, quieter than a Pill. Used in runs. */
export function Tag({ children }) {
  return (
    <span style={{
      ...TYPE.micro, fontFamily: FONT_MONO, color: T.accentText,
      background: `${T.accent}12`, border: `1px solid ${T.accent}30`,
      padding: "2px 8px", borderRadius: 999,
    }}>
      {children}
    </span>
  );
}

/** A live status dot. Pulses when `live`. */
export function Dot({ tone = "muted", live = false }) {
  const color = toneColor(tone);
  return (
    <span style={{
      width: 8, height: 8, borderRadius: "50%", flexShrink: 0, display: "inline-block",
      background: color,
      ...(live ? { animation: "livePulse 1.6s ease-in-out infinite" } : null),
    }} />
  );
}
