import { CONTROL } from "./controlStyle";

export function TextInput({ value, onChange, placeholder, type = "text", disabled = false, onKeyDown, autoFocus }) {
  return (
    <input
      type={type}
      value={value}
      disabled={disabled}
      autoFocus={autoFocus}
      placeholder={placeholder}
      onKeyDown={onKeyDown}
      onChange={e => onChange(e.target.value)}
      style={CONTROL}
    />
  );
}
