import { useRef } from "react";
import { Button } from "../ui/Button";

/** A button that opens the OS file dialog. Hides the <input> plumbing — the
 *  caller only receives the files. */
export function FilePicker({ onFiles, accept, multiple = true, variant = "ghost", size = "md", children }) {
  const ref = useRef(null);
  return (
    <>
      <Button variant={variant} size={size} onClick={() => ref.current?.click()}>{children}</Button>
      <input
        ref={ref}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={e => { onFiles([...e.target.files]); e.target.value = ""; }}
        style={{ display: "none" }}
      />
    </>
  );
}
