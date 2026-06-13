import { useState, useEffect, useRef } from "react";
import { T, FONT_MONO } from "./theme";
import { ObsPanel, EventRow, RefreshBtn, EmptyState, eventMeta } from "./ObsShared";

const API = "http://localhost:8000";

const EVENT_CATEGORIES = [
  { id: "all",     label: "All" },
  { id: "plan",    label: "Plan",    match: t => t.startsWith("plan.") || t.startsWith("step.") },
  { id: "risk",    label: "Risk",    match: t => t.startsWith("risk.") || t.startsWith("reflection.") },
  { id: "query",   label: "Query",   match: t => t.startsWith("query.") || t.startsWith("agent.") || t.startsWith("response.") },
  { id: "memory",  label: "Memory",  match: t => t.startsWith("memory.") || t.startsWith("contradiction.") },
  { id: "learn",   label: "Learn",   match: t => t.startsWith("routing.") || t.startsWith("session.") },
];

// ── Count pills ───────────────────────────────────────────────
function CountPills({ counts }) {
  if (!counts || !Object.keys(counts).length) return null;
  const total = Object.values(counts).reduce((s, n) => s + n, 0);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 14 }}>
      <span style={{
        background: T.accent + "22", border: `1px solid ${T.accent}44`,
        color: T.accent, borderRadius: 3, padding: "2px 8px", fontSize: 11, fontFamily: FONT_MONO,
      }}>{total} total</span>
      {Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([type, n]) => {
          const meta = eventMeta(type);
          return (
            <span key={type} style={{
              background: T.surface2, border: `1px solid ${T.border}`,
              borderRadius: 3, padding: "2px 8px", fontSize: 10, color: T.muted,
              display: "inline-flex", alignItems: "center", gap: 4,
            }}>
              <span style={{ color: meta.color }}>{meta.icon}</span>
              {type.replace(/\./g, " ")}
              <span style={{ color: T.mutedLt, fontFamily: FONT_MONO }}>{n}</span>
            </span>
          );
        })}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────
export default function EventLogTab() {
  const [data,       setData]       = useState({ events: [], counts: {} });
  const [filter,     setFilter]     = useState("all");
  const [search,     setSearch]     = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const listRef = useRef(null);

  const load = () => {
    setLoading(true);
    fetch(`${API}/cos/events?n=200`)
      .then(r => r.json())
      .then(d => { setData(d || { events: [], counts: {} }); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); const id = setInterval(load, 10_000); return () => clearInterval(id); }, []);

  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [data, autoScroll]);

  const events = data.events || [];
  const counts = data.counts || {};

  const cat = EVENT_CATEGORIES.find(c => c.id === filter);
  const filtered = events.filter(e => {
    const type = e.event_type || "";
    if (filter !== "all" && cat?.match && !cat.match(type)) return false;
    if (search) {
      const q = search.toLowerCase();
      const payload = JSON.stringify(e.payload || "").toLowerCase();
      if (!type.toLowerCase().includes(q) && !payload.includes(q)) return false;
    }
    return true;
  });

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, color: T.text, fontSize: 18, fontWeight: 700 }}>Event Log</h2>
          <div style={{ color: T.muted, fontSize: 11, marginTop: 2 }}>
            Typed event stream from the cognitive runtime · auto-refresh 10s
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: T.muted, cursor: "pointer" }}>
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)}
              style={{ accentColor: T.accent }} />
            Auto-scroll
          </label>
          <RefreshBtn onClick={load} />
        </div>
      </div>

      {error && (
        <div style={{ color: T.error, background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 5, padding: "8px 14px", marginBottom: 14, fontSize: 12 }}>
          Backend unavailable: {error}
        </div>
      )}

      {/* Event counts */}
      <CountPills counts={counts} />

      {/* Filter bar */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 4 }}>
          {EVENT_CATEGORIES.map(c => (
            <button key={c.id} onClick={() => setFilter(c.id)} style={{
              background: filter === c.id ? T.accent + "33" : T.surface2,
              border: `1px solid ${filter === c.id ? T.accent : T.border}`,
              color: filter === c.id ? T.accent : T.muted,
              borderRadius: 4, padding: "4px 10px", fontSize: 11, cursor: "pointer",
            }}>{c.label}</button>
          ))}
        </div>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search events…"
          style={{
            background: T.surface2, border: `1px solid ${T.border}`, color: T.text,
            borderRadius: 4, padding: "4px 10px", fontSize: 11,
            outline: "none", minWidth: 160,
          }}
        />
        {(search || filter !== "all") && (
          <button onClick={() => { setSearch(""); setFilter("all"); }} style={{
            background: "transparent", border: `1px solid ${T.border}`,
            color: T.muted, borderRadius: 4, padding: "4px 8px", fontSize: 11, cursor: "pointer",
          }}>✕ Clear</button>
        )}
        <span style={{ fontSize: 11, color: T.muted, marginLeft: "auto" }}>
          {filtered.length} / {events.length}
        </span>
      </div>

      {/* Event list */}
      <ObsPanel>
        {loading && !events.length ? (
          <div style={{ color: T.muted, fontSize: 12, textAlign: "center", padding: 24 }}>Loading events…</div>
        ) : filtered.length ? (
          <div ref={listRef} style={{ maxHeight: "calc(100vh - 320px)", overflowY: "auto" }}>
            {filtered.map((e, i) => (
              <EventRow key={i} event={e} />
            ))}
          </div>
        ) : (
          <EmptyState msg={
            events.length === 0
              ? "No events yet — run a query to populate the event log."
              : "No events match this filter."
          } />
        )}
      </ObsPanel>

    </div>
  );
}
