import { useState, useEffect, useCallback } from "react";
import { API } from "./api";
import { T } from "./theme";
import { PageHeader, RefreshBtn } from "./ObsShared";

// Local palette — theme tokens plus the few named colors this view references.
// (Previously aliased `T as C`, but T has no card/blue/green/yellow/red/purple,
//  so type badges and score dots silently fell back to muted/undefined.)
const C = {
  ...T,
  card:   T.surface,
  green:  T.success,
  red:    T.error,
  yellow: T.warn,
  blue:   "#1E5A8A",
  purple: "#7E3F8F",
};


const AGENT_COLORS = {
  python_dev:       "#C48808",
  it_networking:    "#047857",
  dotnet_dev:       "#6D28D9",
  ai_ml:            "#9A6C00",
  knowledge_learning: "#BE185D",
  terse:            "#9A7A60",
};
const AGENT_ICONS  = {
  python_dev: "🐍", it_networking: "🌐", dotnet_dev: "⚡",
  ai_ml: "🤖", knowledge_learning: "📚", terse: "🎯",
};
const TYPE_COLORS  = {
  code: C.blue, lesson: C.green, reflection: C.yellow,
  chat: C.muted, failure: C.red, episodic: C.purple,
};

function TypeBadge({ type }) {
  const col = TYPE_COLORS[type] || C.muted;
  return (
    <span style={{ background: `${col}22`, border: `1px solid ${col}55`, color: col,
      borderRadius: 99, padding: "2px 8px", fontSize: 10, fontFamily: "monospace" }}>
      {type}
    </span>
  );
}

function ScoreDot({ score }) {
  const col = score >= 0.80 ? C.green : score >= 0.60 ? C.yellow : C.red;
  return <span style={{ width: 8, height: 8, borderRadius: "50%", background: col, display: "inline-block" }} />;
}

function MemoryCard({ mem, expanded, onToggle }) {
  return (
    <div
      onClick={onToggle}
      style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8,
        padding: "10px 13px", cursor: "pointer", transition: "border-color .15s",
        borderColor: expanded ? AGENT_COLORS[mem.agent] || C.muted : C.border }}
    >
      <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: expanded ? 6 : 0 }}>
        <ScoreDot score={mem.quality || 0} />
        <TypeBadge type={mem.type} />
        <span style={{ fontSize: 10, color: C.muted, fontFamily: "monospace" }}>
          q={mem.quality?.toFixed(2)}
        </span>
        <span style={{ flex: 1, fontSize: 11, color: "#2E2010", marginLeft: 4,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: expanded ? "normal" : "nowrap" }}>
          {(mem.content || "").slice(0, expanded ? 600 : 80)}{!expanded && mem.content?.length > 80 ? "…" : ""}
        </span>
      </div>
      {expanded && (
        <div style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>
          id={mem.id}  ·  used {mem.use_count ?? 0}×  ·  {mem.timestamp?.slice(0, 16)}
        </div>
      )}
    </div>
  );
}

function AgentCluster({ agent, memories, typeFilter }) {
  const [collapsed, setCollapsed] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  const filtered = typeFilter === "all"
    ? memories
    : memories.filter(m => m.type === typeFilter);

  const color = AGENT_COLORS[agent] || C.muted;
  const icon  = AGENT_ICONS[agent]  || "●";
  const byType = {};
  memories.forEach(m => { byType[m.type] = (byType[m.type] || 0) + 1; });
  const avgQ = memories.length
    ? (memories.reduce((s, m) => s + (m.quality || 0), 0) / memories.length).toFixed(2)
    : "–";

  return (
    <div className="lux-card" style={{ overflow: "hidden", padding: 0 }}>
      {/* Header */}
      <button
        onClick={() => setCollapsed(c => !c)}
        style={{ width: "100%", display: "flex", gap: 10, alignItems: "center",
          padding: "12px 16px", background: "transparent", border: "none",
          cursor: "pointer", textAlign: "left", borderBottom: collapsed ? "none" : `1px solid ${C.border}` }}
      >
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color, flex: 1 }}>
          {agent.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
        </span>
        <span style={{ fontSize: 11, color: C.muted, fontFamily: "monospace" }}>
          {filtered.length}/{memories.length}  avg_q {avgQ}
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {Object.entries(byType).map(([t, n]) => (
            <span key={t} style={{ background: `${TYPE_COLORS[t] || C.muted}22`, color: TYPE_COLORS[t] || C.muted,
              border: `1px solid ${TYPE_COLORS[t] || C.muted}44`, borderRadius: 99, padding: "2px 7px", fontSize: 9 }}>
              {t}:{n}
            </span>
          ))}
        </div>
        <span style={{ color: C.muted, fontSize: 12 }}>{collapsed ? "▶" : "▼"}</span>
      </button>

      {!collapsed && (
        <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 4, maxHeight: 400, overflowY: "auto" }}>
          {filtered.length === 0 ? (
            <div style={{ color: C.muted, fontSize: 12 }}>No memories for this filter.</div>
          ) : (
            filtered.map(mem => (
              <MemoryCard
                key={mem.id}
                mem={mem}
                expanded={expandedId === mem.id}
                onToggle={() => setExpandedId(prev => prev === mem.id ? null : mem.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default function CognitiveMapTab() {
  const [rawMem,      setRawMem]      = useState([]);
  const [stats,       setStats]       = useState(null);
  const [typeFilter,  setTypeFilter]  = useState("all");
  const [agentFilter, setAgentFilter] = useState("all");
  const [searchQ,     setSearchQ]     = useState("");
  const [loading,     setLoading]     = useState(true);
  const [err,         setErr]         = useState(null);

  const load = useCallback(async () => {
    try {
      const [mem, st] = await Promise.all([
        fetch(`${API}/memory/records?limit=400`).then(r => r.json()),
        fetch(`${API}/memory/stats`).then(r => r.json()),
      ]);
      const list = Array.isArray(mem) ? mem : [];
      setRawMem(list);
      setStats(st);
      setErr(null);
    } catch (e) {
      setErr(`Failed to load: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ color: C.muted, padding: 40, textAlign: "center" }}>Loading knowledge map…</div>;
  if (err)     return <div style={{ color: C.red, padding: 20, fontFamily: "monospace" }}>{err}<br/><button onClick={load} style={{color:C.green,background:"transparent",border:"none",cursor:"pointer",marginTop:8}}>Retry</button></div>;

  // Group by agent
  const grouped = {};
  rawMem.forEach(m => {
    const a = m.agent || m.agent_name || "unknown";
    if (!grouped[a]) grouped[a] = [];
    grouped[a].push(m);
  });

  // Apply filters
  const allTypes  = ["all", ...new Set(rawMem.map(m => m.type || m.mem_type || "unknown"))];
  const allAgents = ["all", ...Object.keys(grouped).sort()];

  const visibleAgents = agentFilter === "all" ? Object.keys(grouped) : [agentFilter];

  // Search filter applied per-agent
  const searchFilter = m => {
    if (!searchQ.trim()) return true;
    const q = searchQ.toLowerCase();
    const content = (m.content || "").toLowerCase();
    return content.includes(q);
  };

  const totalVisible = visibleAgents.reduce((acc, a) => {
    const list = (grouped[a] || []).filter(m => (typeFilter === "all" || (m.type || m.mem_type) === typeFilter) && searchFilter(m));
    return acc + list.length;
  }, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, animation: "fadeIn .2s" }}>

      {/* ── Header ── */}
      <PageHeader
        title="Memory Map"
        subtitle={`${rawMem.length} memories across ${Object.keys(grouped).length} agents · ${totalVisible} visible`}
      >
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {stats && (
            <span style={{ fontFamily: "monospace", fontSize: 11, color: C.green }}>
              avg_q {stats.total ? (rawMem.reduce((s, m) => s + (m.quality || 0), 0) / rawMem.length).toFixed(3) : "–"}
            </span>
          )}
          {stats?.prune_candidates > 0 && (
            <span style={{ fontFamily: "monospace", fontSize: 11, color: C.red }}>
              {stats.prune_candidates} prunable
            </span>
          )}
          <RefreshBtn onClick={load} />
        </div>
      </PageHeader>

      {/* ── Filter bar ── */}
      <div className="lux-card" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", padding: "10px 14px" }}>
        <input
          value={searchQ} onChange={e => setSearchQ(e.target.value)}
          placeholder="Search memory content…"
          style={{ flex: 1, minWidth: 180, background: "transparent", border: "none", color: "#2E2010", fontSize: 13, outline: "none", fontFamily: "inherit" }}
        />
        {searchQ && <button onClick={() => setSearchQ("")} style={{ background: "transparent", border: "none", color: C.red, cursor: "pointer", fontSize: 13 }}>✕</button>}
        <span style={{ color: C.border }}>|</span>
        <span style={{ fontSize: 11, color: C.muted }}>type:</span>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {allTypes.map(t => (
            <button key={t} onClick={() => setTypeFilter(t)}
              style={{ background: typeFilter === t ? `${TYPE_COLORS[t] || C.green}33` : "transparent",
                border: `1px solid ${typeFilter === t ? (TYPE_COLORS[t] || C.green) : C.border}`,
                color: typeFilter === t ? (TYPE_COLORS[t] || C.green) : C.muted,
                borderRadius: 99, padding: "3px 11px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
              {t}
            </button>
          ))}
        </div>
        <span style={{ color: C.border }}>|</span>
        <select
          value={agentFilter} onChange={e => setAgentFilter(e.target.value)}
          style={{ background: C.bg, border: `1px solid ${C.border}`, color: "#2E2010", borderRadius: 8, padding: "4px 9px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}
        >
          {allAgents.map(a => <option key={a} value={a}>{a === "all" ? "All agents" : a.replace(/_/g, " ")}</option>)}
        </select>
      </div>

      {/* ── Agent clusters ── */}
      {visibleAgents.length === 0 ? (
        <div style={{ color: C.muted, textAlign: "center", padding: 30 }}>No memories found.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {visibleAgents.map(agent => {
            const mems = (grouped[agent] || []).filter(m =>
              (typeFilter === "all" || (m.type || m.mem_type) === typeFilter) && searchFilter(m)
            );
            if (mems.length === 0 && typeFilter !== "all") return null;
            // Normalise field names
            const norm = (grouped[agent] || []).map(m => ({
              ...m,
              type:    m.type    || m.mem_type    || "unknown",
              agent:   m.agent   || m.agent_name  || agent,
              content: m.content || "",
              quality: m.quality || 0,
            }));
            return (
              <AgentCluster
                key={agent}
                agent={agent}
                memories={norm}
                typeFilter={typeFilter}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
