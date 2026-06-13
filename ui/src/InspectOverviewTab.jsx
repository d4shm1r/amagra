import { useEffect, useState } from "react";
import { T } from "./theme";

const API = "http://localhost:8000";

// Level-1 Inspect: the calm summary. Key numbers, recent decisions,
// recent work — everything else lives one level deeper (Advanced /
// Developer groups in the view selector). Hierarchy comes from scale
// and spacing; gold is reserved for the single live-activity signal.

function timeAgo(ts) {
  if (!ts) return "";
  const s = Math.max(0, (Date.now() / 1000) - ts);
  if (s < 60)    return `${Math.round(s)}s ago`;
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function Stat({ value, label, live }) {
  return (
    <div className="lux-card lux-card-i" style={{ flex: 1, padding: "18px 22px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 26, fontWeight: 700, color: T.text, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>
          {value ?? "—"}
        </span>
        {live && (
          <span style={{
            width: 7, height: 7, borderRadius: "50%", background: T.accent,
            boxShadow: `0 0 5px ${T.accent}88`, animation: "meshPulse 1.1s ease-in-out infinite",
          }} />
        )}
      </div>
      <div style={{ fontSize: 10.5, fontWeight: 600, color: T.muted, letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 5 }}>
        {label}
      </div>
    </div>
  );
}

function Section({ title, onMore, moreLabel, children }) {
  return (
    <div className="lux-card" style={{ padding: "16px 20px", minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: T.mutedLt, letterSpacing: "0.1em", textTransform: "uppercase", flex: 1 }}>
          {title}
        </span>
        {onMore && (
          <button onClick={onMore} className="nav-btn" style={{
            border: "none", background: "transparent", cursor: "pointer",
            fontSize: 11, fontWeight: 600, color: T.muted, fontFamily: "inherit",
            padding: "2px 8px", borderRadius: 5,
          }}>
            {moreLabel || "View all"} →
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

const Empty = ({ children }) => (
  <div style={{ fontSize: 12.5, color: T.muted, padding: "14px 0 8px", fontStyle: "italic" }}>{children}</div>
);

export default function InspectOverviewTab({ onNav }) {
  const [status,    setStatus]    = useState(null);
  const [decisions, setDecisions] = useState(null);
  const [decStats,  setDecStats]  = useState(null);
  const [runs,      setRuns]      = useState(null);
  const [agents,    setAgents]    = useState([]);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetch(`${API}/status`).then(r => r.ok ? r.json() : null)
        .then(d => alive && d && setStatus(d)).catch(() => {});
      fetch(`${API}/decisions?limit=6`).then(r => r.ok ? r.json() : null)
        .then(d => { if (alive && d) { setDecisions(d.decisions || []); setDecStats(d.stats || null); } }).catch(() => {});
      fetch(`${API}/runs?limit=6`).then(r => r.ok ? r.json() : null)
        .then(d => alive && d && setRuns(d.runs || [])).catch(() => {});
      fetch(`${API}/agents/status`).then(r => r.ok ? r.json() : null)
        .then(d => alive && d?.agents && setAgents(d.agents)).catch(() => {});
    };
    load();
    const id = setInterval(load, 20000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const working = agents.filter(a => a.status === "running").length;

  return (
    <div>

      {/* ── Key numbers ── */}
      <div style={{ display: "flex", gap: 14, marginBottom: 14 }}>
        <Stat value={working || (agents.length ? 0 : "—")} label="Working now" live={working > 0} />
        <Stat value={status?.tasks?.pending}               label="Tasks pending" />
        <Stat value={decStats?.total}                      label="Decisions" />
        <Stat value={status?.memories}                     label="Memories" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>

        {/* ── Recent decisions ── */}
        <Section title="Recent decisions" onMore={() => onNav("brain")}>
          {decisions === null ? <Empty>Loading…</Empty>
          : decisions.length === 0 ? <Empty>No decisions yet — ask something in Chat.</Empty>
          : decisions.map((d, i) => (
            <div key={d.id ?? i} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "8px 0", borderTop: i ? `1px solid ${T.border}55` : "none",
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {d.task || "—"}
                </div>
                <div style={{ fontSize: 10.5, color: T.muted, marginTop: 2, textTransform: "capitalize" }}>
                  {(d.final_agent || d.brain_agent || "").replace(/_/g, " ")}
                  {d.conflict ? " · conflict" : ""}
                  {d.timestamp ? ` · ${timeAgo(d.timestamp)}` : ""}
                </div>
              </div>
              {typeof d.confidence === "number" && (
                <span style={{ fontSize: 11.5, fontWeight: 700, color: T.mutedLt, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
                  {Math.round(d.confidence * 100)}%
                </span>
              )}
            </div>
          ))}
        </Section>

        {/* ── Recent work ── */}
        <Section title="Recent work" onMore={() => onNav("runs")}>
          {runs === null ? <Empty>Loading…</Empty>
          : runs.length === 0 ? <Empty>Nothing has run yet.</Empty>
          : runs.map((r, i) => (
            <div key={r.run_id ?? i} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "8px 0", borderTop: i ? `1px solid ${T.border}55` : "none",
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                background: r.status === "ok" || r.status === "done" || r.ok ? T.success
                          : r.status === "running" ? T.accent : T.error,
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {r.query || "—"}
                </div>
                <div style={{ fontSize: 10.5, color: T.muted, marginTop: 2, textTransform: "capitalize" }}>
                  {(r.agent || "").replace(/_/g, " ")}
                </div>
              </div>
              {typeof r.duration_ms === "number" && (
                <span style={{ fontSize: 11, color: T.muted, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
                  {(r.duration_ms / 1000).toFixed(1)}s
                </span>
              )}
            </div>
          ))}
        </Section>
      </div>

      {/* ── Current context ── */}
      <div style={{ marginTop: 14 }}>
        <Section title="Current context">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 28px", padding: "4px 0" }}>
            {[
              ["Model",        status?.model],
              ["GPU",          status?.gpu],
              ["Reflect rate", decStats ? `${Math.round((decStats.reflect_rate || 0) * 100)}%` : null],
              ["Conflicts",    decStats?.conflicts],
              ["Tasks done",   status?.tasks?.done],
              ["Tasks failed", status?.tasks?.failed],
            ].map(([k, v]) => (
              <div key={k} style={{ fontSize: 12 }}>
                <span style={{ color: T.muted }}>{k}&ensp;</span>
                <span style={{ color: T.text, fontWeight: 600 }}>{v ?? "—"}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
