// PageHeader.jsx — the hero every tab opens with.
//
// One header rule for the whole app: an elegant gold serif title, then the
// description, then any actions — each on its own line. Pinned to the top of
// the tab's scroll surface so it stays put while content scrolls beneath and
// dissolves into a soft canvas fade at its lower edge.
import { T, LUX, TYPE } from "@/styles/theme";

export function PageHeader({ title, subtitle, children, gold = true, center = false, sticky = true }) {
  return (
    <div style={sticky ? {
      position: "sticky", top: -24, zIndex: 30,
      margin: "-24px 0 6px", padding: "24px 0 22px",
      // Solid canvas behind the whole header; only a fixed 16px tail dissolves,
      // so scrolling content never shows through the title/controls themselves.
      background: `linear-gradient(180deg, ${T.bg} calc(100% - 16px), rgba(240,233,223,0) 100%)`,
      ...(center ? { textAlign: "center" } : null),
    } : {
      // `sticky={false}` for headers rendered mid-page (e.g. Diagnostics
      // sections below their segmented nav), where the pinned treatment's
      // negative margin would overlap the content above.
      marginBottom: 20,
      ...(center ? { textAlign: "center" } : null),
    }}>
      <h1 style={{
        // Unselectable: the hero is identity, not content.
        ...TYPE.display, margin: 0, userSelect: "none",
        ...(gold ? { ...LUX.goldText, display: "inline-block" } : { color: T.text }),
      }}>
        {title}
      </h1>
      {subtitle && (
        <div style={{ ...TYPE.caption, color: T.muted, marginTop: 6, maxWidth: 680, userSelect: "none",
                      ...(center ? { marginLeft: "auto", marginRight: "auto" } : null) }}>
          {subtitle}
        </div>
      )}
      {children && (
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginTop: 13,
                      ...(center ? { justifyContent: "center" } : null) }}>
          {children}
        </div>
      )}
    </div>
  );
}
