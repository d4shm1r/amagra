// Card.jsx — the surfaces.
//
// The app has exactly three container depths and no more:
//   Card    — a raised object on the canvas (the .lux-card recipe)
//   Section — a Card with a gold eyebrow title; every titled panel is one
//   Well    — a recessed surface INSIDE a Section. Never nest a Card in a Card.
//   Tile    — a small labelled readout that lives inside a Well/Grid
import { T, TYPE, SPACE, RADIUS, DUR, EASE } from "@/styles/theme";
import { toneColor } from "./tone";
import { Button } from "./Button";
import { Row, Spacer } from "./Layout";

/** A raised object on the canvas. `interactive` earns the hover lift (use it
 *  for discrete things you can click, never for static containers).
 *  `rule` paints a status edge down the left side — the one place a card is
 *  allowed to carry a semantic color. */
export function Card({ interactive = false, accent = false, rule, pad = "lg", onClick, children }) {
  const PAD = {
    sm: `${SPACE[3]}px ${SPACE[4]}px`,
    md: `${SPACE[4]}px ${SPACE[5]}px`,
    lg: `${SPACE[5]}px ${SPACE[6]}px`,
  }[pad];
  return (
    <div
      className={`lux-card${interactive ? " lux-card-i" : ""}`}
      onClick={onClick}
      style={{
        padding: PAD,
        ...(onClick ? { cursor: "pointer" } : null),
        // `accent` holds the gold edge on permanently — for the one call-out per
        // page that must read as primary. Everything else earns it on hover.
        ...(accent ? { borderColor: `${T.accent}44` } : null),
        ...(rule ? { borderLeft: `3px solid ${toneColor(rule)}` } : null),
      }}
    >
      {children}
    </div>
  );
}

/** THE titled panel — gold eyebrow, optional hint, optional right-aligned
 *  action, on the app-wide card chrome. `onMore` is sugar for "View all →". */
export function Section({ title, icon, hint, action, onMore, moreLabel, children, style = {} }) {
  const more = onMore && (
    <Button variant="quiet" size="sm" onClick={onMore}>{moreLabel || "View all"} →</Button>
  );
  return (
    <div className="lux-card" style={{ padding: "16px 20px", ...style }}>
      {(title || action || more) && (
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 14 }}>
          {title && (
            <div style={{ ...TYPE.eyebrow, color: T.accentText }}>
              {icon && <span style={{ marginRight: 6, opacity: 0.7 }}>{icon}</span>}
              {title}
            </div>
          )}
          {hint && (
            <div style={{ ...TYPE.caption, color: T.muted, flex: 1, minWidth: 0 }}>{hint}</div>
          )}
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>{action}{more}</div>
        </div>
      )}
      {children}
    </div>
  );
}

/** Back-compat alias — the observability tabs import ObsPanel. Same thing. */
export const ObsPanel = Section;

/** The recessed surface rows and readouts sit on inside a Section. */
export function Well({ tone, interactive = false, active = false, onClick, style = {}, children }) {
  const edge = active ? `${T.accent}66` : tone ? `${toneColor(tone)}33` : T.border;
  return (
    <div
      onClick={onClick}
      className={interactive ? "hoverable" : undefined}
      style={{
        background: T.surface2, border: `1px solid ${edge}`,
        borderRadius: RADIUS.lg - 2, padding: `${SPACE[3]}px ${SPACE[4]}px`,
        ...(onClick ? { cursor: "pointer" } : null),
        transition: `border-color ${DUR.base} ${EASE.out}, background ${DUR.base} ${EASE.out}`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** A labelled readout — the small "label above, value below" cell used in the
 *  quick-start grid, the tech-stack columns, and every key/value wall. */
export function Tile({ label, value, mono = true, tone = "gold", children }) {
  return (
    <div style={{
      background: T.surface2, border: `1px solid ${T.border}`,
      borderRadius: RADIUS.md + 1, padding: `${SPACE[2]}px ${SPACE[3]}px`,
    }}>
      <div style={{ ...TYPE.micro, color: T.muted, marginBottom: 3 }}>{label}</div>
      {value != null && (
        <div style={{
          ...TYPE.caption, color: toneColor(tone),
          ...(mono ? { fontFamily: "monospace" } : null),
        }}>
          {value}
        </div>
      )}
      {children}
    </div>
  );
}

/** A Tile whose body is a list of plain strings (the tech-stack columns). */
export function ListTile({ label, items }) {
  return (
    <Tile label={<span style={{ ...TYPE.eyebrow, color: T.muted }}>{label}</span>}>
      {items.map(item => (
        <div key={item} style={{
          ...TYPE.caption, color: T.text, padding: "3px 0",
          borderBottom: `1px solid ${T.border}55`,
        }}>
          {item}
        </div>
      ))}
    </Tile>
  );
}

/** Header strip for a Card the kit doesn't otherwise title (title + actions). */
export function CardHeader({ title, meta, children }) {
  return (
    <Row gap="sm">
      <div style={{ ...TYPE.subtitle, color: T.text }}>{title}</div>
      {meta && <div style={{ ...TYPE.caption, color: T.muted }}>{meta}</div>}
      <Spacer />
      {children}
    </Row>
  );
}
