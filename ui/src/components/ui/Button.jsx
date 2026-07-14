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
      padding: "4px 10px", cursor: "pointer", fontFamily: "inherit",
    }}>↻</button>
  );
}
