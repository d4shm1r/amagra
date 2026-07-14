// FileEmblem.jsx — the little dog-eared paper card that stands in for a
// document. A shape, therefore it lives in the kit: the Library composes it,
// it does not draw it.
import { T, TYPE } from "@/styles/theme";
import { toneColor } from "./tone";

export function FileEmblem({ ext = "", tone = "muted" }) {
  return (
    <div style={{
      width: 46, height: 58, borderRadius: 8, flexShrink: 0, position: "relative",
      background: `linear-gradient(160deg, ${T.surface}, ${T.surface2})`,
      border: `1px solid ${T.border}`,
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.7), 0 1px 2px rgba(72,52,28,0.08)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <span style={{ ...TYPE.micro, fontWeight: 800, letterSpacing: "0.05em", color: toneColor(tone) }}>
        {ext.toUpperCase().slice(0, 4)}
      </span>
      {/* the dog-ear */}
      <span style={{
        position: "absolute", top: 0, right: 0, width: 12, height: 12,
        background: T.surface2,
        borderLeft: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}`,
        borderRadius: "0 8px 0 6px",
      }} />
    </div>
  );
}
