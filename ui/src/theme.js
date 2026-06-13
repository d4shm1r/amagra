// Amagra design tokens — "Gilded Calm"
// Warm-white + gold luxury palette, shared with public/landing.html.
// Canvas is layered creams (landing --l0..--l4), brand is the 5-step gold
// ramp (--g1..--g5), text is warm umber (--t1..--t4). Shadows are warm,
// never pure black.

export const T = {
  // Canvas (light → lighter)
  bg:       "#F0E9DF",   // app canvas        (landing --hero-bg)
  surface:  "#FAF7F2",   // raised panels     (landing --l2)
  surface2: "#F4F0E8",   // inset wells/chips (landing --l1)
  border:   "#E0D6C4",   // hairlines on cream
  // Brand
  accent:   "#C48808",   // gold core   (landing --g3)
  accent2:  "#9A6C00",   // deep gold   (landing --g4) — hovers, links
  // Semantic (deepened for light canvas)
  success:  "#15803D",
  warn:     "#A16207",
  error:    "#B42318",
  // Text (warm umber ramp)
  text:     "#2E2010",   // landing --t1
  muted:    "#9A7A60",   // landing --t3
  mutedLt:  "#5C4030",   // landing --t2
};

// Gold ramp for gradients / wordmark
export const GOLD = {
  g1: "#FFE880", g2: "#DEB838", g3: "#C48808", g4: "#9A6C00", g5: "#6C4C00",
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

// Spacing scale (px) — use multiples of 4
export const SPACE = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24 };

// Border radius scale — rounder than the old VS Code look
export const RADIUS = { sm: 6, md: 9, lg: 14, xl: 20 };
