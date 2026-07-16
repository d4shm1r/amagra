// Button.jsx — every clickable affordance in the app.
//
// Four variants, three sizes. A tab that needs a button that isn't one of these
// does not get to invent one inline: add the variant HERE so it exists once.
//   gold   — the single primary CTA on a surface (landing .btn-gold)
//   ghost  — secondary CTA, cream fill + luminous gold border (.btn-ghost)
//   quiet  — tertiary; a bare label that washes on hover (.nav-btn)
//   danger — destructive, quiet until you touch it
import { T, TYPE, RADIUS, DUR, EASE } from "@/styles/theme";
import { toneColor } from "./tone";

const SIZES = {
  sm: { padding: "5px 12px",  ...TYPE.caption, fontWeight: 600 },
  md: { padding: "7px 16px",  ...TYPE.small,   fontWeight: 600 },
  lg: { padding: "12px 30px", ...TYPE.lead,    fontWeight: 700 },
};

export function Button({
  variant = "quiet",
  size = "md",
  onClick,
  disabled = false,
  title,
  ariaLabel,
  full = false,
  align = "center",
  children,
}) {
  const base = {
    ...SIZES[size],
    fontFamily: "inherit",
    cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.55 : 1,
    whiteSpace: "nowrap",
    ...(full ? { width: "100%", textAlign: align, display: "block" } : null),
    transition: `border-color ${DUR.base} ${EASE.out}, color ${DUR.base} ${EASE.out}, background ${DUR.base} ${EASE.out}`,
  };

  // The gold + ghost recipes live in styles/index.css (they carry pseudo-element
  // sheen and multi-layer shadows that inline styles can't express).
  const cls = { gold: "btn-gold", ghost: "btn-ghost", quiet: "nav-btn", danger: "nav-btn" }[variant];

  const variantStyle = {
    gold:  { border: "none", borderRadius: 40 },
    ghost: { borderRadius: 40 },
    quiet: {
      background: "transparent", color: T.mutedLt,
      border: `1px solid ${T.border}`, borderRadius: RADIUS.md,
    },
    danger: {
      background: "transparent", color: toneColor("error"),
      border: "none", borderRadius: RADIUS.sm,
    },
  }[variant];

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={ariaLabel}
      className={cls}
      style={{ ...base, ...variantStyle }}
    >
      {children}
    </button>
  );
}

// ── The hit-target floor ─────────────────────────────────────────
// WCAG 2.2 SC 2.5.8 (AA) puts the minimum target at 24×24 CSS px. These glyph
// buttons were ~29×19 — under it on height, so a ⋯ or ✕ was a smaller thing to
// hit than the standard allows, which is felt by anyone on a trackpad, a touch
// screen, or with a tremor, not just by an audit.
//
// 24 and not the 44×44 of Apple's HIG: these sit in dense rows beside card
// titles, and 44px boxes there would either overlap each other — the later one
// in the DOM silently eating its neighbour's clicks — or force the rows apart
// and make the toolbar louder than the content it serves. 24 is the floor that
// fits the material. The GLYPH does not change size; only its box grows, so
// nothing looks different — the target was simply lying about how big it was.
const HIT = { minWidth: 24, minHeight: 24, display: "inline-flex", alignItems: "center", justifyContent: "center" };

/** A bare glyph button — the ⋯ / ↻ / ✕ affordances. No chrome until hover. */
export function IconButton({ onClick, title, ariaLabel, tone = "muted", children }) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={ariaLabel || title}
      className="nav-btn"
      style={{
        border: "none", background: "transparent", cursor: "pointer",
        color: toneColor(tone), fontSize: 15, lineHeight: 1,
        ...HIT,
        padding: "2px 7px", borderRadius: RADIUS.sm, fontFamily: "inherit",
      }}
    >
      {children}
    </button>
  );
}

/** The ↻ refresh affordance carried by most observability panel headers. */
export function RefreshButton({ onClick }) {
  return (
    <button onClick={onClick} className="nav-btn" title="Refresh" aria-label="Refresh" style={{
      ...TYPE.micro, background: "transparent", color: T.muted,
      border: `1px solid ${T.border}`, borderRadius: 7,
      ...HIT,
      padding: "4px 10px", cursor: "pointer", fontFamily: "inherit",
    }}>↻</button>
  );
}
