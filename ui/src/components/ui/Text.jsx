// Text.jsx — the typographic vocabulary.
//
// Eight roles from TYPE (theme.js), each carrying its own size, weight,
// line-height and tracking. Tabs pick a ROLE and a TONE; they never pick a
// fontSize. That is what keeps the vertical rhythm from drifting per tab.
import { T, TYPE, FONT_MONO, FONT_DISPLAY, SPACE, RADIUS } from "@/styles/theme";
import { toneColor } from "./tone";

function make(role, defaultTone) {
  return function Typo({ tone = defaultTone, weight, mono = false, align, clamp, title, children, block = false }) {
    const style = {
      ...TYPE[role],
      color: toneColor(tone),
      ...(weight ? { fontWeight: weight } : null),
      ...(mono ? { fontFamily: FONT_MONO } : null),
      ...(align ? { textAlign: align } : null),
      ...(clamp ? {
        display: "-webkit-box", WebkitLineClamp: clamp, WebkitBoxOrient: "vertical", overflow: "hidden",
      } : null),
    };
    return <div style={style} title={title}>{children}</div>;
  };
}

/** Serif hero — reserved for page/empty-state headlines. */
export function Display({ tone = "default", align, children }) {
  return (
    <div style={{ ...TYPE.display, fontFamily: FONT_DISPLAY, color: toneColor(tone), textAlign: align }}>
      {children}
    </div>
  );
}

export const Title    = make("title",    "default");  // section / panel heading
export const Subtitle = make("subtitle", "default");  // sub-section heading
export const Lead     = make("lead",     "default");  // emphasized body
export const Body     = make("body",     "default");  // default body
export const Small    = make("small",    "default");  // dense / secondary body
export const Caption  = make("caption",  "muted");    // metadata, hints
export const Micro    = make("micro",    "muted");    // dense numerics
export const Eyebrow  = make("eyebrow",  "gold");     // overline label

/** Inline text run — for use inside a Row where a block would break the flow.
 *  `pulse` marks text as live/in-progress ("Reading…"). */
export function Inline({ role = "body", tone = "default", weight, mono = false, pulse = false, children }) {
  return (
    <span style={{
      ...TYPE[role], color: toneColor(tone),
      ...(weight ? { fontWeight: weight } : null),
      ...(mono ? { fontFamily: FONT_MONO } : null),
      ...(pulse ? { animation: "livePulse 1.4s ease-in-out infinite" } : null),
    }}>
      {children}
    </span>
  );
}

/** Inline code chip — a formula, a path, a command. */
export function Code({ tone = "muted", truncate, children }) {
  return (
    <code style={{
      ...TYPE.caption, fontFamily: FONT_MONO, color: toneColor(tone),
      background: T.surface2, border: `1px solid ${T.border}`,
      borderRadius: RADIUS.sm - 2, padding: "2px 8px",
      ...(truncate ? {
        maxWidth: truncate, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      } : null),
    }}>
      {children}
    </code>
  );
}

/** Block of code / a terminal recipe. */
export function CodeBlock({ tone = "gold", children }) {
  return (
    <div style={{
      ...TYPE.caption, fontFamily: FONT_MONO, color: toneColor(tone),
      background: T.surface2, border: `1px solid ${T.border}`,
      borderRadius: RADIUS.md, padding: `${SPACE[3]}px ${SPACE[4]}px`,
      overflowX: "auto", lineHeight: 1.8,
    }}>
      {children}
    </div>
  );
}
