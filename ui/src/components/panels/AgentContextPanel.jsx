import { useState, useEffect, useCallback } from "react";
import { API } from "@/lib/api";

const T = {
  bg:      "#F4F0E8",
  surface: "#FAF7F2",
  surface2:"#F4F0E8",
  surface3:"#EDE6DA",
  border:  "#E0D6C4",
  accent:  "#C48808",
  accent2: "#0F766E",
  text:    "#2E2010",
  mutedLt: "#5C4030",
  muted:   "#9A7A60",
  success: "#15803D",
  warn:    "#9A6C00",
  error:   "#B42318",
};

const PRIORITY_COLOR = { high: T.error, medium: T.warn, low: T.muted };
const PRIORITY_BG    = { high: `${T.error}15`, medium: `${T.warn}15`, low: `${T.muted}15` };

const MODEL_TIER = {
  reasoning: { label: "Reasoning", color: "#6D4FA8" },
  standard:  { label: "Standard",  color: T.accent2  },
  fast:      { label: "Fast",      color: T.warn      },
};

function SectionHead({ title, count }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 700, color: T.muted, textTransform: "uppercase",
      letterSpacing: "0.09em", marginBottom: 6, display: "flex", alignItems: "center", gap: 5,
    }}>
      {title}
      {count != null && (
        <span style={{
          background: T.surface3, color: T.muted, borderRadius: 8,
          padding: "0px 5px", fontSize: 9, fontWeight: 700,
        }}>{count}</span>
      )}
    </div>
  );
}

function Badge({ label, color, bg }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 8,
      background: bg || `${color}15`, color: color || T.muted,
      whiteSpace: "nowrap", flexShrink: 0,
    }}>{label}</span>
  );
}

// ── Routing section ────────────────────────────────────────────
function RoutingSection({ meta }) {
  if (!meta) return (
    <div style={{ fontSize: 11, color: T.muted, fontStyle: "italic" }}>
      No routing data yet — send a message.
    </div>
  );

  const tier  = MODEL_TIER[meta.model_tier] || MODEL_TIER.fast;
  const conf  = Math.round((meta.signal_conf || 0) * 100);
  const memN  = (meta.memories_used || []).length;
  const confColor = conf >= 80 ? T.success : conf >= 50 ? T.warn : T.error;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>

      {/* Agent */}
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%", background: T.accent, flexShrink: 0,
          boxShadow: `0 0 5px ${T.accent}66`,
        }} />
        <span style={{ fontSize: 11, color: T.text, fontWeight: 600 }}>
          {(meta.agent || "coordinator").replace(/_/g, " ")}
        </span>
        <Badge label={meta.signal_domain || "general"} color={T.accent} />
      </div>

      {/* Confidence + complexity */}
      <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
        <Badge label={`${conf}% sig`}       color={confColor} />
        <Badge label={meta.complexity || "simple"} color={T.muted} />
        {meta.reflect_level && meta.reflect_level !== "none" && (
          <Badge label={`reflect:${meta.reflect_level}`} color="#6D4FA8" />
        )}
      </div>

      {/* Model tier */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 1 }}>
        <span style={{
          width: 7, height: 7, borderRadius: "50%", background: tier.color, flexShrink: 0,
        }} />
        <span style={{ fontSize: 10, color: T.muted }}>
          Model tier: <span style={{ color: tier.color, fontWeight: 600 }}>{tier.label}</span>
        </span>
      </div>

      {/* Memories */}
      {memN > 0 && (
        <div style={{ fontSize: 10, color: T.muted }}>
          ◈ <span style={{ color: T.mutedLt }}>{memN}</span> memor{memN === 1 ? "y" : "ies"} injected
        </div>
      )}

      {/* Elapsed */}
      {meta.elapsed && (
        <div style={{ fontSize: 10, color: T.muted }}>
          ⏱ <span style={{ color: T.mutedLt, fontFamily: "monospace" }}>{meta.elapsed}s</span>
        </div>
      )}
    </div>
  );
}

// ── Active signals section ─────────────────────────────────────
function SignalsSection({ world }) {
  if (!world) return (
    <div style={{ fontSize: 11, color: T.muted, fontStyle: "italic" }}>Loading…</div>
  );

  const issues  = (world.known_issues  || []).slice(-4).reverse();
  // current_goal / project_context may be objects from the world model —
  // only ever render strings.
  const rawGoal = [world.current_goal, world.project_context,
                   world.project_context?.goal, world.project_context?.summary]
    .find(v => typeof v === "string" && v.trim());
  const goal     = rawGoal ? rawGoal.trim() : "";
  const entities = Object.keys(world.entities || {}).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>

      {goal ? (
        <div style={{
          background: T.surface3, borderRadius: 4, padding: "5px 8px",
          fontSize: 11, color: T.text, lineHeight: 1.4,
        }}>
          <span style={{ fontSize: 9, color: T.muted, fontWeight: 700,
                         textTransform: "uppercase", letterSpacing: "0.08em" }}>Goal </span>
          {goal.length > 70 ? goal.slice(0, 70) + "…" : goal}
        </div>
      ) : null}

      {entities > 0 && (
        <div style={{ fontSize: 10, color: T.muted }}>
          ◎ <span style={{ color: T.mutedLt }}>{entities}</span> entities in context
        </div>
      )}

      {issues.length === 0 ? (
        <div style={{ fontSize: 10.5, color: T.muted, fontStyle: "italic" }}>Nothing needs attention.</div>
      ) : (
        issues.map((iss, i) => {
          // Humanize: never show raw JSON — fall back to a readable label.
          let desc = typeof iss === "string" ? iss
            : iss.description || iss.message || iss.error
            || (iss.type ? String(iss.type).replace(/[._]/g, " ") : "");
          if (typeof desc !== "string" || !desc.trim()) desc = "Flagged for review";
          return (
            <div key={i} style={{
              display: "flex", gap: 8, padding: "7px 9px",
              background: `${T.warn}0D`, border: `1px solid ${T.warn}26`,
              borderRadius: 8, alignItems: "flex-start",
            }}>
              <span style={{ fontSize: 11, color: T.warn, flexShrink: 0, marginTop: 1 }}>⚑</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 10.5, color: T.mutedLt, lineHeight: 1.45, wordBreak: "break-word" }}>
                  {desc.length > 90 ? desc.slice(0, 90) + "…" : desc}
                </div>
                {iss.step_id && (
                  <div style={{ fontSize: 9, color: T.muted, marginTop: 3, fontFamily: "monospace", opacity: 0.8 }}>
                    {iss.step_id}
                  </div>
                )}
              </div>
              <Badge label="review" color={T.warn} />
            </div>
          );
        })
      )}
    </div>
  );
}

// ── Activity mini-feed ─────────────────────────────────────────
function ActivityFeed({ events }) {
  if (!events?.length) return (
    <div style={{ fontSize: 11, color: T.muted, fontStyle: "italic" }}>No events yet.</div>
  );

  const getColor = (et) => {
    if (!et) return T.muted;
    const u = et.toUpperCase();
    if (u.includes("FAIL") || u.includes("ERROR"))               return T.error;
    if (u.includes("WARN") || u.includes("BREACH") || u.includes("CONTRADICT")) return T.warn;
    if (u.includes("COMPLET") || u.includes("DONE") || u.includes("PASS"))      return T.success;
    return T.accent;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {events.slice(0, 6).map((ev, i) => {
        const et    = ev.type || ev.event_type || "event";
        const color = getColor(et);
        const label = et.replace(/[._]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
        const tsRaw = ev.ts || ev.timestamp || 0;
        const short = tsRaw
          ? new Date(tsRaw * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
          : "";
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{
              width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0,
            }} />
            <span style={{ fontSize: 10, color: T.mutedLt, flex: 1, minWidth: 0,
                           overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {label}
            </span>
            {short && (
              <span style={{ fontSize: 9, color: T.muted, flexShrink: 0 }}>{short}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Memory section ─────────────────────────────────────────────
function MemorySection({ memories }) {
  if (!memories || !memories.length) return (
    <div style={{ fontSize: 11, color: T.muted, fontStyle: "italic" }}>
      No memories injected — send a message first.
    </div>
  );
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {memories.map((m, i) => {
        const tokEst = Math.round(((m.content || "").length) / 4);
        return (
          <div key={i} style={{
            background: T.surface3, borderRadius: 4, padding: "6px 8px",
            border: `1px solid ${T.border}`,
          }}>
            <div style={{ display: "flex", gap: 5, alignItems: "center", marginBottom: 4, flexWrap: "wrap" }}>
              <Badge label={m.type || "memory"} color="#0E7490" />
              <Badge label={(m.agent || "?").replace(/_/g, " ")} color="#7E3F8F" />
              <span style={{ marginLeft: "auto", fontSize: 9, color: T.muted, fontFamily: "monospace", flexShrink: 0 }}>
                ~{tokEst} tok · {m.score?.toFixed(2)} rel
              </span>
            </div>
            <div style={{ fontSize: 10, color: T.mutedLt, lineHeight: 1.45, wordBreak: "break-word" }}>
              {(m.content || "").slice(0, 130)}{(m.content?.length || 0) > 130 ? "…" : ""}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Suggestions section ────────────────────────────────────────
function SuggestionsSection({ suggestions, onApply }) {
  if (!suggestions) return (
    <div style={{ fontSize: 11, color: T.muted, fontStyle: "italic" }}>Loading…</div>
  );
  if (!suggestions.length) return (
    <div style={{ fontSize: 10, color: T.success }}>✓ Nothing to suggest right now.</div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {suggestions.map((s, i) => {
        const pc = PRIORITY_COLOR[s.priority] || T.muted;
        const pb = PRIORITY_BG  [s.priority] || `${T.muted}15`;
        return (
          <div key={i} style={{
            background: T.surface3, borderRadius: 4, padding: "6px 8px",
            border: `1px solid ${T.border}`,
            display: "flex", flexDirection: "column", gap: 4,
          }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 5 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: T.text,
                              wordBreak: "break-word", lineHeight: 1.3 }}>
                  {s.title}
                </div>
                {s.rationale && (
                  <div style={{ fontSize: 9, color: T.muted, marginTop: 2, lineHeight: 1.4 }}>
                    {s.rationale}
                  </div>
                )}
              </div>
              <Badge label={s.priority || "low"} color={pc} bg={pb} />
            </div>
            <button
              onClick={() => onApply(s)}
              style={{
                alignSelf: "flex-start",
                fontSize: 10, fontWeight: 600, fontFamily: "inherit",
                padding: "2px 9px", borderRadius: 4, cursor: "pointer",
                background: `${T.accent}18`,
                border: `1px solid ${T.accent}55`,
                color: T.accent,
                transition: "background 0.1s",
              }}
              onMouseOver={e => e.currentTarget.style.background = `${T.accent}30`}
              onMouseOut ={e => e.currentTarget.style.background = `${T.accent}18`}
            >
              Apply →
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ── Root component ─────────────────────────────────────────────
export default function AgentContextPanel({ lastMeta, onApply, apiBase = API }) {
  const [world,       setWorld]       = useState(null);
  const [events,      setEvents]      = useState([]);
  const [suggestions, setSuggestions] = useState(null);
  const [activeTab,   setActiveTab]   = useState("routing");

  const fetchWorld = useCallback(() => {
    fetch(`${apiBase}/cos/world`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setWorld(d); })
      .catch(() => {});
  }, [apiBase]);

  const fetchEvents = useCallback(() => {
    fetch(`${apiBase}/cos/events?n=10`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.events) setEvents(d.events); })
      .catch(() => {});
  }, [apiBase]);

  const fetchSuggestions = useCallback(() => {
    fetch(`${apiBase}/cos/suggestions`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.suggestions) setSuggestions(d.suggestions); })
      .catch(() => {});
  }, [apiBase]);

  // Initial load + polling
  useEffect(() => {
    fetchWorld(); fetchEvents(); fetchSuggestions();
    const id1 = setInterval(fetchWorld,       5000);
    const id2 = setInterval(fetchEvents,      5000);
    const id3 = setInterval(fetchSuggestions, 12000);
    return () => { clearInterval(id1); clearInterval(id2); clearInterval(id3); };
  }, [fetchWorld, fetchEvents, fetchSuggestions]);

  // Re-fetch when a new response arrives
  useEffect(() => {
    if (lastMeta) { fetchWorld(); fetchSuggestions(); }
  }, [lastMeta, fetchWorld, fetchSuggestions]);

  const memCount = lastMeta?.memories_used?.length || 0;
  const TABS = [
    { id: "routing",     label: "Route"    },
    { id: "signals",     label: "Signals"  },
    { id: "suggestions", label: "Tips",    dot: suggestions?.length > 0 },
    { id: "memory",      label: "Memory",  dot: memCount > 0 },
    { id: "activity",    label: "Events"   },
  ];

  const issueCount = (world?.known_issues || []).length;

  return (
    <div style={{
      width: 230, minWidth: 230, flexShrink: 0,
      height: "100%", overflow: "hidden",
      display: "flex", flexDirection: "column",
      background: T.surface,
      borderLeft: `1px solid ${T.border}`,
    }}>

      {/* ── Tab bar ── */}
      <div style={{
        display: "flex", borderBottom: `1px solid ${T.border}`,
        background: T.bg, flexShrink: 0, overflowX: "auto",
      }}>
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "7px 0", flex: 1,
              fontSize: 10, fontWeight: activeTab === tab.id ? 700 : 500,
              fontFamily: "inherit", cursor: "pointer",
              background: "none", border: "none",
              borderBottom: activeTab === tab.id ? `2px solid ${T.accent}` : "2px solid transparent",
              color: activeTab === tab.id ? T.accent : T.muted,
              transition: "color 0.1s",
              position: "relative",
            }}>
            {tab.label}
            {tab.dot && (
              <span style={{
                position: "absolute", top: 4, right: 4,
                width: 5, height: 5, borderRadius: "50%",
                background: T.warn,
              }} />
            )}
          </button>
        ))}
      </div>

      {/* ── Body ── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 10px 16px" }}>

        {activeTab === "routing" && (
          <>
            <SectionHead title="Last Request" />
            <RoutingSection meta={lastMeta} />
          </>
        )}

        {activeTab === "signals" && (
          <>
            <SectionHead title="Active Signals" count={issueCount > 0 ? issueCount : undefined} />
            <SignalsSection world={world} />
          </>
        )}

        {activeTab === "suggestions" && (
          <>
            <SectionHead title="Suggestions" count={suggestions?.length} />
            <SuggestionsSection suggestions={suggestions} onApply={onApply} />
          </>
        )}

        {activeTab === "memory" && (
          <>
            <SectionHead title="Injected Memory" count={memCount > 0 ? memCount : undefined} />
            <MemorySection memories={lastMeta?.memories_used} />
          </>
        )}

        {activeTab === "activity" && (
          <>
            <SectionHead title="Event Feed" count={events.length || undefined} />
            <ActivityFeed events={events} />
          </>
        )}
      </div>
    </div>
  );
}
