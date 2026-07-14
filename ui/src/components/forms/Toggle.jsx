import { T, DUR, EASE } from "@/styles/theme";

/** The gold switch. On = gold fill; off = warm cream. Never grey, never black. */
export function Toggle({ checked, onChange, label }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      style={{
        width: 44, height: 25, borderRadius: 999, padding: 0, position: "relative", cursor: "pointer",
        background: checked ? T.accent : T.border,
        border: `1px solid ${checked ? T.accent : T.border}`,
        boxShadow: `inset 0 1px 2px rgba(120,86,20,${checked ? 0.25 : 0.14})`,
        transition: `background ${DUR.base} ${EASE.out}, border-color ${DUR.base} ${EASE.out}`,
      }}
    >
      <span style={{
        position: "absolute", top: 2, left: checked ? 21 : 2, width: 19, height: 19, borderRadius: "50%",
        background: "#fff", border: "1px solid rgba(120,86,20,0.30)",
        boxShadow: "0 1px 4px rgba(72,52,28,0.32)",
        transition: `left ${DUR.base} ${EASE.out}`,
      }} />
    </button>
  );
}
