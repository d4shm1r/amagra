// Menu.jsx — the floating popover menu (the ⋯ affordance on a card).
// Owns its own outside-click dismissal, so no tab re-implements that listener.
import { useEffect, useRef, useState } from "react";
import { T, LUX, TYPE, SPACE, RADIUS } from "@/styles/theme";
import { toneColor } from "./tone";
import { IconButton } from "./Button";
import { Divider } from "./Layout";

/** A ⋯ trigger plus the popover it opens. `align="up"` drops it upward, for
 *  triggers that sit near the bottom of a card. */
export function Menu({ label = "⋯", title = "More", align = "up", width = 168, children }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <IconButton onClick={() => setOpen(o => !o)} title={title}>{label}</IconButton>
      {open && (
        <div style={{
          position: "absolute", right: 0, zIndex: 100, minWidth: width,
          ...(align === "up" ? { bottom: "calc(100% + 6px)" } : { top: "calc(100% + 6px)" }),
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: RADIUS.md + 1, boxShadow: LUX.shadowMd, padding: SPACE[1] + 2,
        }}>
          {/* Any action closes the menu — the caller never manages that. */}
          <div onClick={() => setOpen(false)}>{children}</div>
        </div>
      )}
    </div>
  );
}

/** A row in a Menu. */
export function MenuItem({ onClick, tone = "default", italic = false, children }) {
  return (
    <button onClick={onClick} className="nav-btn" style={{
      display: "block", width: "100%", textAlign: "left",
      padding: `${SPACE[1] + 1}px ${SPACE[2] + 2}px`, border: "none", borderRadius: RADIUS.sm,
      background: "transparent", color: toneColor(tone), cursor: "pointer",
      ...TYPE.caption, fontFamily: "inherit",
      ...(italic ? { fontStyle: "italic" } : null),
    }}>
      {children}
    </button>
  );
}

/** A section label inside a Menu ("Move to"). */
export function MenuLabel({ children }) {
  return (
    <div style={{ ...TYPE.eyebrow, fontSize: 9, color: T.muted, padding: "3px 10px 5px" }}>
      {children}
    </div>
  );
}

export { Divider as MenuDivider };
