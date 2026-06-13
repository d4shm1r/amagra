import { useState, useEffect } from "react";
import { T, FONT_MONO } from "./theme";
import { ObsPanel, MetricCard, EventRow, RefreshBtn, EmptyState, hScore } from "./ObsShared";

const API = "http://localhost:8000";

// ── Entity badges ─────────────────────────────────────────────
function EntityBadge({ label }) {
  return (
    <span style={{
      background: T.accent + "18", border: `1px solid ${T.accent}44`,
      color: T.accent2, borderRadius: 3, padding: "2px 7px",
      fontSize: 11, fontFamily: FONT_MONO,
      marginRight: 4, marginBottom: 4, display: "inline-block",
    }}>{label}</span>
  );
}

// ── Project context card ──────────────────────────────────────
function ProjectCard({ world, uci }) {
  const proj = world?.project_context || {};
  const goal = world?.current_goal;

  return (
    <ObsPanel>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, color: T.muted, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 6 }}>
            Project
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: T.text, marginBottom: 4 }}>
            {proj.project_name || world?.context_summary || "Unknown project"}
          </div>
          {goal && (
            <div style={{ fontSize: 12, color: T.mutedLt }}>
              <span style={{ color: T.muted }}>Goal: </span>{goal}
            </div>
          )}
          {/* Context badges */}
          <div style={{ marginTop: 10 }}>
            {Object.entries(proj)
              .filter(([k, v]) => k !== "project_name" && v)
              .map(([k, v]) => (
                <EntityBadge key={k} label={`${k.replace(/_/g, " ")}: ${v}`} />
              ))}
          </div>
        </div>
        {uci != null && (
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{ fontSize: 10, color: T.muted }}>h_UCI</div>
            <div style={{
              fontFamily: FONT_MONO, fontSize: 32, fontWeight: 700,
              color: hScore(uci), lineHeight: 1,
            }}>{uci.toFixed(1)}</div>
            <div style={{ fontSize: 10, color: hScore(uci), marginTop: 2 }}>
              {uci >= 80 ? "Healthy" : uci >= 60 ? "Nominal" : "Degraded"}
            </div>
          </div>
        )}
      </div>
      {world?.updated_at && (
        <div style={{ fontSize: 10, color: T.muted, marginTop: 10, borderTop: `1px solid ${T.border}`, paddingTop: 8 }}>
          Updated {new Date(world.updated_at).toLocaleTimeString()}
        </div>
      )}
    </ObsPanel>
  );
}

// ── Tasks + Issues ────────────────────────────────────────────
function TasksPanel({ world }) {
  const completed = world?.completed_tasks?.slice(-8) || [];
  const issues    = world?.known_issues?.slice(-8) || [];

  if (!completed.length && !issues.length) return null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      <ObsPanel title="Completed" icon="✓">
        {completed.length ? (
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {completed.map((t, i) => (
              <li key={i} style={{ color: T.success, fontSize: 12, marginBottom: 4, lineHeight: 1.4 }}>{t}</li>
            ))}
          </ul>
        ) : <EmptyState msg="None yet." />}
      </ObsPanel>
      <ObsPanel title="Known Issues" icon="⚠">
        {issues.length ? (
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {issues.map((issue, i) => (
              <li key={i} style={{ color: T.warn, fontSize: 12, marginBottom: 4, lineHeight: 1.4 }}>{issue}</li>
            ))}
          </ul>
        ) : <EmptyState msg="None." />}
      </ObsPanel>
    </div>
  );
}

// ── Active plan ───────────────────────────────────────────────
function ActivePlan({ plan }) {
  if (!plan?.steps?.length) return null;

  return (
    <ObsPanel title="Active Plan" icon="◈"
      action={
        <span style={{ fontSize: 10, color: T.muted, fontFamily: FONT_MONO }}>
          {plan.mode} · u={plan.uncertainty?.toFixed(2)}
        </span>
      }
    >
      {plan.steps.map((step, i) => (
        <div key={step.step_id || i} style={{
          display: "flex", gap: 10, marginBottom: 8, alignItems: "flex-start",
          paddingBottom: 8,
          borderBottom: i < plan.steps.length - 1 ? `1px solid ${T.border}` : "none",
        }}>
          <span style={{ fontSize: 11, color: T.muted, fontFamily: FONT_MONO, minWidth: 20, paddingTop: 1 }}>
            {i + 1}.
          </span>
          <div style={{ flex: 1 }}>
            <span style={{ fontSize: 12, color: T.text }}>{step.description}</span>
            <span style={{ marginLeft: 8, fontSize: 10, color: T.accent2 }}>
              [{step.agent?.replace(/_/g, " ")}]
            </span>
          </div>
          {step.uncertainty != null && (
            <span style={{
              fontSize: 10, color: step.uncertainty > 0.6 ? T.warn : T.muted,
              fontFamily: FONT_MONO, flexShrink: 0,
            }}>
              u={step.uncertainty.toFixed(2)}
            </span>
          )}
        </div>
      ))}
    </ObsPanel>
  );
}

// ── Extracted entities ────────────────────────────────────────
function EntitiesPanel({ entities }) {
  if (!entities || Object.keys(entities).length === 0) return null;

  return (
    <ObsPanel title="Extracted Entities" icon="◎">
      <div style={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
        {Object.entries(entities).map(([k, vals]) =>
          (Array.isArray(vals) ? vals : [vals]).filter(Boolean).map((v, i) => (
            <EntityBadge key={`${k}-${i}`} label={`${k}: ${v}`} />
          ))
        )}
      </div>
    </ObsPanel>
  );
}

// ── Event feed ────────────────────────────────────────────────
function EventFeed({ events, counts }) {
  const [filter, setFilter] = useState("all");

  const categories = {
    all:     { label: "All", types: null },
    plan:    { label: "Plan",   types: t => t.startsWith("plan.") },
    risk:    { label: "Risk",   types: t => t.startsWith("risk.") || t.startsWith("reflection.") },
    memory:  { label: "Memory", types: t => t.startsWith("memory.") },
    query:   { label: "Query",  types: t => t.startsWith("query.") || t.startsWith("agent.") || t.startsWith("response.") },
  };

  const cat = categories[filter];
  const filtered = cat.types ? events.filter(e => cat.types(e.event_type || "")) : events;

  return (
    <ObsPanel title="Event Feed" icon="≡" action={
      <div style={{ display: "flex", gap: 4 }}>
        {Object.entries(categories).map(([k, c]) => (
          <button key={k} onClick={() => setFilter(k)} style={{
            background: filter === k ? T.accent + "33" : "transparent",
            border: `1px solid ${filter === k ? T.accent : T.border}`,
            color: filter === k ? T.accent : T.muted,
            borderRadius: 3, padding: "2px 7px", fontSize: 10, cursor: "pointer",
          }}>{c.label}</button>
        ))}
      </div>
    }>
      {/* Count chips */}
      {counts && Object.keys(counts).length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 10 }}>
          {Object.entries(counts).slice(0, 8).map(([type, n]) => (
            <span key={type} style={{
              background: T.surface2, border: `1px solid ${T.border}`,
              borderRadius: 3, padding: "1px 6px", fontSize: 10, color: T.muted,
            }}>
              {type.replace(/\./g, " ")} <span style={{ color: T.mutedLt }}>{n}</span>
            </span>
          ))}
        </div>
      )}

      {filtered.length ? (
        <div style={{ maxHeight: 300, overflowY: "auto" }}>
          {filtered.slice(0, 40).map((e, i) => (
            <EventRow key={i} event={e} />
          ))}
        </div>
      ) : <EmptyState msg="No events match this filter." />}
    </ObsPanel>
  );
}

// ── Main component ────────────────────────────────────────────
export default function ProjectStateTab() {
  const [world,   setWorld]   = useState(null);
  const [cos,     setCos]     = useState(null);
  const [events,  setEvents]  = useState({ events: [], counts: {} });
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/cos/world`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/state`).then(r => r.json()).catch(() => null),
      fetch(`${API}/cos/events?n=60`).then(r => r.json()).catch(() => null),
    ]).then(([w, s, ev]) => {
      setWorld(w);
      setCos(s);
      setEvents(ev || { events: [], counts: {} });
      setError(null);
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); const id = setInterval(load, 20_000); return () => clearInterval(id); }, []);

  const uci  = cos?.metrics?.h_uci ?? cos?.metrics?.uci;
  const plan = cos?.plan;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, color: T.text, fontSize: 18, fontWeight: 700 }}>Project State</h2>
          <div style={{ color: T.muted, fontSize: 11, marginTop: 2 }}>
            Live world model — what the system knows about your project
          </div>
        </div>
        <RefreshBtn onClick={load} />
      </div>

      {error && (
        <div style={{ color: T.error, background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 5, padding: "8px 14px", marginBottom: 16, fontSize: 12 }}>
          Backend unavailable: {error}
        </div>
      )}

      {loading && !world ? (
        <div style={{ color: T.muted, fontSize: 12, padding: 40, textAlign: "center" }}>Loading…</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <ProjectCard world={world} uci={uci} />
          <TasksPanel world={world} />
          <EntitiesPanel entities={world?.entities} />
          <ActivePlan plan={plan} />
          <EventFeed events={events.events || []} counts={events.counts || {}} />
        </div>
      )}
    </div>
  );
}
