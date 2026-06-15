import { useState, useEffect, useCallback } from "react";
import { T, LUX, GOLD, FONT_MONO } from "./theme";
import { RefreshBtn, EmptyState, PageHeader, MetricCard } from "./ObsShared";

const TYPES  = ["all", "code", "lesson", "episodic", "failure", "chat", "fact", "error"];
const AGENTS = ["all", "python_dev", "ai_ml", "it_networking", "dotnet_dev",
                "web_dev", "devops", "data_analyst", "writer",
                "knowledge_learning", "terse"];

const AGENT_COLOR = {
  python_dev:         "#1E5A8A",
  ai_ml:              "#1E5A8A",
  it_networking:      "#0F766E",
  dotnet_dev:         "#B05B3B",
  web_dev:            "#B45309",
  devops:             "#92702A",
  data_analyst:       "#1F7A5A",
  writer:             "#A23B7C",
  knowledge_learning: "#7E3F8F",
  terse:              "#9A7A60",
};

const TYPE_COLOR = {
  code:     "#1E5A8A",
  lesson:   "#7E3F8F",
  episodic: "#0F766E",
  failure:  "#B42318",
  chat:     "#9A7A60",
  fact:     "#DCDCAA",
  error:    "#B42318",
};

function qualityColor(q) {
  if (q >= 0.85) return T.success || "#2E7D32";
  if (q >= 0.60) return T.warn   || "#A16207";
  return T.error || "#B42318";
}

function QualityBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{
        width: 52, height: 4, borderRadius: 2,
        background: "#E5DCCC", overflow: "hidden", flexShrink: 0,
      }}>
        <div style={{
          width: `${pct}%`, height: "100%",
          background: qualityColor(value),
        }} />
      </div>
      <span style={{
        fontFamily: FONT_MONO, fontSize: 9,
        color: qualityColor(value), flexShrink: 0,
      }}>{pct}%</span>
    </div>
  );
}

function MemoryCard({ item, expanded, onToggle }) {
  // Unified palette: gold for types, muted for agent — semantic red only for
  // failure/error. Keeps the list calm and on-brand (no rainbow chips).
  const isBad = item.type === "failure" || item.type === "error";
  const ac = T.muted;
  const tc = isBad ? T.error : T.accent;
  const ts = item.timestamp
    ? new Date(item.timestamp).toLocaleString(undefined, {
        month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    : "—";

  return (
    <div
      onClick={onToggle}
      className="lux-card lux-card-i"
      style={{
        padding: "13px 17px",
        cursor: "pointer",
        marginBottom: 10,
        borderColor: expanded ? GOLD.g2 + "66" : undefined,
        boxShadow: expanded
          ? "7px 7px 20px rgba(72,52,28,0.12), -3px -3px 11px rgba(255,255,255,0.75), inset 0 1px 1px rgba(255,255,255,0.92), 0 0 22px rgba(196,136,8,0.14)"
          : undefined,
      }}
    >
      {/* ── Header row ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{
          fontFamily: FONT_MONO, fontSize: 9, fontWeight: 700,
          color: tc, background: tc + "20",
          border: `1px solid ${tc}40`,
          borderRadius: 99, padding: "2px 8px",
          textTransform: "uppercase", letterSpacing: "0.06em",
          flexShrink: 0,
        }}>{item.type}</span>

        <span style={{
          fontFamily: FONT_MONO, fontSize: 9, color: ac, flexShrink: 0,
        }}>{item.agent}</span>

        <span style={{ flex: 1 }} />

        <QualityBar value={item.quality} />

        <span style={{
          fontFamily: FONT_MONO, fontSize: 9, color: T.muted,
          flexShrink: 0,
        }}>×{item.use_count || 0}</span>

        <span style={{
          fontFamily: FONT_MONO, fontSize: 9, color: T.muted,
          flexShrink: 0,
        }}>{ts}</span>

        <span style={{ color: T.muted, fontSize: 10, flexShrink: 0 }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {/* ── Content ── */}
      <div style={{
        fontSize: 12, color: T.mutedLt, lineHeight: 1.5,
        overflow: "hidden",
        display: expanded ? "block" : "-webkit-box",
        WebkitLineClamp: expanded ? undefined : 2,
        WebkitBoxOrient: expanded ? undefined : "vertical",
        whiteSpace: expanded ? "pre-wrap" : undefined,
        wordBreak: "break-word",
        minHeight: expanded ? undefined : 36,   // 2 lines → uniform row height
      }}>
        {item.content}
      </div>

      {expanded && (
        <div style={{
          marginTop: 8, paddingTop: 8,
          borderTop: `1px solid ${T.border}`,
          display: "flex", gap: 16,
          fontFamily: FONT_MONO, fontSize: 10, color: T.muted,
        }}>
          <span>id {item.id}</span>
          <span>quality {item.quality?.toFixed(3)}</span>
          <span>used {item.use_count} times</span>
        </div>
      )}
    </div>
  );
}

export default function MemoryBrowserTab() {
  const [records,    setRecords]    = useState([]);
  const [stats,      setStats]      = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [filterType, setFilterType] = useState("all");
  const [filterAgent,setFilterAgent]= useState("all");
  const [search,     setSearch]     = useState("");
  const [expanded,   setExpanded]   = useState(null);
  const [sortBy,     setSortBy]     = useState("newest"); // newest|quality|uses

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rRes, sRes] = await Promise.all([
        fetch("http://localhost:8000/memory/records?limit=500"),
        fetch("http://localhost:8000/memory/stats"),
      ]);
      if (rRes.ok) {
        const d = await rRes.json();
        setRecords(Array.isArray(d) ? d : []);
      }
      if (sRes.ok) setStats(await sRes.json());
    } catch (_) {}
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Filtering + sorting ───────────────────────────────────
  const q = search.trim().toLowerCase();
  const visible = records
    .filter(r =>
      (filterType  === "all" || r.type  === filterType)  &&
      (filterAgent === "all" || r.agent === filterAgent) &&
      (!q || r.content?.toLowerCase().includes(q))
    )
    .sort((a, b) => {
      if (sortBy === "quality") return (b.quality || 0) - (a.quality || 0);
      if (sortBy === "uses")    return (b.use_count || 0) - (a.use_count || 0);
      // newest: sort by id descending
      return b.id - a.id;
    });

  const toggleExpand = (id) => setExpanded(e => e === id ? null : id);

  // ── Stats strip ───────────────────────────────────────────
  const statItems = stats ? [
    { label: "total",       value: stats.total },
    { label: "never used",  value: stats.never_used },
    { label: "prune cands", value: stats.prune_candidates },
    { label: "showing",     value: visible.length },
  ] : [];

  return (
    <div style={{ color: T.text, fontFamily: "inherit" }}>

      {/* ── Header ── */}
      <PageHeader title="Memory" subtitle={`${records.length} records`} gold>
        <RefreshBtn onClick={fetchAll} />
      </PageHeader>

      {/* ── Stats ── */}
      {stats && (
        <>
          {/* Key numbers as calm luxe tiles */}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
            {statItems.map(({ label, value }) => (
              <div key={label} style={{ flex: "1 1 130px", minWidth: 130 }}>
                <MetricCard label={label} value={value} mono />
              </div>
            ))}
          </div>

          {/* Backend + type breakdown as soft pills */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
            {stats.backend && (
              <div style={{
                background: T.surface2 || "#FAF7F2",
                border: `1px solid ${(T.success || "#2E7D32") + "55"}`,
                borderRadius: 99, padding: "5px 13px",
                fontSize: 10, fontFamily: FONT_MONO,
              }}>
                <span style={{ color: T.success || "#2E7D32" }}>
                  {stats.backend.type === "FAISSBackend" ? "FAISS" : stats.backend.type}
                </span>
                <span style={{ color: T.muted }}>
                  {" "}· {stats.backend.total} records
                  {stats.backend.index_ntotal != null &&
                    stats.backend.index_ntotal !== stats.backend.total &&
                    ` (${stats.backend.index_ntotal} indexed)`}
                  {stats.backend.index_size_mb != null &&
                    ` · ${stats.backend.index_size_mb} MB`}
                </span>
                {stats.backend.total < 800 && (
                  <span style={{ color: T.muted }}>
                    {" "}· {800 - stats.backend.total} to FAISS promote
                  </span>
                )}
              </div>
            )}

            {stats.by_type && Object.entries(stats.by_type).map(([type, info]) => (
              <div key={type} style={{
                background: T.surface2 || "#FAF7F2",
                border: `1px solid ${T.border}`,
                borderRadius: 99, padding: "5px 13px",
                fontSize: 10, fontFamily: FONT_MONO,
              }}>
                <span style={{ color: TYPE_COLOR[type] || T.muted }}>{type} </span>
                <span style={{ color: T.text }}>{info.count}</span>
                <span style={{ color: T.muted }}> · q{(info.avg_quality * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Controls ── */}
      <div style={{
        display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12,
        alignItems: "center",
      }}>
        {/* Search */}
        <input
          type="text"
          placeholder="Search content…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            background: T.surface2 || "#FAF7F2",
            border: `1px solid ${T.border}`,
            borderRadius: 99, padding: "7px 14px",
            color: T.text, fontFamily: FONT_MONO, fontSize: 11,
            outline: "none", width: 220,
          }}
        />

        {/* Type filter */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {TYPES.filter(t => t === "all" || records.some(r => r.type === t)).map(t => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              style={{
                background: filterType === t
                  ? (TYPE_COLOR[t] || T.accent) + "30"
                  : (T.surface2 || "#FAF7F2"),
                border: `1px solid ${filterType === t
                  ? (TYPE_COLOR[t] || T.accent)
                  : T.border}`,
                borderRadius: 99, padding: "4px 12px",
                color: filterType === t
                  ? (TYPE_COLOR[t] || T.accent)
                  : T.muted,
                fontSize: 10, fontFamily: FONT_MONO,
                cursor: "pointer",
              }}
            >{t}</button>
          ))}
        </div>

        {/* Agent filter */}
        <select
          value={filterAgent}
          onChange={e => setFilterAgent(e.target.value)}
          style={{
            background: T.surface2 || "#FAF7F2",
            border: `1px solid ${T.border}`,
            borderRadius: 8, padding: "5px 10px",
            color: T.text, fontFamily: FONT_MONO, fontSize: 11,
            cursor: "pointer",
          }}
        >
          {AGENTS.filter(a => a === "all" || records.some(r => r.agent === a))
           .map(a => (
            <option key={a} value={a}>{a === "all" ? "all agents" : a}</option>
          ))}
        </select>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          style={{
            background: T.surface2 || "#FAF7F2",
            border: `1px solid ${T.border}`,
            borderRadius: 8, padding: "5px 10px",
            color: T.text, fontFamily: FONT_MONO, fontSize: 11,
            cursor: "pointer",
          }}
        >
          <option value="newest">newest first</option>
          <option value="quality">highest quality</option>
          <option value="uses">most used</option>
        </select>

        <span style={{
          marginLeft: "auto", fontSize: 10,
          color: T.muted, fontFamily: FONT_MONO,
        }}>
          {visible.length} / {records.length}
        </span>
      </div>

      {/* ── List ── */}
      {!loading && visible.length === 0 && (
        <EmptyState msg={
          records.length === 0
            ? "No memory records yet — run a query to populate memory"
            : "No records match the current filters"
        } />
      )}

      <div>
        {visible.map(item => (
          <MemoryCard
            key={item.id}
            item={item}
            expanded={expanded === item.id}
            onToggle={() => toggleExpand(item.id)}
          />
        ))}
      </div>

    </div>
  );
}
