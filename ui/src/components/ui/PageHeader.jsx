// PageHeader.jsx — the hero every tab opens with.
//
// One header rule for the whole app: an elegant gold serif title, then the
// description, then any actions — each on its own line.
//
// The header is FULL-BLEED: it breaks out of the centered <Column>, spans the
// whole window, and pins flush to the very top of the tab's scroll surface —
// no strip of canvas above it, no gap. Its own words stay aligned to the body
// column underneath, so the page's measure is unchanged.
//
// It must be full-bleed rather than sit inside the column: a column-width band
// of canvas painted over a canvas background shows its own left and right edges,
// which read as a faint rectangle floating behind the title.
//
// The bottom edge DISSOLVES rather than cutting off — the same treatment the
// launcher gives its scroll surface, so the menu and the tabs fade their edges
// identically. The band is opaque under the title and pills; only its last
// HEADER_FADE px thin to nothing, so content scrolling underneath melts away
// instead of hitting a hard line.
import { T, LUX, TYPE, LAYOUT, Z } from "@/styles/theme";

// How far the band's bottom edge dissolves. Matches the launcher's scroll mask
// (linear-gradient to transparent over ~30px), so the menu and the tabs fade
// their edges identically.
const HEADER_FADE = 30;

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
        <div style={{ ...TYPE.small, color: T.muted, marginTop: 8, maxWidth: 640, lineHeight: 1.6, userSelect: "none",
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
      position: "sticky",
      // Stick at -gutterY, NOT 0. The scroll surface has `padding-top: gutterY`,
      // so its sticky viewport top sits gutterY below the container's real top.
      // `top: 0` would pin the band THERE — leaving a gutterY strip of canvas
      // above it that page content scrolls up through. Offsetting the stick point
      // by the same gutter cancels the padding, so the band pins to the true top
      // (0 gap) both at rest and while scrolling. It pairs with the marginTop
      // below, which keeps the at-rest position flush too.
      top: -LAYOUT.gutterY, zIndex: Z.header,
      // Full-bleed: escape the centered column and span the viewport. The scroll
      // surface sets overflowX: hidden, so this never makes a horizontal bar.
      width: "100vw", marginLeft: "calc(50% - 50vw)",
      // Pull up through the scroll surface's whole top gutter so the band starts
      // at y=0 with no strip of canvas above it. The gutter is re-added as the
      // band's own padding, so the title keeps its breathing room.
      marginTop: -LAYOUT.gutterY, marginBottom: 0,
      // Bottom padding carries the dissolve zone (HEADER_FADE) plus the normal
      // gap to the content below, so the fade lands under the pills, never on
      // them.
      padding: `${LAYOUT.gutterY}px ${LAYOUT.gutter}px ${HEADER_FADE + 14}px`,
      // The dissolve — the launcher's treatment (a mask that lets content melt
      // away at the edge instead of being cut off), applied to the band's own
      // canvas. Opaque under the title and pills; over the last HEADER_FADE px it
      // thins to nothing, so content scrolling underneath fades out rather than
      // hitting a hard line.
      background: `linear-gradient(180deg, ${T.bg} 0%, ${T.bg} calc(100% - ${HEADER_FADE}px), transparent 100%)`,
      ...(center ? { textAlign: "center" } : null),
    }}>
      {/* The band is full width; the words inside still line up with the body
          column, so nothing about the page's measure changes. */}
      <div style={{ maxWidth: LAYOUT.content, margin: "0 auto" }}>
        {content}
      </div>
    </div>
  );
}
