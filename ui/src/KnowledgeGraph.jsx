import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "./ObsShared";
import { T, SEM, TYPE } from "./theme";

import { API } from "./api";
import { AGENTS } from "./constants";

// One source of truth for agent identity — constants.js AGENTS (unicode
// symbols + palette colors, never emoji). A local emoji copy had drifted.
const AGENT_META = Object.fromEntries(
  AGENTS.map(a => [a.id, { label: a.label, icon: a.icon, color: a.color }])
);

const TYPE_COLORS = {
  reflection: SEM.purple,
  code:       SEM.teal,
  lesson:     T.success,
  procedural: T.accent2,
  episodic:   SEM.blue,
  chat:       T.muted,
  seed:       T.muted,
  failure:    T.error,
  research:   "#C2410C",
  project:    T.success,
};

const SORT_OPTIONS = [
  { value: "quality",   label: "Quality ↓"  },
  { value: "use_count", label: "Most used"   },
  { value: "newest",    label: "Newest"      },
  { value: "oldest",    label: "Oldest"      },
];

function QualityBar({ quality }) {
  const pct   = Math.round((quality || 0) * 100);
  const color = pct >= 80 ? T.success : pct >= 60 ? T.accent2 : T.error;
  return (
    <div style={{ height: 3, background: T.border, borderRadius: 2, overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.3s" }} />
    </div>
  );
}

function Pill({ label, color, active, onClick }) {
  return (
    <span onClick={onClick} style={{
      ...TYPE.micro, fontWeight: 700, fontFamily: "monospace",
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
      <div style={{ position: "relative", background: T.surface2, borderRadius: 6, overflow: "hidden" }}>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }}>
          {/* Soft radial glow at center */}
          <defs>
            <radialGradient id="centerGlow" cx="50%" cy="50%" r="25%">
              <stop offset="0%" stopColor={T.accent} stopOpacity="0.10" />
              <stop offset="100%" stopColor={T.accent} stopOpacity="0" />
            </radialGradient>
          </defs>
          <ellipse cx={CX} cy={CY} rx={220} ry={140} fill="url(#centerGlow)" />

          {/* Spoke lines: center → agent hub */}
          {agentIds.map(agent => {
            const hub  = hubs[agent];
            const meta = AGENT_META[agent] || { color: T.muted };
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
                stroke={SEM.blue} strokeWidth={0.7} opacity={0.22} />
            );
          })}

          {/* Memory nodes */}
          {Object.values(nodes).map(({ x, y, record }) => {
            const col  = TYPE_COLORS[record.type] || T.muted;
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
            const meta = AGENT_META[agent] || { label: agent, icon: "◈", color: T.muted };
            const cnt  = byAgent[agent].length;
            return (
              <g key={`hub-${agent}`}>
                <circle cx={hub.x} cy={hub.y} r={20}
                  fill={`${meta.color}1A`} stroke={meta.color} strokeWidth={1.4} />
                <text x={hub.x} y={hub.y + 5} textAnchor="middle" fontSize={13}>{meta.icon}</text>
                <text x={hub.x} y={hub.y + 33} textAnchor="middle" fontSize={9} fill={meta.color} fontFamily="monospace">
                  {meta.label}
                </text>
                <text x={hub.x} y={hub.y + 44} textAnchor="middle" fontSize={8} fill={T.muted} fontFamily="monospace">
                  {cnt} mem
                </text>
              </g>
            );
          })}

          {/* Center hub */}
          <circle cx={CX} cy={CY} r={30} fill={T.surface} stroke={T.border} strokeWidth={1.2} />
          <text x={CX} y={CY - 7} textAnchor="middle" fontSize={8} fill={T.muted} fontFamily="monospace">KNOWLEDGE</text>
          <text x={CX} y={CY + 5} textAnchor="middle" fontSize={8} fill={T.muted} fontFamily="monospace">GRAPH</text>
          <text x={CX} y={CY + 17} textAnchor="middle" fontSize={9} fill={SEM.teal} fontFamily="monospace">
            {Object.keys(nodes).length}
          </text>
        </svg>

        {/* Edge loading indicator */}
        {edgeLoad && (
          <div style={{ position: "absolute", top: 8, right: 10, ...TYPE.micro, color: T.muted }}>
            loading edges…
          </div>
        )}
        {!edgeLoad && edges.length > 0 && (
          <div style={{ position: "absolute", top: 8, right: 10, ...TYPE.micro, color: `${SEM.blue}55` }}>
            {edges.length} similarity edges
          </div>
        )}
      </div>

      {/* Hover detail panel */}
      <div style={{
        marginTop: 8, minHeight: 64, background: T.surface,
        border: `1px solid ${hovNode ? (TYPE_COLORS[hovNode.record.type] || T.border) + "55" : T.border}`,
        borderRadius: 4, padding: "10px 14px", transition: "border-color 0.2s",
      }}>
        {hovNode ? (
          <>
            <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
              <Pill label={hovNode.record.type} color={TYPE_COLORS[hovNode.record.type] || T.muted} />
              <Pill label={(AGENT_META[hovNode.agent] || {}).label || hovNode.agent}
                color={(AGENT_META[hovNode.agent] || { color: T.muted }).color} />
              <span style={{ marginLeft: "auto", display: "flex", gap: 8, ...TYPE.micro, color: T.muted, alignItems: "center" }}>
                <span>q={hovNode.record.quality?.toFixed(3)}</span>
                <span>{hovNode.record.use_count}× used</span>
                <span style={{ color: T.border }}>id {hovNode.record.id}</span>
              </span>
            </div>
            <div style={{ ...TYPE.small, color: T.text, lineHeight: 1.55,
              fontFamily: "Charter, 'Source Serif Pro', Georgia, serif" }}>
              {(hovNode.record.content || "").slice(0, 260)}
              {hovNode.record.content?.length > 260 ? "…" : ""}
            </div>
          </>
        ) : (
          <div style={{ ...TYPE.caption, color: T.muted, paddingTop: 6 }}>
            Hover a node to inspect · Node size = quality · Color = memory type
          </div>
        )}
      </div>

      {/* Type legend */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
        {Object.entries(TYPE_COLORS).filter(([t]) => t !== "seed" && t !== "chat").map(([type, col]) => (
          <span key={type} style={{ display: "flex", alignItems: "center", gap: 4, ...TYPE.micro, color: T.muted }}>
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

  if (loading) return <div style={{ color: T.muted, padding: 30, textAlign: "center", ...TYPE.caption }}>Loading audit log…</div>;
  if (!audits.length) return <div style={{ color: T.muted, padding: 30, textAlign: "center", ...TYPE.caption }}>No retrieval events recorded yet.</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ ...TYPE.caption, color: T.muted, marginBottom: 4 }}>
        Most recent {audits.length} retrieval events — what queries triggered what memories.
      </div>
      {audits.map(ev => {
        const isOpen = expanded === ev.id;
        return (
          <div key={ev.id}
            onClick={() => setExp(isOpen ? null : ev.id)}
            style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 4,
              padding: "9px 13px", cursor: "pointer", transition: "border-color 0.15s",
              ...(isOpen ? { borderColor: `${T.accent}44` } : {}),
            }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: isOpen ? 8 : 0 }}>
              <span style={{ ...TYPE.micro, color: T.muted, fontFamily: "monospace", whiteSpace: "nowrap" }}>
                {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "–"}
              </span>
              <span style={{ ...TYPE.small, color: T.text, flex: 1, overflow: "hidden",
                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ev.query || "(no query)"}
              </span>
              <span style={{ ...TYPE.micro, color: T.accent, whiteSpace: "nowrap" }}>
                {ev.count} hit{ev.count !== 1 ? "s" : ""}
              </span>
              {ev.caller && (
                <span style={{ ...TYPE.micro, color: T.muted, fontFamily: "monospace" }}>{ev.caller}</span>
              )}
            </div>
            {isOpen && (ev.retrieved || []).length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingTop: 4,
                borderTop: `1px solid ${T.border}` }}>
                {ev.retrieved.map((r, i) => {
                  const col = TYPE_COLORS[r.type] || T.muted;
                  return (
                    <div key={i} style={{ display: "flex", gap: 6, alignItems: "center", ...TYPE.caption }}>
                      <span style={{ width: 6, height: 6, borderRadius: "50%", background: col, flexShrink: 0 }} />
                      <span style={{ color: T.muted, fontFamily: "monospace", width: 28 }}>#{r.id}</span>
                      <Pill label={r.type || "?"} color={col} />
                      <Pill label={(AGENT_META[r.agent] || { label: r.agent || "?", color: T.muted }).label}
                        color={(AGENT_META[r.agent] || { color: T.muted }).color} />
                      <span style={{ marginLeft: "auto", fontFamily: "monospace", color: T.success, ...TYPE.micro }}>
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
    <div style={{ background: "#F5EDD6", border: `1px solid ${T.accent2}44`,
      borderRadius: 4, padding: "10px 14px", marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ ...TYPE.small }}>⚠</span>
        <span style={{ ...TYPE.caption, color: T.accent2, fontWeight: 600 }}>
          {risks.length} memories near prune threshold
        </span>
        <span style={{ ...TYPE.caption, color: T.muted }}>quality 0.55–0.70, low recall</span>
        <button onClick={() => setOpen(o => !o)}
          style={{ marginLeft: "auto", background: "transparent", border: `1px solid ${T.accent2}33`,
            color: T.accent2, borderRadius: 3, padding: "3px 10px", ...TYPE.micro,
            cursor: "pointer", fontFamily: "inherit" }}>
          {open ? "Hide" : "Inspect"}
        </button>
        <button onClick={onDismiss}
          style={{ background: "transparent", border: "none", color: T.muted, cursor: "pointer",
            ...TYPE.body, padding: "0 4px", lineHeight: 1 }}>×</button>
      </div>
      {open && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
          {risks.map(r => {
            const col = r.quality >= 0.65 ? T.accent2 : T.error;
            return (
              <div key={r.id} style={{ display: "flex", gap: 8, alignItems: "center",
                ...TYPE.caption, background: T.surface2, borderRadius: 3, padding: "5px 9px" }}>
                <span style={{ fontFamily: "monospace", color: T.muted, width: 28 }}>#{r.id}</span>
                <Pill label={r.type} color={TYPE_COLORS[r.type] || T.muted} />
                <Pill label={(AGENT_META[r.agent] || { label: r.agent, color: T.muted }).label}
                  color={(AGENT_META[r.agent] || { color: T.muted }).color} />
                <span style={{ color: T.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {(r.preview || "").slice(0, 80)}
                </span>
                <span style={{ fontFamily: "monospace", color: col, fontWeight: 700, flexShrink: 0 }}>
                  {r.quality.toFixed(3)}
                </span>
                <span style={{ ...TYPE.micro, color: T.muted, flexShrink: 0 }}>{r.use_count}× used</span>
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
    <div style={{ textAlign: "center", padding: "60px 0", color: T.muted }}>
      <div style={{ fontSize: 32, marginBottom: 12, color: T.accent }}>❧</div>
      Loading memory records…
    </div>
  );

  if (error) return (
    <div style={{ padding: 20, background: "#F9E7E1", border: `1.5px solid ${T.error}55`,
      borderRadius: 4, color: T.error, ...TYPE.body }}>
      ⚠ {error}
    </div>
  );

  const beType  = backend?.type || "–";
  const beColor = beType === "PgvectorBackend" ? T.success : beType === "FAISSBackend" ? SEM.blue : T.muted;

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      <PageHeader center title="Knowledge" subtitle="The semantic memory store — what Amagra has learned and how it's retrieved." />

      {/* ── Stats header ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 10, marginBottom: 14 }}>
        {[
          { label: "Total Memories",  value: total,                        color: SEM.blue },
          { label: "Avg Quality",     value: avgQuality.toFixed(2),        color: T.success },
          { label: "Memory Types",    value: Object.keys(byType).length,   color: SEM.teal },
          { label: "Active Agents",   value: Object.keys(byAgent).length,  color: T.accent2 },
          { label: "Backend",         value: beType.replace("Backend",""), color: beColor,
            sub: backend?.engine?.split(" ").slice(0,3).join(" ") || "" },
        ].map(stat => (
          <div key={stat.label} className="lux-card lux-card-i" style={{ padding: "14px 16px" }}>
            <div style={{ ...TYPE.metric, fontWeight: 700, color: stat.color, lineHeight: 1.1,
              fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em" }}>{stat.value}</div>
            <div style={{ ...TYPE.micro, fontWeight: 600, color: T.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 5 }}>{stat.label}</div>
            {stat.sub && <div style={{ ...TYPE.micro, color: T.muted, marginTop: 3, opacity: 0.7 }}>{stat.sub}</div>}
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
            style={{ background: view === tab.id ? `${T.accent}22` : "transparent",
              border: `1px solid ${view === tab.id ? `${T.accent}88` : T.border}`,
              color: view === tab.id ? SEM.blue : T.muted,
              borderRadius: 3, padding: "6px 14px", ...TYPE.caption,
              cursor: "pointer", fontFamily: "inherit", fontWeight: view === tab.id ? 700 : 400,
              transition: "all 0.15s" }}>
            {tab.label}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <a href={`${API}/memory/export.csv`} download
            style={{ background: T.surface, border: `1px solid ${T.border}`, color: T.muted,
              borderRadius: 3, padding: "6px 12px", ...TYPE.caption, textDecoration: "none",
              cursor: "pointer", whiteSpace: "nowrap" }}>
            ↓ Export CSV
          </a>
          <button onClick={load}
            style={{ background: "transparent", border: `1px solid ${T.border}`, borderRadius: 3,
              color: T.muted, padding: "6px 12px", ...TYPE.caption, cursor: "pointer",
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
          <div className="lux-card" style={{ padding: "12px 16px", marginBottom: 14 }}>
            <div style={{ ...TYPE.micro, fontWeight: 700, color: T.muted, marginBottom: 8, letterSpacing: "0.1em" }}>
              TYPE DISTRIBUTION — click to filter
            </div>
            <div style={{ display: "flex", height: 14, borderRadius: 4, overflow: "hidden", gap: 2, marginBottom: 8 }}>
              {Object.entries(byType).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
                <div key={type} title={`${type}: ${count}`}
                  onClick={() => setTypeFilter(typeFilter === type ? "all" : type)}
                  style={{ flex: count, background: TYPE_COLORS[type] || T.muted,
                    cursor: "pointer", minWidth: 4,
                    opacity: typeFilter === "all" || typeFilter === type ? 1 : 0.22,
                    transition: "opacity 0.18s" }} />
              ))}
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {Object.entries(byType).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
                <Pill key={type} label={`${type} (${count})`}
                  color={TYPE_COLORS[type] || T.muted}
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
                    background: agentFilter === agentId ? `${meta.color}22` : T.surface,
                    border: `1px solid ${agentFilter === agentId ? meta.color + "66" : meta.color + "22"}`,
                    color: agentFilter === agentId ? meta.color : T.muted,
                    borderRadius: 3, padding: "5px 10px", ...TYPE.caption,
                    cursor: "pointer", fontFamily: "inherit",
                    fontWeight: agentFilter === agentId ? 700 : 400, transition: "all 0.15s" }}>
                  <span>{meta.icon}</span>
                  <span>{meta.label}</span>
                  <span style={{ background: T.border, borderRadius: 3, padding: "1px 5px", ...TYPE.micro }}>
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
              style={{ flex: 1, minWidth: 200, background: T.surface, border: `1px solid ${T.border}`,
                borderRadius: 4, color: T.text, padding: "8px 12px", ...TYPE.small,
                fontFamily: "inherit", outline: "none" }}
              onFocus={e => e.target.style.borderColor = `${T.success}55`}
              onBlur={e => e.target.style.borderColor = T.border} />
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 4,
                color: T.text, padding: "8px 10px", ...TYPE.caption,
                fontFamily: "inherit", outline: "none", cursor: "pointer" }}>
              {SORT_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            {(search || agentFilter !== "all" || typeFilter !== "all") && (
              <button onClick={() => { setSearch(""); setAgentFilter("all"); setTypeFilter("all"); }}
                style={{ background: `${T.error}18`, border: `1px solid ${T.error}44`, color: T.error,
                  borderRadius: 3, padding: "8px 11px", ...TYPE.caption, cursor: "pointer", fontFamily: "inherit" }}>
                ✕ Clear
              </button>
            )}
            <span style={{ ...TYPE.caption, color: T.muted, whiteSpace: "nowrap" }}>
              {filtered.length} / {total}
            </span>
          </div>

          {/* Card grid */}
          {filtered.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: T.muted, ...TYPE.small }}>
              No memories match the current filters.
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 8 }}>
              {filtered.slice(0, 120).map(record => {
                const meta      = AGENT_META[record.agent] || { label: record.agent, icon: "◈", color: T.muted };
                const typeColor = TYPE_COLORS[record.type] || T.muted;
                const isOpen    = expanded === record.id;
                const qualPct   = Math.round((record.quality || 0) * 100);
                const qualColor = qualPct >= 80 ? T.success : qualPct >= 60 ? T.accent2 : T.error;

                return (
                  <div key={record.id}
                    onClick={() => setExpanded(isOpen ? null : record.id)}
                    style={{ background: isOpen ? `${meta.color}07` : T.surface,
                      border: `1px solid ${isOpen ? meta.color + "55" : T.border}`,
                      borderRadius: 4, padding: "10px 13px", cursor: "pointer",
                      transition: "border-color 0.18s, background 0.18s" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 7, flexWrap: "wrap" }}>
                      <Pill label={record.type} color={typeColor} />
                      <Pill label={`${meta.icon} ${meta.label}`} color={meta.color} />
                      <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                        {record.use_count > 0 && (
                          <span style={{ ...TYPE.micro, color: T.muted }}>{record.use_count}× used</span>
                        )}
                        <span style={{ ...TYPE.micro, color: qualColor, fontFamily: "monospace", fontWeight: 700 }}>
                          {(record.quality || 0).toFixed(2)}
                        </span>
                        <span style={{ ...TYPE.micro, color: meta.color + "77" }}>{isOpen ? "▲" : "▼"}</span>
                      </span>
                    </div>
                    <QualityBar quality={record.quality} />
                    <div style={{ marginTop: 7, ...TYPE.small, color: T.text, lineHeight: 1.55,
                      wordBreak: "break-word", fontFamily: "Charter, 'Source Serif Pro', Georgia, serif" }}>
                      {isOpen
                        ? record.content
                        : `${(record.content || "").slice(0, 130)}${record.content?.length > 130 ? "…" : ""}`}
                    </div>
                    {isOpen && (
                      <div style={{ marginTop: 9, paddingTop: 7, borderTop: `1px solid ${T.border}`,
                        display: "flex", gap: 12, ...TYPE.micro, color: T.muted, flexWrap: "wrap" }}>
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
            <div style={{ textAlign: "center", marginTop: 12, ...TYPE.caption, color: T.muted }}>
              Showing 120 of {filtered.length} — use filters or search to narrow down
            </div>
          )}
        </>
      )}
    </div>
  );
}
