import { CONTROL } from "./controlStyle";

export function TextArea({ value, onChange, placeholder, rows = 4, disabled = false, mono = false }) {
  return (
    <textarea
      value={value}
      rows={rows}
      disabled={disabled}
      placeholder={placeholder}
      onChange={e => onChange(e.target.value)}
      style={{
        ...CONTROL,
        resize: "vertical",
        lineHeight: 1.6,
        ...(mono ? { fontFamily: "'JetBrains Mono', monospace" } : null),
      }}
    />
  );
}
