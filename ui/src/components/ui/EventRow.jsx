// EventRow.jsx — one line in an event feed, and the glyph/tone table behind it.
// The event vocabulary is meaning, not decoration: every type maps to a tone in
// tone.js, never to a hex written at a call site.
import { T, TYPE } from "@/styles/theme";
import { toneColor } from "./tone";

const EVENT_META = {
  "plan.created":           { icon: "◈", tone: "accent" },
  "plan.step.started":      { icon: "▷", tone: "accent" },
  "plan.step.completed":    { icon: "✓", tone: "success" },
  "plan.step.failed":       { icon: "✗", tone: "error" },
  "plan.step.retry":        { icon: "↺", tone: "warn" },
  "plan.aborted":           { icon: "⊗", tone: "error" },
  "plan.completed":         { icon: "◆", tone: "success" },
  "query.received":         { icon: "→", tone: "gold" },
  "agent.selected":         { icon: "◉", tone: "gold" },
  "response.generated":     { icon: "◎", tone: "success" },
  "step.verified.pass":     { icon: "✓", tone: "success" },
  "step.verified.fail":     { icon: "✗", tone: "error" },
  "risk.computed":          { icon: "⚑", tone: "warn" },
  "reflection.triggered":   { icon: "⌇", tone: "warn" },
  "reflection.completed":   { icon: "⌇", tone: "success" },
  "memory.retrieved":       { icon: "◎", tone: "blue" },
  "memory.stored":          { icon: "◎", tone: "blue" },
  "contradiction.detected": { icon: "⊗", tone: "error" },
  "routing.weight.changed": { icon: "△", tone: "gold" },
  "session.started":        { icon: "◦", tone: "muted" },
  "session.ended":          { icon: "◦", tone: "muted" },
};

/** type → { icon, color }. Kept returning a color for the existing call sites
 *  that paint a glyph themselves (timelines, graphs). */
export function eventMeta(type) {
  const m = EVENT_META[type] || { icon: "·", tone: "muted" };
  return { icon: m.icon, tone: m.tone, color: toneColor(m.tone) };
}

export function EventRow({ event, compact = false }) {
  const meta  = eventMeta(event.event_type || event.type || "");
  const ts    = event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString() : "";
  const label = (event.event_type || event.type || "event").replace(/\./g, " ");

  if (compact) {
    return (
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "3px 0",
                    borderBottom: `1px solid ${T.border}20` }}>
        <span style={{ color: meta.color, fontSize: 12, minWidth: 16 }}>{meta.icon}</span>
        <span style={{ ...TYPE.micro, color: T.muted, minWidth: 44 }}>{ts}</span>
        <span style={{ ...TYPE.caption, color: T.text, flex: 1 }}>{label}</span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0",
                  borderBottom: `1px solid ${T.border}` }}>
      <span style={{ color: meta.color, fontSize: 14, minWidth: 18, paddingTop: 1 }}>{meta.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
          <span style={{ ...TYPE.caption, color: T.text, fontWeight: 500 }}>{label}</span>
          <span style={{ ...TYPE.micro, color: T.muted }}>{ts}</span>
        </div>
        {event.payload && Object.keys(event.payload).length > 0 && (
          <div style={{ ...TYPE.micro, color: T.muted, marginTop: 2 }}>
            {Object.entries(event.payload)
              .filter(([k]) => !["session_id", "run_id"].includes(k))
              .slice(0, 4)
              .map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed ? v.toFixed(2) : v : v}`)
              .join(" · ")}
          </div>
        )}
      </div>
    </div>
  );
}
