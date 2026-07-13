import { T, TYPE, EASE, DUR, RADIUS, FONT_MONO } from "./theme";
import { PageHeader } from "./ObsShared";

export default function LogTab({ sessionLog, onClear }) {
  return (
    <div style={{ animation: `fadeIn ${DUR.base} ${EASE.out}` }}>
      <PageHeader
        center
        title="Session Log"
        subtitle="Agent activity from this session — kept on this device between sessions."
      >
        <span style={{ ...TYPE.caption, color: T.muted }}>
          {sessionLog.length} event{sessionLog.length === 1 ? "" : "s"}
        </span>
        <button onClick={onClear} disabled={sessionLog.length === 0} style={{
          background: "#fff", border: `1px solid ${sessionLog.length ? T.accent : T.border}`,
          color: sessionLog.length ? T.accentText : T.muted,
          padding: "6px 14px", borderRadius: RADIUS.md, fontSize: 11, fontWeight: 600,
          cursor: sessionLog.length ? "pointer" : "default", fontFamily: "inherit",
          opacity: sessionLog.length ? 1 : 0.55,
          transition: `border-color ${DUR.base} ${EASE.out}, color ${DUR.base} ${EASE.out}`,
        }}>
          Clear log
        </button>
      </PageHeader>

      {sessionLog.length === 0 ? (
        <div className="lux-card" style={{ padding: "52px 0", textAlign: "center" }}>
          <div style={{ ...TYPE.small, color: T.muted }}>
            No events yet — send a chat message to see activity here.
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {[...sessionLog].reverse().map((e, i) => (
            <div key={i} className="lux-card" style={{
              display: "flex", gap: 14, alignItems: "center",
              padding: "10px 15px",
              // Card chrome from the shared recipe; the status rule stays.
              borderLeft: `3px solid ${e.color}`,
            }}>
              <span style={{ ...TYPE.caption, fontFamily: FONT_MONO, color: T.muted,
                             minWidth: 76, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                {e.ts}
              </span>
              <span style={{ ...TYPE.small, color: e.color, fontWeight: 600 }}>{e.msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
