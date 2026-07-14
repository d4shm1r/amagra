import { CONTROL_PILL } from "./controlStyle";

/** The pill search field carried in a PageHeader. */
export function SearchInput({ value, onChange, placeholder = "Search…", width = 230 }) {
  return (
    <input
      value={value}
      placeholder={placeholder}
      onChange={e => onChange(e.target.value)}
      style={{ ...CONTROL_PILL, width }}
    />
  );
}
