import { CONTROL } from "./controlStyle";

/** options: [{ value, label }] or plain strings. */
export function Select({ value, onChange, options, disabled = false }) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={e => onChange(e.target.value)}
      className="agent-sel"
      style={{ ...CONTROL, cursor: "pointer" }}
    >
      {options.map(o => {
        const val = typeof o === "string" ? o : o.value;
        const lab = typeof o === "string" ? o : o.label;
        return <option key={val} value={val}>{lab}</option>;
      })}
    </select>
  );
}
