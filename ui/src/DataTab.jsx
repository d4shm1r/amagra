import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "./ObsShared";
import { T, SEM, TYPE } from "./theme";

import { API } from "./api";

const VERDICT_META = {
  core:       { color: T.success,   label: "CORE",       desc: "Essential — high volume, reliable routing" },
  narrow:     { color: T.accent2,   label: "NARROW",     desc: "Specialized but low volume — survives if domain is real" },
  struggling: { color: T.error,     label: "STRUGGLING", desc: "High conflict + regret — routing unreliable" },
  redundant:  { color: SEM.magenta, label: "REDUNDANT",  desc: "Domain overlaps with higher-quality agent" },
};

const AGENT_META = {
  it_networking:      { icon: "🌐", color: T.success },
  python_dev:         { icon: "🐍", color: T.accent },
  dotnet_dev:         { icon: "⚡", color: SEM.violet },
  ai_ml:              { icon: "🤖", color: SEM.magenta },
  knowledge_learning: { icon: "📚", color: SEM.blue },
  terse:              { icon: "⚡", color: T.accent2 },
};

function StatCard({ label, value, sub, color = T.muted, wide = false }) {
  return (
    <div className="lux-card lux-card-i" style={{
      padding: "14px 16px", flex: wide ? "1 1 220px" : "1 1 120px",
    }}>
      <div style={{ ...TYPE.metric, color }}>{value}</div>
      <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.08em", color: T.muted, marginTop: 5 }}>{label}</div>
      {sub && <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function CovBar({ label, pct, color = SEM.teal }) {
  const p = Math.round((pct || 0) * 100);
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ ...TYPE.caption, color: T.muted }}>{label}</span>
        <span style={{ ...TYPE.caption, color, fontFamily: "monospace", fontWeight: 700 }}>{p}%</span>
      </div>
      <div style={{ height: 4, background: T.border, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${p}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

function VerdictBadge({ verdict }) {
  const m = VERDICT_META[verdict] || { color: T.muted, label: verdict?.toUpperCase() || "?" };
  return (
    <span style={{
      ...TYPE.micro, fontWeight: 700, padding: "2px 8px", borderRadius: 3,
      background: m.color + "22", color: m.color, border: `1px solid ${m.color}55`,
      whiteSpace: "nowrap",
    }}>
      {m.label}
    </span>
  );
}

function SpecializationTable({ data }) {
  if (!data) return null;
  const agents = Object.entries(data).sort((a, b) => b[1].total_decisions - a[1].total_decisions);
  return (
    <div>
      <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: T.muted, marginBottom: 10 }}>
        Agent Specialization Index
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ ...TYPE.caption, width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.06em", borderBottom: `1px solid ${T.border}`, color: T.muted }}>
              {["Agent", "N", "Conflict", "Regret", "Quality", "Top Domain", "Verdict", "Note"].map(h => (
                <th key={h} style={{ padding: "4px 8px", textAlign: "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {agents.map(([id, r]) => {
              const m   = AGENT_META[id] || { icon: "?", color: T.muted };
              const vm  = VERDICT_META[r.verdict] || { color: T.muted };
              const crc = r.conflict_rate >= 0.40 ? T.error : r.conflict_rate >= 0.20 ? T.accent2 : T.success;
              const qc  = r.avg_quality_proxy >= 0.78 ? T.success : r.avg_quality_proxy >= 0.70 ? T.accent2 : T.error;
              return (
                <tr key={id} style={{ borderBottom: `1px solid ${T.border}11` }}>
                  <td style={{ padding: "7px 8px" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                      <span>{m.icon}</span>
                      <span style={{ color: m.color, fontWeight: 700 }}>{id.replace(/_/g, " ")}</span>
                    </span>
                  </td>
                  <td style={{ padding: "7px 8px", color: T.text, fontFamily: "monospace" }}>{r.total_decisions}</td>
                  <td style={{ padding: "7px 8px", color: crc, fontFamily: "monospace" }}>
                    {(r.conflict_rate * 100).toFixed(0)}%
                  </td>
                  <td style={{ padding: "7px 8px", color: T.muted, fontFamily: "monospace" }}>
                    {r.avg_regret.toFixed(4)}
                  </td>
                  <td style={{ padding: "7px 8px", color: qc, fontFamily: "monospace" }}>
                    {r.avg_quality_proxy.toFixed(3)}
                  </td>
                  <td style={{ padding: "7px 8px", color: SEM.teal, fontFamily: "monospace", fontSize: 11 }}>
                    {r.top_domain} ({(r.top_domain_pct * 100).toFixed(0)}%)
                  </td>
                  <td style={{ padding: "7px 8px" }}><VerdictBadge verdict={r.verdict} /></td>
                  <td style={{ ...TYPE.micro, fontWeight: 400, padding: "7px 8px", color: T.muted, maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.verdict_reason}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {/* Legend */}
      <div style={{ display: "flex", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
        {Object.entries(VERDICT_META).map(([k, m]) => (
          <span key={k} style={{ ...TYPE.micro, fontWeight: 400, color: T.muted }}>
            <span style={{ color: m.color, fontWeight: 700 }}>{m.label}</span> — {m.desc}
          </span>
        ))}
      </div>
    </div>
  );
}

function CounterfactualPanel({ candidates }) {
  if (!candidates?.length) return (
    <div style={{ ...TYPE.caption, color: T.muted, padding: "16px 0" }}>
      No high-priority counterfactual candidates yet.
    </div>
  );
  return (
    <div>
      <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: T.muted, marginBottom: 10 }}>
        Counterfactual Candidates
        <span style={{ ...TYPE.micro, fontWeight: 400, marginLeft: 8, color: T.muted, textTransform: "none", letterSpacing: 0 }}>
          high-regret and conflict decisions worth re-running with the alternative agent
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {candidates.map(c => {
          const pColor = c.priority === "high" ? T.error : T.accent2;
          const origM = AGENT_META[c.original_agent] || { icon: "?", color: T.muted };
          const altM  = AGENT_META[c.suggested_alt]  || { icon: "?", color: T.muted };
          return (
            <div key={c.decision_id} style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 3, padding: "8px 13px", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, fontFamily: "monospace", minWidth: 28 }}>#{c.decision_id}</span>
              <span style={{ ...TYPE.micro, fontWeight: 700, background: pColor + "22", color: pColor, border: `1px solid ${pColor}44`, borderRadius: 4, padding: "1px 6px" }}>
                {c.priority}
              </span>
              <span style={{ ...TYPE.caption, color: origM.color, fontWeight: 700 }}>{origM.icon} {c.original_agent?.replace(/_/g, " ")}</span>
              <span style={{ color: T.muted }}>→</span>
              {c.suggested_alt
                ? <span style={{ ...TYPE.caption, color: altM.color, fontWeight: 700 }}>{altM.icon} {c.suggested_alt?.replace(/_/g, " ")}</span>
                : <span style={{ ...TYPE.caption, color: T.muted }}>no alt</span>}
              <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, fontFamily: "monospace" }}>regret={c.regret?.toFixed(4)}</span>
              {c.conflict && <span style={{ ...TYPE.micro, fontWeight: 400, color: T.error }}>⚡ conflict</span>}
              <span style={{ ...TYPE.caption, flex: 1, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.query}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ ...TYPE.caption, marginTop: 10, color: T.muted, fontStyle: "italic" }}>
        Run: <code style={{ color: T.muted }}>POST /analysis/counterfactual/&#123;id&#125;?alt_agent=X&dry_run=false</code> to invoke.
        Statistical claims require 400+ real sessions.
      </div>
    </div>
  );
}

function GraphStatsPanel({ graph }) {
  if (!graph) return null;
  const s = graph.stats || {};
  const nodeTypes = s.by_node_type || {};
  const edgeTypes = s.by_edge_type || {};
  const NODE_COLORS = { query: SEM.teal, agent: T.success, memory: SEM.blue, reflection: SEM.magenta, outcome: T.accent2 };
  const EDGE_COLORS = { SELECTED: T.success, REJECTED: T.error, RETRIEVED: SEM.blue, INFLUENCED: SEM.violet, PRODUCED: T.accent2, REFLECTED: SEM.magenta };
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
        <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: T.muted }}>Decision Graph</div>
        <span style={{ ...TYPE.micro, fontWeight: 400, fontFamily: "monospace", color: T.muted }}>{graph.version}</span>
        <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted }}>· {graph.trace_count} traces · {s.node_count} nodes · {s.edge_count} edges · deg {s.avg_degree}</span>
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 200px" }}>
          <div style={{ ...TYPE.eyebrow, fontWeight: 400, letterSpacing: "0.08em", color: T.muted, marginBottom: 6 }}>Nodes</div>
          {Object.entries(nodeTypes).map(([t, n]) => (
            <div key={t} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ ...TYPE.caption, color: NODE_COLORS[t] || T.muted, fontWeight: 700 }}>{t}</span>
              <span style={{ ...TYPE.caption, fontFamily: "monospace", color: T.text }}>{n}</span>
            </div>
          ))}
        </div>
        <div style={{ flex: "1 1 200px" }}>
          <div style={{ ...TYPE.eyebrow, fontWeight: 400, letterSpacing: "0.08em", color: T.muted, marginBottom: 6 }}>Edges</div>
          {Object.entries(edgeTypes).map(([t, n]) => (
            <div key={t} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ ...TYPE.caption, color: EDGE_COLORS[t] || T.muted, fontWeight: 700 }}>{t}</span>
              <span style={{ ...TYPE.caption, fontFamily: "monospace", color: T.text }}>{n}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CausalPathPanel() {
  const [decisionId, setDecisionId] = useState("");
  const [path,       setPath]       = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState("");

  const query = async () => {
    const id = parseInt(decisionId, 10);
    if (!id) return;
    setLoading(true); setError(""); setPath(null);
    try {
      const r = await fetch(`${API}/data/causal/${id}`);
      if (!r.ok) { setError(`Not found: decision ${id}`); setLoading(false); return; }
      setPath(await r.json());
    } catch { setError("Request failed"); }
    setLoading(false);
  };

  const FLAG_COLORS = { routing_conflict: T.error, high_regret: T.accent2, low_quality: T.error, low_relevance_memory: SEM.magenta };

  return (
    <div>
      <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: T.muted, marginBottom: 10 }}>
        Causal Path Explorer
        <span style={{ ...TYPE.micro, fontWeight: 400, marginLeft: 8, color: T.muted, textTransform: "none", letterSpacing: 0 }}>
          inspect why a specific decision was made — routing, memory, outcome
        </span>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input value={decisionId} onChange={e => setDecisionId(e.target.value)}
          onKeyDown={e => e.key === "Enter" && query()}
          placeholder="Decision ID (e.g. 172)" type="number"
          style={{ ...TYPE.caption, width: 160, background: T.surface2, border: `1.5px solid ${T.border}`, borderRadius: 3, color: T.text, padding: "5px 10px", fontFamily: "monospace", outline: "none" }} />
        <button onClick={query} disabled={loading}
          style={{ ...TYPE.caption, fontWeight: 700, padding: "5px 14px", borderRadius: 3, fontFamily: "inherit", background: SEM.teal + "22", color: SEM.teal, border: `1px solid ${SEM.teal}44`, cursor: "pointer" }}>
          {loading ? "…" : "Trace"}
        </button>
      </div>
      {error && <div style={{ ...TYPE.caption, color: T.error, marginBottom: 8 }}>{error}</div>}
      {path && !path.error && (
        <div style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 3, padding: "14px 16px" }}>
          {/* Causal flags */}
          {path.causal_flags?.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
              {path.causal_flags.map((f, i) => (
                <span key={i} style={{ ...TYPE.micro, fontWeight: 700, background: (FLAG_COLORS[f.type] || T.muted) + "22", color: FLAG_COLORS[f.type] || T.muted, border: `1px solid ${FLAG_COLORS[f.type] || T.muted}44`, borderRadius: 3, padding: "2px 8px" }}>
                  ⚠ {f.type.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
          {/* Path steps */}
          {[
            { label: "QUERY",      color: SEM.teal,    content: `"${(path.query || "").slice(0,100)}"` },
            { label: "SIGNAL",     color: SEM.cyan,    content: `domain=${path.signal?.domain} shape=${path.signal?.shape} conf=${path.signal?.conf?.toFixed(2)}` },
            { label: "ACTION",     color: SEM.blue,    content: `${path.action} / ${path.complexity}` },
            { label: "SELECTED",   color: T.success,   content: path.selected_agent || "—" },
            { label: "REJECTED",   color: T.error,     content: path.rejected_agents?.length ? path.rejected_agents.join(", ") : "none (no conflict)" },
            { label: "MEMORY",     color: SEM.violet,  content: `${path.memories_retrieved} records retrieved` + (path.top_memories?.length ? ` (top: ${path.top_memories.slice(0,2).map(m => `${m.mem_type}@${m.agent} score=${m.score?.toFixed(2)}`).join(", ")})` : "") },
            { label: "OUTCOME",    color: T.accent2,   content: `quality=${path.outcome?.quality_proxy?.toFixed(3)}  regret=${path.outcome?.regret?.toFixed(4)}  conf=${path.outcome?.confidence?.toFixed(2)}  ${path.outcome?.duration_ms}ms` },
            { label: "REFLECTION", color: SEM.magenta, content: path.reflection?.triggered ? `YES (${path.reflection?.reflect_type})` : "none" },
          ].map(step => (
            <div key={step.label} style={{ display: "flex", gap: 10, marginBottom: 5, alignItems: "flex-start" }}>
              <span style={{ fontSize: 9, fontFamily: "monospace", color: step.color, fontWeight: 700, minWidth: 70, paddingTop: 1, textAlign: "right" }}>{step.label}</span>
              <span style={{ ...TYPE.caption, color: T.text, lineHeight: 1.5 }}>{step.content}</span>
            </div>
          ))}
          {/* Causal flag detail */}
          {path.causal_flags?.length > 0 && (
            <div style={{ marginTop: 10, borderTop: `1px solid ${T.border}`, paddingTop: 8 }}>
              {path.causal_flags.map((f, i) => (
                <div key={i} style={{ ...TYPE.caption, color: FLAG_COLORS[f.type] || T.muted, marginBottom: 3 }}>
                  ↳ {f.detail}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Memory Backend Panel ──────────────────────────────────────

function MemoryBackendPanel({ backend, onRefresh }) {
  const [bench,      setBench]      = useState(null);
  const [benching,   setBenching]   = useState(false);
  const [promoting,  setPromoting]  = useState(false);
  const [promoteMsg, setPromoteMsg] = useState(null);

  async function runBench() {
    setBenching(true);
    setBench(null);
    try {
      const r = await fetch(`${API}/analysis/memory_backend/bench?n=7`);
      if (r.ok) setBench(await r.json());
    } catch {}
    setBenching(false);
  }

  async function promote() {
    setPromoting(true);
    setPromoteMsg(null);
    try {
      const r = await fetch(`${API}/analysis/memory_backend/promote`, { method: "POST" });
      const d = await r.json();
      setPromoteMsg(d.promoted
        ? `Promoted to FAISSBackend (${d.backend?.total ?? "?"} entries)`
        : "Already on optimal backend — no promotion needed");
      onRefresh();
    } catch (e) {
      setPromoteMsg(`Error: ${e.message}`);
    }
    setPromoting(false);
  }

  if (!backend) return null;

  const isFaiss   = backend.type === "FAISSBackend";
  const isSqlite  = backend.type === "SQLiteBackend";
  const threshold = backend.promote_threshold || 800;
  const total     = backend.total || 0;
  const progress  = Math.min(100, Math.round((total / threshold) * 100));
  const typeColor = isFaiss ? T.success : isSqlite ? T.accent2 : SEM.blue;
  const driftOk   = (backend.drift_pct ?? 0) <= 5;

  const searchPassing = bench?.search_passing || bench?.raw_vector_ok;
  const searchColor   = bench
    ? (searchPassing ? T.success : T.accent2)
    : T.muted;
  const totalColor    = bench
    ? (bench.total_p50_ms < 200 ? T.success : T.accent2)
    : T.muted;

  // Smaller stat numeral — sits below the 22px metric tier (StatCard) used above.
  const statNum = { ...TYPE.subtitle, fontWeight: 800, fontFamily: "monospace", fontVariantNumeric: "tabular-nums" };

  return (
    <div style={{
      background: T.surface,
      border: `1.5px solid ${backend.fan_out_warning ? T.error : typeColor}28`,
      borderRadius: 3, padding: "16px 20px", marginBottom: 16,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", marginBottom: 14, gap: 10 }}>
        <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: T.muted, flex: 1 }}>
          Memory Backend
        </div>
        <span style={{
          ...TYPE.micro, fontWeight: 700, color: typeColor,
          background: `${typeColor}18`, border: `1px solid ${typeColor}44`,
          borderRadius: 3, padding: "2px 8px", fontFamily: "monospace",
        }}>
          {backend.type}
        </span>
        <button onClick={runBench} disabled={benching}
          style={{ ...TYPE.micro, fontWeight: 600, padding: "4px 10px", borderRadius: 3, fontFamily: "inherit", background: SEM.blue + "18", color: SEM.blue, border: `1px solid ${SEM.blue}44`, cursor: benching ? "wait" : "pointer" }}>
          {benching ? "Running…" : "⏱ Benchmark"}
        </button>
        {isSqlite && (
          <button onClick={promote} disabled={promoting}
            style={{ ...TYPE.micro, fontWeight: 600, padding: "4px 10px", borderRadius: 3, fontFamily: "inherit", background: T.success + "18", color: T.success, border: `1px solid ${T.success}44`, cursor: promoting ? "wait" : "pointer" }}>
            {promoting ? "Promoting…" : "⚡ Promote to FAISS"}
          </button>
        )}
      </div>

      {/* Info grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 14 }}>
        <div style={{ background: T.surface2, borderRadius: 3, padding: "10px 14px", border: `1px solid ${T.border}22` }}>
          <div style={{ ...statNum, color: T.text }}>{total.toLocaleString()}</div>
          <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 2 }}>Total entries</div>
        </div>
        {isFaiss && backend.index_ntotal != null && (
          <div style={{ background: T.surface2, borderRadius: 3, padding: "10px 14px", border: `1px solid ${driftOk ? `${T.border}22` : `${T.accent2}44`}` }}>
            <div style={{ ...statNum, color: driftOk ? T.success : T.accent2 }}>{backend.index_ntotal.toLocaleString()}</div>
            <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 2 }}>FAISS index vectors</div>
            <div style={{ fontSize: 9, color: driftOk ? T.success : T.accent2, marginTop: 2 }}>{backend.drift_pct}% drift {driftOk ? "✓" : "⚠"}</div>
          </div>
        )}
        {isFaiss && backend.index_size_mb != null && (
          <div style={{ background: T.surface2, borderRadius: 3, padding: "10px 14px", border: `1px solid ${T.border}22` }}>
            <div style={{ ...statNum, color: SEM.blue }}>{backend.index_size_mb} MB</div>
            <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 2 }}>Index file size</div>
          </div>
        )}
        {bench && bench.search_p50_ms != null && (
          <div style={{ background: T.surface2, borderRadius: 3, padding: "10px 14px", border: `1px solid ${searchColor}33` }}>
            <div style={{ ...statNum, color: searchColor }}>{bench.search_p50_ms} ms</div>
            <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 2 }}>Vector search P50 (target ≤{bench.search_target_ms}ms)</div>
            <div style={{ fontSize: 9, color: searchColor, marginTop: 2 }}>{searchPassing ? "✓ Passing" : "⚠ Above target"} · P95: {bench.search_p95_ms}ms</div>
          </div>
        )}
        {bench && bench.total_p50_ms != null && (
          <div style={{ background: T.surface2, borderRadius: 3, padding: "10px 14px", border: `1px solid ${totalColor}33` }}>
            <div style={{ ...statNum, color: totalColor }}>{bench.total_p50_ms} ms</div>
            <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 2 }}>Full pipeline P50</div>
            <div style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, marginTop: 2 }}>embed + search + re-rank</div>
          </div>
        )}
      </div>

      {/* Promotion threshold bar (SQLite only) */}
      {isSqlite && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ ...TYPE.caption, color: T.muted }}>Fan-out threshold ({total} / {threshold} entries)</span>
            <span style={{ ...TYPE.caption, color: progress >= 100 ? T.error : T.accent2, fontFamily: "monospace" }}>{progress}%</span>
          </div>
          <div style={{ height: 5, background: T.border, borderRadius: 3, overflow: "hidden" }}>
            <div style={{ width: `${progress}%`, height: "100%", background: progress >= 100 ? T.error : T.accent2, borderRadius: 3, transition: "width 0.4s" }} />
          </div>
          {progress >= 80 && (
            <div style={{ ...TYPE.micro, fontWeight: 400, color: T.accent2, marginTop: 5 }}>
              ⚠ Approaching FAISS threshold — auto-promote triggers at {threshold} entries
            </div>
          )}
        </div>
      )}

      {/* Engine detail */}
      <div style={{ ...TYPE.caption, color: T.muted, lineHeight: 1.6 }}>
        Engine: <span style={{ color: SEM.teal }}>{backend.engine || "—"}</span>
        {isFaiss && <span style={{ color: T.success, marginLeft: 12 }}>✓ O(log n) ANN · thread-safe · incremental updates</span>}
        {isSqlite && <span style={{ color: T.accent2, marginLeft: 12 }}>O(n) cosine scan · auto-promotes at {threshold} entries</span>}
      </div>

      {/* Benchmark summary */}
      {bench && (
        <div style={{ ...TYPE.caption, marginTop: 10, padding: "8px 12px", background: `${searchColor}0D`, border: `1px solid ${searchColor}33`, borderRadius: 3 }}>
          <span style={{ color: searchColor, fontWeight: 700 }}>
            {searchPassing ? "✓ Vector search passing" : "⚠ Vector search above target"}
          </span>
          <span style={{ color: T.muted, marginLeft: 10 }}>
            {bench.n_queries} queries · {bench.entry_count} entries · {bench.embed_note}
          </span>
        </div>
      )}
      {promoteMsg && (
        <div style={{ ...TYPE.caption, marginTop: 10, padding: "7px 12px", background: `${T.success}10`, border: `1px solid ${T.success}33`, borderRadius: 3, color: T.success }}>
          {promoteMsg}
        </div>
      )}
    </div>
  );
}


// ── Main component ────────────────────────────────────────────

export default function DataTab() {
  const [stats,    setStats]    = useState(null);
  const [spec,     setSpec]     = useState(null);
  const [cands,    setCands]    = useState(null);
  const [backend,  setBackend]  = useState(null);
  const [graphStats, setGraphStats] = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sR, spR, cR, bR, gR] = await Promise.all([
        fetch(`${API}/data/stats`),
        fetch(`${API}/analysis/specialization`),
        fetch(`${API}/analysis/counterfactual/candidates?n=8`),
        fetch(`${API}/analysis/memory_backend`),
        fetch(`${API}/data/graph/stats`),
      ]);
      if (sR.ok)  setStats(await sR.json());
      if (spR.ok) setSpec(await spR.json());
      if (cR.ok)  { const d = await cR.json(); setCands(d.candidates || []); }
      if (bR.ok)  setBackend(await bR.json());
      if (gR.ok)  setGraphStats(await gR.json());
    } catch {
      setStats(null);
    }
    setLoading(false);
  }, []);

  const rebuild = async () => {
    setRebuilding(true);
    try {
      const [sR, spR, gR] = await Promise.all([
        fetch(`${API}/data/stats?rebuild=true`),
        fetch(`${API}/analysis/specialization?rebuild=true`),
        fetch(`${API}/data/graph/stats?rebuild=true`),
      ]);
      if (sR.ok)  setStats(await sR.json());
      if (spR.ok) setSpec(await spR.json());
      if (gR.ok)  setGraphStats(await gR.json());
    } catch {}
    setRebuilding(false);
  };

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      {/* Header */}
      <PageHeader
        title="Decision Trace Dataset"
        subtitle="Every routing decision joined with memory, reflection, and session data — structured for training and analysis."
      >
        <div style={{ display: "flex", gap: 8 }}>
          <a href={`${API}/data/traces.jsonl`} download="trace_dataset.jsonl"
            style={{ ...TYPE.caption, fontWeight: 700, padding: "7px 14px", borderRadius: 4, background: SEM.blue + "22", color: SEM.blue, border: `1px solid ${SEM.blue}44`, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 5 }}>
            ⬇ JSONL
          </a>
          <button onClick={rebuild} disabled={rebuilding}
            style={{ ...TYPE.caption, fontWeight: 700, padding: "7px 14px", borderRadius: 4, fontFamily: "inherit", background: T.accent2 + "22", color: T.accent2, border: `1px solid ${T.accent2}44`, cursor: rebuilding ? "wait" : "pointer" }}>
            {rebuilding ? "Rebuilding…" : "⟳ Rebuild"}
          </button>
          <button onClick={load} disabled={loading}
            style={{ ...TYPE.caption, fontWeight: 700, padding: "7px 14px", borderRadius: 4, fontFamily: "inherit", background: T.success + "22", color: T.success, border: `1px solid ${T.success}44`, cursor: "pointer" }}>
            {loading ? "…" : "↻ Refresh"}
          </button>
        </div>
      </PageHeader>

      {/* Coverage stats */}
      {stats && (
        <div className="lux-card" style={{ padding: "16px 20px", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
            <StatCard label="Total traces"    value={stats.total}            color={SEM.blue} />
            <StatCard label="Real sessions"   value={stats.real_sessions}    color={T.success} />
            <StatCard label="Eval decisions"  value={stats.eval_decisions}   color={T.muted} />
            <StatCard label="Avg quality"     value={stats.avg_quality_proxy?.toFixed(3)} color={T.accent2} />
            <StatCard label="Avg memories/q"  value={stats.avg_memories_per_query?.toFixed(1)} color={SEM.teal} sub="fan-out signal" />
            <StatCard label="Avg regret"      value={stats.avg_regret?.toFixed(4)} color={stats.avg_regret > 0.1 ? T.error : T.muted} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: T.muted, marginBottom: 8 }}>Signal Coverage</div>
              {stats.coverage && Object.entries({
                "Has response":   [stats.coverage.response_pct,   T.success],
                "Has memory":     [stats.coverage.memory_pct,     SEM.teal],
                "Has reflection": [stats.coverage.reflection_pct, SEM.magenta],
                "Has conflict":   [stats.coverage.conflict_pct,   T.error],
                "Has feedback":   [stats.coverage.feedback_pct,   T.accent2],
              }).map(([lbl, [pct, col]]) => (
                <CovBar key={lbl} label={lbl} pct={pct} color={col} />
              ))}
            </div>
            <div>
              <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: T.muted, marginBottom: 8 }}>Agent Distribution</div>
              {stats.agent_distribution && Object.entries(stats.agent_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([agent, n]) => {
                  const pct = n / stats.total;
                  const m = AGENT_META[agent] || { color: T.muted };
                  return (
                    <div key={agent} style={{ marginBottom: 5 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                        <span style={{ ...TYPE.caption, color: T.muted }}>{agent.replace(/_/g, " ")}</span>
                        <span style={{ ...TYPE.caption, color: m.color, fontFamily: "monospace" }}>{n} ({(pct*100).toFixed(0)}%)</span>
                      </div>
                      <div style={{ height: 3, background: T.border, borderRadius: 2, overflow: "hidden" }}>
                        <div style={{ width: `${pct*100}%`, height: "100%", background: m.color, borderRadius: 2 }} />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}

      {/* Specialization table */}
      {spec && (
        <div className="lux-card" style={{ padding: "16px 20px", marginBottom: 16 }}>
          <SpecializationTable data={spec} />
        </div>
      )}

      {/* Counterfactual candidates */}
      {cands !== null && (
        <div className="lux-card" style={{ padding: "16px 20px", marginBottom: 16 }}>
          <CounterfactualPanel candidates={cands} />
        </div>
      )}

      {/* Decision graph stats */}
      {graphStats && (
        <div className="lux-card" style={{ padding: "16px 20px", marginBottom: 16 }}>
          <GraphStatsPanel graph={graphStats} />
        </div>
      )}

      {/* Causal path explorer */}
      <div className="lux-card" style={{ padding: "16px 20px", marginBottom: 16 }}>
        <CausalPathPanel />
      </div>

      {/* Memory backend status */}
      <MemoryBackendPanel backend={backend} onRefresh={load} />

    </div>
  );
}
