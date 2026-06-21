import { useState, useEffect, useCallback } from "react";
import { AGENTS } from "./constants";
import { T, FONT_DISPLAY } from "./theme";


const DOMAIN_COLORS = {
  networking:  "#15803D",
  python:      "#C48808",
  dotnet:      "#7C3AED",
  ai_ml:       "#BE185D",
  general:     "#9A7A60",
  factual:     "#9A6C00",
  knowledge:   "#1E5A8A",
};

function AgentChip({ id, size = 11 }) {
  const agent = AGENTS.find(a => a.id === id);
  if (!agent) return (
    <span style={{ fontSize: size, color: T.muted, fontFamily: "monospace" }}>{id}</span>
  );
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 7px", borderRadius: 3, fontSize: size,
      background: agent.color + "22", color: agent.color,
      border: `1px solid ${agent.color}44`, fontWeight: 700, whiteSpace: "nowrap",
    }}>
      {agent.icon} {agent.label.split(" ")[0]}
    </span>
  );
}

function SignalPill({ label, color }) {
  if (!label || label === "unknown") return null;
  return (
    <span style={{
      background: `${color}22`, border: `1px solid ${color}44`,
      color, borderRadius: 3, padding: "1px 6px", fontSize: 10,
      fontFamily: "monospace", fontWeight: 600, whiteSpace: "nowrap",
    }}>
      {label}
    </span>
  );
}

function AgentUsageSummary({ traces }) {
  const counts = {};
  traces.forEach(t => {
    const id = t.agent || "unknown";
    counts[id] = (counts[id] || 0) + 1;
  });
  const total = traces.length;
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  if (sorted.length === 0) return null;

  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${T.border}`,
      borderRadius: 4, padding: "12px 16px",
      marginBottom: 16,
    }}>
      <div style={{
        fontSize: 10, fontWeight: 700, color: T.muted,
        letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10,
      }}>
        Agent Usage — {total} traces
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {sorted.map(([id, n]) => {
          const agent = AGENTS.find(a => a.id === id);
          const color = agent?.color || T.muted;
          const pct   = total > 0 ? (n / total) : 0;
          return (
            <div key={id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, flexShrink: 0 }}>{agent?.icon || "●"}</span>
              <span style={{ fontSize: 11, color, fontWeight: 600, minWidth: 110, flexShrink: 0 }}>
                {(agent?.label || id).replace(/_/g, " ")}
              </span>
              <div style={{ flex: 1, height: 5, background: T.border, borderRadius: 3, overflow: "hidden" }}>
                <div style={{ width: `${pct * 100}%`, height: "100%", background: color, borderRadius: 3 }} />
              </div>
              <span style={{ fontSize: 11, color: T.muted, fontFamily: "monospace", minWidth: 28, textAlign: "right" }}>
                {n}
              </span>
              <span style={{ fontSize: 10, color: T.muted, fontFamily: "monospace", minWidth: 36, textAlign: "right" }}>
                {Math.round(pct * 100)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TraceCard({ t, idx }) {
  const agent  = AGENTS.find(a => a.id === t.agent);
  const ac     = agent?.color || T.muted;
  const domain = t.signal_domain || t.domain || "general";
  const domCol = DOMAIN_COLORS[domain] || T.muted;

  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${T.border}`,
      borderLeft: `3px solid ${ac}`,
      borderRadius: 3,
      padding: "10px 14px",
    }}>
      {/* Top row: agent + timestamp + duration */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <AgentChip id={t.agent} />
        {t.signal_domain && (
          <SignalPill label={t.signal_domain.replace(/_/g, " ")} color={domCol} />
        )}
        {t.signal_shape && (
          <SignalPill label={t.signal_shape} color="#7E3F8F" />
        )}
        {t.signal_conf != null && (
          <SignalPill label={`${Math.round(t.signal_conf * 100)}%`} color="#9A6C00" />
        )}
        <span style={{
          marginLeft: "auto", fontSize: 10, color: T.muted,
          fontFamily: "monospace", flexShrink: 0,
        }}>
          {t.duration_ms != null ? `${t.duration_ms}ms` : "—"}
          {t.timestamp ? ` · ${t.timestamp.slice(11, 19)}` : ""}
        </span>
      </div>

      {/* User message */}
      <div style={{
        fontSize: 12, color: T.mutedLt, marginBottom: t.routing_reason ? 5 : 0,
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      }}>
        {(t.user_message || "—").slice(0, 120)}{(t.user_message || "").length > 120 ? "…" : ""}
      </div>

      {/* Routing reason */}
      {t.routing_reason && (
        <div style={{ fontSize: 11, color: T.muted }}>
          <span style={{ color: T.warn, fontWeight: 700 }}>reason </span>
          {t.routing_reason}
        </div>
      )}
    </div>
  );
}

export default function TracesTab() {
  const [traces,      setTraces]      = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [agentFilter, setAgentFilter] = useState("all");
  const [search,      setSearch]      = useState("");

  const load = useCallback(() => {
    setLoading(true);
    fetch("http://localhost:8000/traces")
      .then(r => r.ok ? r.json() : { traces: [] })
      .then(d => { setTraces(d.traces || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const activeAgents = [...new Set(traces.map(t => t.agent).filter(Boolean))];

  const filtered = traces.filter(t => {
    if (agentFilter !== "all" && t.agent !== agentFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      if (!(t.user_message || "").toLowerCase().includes(q) &&
          !(t.routing_reason || "").toLowerCase().includes(q) &&
          !(t.agent || "").toLowerCase().includes(q)) return false;
    }
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", animation: "fadeIn .2s" }}>

      {/* ── Header ── */}
      <div style={{
        padding: "16px 24px 14px",
        borderBottom: `1px solid ${T.border}`,
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12 }}>
          <div>
            <div style={{ fontFamily: FONT_DISPLAY, fontSize: 24, fontWeight: 600, letterSpacing: "0.02em", color: T.text, marginBottom: 3 }}>
              Routing Signal Log
            </div>
            <div style={{ fontSize: 12, color: T.muted }}>
              Live routing decisions — agent selected, signal domain, confidence, and routing reason.
            </div>
          </div>
          <button
            onClick={load}
            style={{
              background: `${T.accent}18`, border: `1px solid ${T.accent}44`,
              color: T.accent, padding: "6px 14px", borderRadius: 3,
              fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
            }}
          >
            ↻ Refresh
          </button>
        </div>

        {/* Filter row */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search messages, reasons, agents…"
            style={{
              background: T.surface, border: `1px solid ${T.border}`,
              borderRadius: 3, color: T.text, padding: "5px 10px",
              fontSize: 12, fontFamily: "inherit", outline: "none", width: 220,
            }}
          />
          <button
            onClick={() => setAgentFilter("all")}
            style={{
              padding: "4px 10px", borderRadius: 3, fontSize: 11, fontFamily: "inherit",
              background: agentFilter === "all" ? `${T.accent}22` : "transparent",
              border: `1px solid ${agentFilter === "all" ? T.accent : T.border}`,
              color: agentFilter === "all" ? T.accent : T.muted,
              cursor: "pointer",
            }}
          >
            All
          </button>
          {activeAgents.map(id => {
            const agent  = AGENTS.find(a => a.id === id);
            const color  = agent?.color || T.muted;
            const active = agentFilter === id;
            return (
              <button
                key={id}
                onClick={() => setAgentFilter(active ? "all" : id)}
                style={{
                  padding: "4px 10px", borderRadius: 3, fontSize: 11, fontFamily: "inherit",
                  background: active ? `${color}22` : "transparent",
                  border: `1px solid ${active ? color + "66" : color + "22"}`,
                  color: active ? color : T.muted,
                  cursor: "pointer", whiteSpace: "nowrap",
                }}
              >
                {agent?.icon} {(agent?.label || id).split(" ")[0]}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px" }}>
        {loading ? (
          <div style={{ textAlign: "center", color: T.muted, fontSize: 13, paddingTop: 60 }}>
            Loading traces…
          </div>
        ) : traces.length === 0 ? (
          <div style={{ textAlign: "center", paddingTop: 60 }}>
            <div style={{ fontSize: 28, marginBottom: 10, opacity: 0.3 }}>⌘</div>
            <div style={{ fontSize: 13, color: T.muted }}>
              No traces yet — send a message in Chat to see routing decisions here.
            </div>
          </div>
        ) : (
          <>
            <AgentUsageSummary traces={traces} />
            {filtered.length === 0 ? (
              <div style={{ textAlign: "center", color: T.muted, fontSize: 13, paddingTop: 24 }}>
                No traces match this filter.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {filtered.map((t, i) => (
                  <TraceCard key={i} t={t} idx={i} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
