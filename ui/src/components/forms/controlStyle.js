// controlStyle.js — the one input recipe.
// Every field in the app (text, search, textarea, select) is this surface:
// cream fill, hairline border, gold focus. Shared here so a new control can
// never be born slightly-different from the ones already in the app.
import { T, TYPE, RADIUS } from "@/styles/theme";

export const CONTROL = {
  ...TYPE.small,
  background: T.surface,
  border: `1px solid ${T.border}`,
  borderRadius: RADIUS.md,
  padding: "7px 12px",
  color: T.text,
  fontFamily: "inherit",
  outline: "none",
  width: "100%",
};

/** Pill-shaped variant — search fields and other "chip" controls. */
export const CONTROL_PILL = {
  ...CONTROL,
  borderRadius: 20,
  padding: "7px 16px",
};
