// Disclosure.jsx — the expandable row.
//
// The single most-repeated pattern in the app: a Well you click to reveal more
// (agents, metrics, how-tos, architecture steps, docs). It was hand-rolled five
// times in the Guide alone. Now it exists once.
import { T, TYPE, SPACE, RADIUS } from "@/styles/theme";
import { Well } from "./Card";
import { Row } from "./Layout";

/** One expandable row.
 *  `title`    — the always-visible label
 *  `subtitle` — a second always-visible line beneath it (an agent's focus)
 *  `meta`     — right-aligned hint ("6 tips", "3.2 KB", a formula)
 *  `open` / `onToggle` — controlled, so a list can keep single-open behaviour */
export function Disclosure({ title, subtitle, icon, meta, open = false, onToggle, children }) {
  return (
    <Well interactive active={open} onClick={onToggle}>
      <Row gap="md" align={subtitle ? "flex-start" : "center"}>
        {icon && <span style={{ ...TYPE.subtitle, color: T.accent }}>{icon}</span>}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ ...TYPE.small, fontWeight: 700, color: T.text }}>{title}</div>
          {subtitle && (
            <div style={{ ...TYPE.micro, color: T.muted, marginTop: 2, lineHeight: 1.5 }}>{subtitle}</div>
          )}
        </div>
        {meta}
        <span style={{ ...TYPE.micro, color: T.accent, opacity: 0.7 }}>{open ? "▲" : "▼"}</span>
      </Row>
      {open && <div style={{ marginTop: SPACE[3] }} onClick={e => e.stopPropagation()}>{children}</div>}
    </Well>
  );
}

/** The revealed body — a raised inset inside the Well, so the opened content
 *  reads as a layer above the row rather than more of the same surface. */
export function DisclosureBody({ children }) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: RADIUS.md - 2, padding: `${SPACE[3]}px ${SPACE[3]}px`,
      ...TYPE.caption, color: T.text, lineHeight: 1.7,
    }}>
      {children}
    </div>
  );
}

/** A bullet/numbered list inside a DisclosureBody. The app's only list style. */
export function BulletList({ items, ordered = false }) {
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag style={{ margin: 0, padding: `0 0 0 ${SPACE[5]}px` }}>
      {items.map((item, i) => (
        <li key={i} style={{ ...TYPE.caption, color: T.text, lineHeight: 1.8, marginBottom: 2 }}>
          {item}
        </li>
      ))}
    </Tag>
  );
}
