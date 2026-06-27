import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "./ObsShared";

import { API } from "./api";

const VERDICT_META = {
  core:       { color: "#15803D", label: "CORE",       desc: "Essential — high volume, reliable routing" },
  narrow:     { color: "#9A6C00", label: "NARROW",     desc: "Specialized but low volume — survives if domain is real" },
  struggling: { color: "#B42318", label: "STRUGGLING", desc: "High conflict + regret — routing unreliable" },
  redundant:  { color: "#BE185D", label: "REDUNDANT",  desc: "Domain overlaps with higher-quality agent" },
};

const AGENT_META = {
  it_networking:      { icon: "🌐", color: "#15803D" },
  python_dev:         { icon: "🐍", color: "#C48808" },
  dotnet_dev:         { icon: "⚡", color: "#7C3AED" },
  ai_ml:              { icon: "🤖", color: "#BE185D" },
  knowledge_learning: { icon: "📚", color: "#1E5A8A" },
  terse:              { icon: "⚡", color: "#9A6C00" },
};

function StatCard({ label, value, sub, color = "#9A7A60", wide = false }) {
  return (
    <div className="lux-card lux-card-i" style={{
      padding: "14px 16px", flex: wide ? "1 1 220px" : "1 1 120px",
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em", lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 10, fontWeight: 600, color: "#9A7A60", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 5 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function CovBar({ label, pct, color = "#0F766E" }) {
  const p = Math.round((pct || 0) * 100);
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontSize: 11, color: "#9A7A60" }}>{label}</span>
        <span style={{ fontSize: 11, color, fontFamily: "monospace", fontWeight: 700 }}>{p}%</span>
      </div>
      <div style={{ height: 4, background: "#E0D6C4", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${p}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

function VerdictBadge({ verdict }) {
  const m = VERDICT_META[verdict] || { color: "#9A7A60", label: verdict?.toUpperCase() || "?" };
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 3, fontSize: 10, fontWeight: 700,
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
      <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", marginBottom: 10, textTransform: "uppercase", letterSpacing: 1 }}>
        Agent Specialization Index
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #E0D6C4", color: "#9A7A60", fontSize: 10, textTransform: "uppercase" }}>
              {["Agent", "N", "Conflict", "Regret", "Quality", "Top Domain", "Verdict", "Note"].map(h => (
                <th key={h} style={{ padding: "4px 8px", textAlign: "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {agents.map(([id, r]) => {
              const m   = AGENT_META[id] || { icon: "?", color: "#9A7A60" };
              const vm  = VERDICT_META[r.verdict] || { color: "#9A7A60" };
              const crc = r.conflict_rate >= 0.40 ? "#B42318" : r.conflict_rate >= 0.20 ? "#9A6C00" : "#15803D";
              const qc  = r.avg_quality_proxy >= 0.78 ? "#15803D" : r.avg_quality_proxy >= 0.70 ? "#9A6C00" : "#B42318";
              return (
                <tr key={id} style={{ borderBottom: "1px solid #E0D6C411" }}>
                  <td style={{ padding: "7px 8px" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                      <span>{m.icon}</span>
                      <span style={{ color: m.color, fontWeight: 700 }}>{id.replace(/_/g, " ")}</span>
                    </span>
                  </td>
                  <td style={{ padding: "7px 8px", color: "#2E2010", fontFamily: "monospace" }}>{r.total_decisions}</td>
                  <td style={{ padding: "7px 8px", color: crc, fontFamily: "monospace" }}>
                    {(r.conflict_rate * 100).toFixed(0)}%
                  </td>
                  <td style={{ padding: "7px 8px", color: "#9A7A60", fontFamily: "monospace" }}>
                    {r.avg_regret.toFixed(4)}
                  </td>
                  <td style={{ padding: "7px 8px", color: qc, fontFamily: "monospace" }}>
                    {r.avg_quality_proxy.toFixed(3)}
                  </td>
                  <td style={{ padding: "7px 8px", color: "#0F766E", fontFamily: "monospace", fontSize: 11 }}>
                    {r.top_domain} ({(r.top_domain_pct * 100).toFixed(0)}%)
                  </td>
                  <td style={{ padding: "7px 8px" }}><VerdictBadge verdict={r.verdict} /></td>
                  <td style={{ padding: "7px 8px", color: "#9A7A60", fontSize: 10, maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
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
          <span key={k} style={{ fontSize: 10, color: "#9A7A60" }}>
            <span style={{ color: m.color, fontWeight: 700 }}>{m.label}</span> — {m.desc}
          </span>
        ))}
      </div>
    </div>
  );
}

function CounterfactualPanel({ candidates }) {
  if (!candidates?.length) return (
    <div style={{ fontSize: 12, color: "#9A7A60", padding: "16px 0" }}>
      No high-priority counterfactual candidates yet.
    </div>
  );
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", marginBottom: 10, textTransform: "uppercase", letterSpacing: 1 }}>
        Counterfactual Candidates
        <span style={{ marginLeft: 8, fontSize: 10, color: "#9A7A60", textTransform: "none", fontWeight: 400 }}>
          high-regret and conflict decisions worth re-running with the alternative agent
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {candidates.map(c => {
          const pColor = c.priority === "high" ? "#B42318" : "#9A6C00";
          const origM = AGENT_META[c.original_agent] || { icon: "?", color: "#9A7A60" };
          const altM  = AGENT_META[c.suggested_alt]  || { icon: "?", color: "#9A7A60" };
          return (
            <div key={c.decision_id} style={{ background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 3, padding: "8px 13px", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 10, color: "#9A7A60", fontFamily: "monospace", minWidth: 28 }}>#{c.decision_id}</span>
              <span style={{ background: pColor + "22", color: pColor, border: `1px solid ${pColor}44`, borderRadius: 4, padding: "1px 6px", fontSize: 10, fontWeight: 700 }}>
                {c.priority}
              </span>
              <span style={{ color: origM.color, fontSize: 11, fontWeight: 700 }}>{origM.icon} {c.original_agent?.replace(/_/g, " ")}</span>
              <span style={{ color: "#9A7A60" }}>→</span>
              {c.suggested_alt
                ? <span style={{ color: altM.color, fontSize: 11, fontWeight: 700 }}>{altM.icon} {c.suggested_alt?.replace(/_/g, " ")}</span>
                : <span style={{ color: "#9A7A60", fontSize: 11 }}>no alt</span>}
              <span style={{ fontSize: 10, color: "#9A7A60", fontFamily: "monospace" }}>regret={c.regret?.toFixed(4)}</span>
              {c.conflict && <span style={{ fontSize: 10, color: "#B42318" }}>⚡ conflict</span>}
              <span style={{ flex: 1, fontSize: 11, color: "#2E2010", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.query}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 10, fontSize: 11, color: "#9A7A60", fontStyle: "italic" }}>
        Run: <code style={{ color: "#9A7A60" }}>POST /analysis/counterfactual/&#123;id&#125;?alt_agent=X&dry_run=false</code> to invoke.
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
  const NODE_COLORS = { query: "#0F766E", agent: "#15803D", memory: "#1E5A8A", reflection: "#BE185D", outcome: "#9A6C00" };
  const EDGE_COLORS = { SELECTED: "#15803D", REJECTED: "#B42318", RETRIEVED: "#1E5A8A", INFLUENCED: "#7C3AED", PRODUCED: "#9A6C00", REFLECTED: "#BE185D" };
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", textTransform: "uppercase", letterSpacing: 1 }}>Decision Graph</div>
        <span style={{ fontSize: 10, fontFamily: "monospace", color: "#9A7A60" }}>{graph.version}</span>
        <span style={{ fontSize: 10, color: "#9A7A60" }}>· {graph.trace_count} traces · {s.node_count} nodes · {s.edge_count} edges · deg {s.avg_degree}</span>
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 200px" }}>
          <div style={{ fontSize: 10, color: "#9A7A60", marginBottom: 6, textTransform: "uppercase", letterSpacing: 1 }}>Nodes</div>
          {Object.entries(nodeTypes).map(([t, n]) => (
            <div key={t} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ fontSize: 11, color: NODE_COLORS[t] || "#9A7A60", fontWeight: 700 }}>{t}</span>
              <span style={{ fontSize: 11, fontFamily: "monospace", color: "#2E2010" }}>{n}</span>
            </div>
          ))}
        </div>
        <div style={{ flex: "1 1 200px" }}>
          <div style={{ fontSize: 10, color: "#9A7A60", marginBottom: 6, textTransform: "uppercase", letterSpacing: 1 }}>Edges</div>
          {Object.entries(edgeTypes).map(([t, n]) => (
            <div key={t} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ fontSize: 11, color: EDGE_COLORS[t] || "#9A7A60", fontWeight: 700 }}>{t}</span>
              <span style={{ fontSize: 11, fontFamily: "monospace", color: "#2E2010" }}>{n}</span>
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

  const FLAG_COLORS = { routing_conflict: "#B42318", high_regret: "#9A6C00", low_quality: "#B42318", low_relevance_memory: "#BE185D" };

  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", marginBottom: 10, textTransform: "uppercase", letterSpacing: 1 }}>
        Causal Path Explorer
        <span style={{ marginLeft: 8, fontSize: 10, color: "#9A7A60", textTransform: "none", fontWeight: 400 }}>
          inspect why a specific decision was made — routing, memory, outcome
        </span>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input value={decisionId} onChange={e => setDecisionId(e.target.value)}
          onKeyDown={e => e.key === "Enter" && query()}
          placeholder="Decision ID (e.g. 172)" type="number"
          style={{ width: 160, background: "#F4F0E8", border: "1.5px solid #E0D6C4", borderRadius: 3, color: "#2E2010", padding: "5px 10px", fontSize: 12, fontFamily: "monospace", outline: "none" }} />
        <button onClick={query} disabled={loading}
          style={{ padding: "5px 14px", borderRadius: 3, fontSize: 12, fontWeight: 700, fontFamily: "inherit", background: "#0F766E22", color: "#0F766E", border: "1px solid #0F766E44", cursor: "pointer" }}>
          {loading ? "…" : "Trace"}
        </button>
      </div>
      {error && <div style={{ fontSize: 12, color: "#B42318", marginBottom: 8 }}>{error}</div>}
      {path && !path.error && (
        <div style={{ background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 3, padding: "14px 16px" }}>
          {/* Causal flags */}
          {path.causal_flags?.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
              {path.causal_flags.map((f, i) => (
                <span key={i} style={{ background: (FLAG_COLORS[f.type] || "#9A7A60") + "22", color: FLAG_COLORS[f.type] || "#9A7A60", border: `1px solid ${FLAG_COLORS[f.type] || "#9A7A60"}44`, borderRadius: 3, padding: "2px 8px", fontSize: 10, fontWeight: 700 }}>
                  ⚠ {f.type.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
          {/* Path steps */}
          {[
            { label: "QUERY",      color: "#0F766E", content: `"${(path.query || "").slice(0,100)}"` },
            { label: "SIGNAL",     color: "#0E7490", content: `domain=${path.signal?.domain} shape=${path.signal?.shape} conf=${path.signal?.conf?.toFixed(2)}` },
            { label: "ACTION",     color: "#1E5A8A", content: `${path.action} / ${path.complexity}` },
            { label: "SELECTED",   color: "#15803D", content: path.selected_agent || "—" },
            { label: "REJECTED",   color: "#B42318", content: path.rejected_agents?.length ? path.rejected_agents.join(", ") : "none (no conflict)" },
            { label: "MEMORY",     color: "#7C3AED", content: `${path.memories_retrieved} records retrieved` + (path.top_memories?.length ? ` (top: ${path.top_memories.slice(0,2).map(m => `${m.mem_type}@${m.agent} score=${m.score?.toFixed(2)}`).join(", ")})` : "") },
            { label: "OUTCOME",    color: "#9A6C00", content: `quality=${path.outcome?.quality_proxy?.toFixed(3)}  regret=${path.outcome?.regret?.toFixed(4)}  conf=${path.outcome?.confidence?.toFixed(2)}  ${path.outcome?.duration_ms}ms` },
            { label: "REFLECTION", color: "#BE185D", content: path.reflection?.triggered ? `YES (${path.reflection?.reflect_type})` : "none" },
          ].map(step => (
            <div key={step.label} style={{ display: "flex", gap: 10, marginBottom: 5, alignItems: "flex-start" }}>
              <span style={{ fontSize: 9, fontFamily: "monospace", color: step.color, fontWeight: 700, minWidth: 70, paddingTop: 1, textAlign: "right" }}>{step.label}</span>
              <span style={{ fontSize: 11, color: "#2E2010", lineHeight: 1.5 }}>{step.content}</span>
            </div>
          ))}
          {/* Causal flag detail */}
          {path.causal_flags?.length > 0 && (
            <div style={{ marginTop: 10, borderTop: "1px solid #E0D6C4", paddingTop: 8 }}>
              {path.causal_flags.map((f, i) => (
                <div key={i} style={{ fontSize: 11, color: FLAG_COLORS[f.type] || "#9A7A60", marginBottom: 3 }}>
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
  const typeColor = isFaiss ? "#15803D" : isSqlite ? "#9A6C00" : "#1E5A8A";
  const driftOk   = (backend.drift_pct ?? 0) <= 5;

  const searchPassing = bench?.search_passing || bench?.raw_vector_ok;
  const searchColor   = bench
    ? (searchPassing ? "#15803D" : "#9A6C00")
    : "#9A7A60";
  const totalColor    = bench
    ? (bench.total_p50_ms < 200 ? "#15803D" : "#9A6C00")
    : "#9A7A60";

  return (
    <div style={{
      background: "#FAF7F2",
      border: `1.5px solid ${backend.fan_out_warning ? "#B42318" : typeColor}28`,
      borderRadius: 3, padding: "16px 20px", marginBottom: 16,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", marginBottom: 14, gap: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", textTransform: "uppercase", letterSpacing: 1, flex: 1 }}>
          Memory Backend
        </div>
        <span style={{
          fontSize: 10, fontWeight: 700, color: typeColor,
          background: `${typeColor}18`, border: `1px solid ${typeColor}44`,
          borderRadius: 3, padding: "2px 8px", fontFamily: "monospace",
        }}>
          {backend.type}
        </span>
        <button onClick={runBench} disabled={benching}
          style={{ padding: "4px 10px", borderRadius: 3, fontSize: 11, fontWeight: 600, fontFamily: "inherit", background: "#1E5A8A18", color: "#1E5A8A", border: "1px solid #1E5A8A44", cursor: benching ? "wait" : "pointer" }}>
          {benching ? "Running…" : "⏱ Benchmark"}
        </button>
        {isSqlite && (
          <button onClick={promote} disabled={promoting}
            style={{ padding: "4px 10px", borderRadius: 3, fontSize: 11, fontWeight: 600, fontFamily: "inherit", background: "#15803D18", color: "#15803D", border: "1px solid #15803D44", cursor: promoting ? "wait" : "pointer" }}>
            {promoting ? "Promoting…" : "⚡ Promote to FAISS"}
          </button>
        )}
      </div>

      {/* Info grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 14 }}>
        <div style={{ background: "#F4F0E8", borderRadius: 3, padding: "10px 14px", border: "1px solid #E0D6C422" }}>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#2E2010", fontFamily: "monospace" }}>{total.toLocaleString()}</div>
          <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 2 }}>Total entries</div>
        </div>
        {isFaiss && backend.index_ntotal != null && (
          <div style={{ background: "#F4F0E8", borderRadius: 3, padding: "10px 14px", border: `1px solid ${driftOk ? "#E0D6C422" : "#9A6C0044"}` }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: driftOk ? "#15803D" : "#9A6C00", fontFamily: "monospace" }}>{backend.index_ntotal.toLocaleString()}</div>
            <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 2 }}>FAISS index vectors</div>
            <div style={{ fontSize: 9, color: driftOk ? "#15803D" : "#9A6C00", marginTop: 2 }}>{backend.drift_pct}% drift {driftOk ? "✓" : "⚠"}</div>
          </div>
        )}
        {isFaiss && backend.index_size_mb != null && (
          <div style={{ background: "#F4F0E8", borderRadius: 3, padding: "10px 14px", border: "1px solid #E0D6C422" }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#1E5A8A", fontFamily: "monospace" }}>{backend.index_size_mb} MB</div>
            <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 2 }}>Index file size</div>
          </div>
        )}
        {bench && bench.search_p50_ms != null && (
          <div style={{ background: "#F4F0E8", borderRadius: 3, padding: "10px 14px", border: `1px solid ${searchColor}33` }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: searchColor, fontFamily: "monospace" }}>{bench.search_p50_ms} ms</div>
            <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 2 }}>Vector search P50 (target ≤{bench.search_target_ms}ms)</div>
            <div style={{ fontSize: 9, color: searchColor, marginTop: 2 }}>{searchPassing ? "✓ Passing" : "⚠ Above target"} · P95: {bench.search_p95_ms}ms</div>
          </div>
        )}
        {bench && bench.total_p50_ms != null && (
          <div style={{ background: "#F4F0E8", borderRadius: 3, padding: "10px 14px", border: `1px solid ${totalColor}33` }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: totalColor, fontFamily: "monospace" }}>{bench.total_p50_ms} ms</div>
            <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 2 }}>Full pipeline P50</div>
            <div style={{ fontSize: 9, color: "#9A7A60", marginTop: 2 }}>embed + search + re-rank</div>
          </div>
        )}
      </div>

      {/* Promotion threshold bar (SQLite only) */}
      {isSqlite && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: "#9A7A60" }}>Fan-out threshold ({total} / {threshold} entries)</span>
            <span style={{ fontSize: 11, color: progress >= 100 ? "#B42318" : "#9A6C00", fontFamily: "monospace" }}>{progress}%</span>
          </div>
          <div style={{ height: 5, background: "#E0D6C4", borderRadius: 3, overflow: "hidden" }}>
            <div style={{ width: `${progress}%`, height: "100%", background: progress >= 100 ? "#B42318" : "#9A6C00", borderRadius: 3, transition: "width 0.4s" }} />
          </div>
          {progress >= 80 && (
            <div style={{ fontSize: 10, color: "#9A6C00", marginTop: 5 }}>
              ⚠ Approaching FAISS threshold — auto-promote triggers at {threshold} entries
            </div>
          )}
        </div>
      )}

      {/* Engine detail */}
      <div style={{ fontSize: 11, color: "#9A7A60", lineHeight: 1.6 }}>
        Engine: <span style={{ color: "#0F766E" }}>{backend.engine || "—"}</span>
        {isFaiss && <span style={{ color: "#15803D", marginLeft: 12 }}>✓ O(log n) ANN · thread-safe · incremental updates</span>}
        {isSqlite && <span style={{ color: "#9A6C00", marginLeft: 12 }}>O(n) cosine scan · auto-promotes at {threshold} entries</span>}
      </div>

      {/* Benchmark summary */}
      {bench && (
        <div style={{ marginTop: 10, padding: "8px 12px", background: `${searchColor}0D`, border: `1px solid ${searchColor}33`, borderRadius: 3, fontSize: 11 }}>
          <span style={{ color: searchColor, fontWeight: 700 }}>
            {searchPassing ? "✓ Vector search passing" : "⚠ Vector search above target"}
          </span>
          <span style={{ color: "#9A7A60", marginLeft: 10 }}>
            {bench.n_queries} queries · {bench.entry_count} entries · {bench.embed_note}
          </span>
        </div>
      )}
      {promoteMsg && (
        <div style={{ marginTop: 10, padding: "7px 12px", background: "#15803D10", border: "1px solid #15803D33", borderRadius: 3, fontSize: 11, color: "#15803D" }}>
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
            style={{ padding: "7px 14px", borderRadius: 4, fontSize: 12, fontWeight: 700, background: "#1E5A8A22", color: "#1E5A8A", border: "1px solid #1E5A8A44", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 5 }}>
            ⬇ JSONL
          </a>
          <button onClick={rebuild} disabled={rebuilding}
            style={{ padding: "7px 14px", borderRadius: 4, fontSize: 12, fontWeight: 700, fontFamily: "inherit", background: "#9A6C0022", color: "#9A6C00", border: "1px solid #9A6C0044", cursor: rebuilding ? "wait" : "pointer" }}>
            {rebuilding ? "Rebuilding…" : "⟳ Rebuild"}
          </button>
          <button onClick={load} disabled={loading}
            style={{ padding: "7px 14px", borderRadius: 4, fontSize: 12, fontWeight: 700, fontFamily: "inherit", background: "#15803D22", color: "#15803D", border: "1px solid #15803D44", cursor: "pointer" }}>
            {loading ? "…" : "↻ Refresh"}
          </button>
        </div>
      </PageHeader>

      {/* Coverage stats */}
      {stats && (
        <div className="lux-card" style={{ padding: "16px 20px", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
            <StatCard label="Total traces"    value={stats.total}            color="#1E5A8A" />
            <StatCard label="Real sessions"   value={stats.real_sessions}    color="#15803D" />
            <StatCard label="Eval decisions"  value={stats.eval_decisions}   color="#9A7A60" />
            <StatCard label="Avg quality"     value={stats.avg_quality_proxy?.toFixed(3)} color="#9A6C00" />
            <StatCard label="Avg memories/q"  value={stats.avg_memories_per_query?.toFixed(1)} color="#0F766E" sub="fan-out signal" />
            <StatCard label="Avg regret"      value={stats.avg_regret?.toFixed(4)} color={stats.avg_regret > 0.1 ? "#B42318" : "#9A7A60"} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: "#9A7A60", marginBottom: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>Signal Coverage</div>
              {stats.coverage && Object.entries({
                "Has response":   [stats.coverage.response_pct,   "#15803D"],
                "Has memory":     [stats.coverage.memory_pct,     "#0F766E"],
                "Has reflection": [stats.coverage.reflection_pct, "#BE185D"],
                "Has conflict":   [stats.coverage.conflict_pct,   "#B42318"],
                "Has feedback":   [stats.coverage.feedback_pct,   "#9A6C00"],
              }).map(([lbl, [pct, col]]) => (
                <CovBar key={lbl} label={lbl} pct={pct} color={col} />
              ))}
            </div>
            <div>
              <div style={{ fontSize: 11, color: "#9A7A60", marginBottom: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>Agent Distribution</div>
              {stats.agent_distribution && Object.entries(stats.agent_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([agent, n]) => {
                  const pct = n / stats.total;
                  const m = AGENT_META[agent] || { color: "#9A7A60" };
                  return (
                    <div key={agent} style={{ marginBottom: 5 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                        <span style={{ fontSize: 11, color: "#9A7A60" }}>{agent.replace(/_/g, " ")}</span>
                        <span style={{ fontSize: 11, color: m.color, fontFamily: "monospace" }}>{n} ({(pct*100).toFixed(0)}%)</span>
                      </div>
                      <div style={{ height: 3, background: "#E0D6C4", borderRadius: 2, overflow: "hidden" }}>
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
