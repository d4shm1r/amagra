import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "./ObsShared";

const API = "http://localhost:8000";

const AGENT_META = {
  coordinator:        { label: "Coordinator",  icon: "👑", color: "#9A6C00" },
  it_networking:      { label: "Networking",   icon: "🌐", color: "#15803D" },
  python_dev:         { label: "Python Dev",   icon: "🐍", color: "#C48808" },
  dotnet_dev:         { label: ".NET / Blazor", icon: "⚡", color: "#7C3AED" },
  ai_ml:              { label: "AI & ML",      icon: "🤖", color: "#BE185D" },
  knowledge_learning: { label: "Knowledge",    icon: "📚", color: "#1E5A8A" },
  terse:              { label: "Terse",        icon: "🎯", color: "#9A6C00" },
};

const TYPE_COLORS = {
  reflection: "#7E3F8F",
  code:       "#0F766E",
  lesson:     "#15803D",
  procedural: "#9A6C00",
  episodic:   "#1E5A8A",
  chat:       "#9A7A60",
  seed:       "#9A7A60",
  failure:    "#B42318",
  research:   "#C2410C",
  project:    "#15803D",
};

const SORT_OPTIONS = [
  { value: "quality",   label: "Quality ↓"  },
  { value: "use_count", label: "Most used"   },
  { value: "newest",    label: "Newest"      },
  { value: "oldest",    label: "Oldest"      },
];

function QualityBar({ quality }) {
  const pct   = Math.round((quality || 0) * 100);
  const color = pct >= 80 ? "#15803D" : pct >= 60 ? "#9A6C00" : "#B42318";
  return (
    <div style={{ height: 3, background: "#E0D6C4", borderRadius: 2, overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.3s" }} />
    </div>
  );
}

function Pill({ label, color, active, onClick }) {
  return (
    <span onClick={onClick} style={{
      fontSize: 10, fontWeight: 700, fontFamily: "monospace",
      background: active ? `${color}28` : `${color}12`,
      border: `1px solid ${active ? color + "88" : color + "33"}`,
      color: active ? color : color + "99",
      borderRadius: 4, padding: "1px 7px",
      cursor: onClick ? "pointer" : "default",
      transition: "all 0.15s", whiteSpace: "nowrap",
    }}>{label}</span>
  );
}

// ── Memory node position within an agent cluster ──────────────
function memPos(hubX, hubY, hubAngle, idx, total) {
  const FAN   = 0.78;
  const DISTS = [62, 79, 96];
  const ring  = Math.floor(idx / 3);
  const slot  = idx % 3;
  const inRing = Math.min(3, total - ring * 3);
  const spread = inRing <= 1 ? 0 : (slot / (inRing - 1) - 0.5) * FAN;
  const dist   = DISTS[Math.min(ring, 2)];
  return {
    x: hubX + dist * Math.cos(hubAngle + spread),
    y: hubY + dist * Math.sin(hubAngle + spread),
  };
}

// ── SVG knowledge graph ───────────────────────────────────────
function MemoryGraph({ records }) {
  const [hovered,  setHovered]  = useState(null);
  const [edges,    setEdges]    = useState([]);
  const [edgeLoad, setEdgeLoad] = useState(true);

  const MAX_PER = 9;
  const W = 860, H = 540, CX = 430, CY = 270, HUB_R = 175;

  // Group by agent, sort by quality, cap
  const byAgent = {};
  records.forEach(r => {
    if (!byAgent[r.agent]) byAgent[r.agent] = [];
    byAgent[r.agent].push(r);
  });
  const agentIds = Object.keys(byAgent).filter(a => byAgent[a].length > 0);
  const n = agentIds.length;

  // Hub positions
  const hubs = {};
  agentIds.forEach((agent, i) => {
    const θ = (i / n) * 2 * Math.PI - Math.PI / 2;
    const x = CX + HUB_R * Math.cos(θ);
    const y = CY + HUB_R * Math.sin(θ);
    hubs[agent] = { x, y, θ };
  });

  // Memory node positions
  const nodes = {};
  agentIds.forEach(agent => {
    const hub  = hubs[agent];
    const mems = [...byAgent[agent]]
      .sort((a, b) => (b.quality || 0) - (a.quality || 0))
      .slice(0, MAX_PER);
    mems.forEach((r, i) => {
      const pos = memPos(hub.x, hub.y, hub.θ, i, mems.length);
      nodes[r.id] = { ...pos, record: r, agent };
    });
  });

  // Load similarity edges async (only between displayed nodes)
  useEffect(() => {
    setEdgeLoad(true);
    fetch(`${API}/memory/consolidate?threshold=0.88`)
      .then(r => r.json())
      .then(d => {
        setEdges(
          (d.pairs || [])
            .filter(p => nodes[p.kept_id] && nodes[p.removed_id])
            .slice(0, 60)
        );
      })
      .catch(() => {})
      .finally(() => setEdgeLoad(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [records.length]);

  const hovNode = hovered != null ? nodes[hovered] : null;

  return (
    <div>
      <div style={{ position: "relative", background: "#F4F0E8", borderRadius: 6, overflow: "hidden" }}>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }}>
          {/* Soft radial glow at center */}
          <defs>
            <radialGradient id="centerGlow" cx="50%" cy="50%" r="25%">
              <stop offset="0%" stopColor="#C48808" stopOpacity="0.10" />
              <stop offset="100%" stopColor="#C48808" stopOpacity="0" />
            </radialGradient>
          </defs>
          <ellipse cx={CX} cy={CY} rx={220} ry={140} fill="url(#centerGlow)" />

          {/* Spoke lines: center → agent hub */}
          {agentIds.map(agent => {
            const hub  = hubs[agent];
            const meta = AGENT_META[agent] || { color: "#9A7A60" };
            return (
              <line key={`spoke-${agent}`}
                x1={CX} y1={CY} x2={hub.x} y2={hub.y}
                stroke={meta.color} strokeWidth={0.6} opacity={0.18} />
            );
          })}

          {/* Similarity edges */}
          {edges.map((e, i) => {
            const a = nodes[e.kept_id], b = nodes[e.removed_id];
            if (!a || !b) return null;
            return (
              <line key={`edge-${i}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke="#1E5A8A" strokeWidth={0.7} opacity={0.22} />
            );
          })}

          {/* Memory nodes */}
          {Object.values(nodes).map(({ x, y, record }) => {
            const col  = TYPE_COLORS[record.type] || "#9A7A60";
            const r    = 4 + (record.quality || 0) * 5;
            const isH  = hovered === record.id;
            return (
              <circle key={record.id} cx={x} cy={y}
                r={isH ? r + 3 : r}
                fill={col} stroke={isH ? "#1F1408" : col}
                strokeWidth={isH ? 1.5 : 0.4} opacity={isH ? 1 : 0.8}
                style={{ cursor: "pointer", transition: "r 0.12s" }}
                onMouseEnter={() => setHovered(record.id)}
                onMouseLeave={() => setHovered(null)}
              />
            );
          })}

          {/* Agent hubs */}
          {agentIds.map(agent => {
            const hub  = hubs[agent];
            const meta = AGENT_META[agent] || { label: agent, icon: "🤖", color: "#9A7A60" };
            const cnt  = byAgent[agent].length;
            return (
              <g key={`hub-${agent}`}>
                <circle cx={hub.x} cy={hub.y} r={20}
                  fill={`${meta.color}1A`} stroke={meta.color} strokeWidth={1.4} />
                <text x={hub.x} y={hub.y + 5} textAnchor="middle" fontSize={13}>{meta.icon}</text>
                <text x={hub.x} y={hub.y + 33} textAnchor="middle" fontSize={9} fill={meta.color} fontFamily="monospace">
                  {meta.label}
                </text>
                <text x={hub.x} y={hub.y + 44} textAnchor="middle" fontSize={8} fill="#9A7A60" fontFamily="monospace">
                  {cnt} mem
                </text>
              </g>
            );
          })}

          {/* Center hub */}
          <circle cx={CX} cy={CY} r={30} fill="#FAF7F2" stroke="#E0D6C4" strokeWidth={1.2} />
          <text x={CX} y={CY - 7} textAnchor="middle" fontSize={8} fill="#9A7A60" fontFamily="monospace">KNOWLEDGE</text>
          <text x={CX} y={CY + 5} textAnchor="middle" fontSize={8} fill="#9A7A60" fontFamily="monospace">GRAPH</text>
          <text x={CX} y={CY + 17} textAnchor="middle" fontSize={9} fill="#0F766E" fontFamily="monospace">
            {Object.keys(nodes).length}
          </text>
        </svg>

        {/* Edge loading indicator */}
        {edgeLoad && (
          <div style={{ position: "absolute", top: 8, right: 10, fontSize: 10, color: "#9A7A60" }}>
            loading edges…
          </div>
        )}
        {!edgeLoad && edges.length > 0 && (
          <div style={{ position: "absolute", top: 8, right: 10, fontSize: 10, color: "#1E5A8A55" }}>
            {edges.length} similarity edges
          </div>
        )}
      </div>

      {/* Hover detail panel */}
      <div style={{
        marginTop: 8, minHeight: 64, background: "#FAF7F2",
        border: `1px solid ${hovNode ? (TYPE_COLORS[hovNode.record.type] || "#E0D6C4") + "55" : "#E0D6C4"}`,
        borderRadius: 4, padding: "10px 14px", transition: "border-color 0.2s",
      }}>
        {hovNode ? (
          <>
            <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
              <Pill label={hovNode.record.type} color={TYPE_COLORS[hovNode.record.type] || "#9A7A60"} />
              <Pill label={(AGENT_META[hovNode.agent] || {}).label || hovNode.agent}
                color={(AGENT_META[hovNode.agent] || { color: "#9A7A60" }).color} />
              <span style={{ marginLeft: "auto", display: "flex", gap: 8, fontSize: 10, color: "#9A7A60", alignItems: "center" }}>
                <span>q={hovNode.record.quality?.toFixed(3)}</span>
                <span>{hovNode.record.use_count}× used</span>
                <span style={{ color: "#E0D6C4" }}>id {hovNode.record.id}</span>
              </span>
            </div>
            <div style={{ fontSize: 12.5, color: "#2E2010", lineHeight: 1.55,
              fontFamily: "Charter, 'Source Serif Pro', Georgia, serif" }}>
              {(hovNode.record.content || "").slice(0, 260)}
              {hovNode.record.content?.length > 260 ? "…" : ""}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 12, color: "#9A7A60", paddingTop: 6 }}>
            Hover a node to inspect · Node size = quality · Color = memory type
          </div>
        )}
      </div>

      {/* Type legend */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
        {Object.entries(TYPE_COLORS).filter(([t]) => t !== "seed" && t !== "chat").map(([type, col]) => (
          <span key={type} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: "#9A7A60" }}>
            <svg width={8} height={8}><circle cx={4} cy={4} r={4} fill={col} /></svg>
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Retrieval audit view ──────────────────────────────────────
function AuditPanel() {
  const [audits,  setAudits]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExp]    = useState(null);

  useEffect(() => {
    fetch(`${API}/memory/audit?limit=30`)
      .then(r => r.json())
      .then(d => { setAudits(d.audits || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: "#9A7A60", padding: 30, textAlign: "center", fontSize: 12 }}>Loading audit log…</div>;
  if (!audits.length) return <div style={{ color: "#9A7A60", padding: 30, textAlign: "center", fontSize: 12 }}>No retrieval events recorded yet.</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 11, color: "#9A7A60", marginBottom: 4 }}>
        Most recent {audits.length} retrieval events — what queries triggered what memories.
      </div>
      {audits.map(ev => {
        const isOpen = expanded === ev.id;
        return (
          <div key={ev.id}
            onClick={() => setExp(isOpen ? null : ev.id)}
            style={{ background: "#FAF7F2", border: "1px solid #E0D6C4", borderRadius: 4,
              padding: "9px 13px", cursor: "pointer", transition: "border-color 0.15s",
              ...(isOpen ? { borderColor: "#C4880844" } : {}),
            }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: isOpen ? 8 : 0 }}>
              <span style={{ fontSize: 10, color: "#9A7A60", fontFamily: "monospace", whiteSpace: "nowrap" }}>
                {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "–"}
              </span>
              <span style={{ fontSize: 12.5, color: "#2E2010", flex: 1, overflow: "hidden",
                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ev.query || "(no query)"}
              </span>
              <span style={{ fontSize: 10, color: "#C48808", whiteSpace: "nowrap" }}>
                {ev.count} hit{ev.count !== 1 ? "s" : ""}
              </span>
              {ev.caller && (
                <span style={{ fontSize: 9, color: "#9A7A60", fontFamily: "monospace" }}>{ev.caller}</span>
              )}
            </div>
            {isOpen && (ev.retrieved || []).length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingTop: 4,
                borderTop: "1px solid #E0D6C4" }}>
                {ev.retrieved.map((r, i) => {
                  const col = TYPE_COLORS[r.type] || "#9A7A60";
                  return (
                    <div key={i} style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 11 }}>
                      <span style={{ width: 6, height: 6, borderRadius: "50%", background: col, flexShrink: 0 }} />
                      <span style={{ color: "#9A7A60", fontFamily: "monospace", width: 28 }}>#{r.id}</span>
                      <Pill label={r.type || "?"} color={col} />
                      <Pill label={(AGENT_META[r.agent] || { label: r.agent || "?", color: "#9A7A60" }).label}
                        color={(AGENT_META[r.agent] || { color: "#9A7A60" }).color} />
                      <span style={{ marginLeft: "auto", fontFamily: "monospace", color: "#15803D", fontSize: 10 }}>
                        {typeof r.weighted === "number" ? r.weighted.toFixed(4) : typeof r.score === "number" ? r.score.toFixed(4) : "–"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── At-risk strip ─────────────────────────────────────────────
function AtRiskStrip({ onDismiss }) {
  const [risks, setRisks] = useState(null);
  const [open,  setOpen]  = useState(false);

  useEffect(() => {
    fetch(`${API}/memory/at-risk?n=20`)
      .then(r => r.json())
      .then(d => { if ((d.at_risk || []).length > 0) setRisks(d.at_risk); })
      .catch(() => {});
  }, []);

  if (!risks) return null;

  return (
    <div style={{ background: "#F5EDD6", border: "1px solid #9A6C0044",
      borderRadius: 4, padding: "10px 14px", marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 13 }}>⚠</span>
        <span style={{ fontSize: 12, color: "#9A6C00", fontWeight: 600 }}>
          {risks.length} memories near prune threshold
        </span>
        <span style={{ fontSize: 11, color: "#9A7A60" }}>quality 0.55–0.70, low recall</span>
        <button onClick={() => setOpen(o => !o)}
          style={{ marginLeft: "auto", background: "transparent", border: "1px solid #9A6C0033",
            color: "#9A6C00", borderRadius: 3, padding: "3px 10px", fontSize: 10,
            cursor: "pointer", fontFamily: "inherit" }}>
          {open ? "Hide" : "Inspect"}
        </button>
        <button onClick={onDismiss}
          style={{ background: "transparent", border: "none", color: "#9A7A60", cursor: "pointer",
            fontSize: 14, padding: "0 4px", lineHeight: 1 }}>×</button>
      </div>
      {open && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
          {risks.map(r => {
            const col = r.quality >= 0.65 ? "#9A6C00" : "#B42318";
            return (
              <div key={r.id} style={{ display: "flex", gap: 8, alignItems: "center",
                fontSize: 11, background: "#F4F0E8", borderRadius: 3, padding: "5px 9px" }}>
                <span style={{ fontFamily: "monospace", color: "#9A7A60", width: 28 }}>#{r.id}</span>
                <Pill label={r.type} color={TYPE_COLORS[r.type] || "#9A7A60"} />
                <Pill label={(AGENT_META[r.agent] || { label: r.agent, color: "#9A7A60" }).label}
                  color={(AGENT_META[r.agent] || { color: "#9A7A60" }).color} />
                <span style={{ color: "#2E2010", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {(r.preview || "").slice(0, 80)}
                </span>
                <span style={{ fontFamily: "monospace", color: col, fontWeight: 700, flexShrink: 0 }}>
                  {r.quality.toFixed(3)}
                </span>
                <span style={{ fontSize: 10, color: "#9A7A60", flexShrink: 0 }}>{r.use_count}× used</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────
export default function KnowledgeGraph() {
  const [records,     setRecords]     = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [backend,     setBackend]     = useState(null);
  const [expanded,    setExpanded]    = useState(null);
  const [search,      setSearch]      = useState("");
  const [agentFilter, setAgentFilter] = useState("all");
  const [typeFilter,  setTypeFilter]  = useState("all");
  const [sortBy,      setSortBy]      = useState("quality");
  const [view,        setView]        = useState("cards"); // cards | graph | audit
  const [atRiskOff,   setAtRiskOff]   = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [recRes, beRes] = await Promise.all([
        fetch(`${API}/memory/records?limit=500`),
        fetch(`${API}/analysis/memory_backend`),
      ]);
      if (!recRes.ok) throw new Error(`HTTP ${recRes.status}`);
      const [recData, beData] = await Promise.all([recRes.json(), beRes.ok ? beRes.json() : Promise.resolve(null)]);
      setRecords(recData.records || []);
      setBackend(beData);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      setError("Cannot reach API — make sure the backend is running on port 8000.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 45_000);
    return () => clearInterval(id);
  }, [load]);

  const total      = records.length;
  const avgQuality = total > 0 ? (records.reduce((s, r) => s + (r.quality || 0), 0) / total) : 0;

  const byType  = {};
  const byAgent = {};
  records.forEach(r => {
    byType[r.type]   = (byType[r.type]   || 0) + 1;
    byAgent[r.agent] = (byAgent[r.agent] || 0) + 1;
  });

  const agentOptions = ["all", ...Object.keys(AGENT_META).filter(a => byAgent[a])];

  const filtered = records
    .filter(r => {
      if (agentFilter !== "all" && r.agent !== agentFilter) return false;
      if (typeFilter  !== "all" && r.type  !== typeFilter)  return false;
      if (search.trim()) {
        if (!(r.content || "").toLowerCase().includes(search.toLowerCase())) return false;
      }
      return true;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case "quality":   return (b.quality   || 0) - (a.quality   || 0);
        case "use_count": return (b.use_count || 0) - (a.use_count || 0);
        case "oldest":    return (a.id        || 0) - (b.id        || 0);
        default:          return (b.id        || 0) - (a.id        || 0);
      }
    });

  if (loading) return (
    <div style={{ textAlign: "center", padding: "60px 0", color: "#9A7A60" }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>📚</div>
      Loading memory records…
    </div>
  );

  if (error) return (
    <div style={{ padding: 20, background: "#F9E7E1", border: "1.5px solid #B4231855",
      borderRadius: 4, color: "#B42318", fontSize: 14 }}>
      ⚠ {error}
    </div>
  );

  const beType  = backend?.type || "–";
  const beColor = beType === "PgvectorBackend" ? "#15803D" : beType === "FAISSBackend" ? "#1E5A8A" : "#9A7A60";

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      <PageHeader title="Knowledge" subtitle="The semantic memory store — what Amagra has learned and how it's retrieved." />

      {/* ── Stats header ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 10, marginBottom: 14 }}>
        {[
          { label: "Total Memories",  value: total,                        color: "#1E5A8A" },
          { label: "Avg Quality",     value: avgQuality.toFixed(2),        color: "#15803D" },
          { label: "Memory Types",    value: Object.keys(byType).length,   color: "#0F766E" },
          { label: "Active Agents",   value: Object.keys(byAgent).length,  color: "#9A6C00" },
          { label: "Backend",         value: beType.replace("Backend",""), color: beColor,
            sub: backend?.engine?.split(" ").slice(0,3).join(" ") || "" },
        ].map(stat => (
          <div key={stat.label} className="lux-card lux-card-i" style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: stat.color, lineHeight: 1.1,
              fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em" }}>{stat.value}</div>
            <div style={{ fontSize: 10, fontWeight: 600, color: "#9A7A60", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 5 }}>{stat.label}</div>
            {stat.sub && <div style={{ fontSize: 9, color: "#9A7A60", marginTop: 3, opacity: 0.7 }}>{stat.sub}</div>}
          </div>
        ))}
      </div>

      {/* ── View tabs + export ── */}
      <div style={{ display: "flex", gap: 6, marginBottom: 14, alignItems: "center" }}>
        {[
          { id: "cards", label: "Cards" },
          { id: "graph", label: "Graph" },
          { id: "audit", label: "Retrieval Audit" },
        ].map(tab => (
          <button key={tab.id} onClick={() => setView(tab.id)}
            style={{ background: view === tab.id ? "#C4880822" : "transparent",
              border: `1px solid ${view === tab.id ? "#C4880888" : "#E0D6C4"}`,
              color: view === tab.id ? "#1E5A8A" : "#9A7A60",
              borderRadius: 3, padding: "6px 14px", fontSize: 12,
              cursor: "pointer", fontFamily: "inherit", fontWeight: view === tab.id ? 700 : 400,
              transition: "all 0.15s" }}>
            {tab.label}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <a href={`${API}/memory/export.csv`} download
            style={{ background: "#FAF7F2", border: "1px solid #E0D6C4", color: "#9A7A60",
              borderRadius: 3, padding: "6px 12px", fontSize: 11, textDecoration: "none",
              cursor: "pointer", whiteSpace: "nowrap" }}>
            ↓ Export CSV
          </a>
          <button onClick={load}
            style={{ background: "transparent", border: "1px solid #E0D6C4", borderRadius: 3,
              color: "#9A7A60", padding: "6px 12px", fontSize: 11, cursor: "pointer",
              fontFamily: "inherit", whiteSpace: "nowrap" }}>
            ↻ {lastUpdated ? `Updated ${lastUpdated}` : "Refresh"}
          </button>
        </div>
      </div>

      {/* ── At-risk strip (cards view only) ── */}
      {view === "cards" && !atRiskOff && <AtRiskStrip onDismiss={() => setAtRiskOff(true)} />}

      {/* ── Graph view ── */}
      {view === "graph" && <MemoryGraph records={records} />}

      {/* ── Audit view ── */}
      {view === "audit" && <AuditPanel />}

      {/* ── Cards view ── */}
      {view === "cards" && (
        <>
          {/* Type distribution bar */}
          <div style={{ background: "#FAF7F2", border: "1px solid #E0D6C4", borderRadius: 4,
            padding: "12px 16px", marginBottom: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#9A7A60", marginBottom: 8, letterSpacing: "0.1em" }}>
              TYPE DISTRIBUTION — click to filter
            </div>
            <div style={{ display: "flex", height: 14, borderRadius: 4, overflow: "hidden", gap: 2, marginBottom: 8 }}>
              {Object.entries(byType).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
                <div key={type} title={`${type}: ${count}`}
                  onClick={() => setTypeFilter(typeFilter === type ? "all" : type)}
                  style={{ flex: count, background: TYPE_COLORS[type] || "#9A7A60",
                    cursor: "pointer", minWidth: 4,
                    opacity: typeFilter === "all" || typeFilter === type ? 1 : 0.22,
                    transition: "opacity 0.18s" }} />
              ))}
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {Object.entries(byType).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
                <Pill key={type} label={`${type} (${count})`}
                  color={TYPE_COLORS[type] || "#9A7A60"}
                  active={typeFilter === type}
                  onClick={() => setTypeFilter(typeFilter === type ? "all" : type)} />
              ))}
            </div>
          </div>

          {/* Agent buttons */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
            {agentOptions.filter(a => a !== "all").map(agentId => {
              const meta = AGENT_META[agentId];
              return (
                <button key={agentId}
                  onClick={() => setAgentFilter(agentFilter === agentId ? "all" : agentId)}
                  style={{ display: "flex", alignItems: "center", gap: 5,
                    background: agentFilter === agentId ? `${meta.color}22` : "#FAF7F2",
                    border: `1px solid ${agentFilter === agentId ? meta.color + "66" : meta.color + "22"}`,
                    color: agentFilter === agentId ? meta.color : "#9A7A60",
                    borderRadius: 3, padding: "5px 10px", fontSize: 11,
                    cursor: "pointer", fontFamily: "inherit",
                    fontWeight: agentFilter === agentId ? 700 : 400, transition: "all 0.15s" }}>
                  <span>{meta.icon}</span>
                  <span>{meta.label}</span>
                  <span style={{ background: "#E0D6C4", borderRadius: 3, padding: "1px 5px", fontSize: 10 }}>
                    {byAgent[agentId] || 0}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Search + sort */}
          <div style={{ display: "flex", gap: 8, marginBottom: 14, alignItems: "center", flexWrap: "wrap" }}>
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search memory content…"
              style={{ flex: 1, minWidth: 200, background: "#FAF7F2", border: "1px solid #E0D6C4",
                borderRadius: 4, color: "#2E2010", padding: "8px 12px", fontSize: 13,
                fontFamily: "inherit", outline: "none" }}
              onFocus={e => e.target.style.borderColor = "#15803D55"}
              onBlur={e => e.target.style.borderColor = "#E0D6C4"} />
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              style={{ background: "#FAF7F2", border: "1px solid #E0D6C4", borderRadius: 4,
                color: "#2E2010", padding: "8px 10px", fontSize: 12,
                fontFamily: "inherit", outline: "none", cursor: "pointer" }}>
              {SORT_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            {(search || agentFilter !== "all" || typeFilter !== "all") && (
              <button onClick={() => { setSearch(""); setAgentFilter("all"); setTypeFilter("all"); }}
                style={{ background: "#B4231818", border: "1px solid #B4231844", color: "#B42318",
                  borderRadius: 3, padding: "8px 11px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
                ✕ Clear
              </button>
            )}
            <span style={{ fontSize: 11, color: "#9A7A60", whiteSpace: "nowrap" }}>
              {filtered.length} / {total}
            </span>
          </div>

          {/* Card grid */}
          {filtered.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "#9A7A60", fontSize: 13 }}>
              No memories match the current filters.
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 8 }}>
              {filtered.slice(0, 120).map(record => {
                const meta      = AGENT_META[record.agent] || { label: record.agent, icon: "🤖", color: "#9A7A60" };
                const typeColor = TYPE_COLORS[record.type] || "#9A7A60";
                const isOpen    = expanded === record.id;
                const qualPct   = Math.round((record.quality || 0) * 100);
                const qualColor = qualPct >= 80 ? "#15803D" : qualPct >= 60 ? "#9A6C00" : "#B42318";

                return (
                  <div key={record.id}
                    onClick={() => setExpanded(isOpen ? null : record.id)}
                    style={{ background: isOpen ? `${meta.color}07` : "#FAF7F2",
                      border: `1px solid ${isOpen ? meta.color + "55" : "#E0D6C4"}`,
                      borderRadius: 4, padding: "10px 13px", cursor: "pointer",
                      transition: "border-color 0.18s, background 0.18s" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 7, flexWrap: "wrap" }}>
                      <Pill label={record.type} color={typeColor} />
                      <Pill label={`${meta.icon} ${meta.label}`} color={meta.color} />
                      <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                        {record.use_count > 0 && (
                          <span style={{ fontSize: 10, color: "#9A7A60" }}>{record.use_count}× used</span>
                        )}
                        <span style={{ fontSize: 10, color: qualColor, fontFamily: "monospace", fontWeight: 700 }}>
                          {(record.quality || 0).toFixed(2)}
                        </span>
                        <span style={{ fontSize: 10, color: meta.color + "77" }}>{isOpen ? "▲" : "▼"}</span>
                      </span>
                    </div>
                    <QualityBar quality={record.quality} />
                    <div style={{ marginTop: 7, fontSize: 12.5, color: "#2E2010", lineHeight: 1.55,
                      wordBreak: "break-word", fontFamily: "Charter, 'Source Serif Pro', Georgia, serif" }}>
                      {isOpen
                        ? record.content
                        : `${(record.content || "").slice(0, 130)}${record.content?.length > 130 ? "…" : ""}`}
                    </div>
                    {isOpen && (
                      <div style={{ marginTop: 9, paddingTop: 7, borderTop: "1px solid #E0D6C4",
                        display: "flex", gap: 12, fontSize: 10, color: "#9A7A60", flexWrap: "wrap" }}>
                        <span>id {record.id}</span>
                        <span>quality <span style={{ color: qualColor, fontFamily: "monospace", fontWeight: 700 }}>
                          {(record.quality || 0).toFixed(3)}
                        </span></span>
                        <span>used {record.use_count || 0}×</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {filtered.length > 120 && (
            <div style={{ textAlign: "center", marginTop: 12, fontSize: 12, color: "#9A7A60" }}>
              Showing 120 of {filtered.length} — use filters or search to narrow down
            </div>
          )}
        </>
      )}
    </div>
  );
}
