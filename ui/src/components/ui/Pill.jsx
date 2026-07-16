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

/** A live status dot. Pulses when `live`.
 *
 *  A dot carries its whole meaning in ONE channel: hue. That is the channel a
 *  colour-blind user does not have and a screen reader cannot see at all, so a
 *  bare dot is an indicator that only works for people who were going to be fine
 *  anyway. It therefore needs a second channel, and there are exactly two honest
 *  ways to give it one:
 *
 *    · Text beside it does the work — `<Dot tone="success" /> Ollama · serving`.
 *      The dot is then decoration, and decoration must be invisible to a screen
 *      reader or it just stutters what the label already said. This is the
 *      DEFAULT, and it is the pattern to prefer: real text beats an aria-label,
 *      because sighted colour-blind users can read it too.
 *
 *    · The dot stands alone, in which case it is not decoration and must say
 *      what it means: pass `label` ("Engine online") and it becomes an image
 *      with an accessible name.
 *
 *  So: `label` is not politeness, it is the answer to "does anything else here
 *  say what this colour means?" If nothing does, it is required. */
export function Dot({ tone = "muted", live = false, label }) {
  const color = toneColor(tone);
  return (
    <span
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
      style={{
        width: 8, height: 8, borderRadius: "50%", flexShrink: 0, display: "inline-block",
        background: color,
        ...(live ? { animation: "livePulse 1.6s ease-in-out infinite" } : null),
      }}
    />
  );
}
