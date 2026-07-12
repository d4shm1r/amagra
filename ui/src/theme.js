// Amagra design tokens — "Gilded Calm"
// Warm-white + gold luxury palette. The CSS source of truth is
// public/tokens.css (:root vars), loaded by BOTH the app and landing.html.
// This file is its JS mirror — React inline styles need raw hex for
// alpha-suffix templates like `${T.accent}44`, which CSS vars can't do.
// If you change a value here, change tokens.css in the same commit.
// Canvas is layered creams (--l0..--l4), brand is the 5-step gold ramp
// (--g1..--g5), text is warm umber (--t1..--t4). Shadows warm, never black.

export const T = {
  // Canvas (light → lighter)
  bg:       "#F0E9DF",   // app canvas        (landing --hero-bg)
  surface:  "#FAF7F2",   // raised panels     (landing --l2)
  surface2: "#F4F0E8",   // inset wells/chips (landing --l1)
  border:   "#E0D6C4",   // hairlines on cream
  // Brand
  accent:   "#C48808",   // gold core   (landing --g3) — fills, dots, borders, icons
  accent2:  "#9A6C00",   // deep gold   (landing --g4) — hovers, links
  accentText: "#8A5A00", // readable gold for TEXT on cream (~5:1 AA). The bright
                         // accent is only 2.5:1 as text — use this when gold is
                         // a label/title/link, not a fill.
  // Semantic (deepened for light canvas)
  success:  "#15803D",
  warn:     "#A16207",
  error:    "#B42318",
  // Text (warm umber ramp) — all three tiers now clear WCAG AA (4.5:1) on the
  // cream surfaces. `muted` was #9A7A60 (3.3:1, below the floor); deepened to
  // #806044 (~4.7:1) so secondary text stays recessive but is actually legible.
  text:     "#2E2010",   // landing --t1   — primary  (AAA)
  muted:    "#806044",   // tertiary / metadata        (AA)
  mutedLt:  "#5C4030",   // landing --t2   — secondary (AAA)
};

// Gold ramp for gradients / wordmark
export const GOLD = {
  g1: "#FFE880", g2: "#DEB838", g3: "#C48808", g4: "#9A6C00", g5: "#6C4C00",
};

// Semantic data-viz accents — categorical encodings (node/edge/agent types,
// causal-path stages) used by the analysis tabs. NOT decoration: each carries
// meaning, like the status colors. Centralized so the four legacy tabs
// (Data, DecisionTimeline, ContextInspector, KnowledgeGraph) share one
// vocabulary instead of re-hardcoding the same hex. Deepened for the cream
// canvas to match T.success/T.error.
export const SEM = {
  teal:    "#0F766E",
  blue:    "#1E5A8A",
  cyan:    "#0E7490",
  violet:  "#7C3AED",
  purple:  "#7E3F8F",
  magenta: "#BE185D",
  clay:    "#C06040",
};

// Reusable luxury accents
export const LUX = {
  goldText: {
    background: `linear-gradient(135deg, ${GOLD.g5} 0%, ${GOLD.g4} 18%, ${GOLD.g3} 36%, ${GOLD.g2} 52%, ${GOLD.g3} 68%, ${GOLD.g4} 84%, ${GOLD.g5} 100%)`,
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    backgroundClip: "text",
  },
  goldTint:   "rgba(196, 136, 8, 0.10)",   // active/selected fills
  goldTint2:  "rgba(196, 136, 8, 0.22)",   // stronger fills / focus rings
  hover:      "rgba(72, 52, 28, 0.05)",    // neutral hover wash

  // "Depth, not outline" — luxury cards resting on the cream field. The face is
  // translucent so it borrows the canvas underneath; the hairline is a whisper
  // of gold (not a grey box border); depth comes from a soft, warm lift shadow.
  tileBorder: "rgba(182, 138, 50, 0.14)",  // near-invisible card hairline
  tileFace:   "rgba(255, 255, 255, 0.58)", // frosted translucent card face
  tileLift:   "0 8px 30px rgba(95, 75, 20, 0.05)", // resting depth (warm, low)
  shadowSm:   "0 1px 3px rgba(72, 52, 28, 0.08)",
  shadowMd:   "0 4px 18px rgba(72, 52, 28, 0.11)",
  shadowLg:   "0 18px 48px rgba(62, 44, 20, 0.20)",
  glass:      "rgba(250, 247, 242, 0.88)", // frosted bars (pair with backdropFilter)

  // Landing-style "luxe card" recipe (mirrors public/landing.html .for-card).
  // Prefer className="lux-card" / "lux-card-i" (index.css) — it adds the top
  // gloss + hover. These tokens are for surfaces that must stay inline-styled.
  cardBg:     "linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 42%), #FAF7F2",
  cardBorder: "rgba(255, 255, 255, 0.45)",
  cardShadow: "7px 7px 20px rgba(72,52,28,0.10), -3px -3px 11px rgba(255,255,255,0.75), inset 0 1px 1px rgba(255,255,255,0.92), inset 0 -1px 1px rgba(138,99,36,0.04)",
};

// Font stacks
export const FONT_UI      = "'DM Sans', 'Manrope', system-ui, -apple-system, 'Segoe UI', 'Ubuntu', 'Roboto', sans-serif";
export const FONT_DISPLAY = "'Cormorant Garamond', 'Iowan Old Style', Palatino, Georgia, serif";
export const FONT_MONO    = "'JetBrains Mono', 'Cascadia Code', 'Consolas', 'Droid Sans Mono', 'Courier New', monospace";

// ── Type scale — "type is architecture" ──────────────────────────
// Eight role-based steps (30/22/18/15/14/13/12/10.5) replacing the 36
// ad-hoc sizes that had accreted. Each role is a ready-to-spread style
// object: it carries its own line-height, weight, and tracking so the
// vertical rhythm lives in the token, not in per-component guesswork.
//
//   style={{ ...TYPE.body, color: T.text }}
//
// Override weight inline for one-off emphasis (e.g. ...TYPE.small, fontWeight: 700).
export const TYPE = {
  display:  { fontSize: 36,   lineHeight: 1.12, fontWeight: 600, letterSpacing: "0.01em",   fontFamily: FONT_DISPLAY }, // page hero (serif)
  title:    { fontSize: 22,   lineHeight: 1.25, fontWeight: 600, letterSpacing: "-0.01em" },                            // section / panel heading
  subtitle: { fontSize: 18,   lineHeight: 1.4,  fontWeight: 600, letterSpacing: "-0.005em" },                          // sub-section heading
  lead:     { fontSize: 15,   lineHeight: 1.66, fontWeight: 400 },                                                     // emphasized / readable body
  body:     { fontSize: 14,   lineHeight: 1.6,  fontWeight: 400 },                                                     // default body
  small:    { fontSize: 13,   lineHeight: 1.55, fontWeight: 400 },                                                     // dense / secondary body
  caption:  { fontSize: 12,   lineHeight: 1.45, fontWeight: 400 },                                                     // captions, metadata, hints
  metric:   { fontSize: 22,   lineHeight: 1.1,  fontWeight: 700, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }, // stat-card numerals
  micro:    { fontSize: 10.5, lineHeight: 1.4,  fontWeight: 400 },                                                     // dense meta / numerics (badges add their own weight)
  eyebrow:  { fontSize: 10.5, lineHeight: 1.4,  fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase" }, // overline labels / dividers
};

// ── Motion tokens — one easing language, four durations ──────────
// The decel curve already used everywhere, named once. Durations match
// the existing lux-card / button timings so adoption is a no-op visually.
export const EASE = {
  out:   "cubic-bezier(0.22, 1, 0.36, 1)",  // standard decelerate — enters, lifts
  inOut: "cubic-bezier(0.65, 0, 0.35, 1)",  // symmetric — loops, toggles
};
export const DUR = { fast: "140ms", base: "200ms", slow: "280ms", slower: "600ms" };

// Spacing scale (px) — use multiples of 4
export const SPACE = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 7: 32, 8: 40, 10: 48 };

// Border radius scale — rounder than the old VS Code look
export const RADIUS = { sm: 6, md: 9, lg: 14, xl: 20 };
