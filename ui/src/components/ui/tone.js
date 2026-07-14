// tone.js — the semantic color vocabulary.
//
// Tabs never name a color. They name a MEANING ("this row is an error", "this
// number is healthy") and the kit resolves it to a hex. This is the single
// translation table between the two, so a palette change lands in one place.
import { T, SEM } from "@/styles/theme";

/** Every tone a component may be given. Anything else is a bug, not a color. */
export const TONES = {
  default: T.text,
  accent:  T.accent,        // gold fills, dots, borders
  gold:    T.accentText,    // gold as TEXT (AA-safe; the bright accent is not)
  muted:   T.muted,
  subtle:  T.mutedLt,       // secondary text — recessive but fully legible
  success: T.success,
  warn:    T.warn,
  error:   T.error,
  // Categorical encodings — meaning, not decoration (node/agent/stage types).
  teal:    SEM.teal,
  blue:    SEM.blue,
  cyan:    SEM.cyan,
  violet:  SEM.violet,
  purple:  SEM.purple,
  magenta: SEM.magenta,
  clay:    SEM.clay,
};

/** tone name → hex.
 *
 *  A raw color is passed through untouched. That is deliberate and narrow: some
 *  colors are DATA, not styling — an agent's identity color from the AGENTS
 *  table, a node type from an API payload. A view forwarding one of those is
 *  fine. A view *writing* "#C48808" is not, and `npm run lint:ui` fails on it.
 *
 *  Unknown tone names fall back to muted rather than crashing the render. */
export function toneColor(tone = "default") {
  if (typeof tone === "string" && (tone.startsWith("#") || tone.startsWith("rgb"))) return tone;
  return TONES[tone] ?? TONES.muted;
}

/** Score in 0–100 → tone (healthy ≥80, watch 60–80, degraded <60). */
export function scoreTone(v) {
  if (v == null) return "muted";
  return v >= 80 ? "success" : v >= 60 ? "warn" : "error";
}

/** Probability in 0–1 → tone (healthy ≥0.80, watch 0.65–0.80, degraded <0.65). */
export function probTone(v) {
  if (v == null) return "muted";
  return v >= 0.80 ? "success" : v >= 0.65 ? "warn" : "error";
}

// Back-compat: the observability tabs still ask for a raw color for a score.
export const hScore = (v) => toneColor(scoreTone(v));
export const hProb  = (v) => toneColor(probTone(v));
