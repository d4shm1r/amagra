// KeyChord.jsx — "Ctrl+Shift+D" rendered as discrete gold key caps joined by a
// hair "+". The app's only representation of a keyboard binding.
import { T, LUX, TYPE, RADIUS, FONT_MONO } from "@/styles/theme";

export function KeyChord({ combo }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 3, flexShrink: 0 }}>
      {combo.split("+").map((k, i) => (
        <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
          {i > 0 && <span style={{ ...TYPE.micro, fontSize: 9, color: T.muted }}>+</span>}
          <kbd style={{
            ...TYPE.micro, fontFamily: FONT_MONO, fontWeight: 700, lineHeight: 1,
            color: T.accentText, background: `${T.accent}12`,
            border: `1px solid ${T.accent}38`, borderRadius: RADIUS.sm - 3,
            padding: "3px 6px", whiteSpace: "nowrap", boxShadow: LUX.shadowSm,
          }}>
            {k}
          </kbd>
        </span>
      ))}
    </span>
  );
}
