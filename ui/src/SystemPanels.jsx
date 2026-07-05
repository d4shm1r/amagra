// ── SystemPanels ──────────────────────────────────────────────────────────────
// Live panels rehomed from the retired Progress tab (v1.7.1 menu declutter).
//   • MemoryAdminPanel — prune / consolidate / export actions + the "at-risk"
//     list. Lives inside the Memory surface (MemoryBrowserTab already renders the
//     stats display, so this adds only the *actions* it was missing).
//   • FeedbackLoopPanel — 👍/👎 rating rollup by agent. Lives as a Diagnostics
//     section under Cognition.
// Each is self-contained (owns its own fetches) so it can drop into any tab.
import { useState, useEffect, useCallback } from "react";
import { API } from "./api";
import { T } from "./theme";

function SectionHead({ title }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 700, color: T.muted, letterSpacing: "0.1em",
                  textTransform: "uppercase", marginBottom: 12 }}>
      {title}
    </div>
  );
}

function StatCard({ label, value, color, sub }) {
  return (
    <div style={{ background: T.bg, borderRadius: 4, padding: "12px 16px", border: `1px solid ${color}22` }}>
      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "monospace" }}>{value}</div>
      <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

// ── Memory admin: prune / consolidate / export + at-risk ──────────────────────
// `stats` is the /memory/stats object the host tab already fetched; `onChanged`
// lets the host refresh its own view after a destructive action.
export function MemoryAdminPanel({ stats, onChanged }) {
  const [atRisk,            setAtRisk]            = useState([]);
  const [atRiskOpen,        setAtRiskOpen]        = useState(false);
  const [pruning,           setPruning]           = useState(false);
  const [pruneResult,       setPruneResult]       = useState(null);
  const [consolidating,     setConsolidating]     = useState(false);
  const [consolidateResult, setConsolidateResult] = useState(null);

  const loadAtRisk = useCallback(() => {
    fetch(`${API}/memory/at-risk?n=20`).then(r => r.json())
      .then(d => setAtRisk(d.at_risk || [])).catch(() => {});
  }, []);
  useEffect(() => { loadAtRisk(); }, [loadAtRisk]);

  const prunable = stats?.prune_candidates ?? 0;

  const runPrune = async () => {
    setPruning(true); setPruneResult(null);
    try {
      const d = await fetch(`${API}/memory/prune`, { method: "POST" }).then(r => r.json());
      setPruneResult(d); loadAtRisk(); onChanged?.();
    } catch { setPruneResult({ error: "Request failed" }); }
    setPruning(false);
  };

  const runConsolidate = async () => {
    setConsolidating(true); setConsolidateResult(null);
    try {
      const d = await fetch(`${API}/memory/consolidate`, { method: "POST" }).then(r => r.json());
      setConsolidateResult(d); loadAtRisk(); onChanged?.();
    } catch { setConsolidateResult({ error: "Request failed" }); }
    setConsolidating(false);
  };

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14,
                  padding: "16px 18px", marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <SectionHead title="Memory Health" />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {[["csv", "memories.csv"], ["json", "memories.json"], ["md", "memories.md"]].map(([fmt, fname]) => (
            <a key={fmt} href={`${API}/memory/export.${fmt}`} download={fname}
              style={{ padding: "4px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700, fontFamily: "inherit", cursor: "pointer", background: "#0F766E18", color: "#0F766E", border: "1px solid #0F766E40", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}>
              ⬇ {fmt.toUpperCase()}
            </a>
          ))}
          <button onClick={runConsolidate} disabled={consolidating}
            style={{ padding: "4px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700, fontFamily: "inherit", cursor: consolidating ? "not-allowed" : "pointer", background: "#1E5A8A18", color: "#1E5A8A", border: "1px solid #1E5A8A40" }}>
            {consolidating ? "Running…" : "⊕ Consolidate"}
          </button>
          <button onClick={runPrune} disabled={pruning || prunable === 0}
            style={{ padding: "4px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700, fontFamily: "inherit", cursor: pruning || prunable === 0 ? "not-allowed" : "pointer", background: prunable > 0 ? "#B4231818" : "#E0D6C4", color: prunable > 0 ? "#B42318" : "#9A7A60", border: `1px solid ${prunable > 0 ? "#B4231840" : "#E0D6C4"}` }}>
            {pruning ? "Pruning…" : `✂ Prune${prunable > 0 ? ` (${prunable})` : ""}`}
          </button>
        </div>
      </div>

      {consolidateResult && (
        <div style={{ marginBottom: 10, padding: "7px 12px", borderRadius: 4, background: consolidateResult.error ? "#F9E7E1" : "#F0EDF6", border: `1px solid ${consolidateResult.error ? "#B4231855" : "#1E5A8A44"}`, fontSize: 12, color: consolidateResult.error ? "#B42318" : "#1E5A8A" }}>
          {consolidateResult.error ? `Error: ${consolidateResult.error}` : `Removed ${consolidateResult.removed} near-duplicates · ${consolidateResult.remaining} memories remaining`}
        </div>
      )}
      {pruneResult && (
        <div style={{ marginBottom: 10, padding: "7px 12px", borderRadius: 4, background: pruneResult.error ? "#F9E7E1" : "#E7F2E6", border: `1px solid ${pruneResult.error ? "#B4231855" : "#15803D33"}`, fontSize: 12, color: pruneResult.error ? "#B42318" : "#15803D" }}>
          {pruneResult.error ? `Error: ${pruneResult.error}` : `Deleted ${pruneResult.deleted} entries · ${pruneResult.remaining} remaining`}
        </div>
      )}

      <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }} onClick={() => setAtRiskOpen(o => !o)}>
          <span style={{ fontSize: 11, fontWeight: 700, color: T.warn }}>⚠ At Risk</span>
          <span style={{ fontSize: 11, color: T.muted }}>{atRisk.length} memories (q 0.55–0.70, used ≤ 1×)</span>
          <span style={{ marginLeft: "auto", fontSize: 11, color: T.muted }}>{atRiskOpen ? "▲" : "▼"}</span>
        </div>
        {atRiskOpen && (
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
            {atRisk.length === 0 ? (
              <div style={{ fontSize: 12, color: T.muted, padding: "6px 0" }}>No at-risk memories right now.</div>
            ) : atRisk.map(m => {
              const q = m.quality || 0;
              const dc = q < 0.60 ? T.error : T.warn;
              return (
                <div key={m.id} style={{ background: T.bg, border: `1px solid ${dc}33`, borderRadius: 7, padding: "7px 11px", display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 36, height: 4, background: T.border, borderRadius: 2, overflow: "hidden", flexShrink: 0 }}>
                    <div style={{ width: `${Math.round(((q - 0.55) / 0.15) * 100)}%`, height: "100%", background: dc, borderRadius: 2 }} />
                  </div>
                  <span style={{ fontSize: 10, color: dc, fontFamily: "monospace", fontWeight: 700, minWidth: 38 }}>{q.toFixed(3)}</span>
                  <span style={{ fontSize: 10, color: T.muted, minWidth: 30 }}>{m.agent?.replace(/_/g, " ")}</span>
                  <span style={{ fontSize: 10, color: T.muted, minWidth: 24 }}>{m.type}</span>
                  <span style={{ fontSize: 11, color: T.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.preview}</span>
                  <span style={{ fontSize: 10, color: T.muted, flexShrink: 0 }}>×{m.use_count}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Feedback loop: 👍/👎 rollup by agent ──────────────────────────────────────
function buildFeedbackStats(entries) {
  const byAgent = {};
  for (const e of entries) {
    if (!byAgent[e.agent]) byAgent[e.agent] = { up: 0, down: 0 };
    if (e.rating === 1)  byAgent[e.agent].up++;
    if (e.rating === -1) byAgent[e.agent].down++;
  }
  return byAgent;
}

export function FeedbackLoopPanel() {
  const [feedback, setFeedback] = useState([]);

  useEffect(() => {
    fetch(`${API}/feedback?limit=500`).then(r => r.json())
      .then(d => setFeedback(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const total     = feedback.length;
  const totalUp   = feedback.filter(f => f.rating === 1).length;
  const totalDown = feedback.filter(f => f.rating === -1).length;
  const byAgent   = buildFeedbackStats(feedback);
  const agentRows = Object.entries(byAgent).sort((a, b) => (b[1].up + b[1].down) - (a[1].up + a[1].down));

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14, padding: "16px 18px" }}>
      <SectionHead title="Feedback Loop" />
      {total === 0 ? (
        <div style={{ padding: "20px 0", textAlign: "center" }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>👍 👎</div>
          <div style={{ fontSize: 13, color: T.muted }}>No ratings yet.</div>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 4 }}>
            Use the thumbs buttons under any response in the Chat tab to start collecting feedback.
          </div>
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 14 }}>
            <StatCard label="Total Ratings" value={total}     color="#1E5A8A" />
            <StatCard label="Positive 👍"   value={totalUp}   color="#15803D" sub={total > 0 ? `${Math.round((totalUp/total)*100)}%` : ""} />
            <StatCard label="Negative 👎"   value={totalDown} color="#B42318" sub={total > 0 ? `${Math.round((totalDown/total)*100)}%` : ""} />
          </div>
          {agentRows.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {agentRows.map(([agent, d]) => {
                const tot = d.up + d.down;
                const pct = tot > 0 ? Math.round((d.up / tot) * 100) : 0;
                const barColor = pct >= 70 ? "#15803D" : pct >= 40 ? "#9A6C00" : "#B42318";
                return (
                  <div key={agent} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 10px", background: T.bg, borderRadius: 4, border: `1px solid ${T.border}` }}>
                    <span style={{ fontSize: 11, color: T.mutedLt, minWidth: 140, fontFamily: "monospace" }}>{agent.replace(/_/g," ")}</span>
                    <div style={{ flex: 1, height: 4, background: T.border, borderRadius: 2 }}>
                      <div style={{ width: `${pct}%`, height: 4, background: barColor, borderRadius: 2, transition: "width .3s" }} />
                    </div>
                    <span style={{ fontSize: 10, color: T.success, minWidth: 28, textAlign: "right" }}>👍{d.up}</span>
                    <span style={{ fontSize: 10, color: T.error,   minWidth: 28, textAlign: "right" }}>👎{d.down}</span>
                    <span style={{ fontSize: 10, color: barColor,  minWidth: 32, textAlign: "right", fontFamily: "monospace" }}>{pct}%</span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
