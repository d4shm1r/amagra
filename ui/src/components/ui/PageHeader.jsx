// PageHeader.jsx — the hero every tab opens with.
//
// One header rule for the whole app: an elegant gold serif title, then the
// description, then any actions — each on its own line.
//
// The header is FULL-BLEED: it breaks out of the centered <Column> and spans the
// whole window, pinned flush to the top of the tab's scroll surface. Its own
// content stays aligned to the body column underneath. Two reasons it works this
// way rather than sitting inside the column:
//
//   1. A column-width band of canvas painted over a canvas background shows its
//      own left and right edges — a faint rectangle floating behind the title.
//   2. The old fade-to-transparent tail did the same at the bottom: a soft
//      gradient seam across the page. The background is now a flat, opaque
//      T.bg, so content simply disappears under a clean edge as it scrolls.
import { T, LUX, TYPE, LAYOUT } from "@/styles/theme";

export function PageHeader({ title, subtitle, children, gold = true, center = false, sticky = true }) {
  const content = (
    <>
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
    </>
  );

  // `sticky={false}` for headers rendered mid-page (e.g. the Diagnostics sections
  // below their segmented nav), where the pinned treatment would overlap what's
  // above it.
  if (!sticky) {
    return (
      <div style={{ marginBottom: 20, ...(center ? { textAlign: "center" } : null) }}>
        {content}
      </div>
    );
  }

  return (
    <div style={{
      position: "sticky", top: 0, zIndex: 30,
      // Escape the centered column and span the viewport. The scroll surface sets
      // overflowX: hidden, so this never produces a horizontal scrollbar.
      width: "100vw", marginLeft: "calc(50% - 50vw)",
      // Pull up through the scroll surface's top padding so the band reaches the
      // very top edge, and re-add that padding inside.
      marginTop: -LAYOUT.gutterY, marginBottom: 6,
      padding: `${LAYOUT.gutterY}px ${LAYOUT.gutter}px 22px`,
      background: T.bg,   // flat and opaque — no gradient, no seam
      ...(center ? { textAlign: "center" } : null),
    }}>
      {/* The band is full width; the words inside still line up with the body. */}
      <div style={{ maxWidth: LAYOUT.content, margin: "0 auto" }}>
        {content}
      </div>
    </div>
  );
}
