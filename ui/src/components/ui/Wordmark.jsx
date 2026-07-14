// Wordmark.jsx — the AMAGRA identity: serif, wide-tracked, gold gradient.
// Identity is not content, so it lives in the kit and is written once.
import { LUX, TYPE, FONT_DISPLAY } from "@/styles/theme";

export function Wordmark({ size = 28, children = "AMAGRA" }) {
  return (
    <h2 style={{
      ...TYPE.title, margin: 0, fontSize: size, fontFamily: FONT_DISPLAY,
      letterSpacing: "0.08em", userSelect: "none",
      ...LUX.goldText, display: "inline-block",
    }}>
      {children}
    </h2>
  );
}
