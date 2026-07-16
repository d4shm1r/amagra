// DropZone.jsx — drag-and-drop onto a whole surface.
// Owns the dragenter/leave bookkeeping (the "did I leave for a child element?"
// trap) and the overlay, so a tab only says what to do with the files.
import { useState } from "react";
import { T, TYPE, FONT_DISPLAY } from "@/styles/theme";

export function DropZone({ onDrop, label = "Drop to add", children }) {
  const [over, setOver] = useState(false);
  return (
    <div
      style={{ position: "relative" }}
      onDragOver={e => { e.preventDefault(); setOver(true); }}
      onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(false); }}
      onDrop={e => { e.preventDefault(); setOver(false); onDrop([...e.dataTransfer.files]); }}
    >
      {children}
      {/* The overlay's zIndex below is LOCAL, not a layer from Z: it is absolute
          inside the relative wrapper above, so it only has to out-stack its own
          siblings. Do not "fix" it into the global scale — it is not competing
          with the header or the launcher, it is competing with the card it
          covers. */}
      {over && (
        <div style={{
          position: "absolute", inset: -12, borderRadius: 18, zIndex: 50,
          border: `2px dashed ${T.accent}`, background: `${T.accent}0D`,
          display: "flex", alignItems: "center", justifyContent: "center",
          pointerEvents: "none",
        }}>
          <span style={{ ...TYPE.title, fontFamily: FONT_DISPLAY, color: T.accent2 }}>{label}</span>
        </div>
      )}
    </div>
  );
}
