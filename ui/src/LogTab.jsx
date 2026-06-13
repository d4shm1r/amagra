export default function LogTab({ sessionLog, onClear }) {
  return (
    <div style={{ animation: "fadeIn .2s" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <p style={{ color: "#9A7A60", fontSize: 13, margin: 0 }}>Agent activity log — saved between sessions.</p>
        <button onClick={onClear} style={{ background: "#F9E7E1", border: "2px solid #B4231866", color: "#B42318", padding: "6px 14px", borderRadius: 4, fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
          Clear
        </button>
      </div>

      {sessionLog.length === 0 ? (
        <div style={{ textAlign: "center", color: "#9A7A60", fontSize: 14, padding: "50px 0" }}>
          No events yet — send a chat message to see activity here.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {[...sessionLog].reverse().map((e, i) => (
            <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "8px 14px", background: "#FAF7F2", border: `1.5px solid ${e.color}33`, borderRadius: 4, borderLeft: `4px solid ${e.color}` }}>
              <span style={{ fontSize: 11, color: "#9A7A60", fontFamily: "monospace", minWidth: 72 }}>{e.ts}</span>
              <span style={{ fontSize: 13, color: e.color, fontWeight: 600 }}>{e.msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
