import { T, TYPE, SPACE } from "@/styles/theme";

/** A settings row: label + hint on the left, the control on the right.
 *  Consecutive Fields divide themselves with a hairline (.set-row in
 *  styles/index.css) — the caller never draws the separator. */
export function Field({ label, hint, children }) {
  return (
    <div className="set-row" style={{
      display: "flex", alignItems: "center", gap: SPACE[4],
      padding: `${SPACE[3]}px 0`,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ ...TYPE.small, color: T.text }}>{label}</div>
        {hint && <div style={{ ...TYPE.caption, color: T.muted, marginTop: 2 }}>{hint}</div>}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  );
}
