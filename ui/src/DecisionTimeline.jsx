import { useState, useEffect, useCallback } from "react";
import { AGENTS } from "./constants";
import { PageHeader } from "./ObsShared";

const API = "http://localhost:8000";

// Compact labels for chip display, derived from shared constants
const SHORT_LABEL = {
  "IT & Networking": "IT & Net",
  "Knowledge & Learning": "Knowledge",
  "AI & ML": "AI/ML",
  "Coordinator": "Coord",
};
const AGENT_META = Object.fromEntries(
  AGENTS.map(a => [a.id, {
    icon:  a.icon,
    color: a.color,
    label: SHORT_LABEL[a.label] || a.label.replace(" Dev", ""),
  }])
);

const ACTION_COLORS = {
  build:    "#C48808",
  debug:    "#B42318",
  explain:  "#1E5A8A",
  compare:  "#0F766E",
  research: "#BE185D",
  lookup:   "#9A6C00",
  plan:     "#047857",
  unknown:  "#9A7A60",
};

function AgentChip({ id, size = 12 }) {
  const m = AGENT_META[id] || { icon: "?", color: "#9A7A60", label: id };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", borderRadius: 3, fontSize: size,
      background: m.color + "22", color: m.color,
      border: `1px solid ${m.color}55`, fontWeight: 700, whiteSpace: "nowrap",
    }}>
      {m.icon} {m.label}
    </span>
  );
}

function ActionChip({ action }) {
  const c = ACTION_COLORS[action] || "#9A7A60";
  return (
    <span style={{
      padding: "1px 7px", borderRadius: 3, fontSize: 11,
      background: c + "22", color: c, border: `1px solid ${c}44`, fontWeight: 600,
    }}>
      {action}
    </span>
  );
}

function ConfidenceBar({ value, width = 80 }) {
  const pct = Math.round((value || 0) * 100);
  const c = pct >= 70 ? "#15803D" : pct >= 45 ? "#9A6C00" : "#B42318";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{
        width, height: 5, background: "#E0D6C4", borderRadius: 3, overflow: "hidden",
        display: "inline-block",
      }}>
        <span style={{ display: "block", width: `${pct}%`, height: "100%", background: c, borderRadius: 3 }} />
      </span>
      <span style={{ fontSize: 11, color: c, fontWeight: 700 }}>{pct}%</span>
    </span>
  );
}

function RegretBar({ value, width = 60 }) {
  const v = value || 0;
  const pct = Math.min(100, Math.round(v * 100 / 0.5));   // 0.5 = full red
  const c = v < 0.1 ? "#15803D" : v < 0.25 ? "#9A6C00" : "#B42318";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width, height: 4, background: "#E0D6C4", borderRadius: 2, overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", width: `${pct}%`, height: "100%", background: c, borderRadius: 2 }} />
      </span>
      <span style={{ fontSize: 11, color: c, fontWeight: 700 }}>{v.toFixed(3)}</span>
    </span>
  );
}


function DriftMonitorPanel({ drift }) {
  if (!drift) return null;
  const healthy     = drift.healthy;
  const flags       = drift.flags || [];
  const regret      = drift.regret_mean_50 || 0;
  const variance    = drift.weight_variance || 0;
  const calErrors   = drift.calibration_errors || {};
  const maxCalErr   = Object.values(calErrors).length > 0 ? Math.max(...Object.values(calErrors)) : 0;
  // Instability composite (mirrors learning.py)
  const instability = Math.min(1, 0.4*regret + 0.4*maxCalErr + 0.2*variance);
  const instPct     = Math.round(instability * 100);
  const instColor   = instability < 0.4 ? "#15803D" : instability < 0.7 ? "#9A6C00" : "#B42318";
  const label       = healthy ? "STABLE" : instability >= 0.8 ? "UNSTABLE — learning frozen" : "DEGRADING";
  const labelColor  = healthy ? "#15803D" : instability >= 0.8 ? "#B42318" : "#9A6C00";

  return (
    <div style={{
      background: "#FAF7F2",
      border: `1.5px solid ${labelColor}44`,
      borderRadius: 3, padding: "12px 18px", marginBottom: 16,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", textTransform: "uppercase", letterSpacing: 1 }}>
          System Drift
        </div>
        <span style={{
          padding: "2px 10px", borderRadius: 3, fontSize: 11, fontWeight: 700,
          background: labelColor + "22", color: labelColor, border: `1px solid ${labelColor}55`,
        }}>
          {label}
        </span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#9A7A60" }}>
          instability {instPct}%
        </span>
      </div>

      {/* Instability bar */}
      <div style={{ height: 5, background: "#E0D6C4", borderRadius: 3, overflow: "hidden", marginBottom: 12 }}>
        <div style={{ width: `${instPct}%`, height: "100%", background: instColor, borderRadius: 3, transition: "width 0.4s" }} />
      </div>

      {/* Signals row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: flags.length > 0 ? 10 : 0 }}>
        {[
          { label: "regret mean", value: regret.toFixed(3), threshold: 0.3, v: regret },
          { label: "max cal error", value: maxCalErr > 0 ? maxCalErr.toFixed(3) : "—", threshold: 0.25, v: maxCalErr },
          { label: "weight var", value: variance.toFixed(5), threshold: 0.05, v: variance },
        ].map(({ label, value, threshold, v }) => {
          const c = v < threshold * 0.5 ? "#9A7A60" : v < threshold ? "#9A6C00" : "#B42318";
          return (
            <div key={label} style={{ background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 4, padding: "6px 12px", flex: "1 1 120px" }}>
              <div style={{ fontSize: 10, color: "#9A7A60", marginBottom: 2 }}>{label}</div>
              <div style={{ fontSize: 14, fontWeight: 800, color: c }}>{value}</div>
            </div>
          );
        })}
      </div>

      {/* Flags */}
      {flags.map((f, i) => (
        <div key={i} style={{
          background: "#B4231811", border: "1px solid #B4231844", borderRadius: 7,
          padding: "6px 12px", fontSize: 11, color: "#B42318", marginTop: 4, lineHeight: 1.5,
        }}>
          ⚠ <strong>{f.type}</strong>{f.agent ? ` [${f.agent}]` : ""} — {f.detail}
        </div>
      ))}
    </div>
  );
}


function BrainInspector({ decision, onReplay }) {
  const [replayData, setReplayData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { setReplayData(null); }, [decision?.id]);

  const handleReplay = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/replay/${decision.id}`);
      const d = await r.json();
      setReplayData(d);
    } catch (e) {
      setReplayData({ error: "Replay failed — backend offline?" });
    } finally {
      setLoading(false);
    }
  };

  if (!decision) return (
    <div style={{
      flex: 1, background: "#FAF7F2", border: "1.5px solid #E0D6C4",
      borderRadius: 3, padding: 24, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", color: "#9A7A60", fontSize: 13,
    }}>
      <div style={{ fontSize: 28, marginBottom: 10 }}>🧠</div>
      Select a decision to inspect
    </div>
  );

  const m = AGENT_META[decision.brain_agent] || { color: "#9A7A60" };
  const rm = AGENT_META[decision.router_agent];
  const agree = !decision.conflict;

  return (
    <div style={{
      flex: 1, background: "#FAF7F2", border: "1.5px solid #E0D6C4",
      borderRadius: 3, padding: "18px 20px", overflowY: "auto",
    }}>
      {/* Header */}
      <div style={{ fontSize: 11, fontWeight: 700, color: "#9A7A60", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
        Brain Inspector · #{decision.id}
      </div>

      {/* Task */}
      <div style={{ fontSize: 13, color: "#2E2010", marginBottom: 14, lineHeight: 1.5, background: "#F4F0E8", borderRadius: 4, padding: "10px 12px", border: "1px solid #E0D6C4" }}>
        "{decision.task}"
      </div>

      {/* Intent */}
      <Section label="Intent">
        <Row label="Action"><ActionChip action={decision.action} /></Row>
        <Row label="Complexity">
          <span style={{ fontSize: 12, color: decision.complexity === "compound" ? "#BE185D" : decision.complexity === "ambiguous" ? "#9A6C00" : "#15803D", fontWeight: 700 }}>
            {decision.complexity}
          </span>
        </Row>
        <Row label="Confidence"><ConfidenceBar value={decision.confidence || 0.67} /></Row>
        {decision.regret != null && (
          <Row label="Regret">
            <RegretBar value={decision.regret} />
            {decision.regret > 0.25 && (
              <span style={{ fontSize: 10, color: "#B42318", marginLeft: 4 }}>suboptimal route</span>
            )}
          </Row>
        )}
      </Section>

      <Divider />

      {/* Routing */}
      <Section label="Routing">
        <Row label="Brain"><AgentChip id={decision.brain_agent} /></Row>
        <Row label="Router">
          {decision.router_agent && decision.router_agent !== "none"
            ? <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <AgentChip id={decision.router_agent} />
                {agree
                  ? <span style={{ fontSize: 11, color: "#15803D", fontWeight: 700 }}>✓ agree</span>
                  : <span style={{ fontSize: 11, color: "#B42318", fontWeight: 700 }}>⚡ conflict</span>}
              </span>
            : <span style={{ fontSize: 12, color: "#9A7A60" }}>no match (brain decides)</span>}
        </Row>
        <Row label="Final"><AgentChip id={decision.final_agent} /></Row>
      </Section>

      <Divider />

      {/* Reflection */}
      <Section label="Reflection Gate">
        <Row label="Triggered">
          {decision.reflect
            ? <span style={{ fontSize: 12, color: "#BE185D", fontWeight: 700 }}>YES · {decision.reflect_type}</span>
            : <span style={{ fontSize: 12, color: "#9A7A60" }}>No</span>}
        </Row>
        {decision.reflect_level && decision.reflect_level !== "none" && (
          <Row label="Level">
            <span style={{
              padding: "1px 8px", borderRadius: 3, fontSize: 11, fontWeight: 700,
              background: decision.reflect_level === "full" ? "#C0604022" : "#9A6C0022",
              color:      decision.reflect_level === "full" ? "#C06040"   : "#9A6C00",
              border: `1px solid ${decision.reflect_level === "full" ? "#C0604055" : "#9A6C0055"}`,
            }}>
              {decision.reflect_level}
            </span>
          </Row>
        )}
        {decision.reflect && (
          <Row label="Why">
            <span style={{ fontSize: 11, color: "#9A7A60" }}>
              {decision.reflect_type === "code" ? "build/debug + code agent → execute check"
                : decision.reflect_type === "research" ? "research task → completeness critique"
                : "general quality pass"}
            </span>
          </Row>
        )}
      </Section>

      <Divider />

      {/* Timing */}
      <Section label="Timing">
        <Row label="Duration"><span style={{ fontSize: 12, color: "#0F766E", fontWeight: 700 }}>{decision.duration_ms}ms</span></Row>
        <Row label="Time"><span style={{ fontSize: 12, color: "#9A7A60" }}>{decision.timestamp?.slice(0, 19).replace("T", " ")}</span></Row>
      </Section>

      <Divider />

      {/* Replay */}
      <div style={{ marginTop: 4 }}>
        <button
          onClick={handleReplay}
          disabled={loading}
          style={{
            width: "100%", padding: "9px 0", background: loading ? "#F4F0E8" : "#E7F2E6",
            border: `1.5px solid ${loading ? "#E0D6C4" : "#15803D66"}`, borderRadius: 4,
            color: loading ? "#9A7A60" : "#15803D", fontSize: 13, fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer", fontFamily: "inherit",
          }}
        >
          {loading ? "▷ Replaying…" : "▶ REPLAY — compare then vs now"}
        </button>

        {replayData && !replayData.error && (
          <div style={{ marginTop: 12, background: "#F4F0E8", border: "1.5px solid #15803D33", borderRadius: 4, padding: "12px 14px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#15803D", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Replay Result</div>
            {[
              ["Agent",          decision.brain_agent,               replayData.now?.agent,                replayData.diff?.agent],
              ["Action",         decision.action,                    replayData.now?.action,               replayData.diff?.action],
              ["Confidence",     (decision.confidence || 0.67).toFixed(2), replayData.now?.confidence?.toFixed(2), replayData.diff?.confidence],
              ["Reflect",        String(decision.reflect),           String(replayData.now?.reflect),      replayData.diff?.reflect],
              ["Reflect Level",  decision.reflect_level || "none",   replayData.now?.reflect_level || "none", replayData.diff?.reflect_level],
            ].map(([label, then, now, status]) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <span style={{ fontSize: 11, color: "#9A7A60", minWidth: 70 }}>{label}</span>
                <span style={{ fontSize: 12, color: "#9A7A60" }}>{then}</span>
                <span style={{ fontSize: 11, color: "#9A7A60" }}>→</span>
                <span style={{ fontSize: 12, color: "#2E2010", fontWeight: 600 }}>{now}</span>
                <span style={{ fontSize: 11, marginLeft: "auto", fontWeight: 700,
                  color: status === "same" ? "#15803D" : status === "improved" ? "#0F766E" : "#B42318" }}>
                  {status === "same" ? "✓ same" : status === "improved" ? "↑ better" : status === "declined" ? "↓ worse" : status === "changed" ? "⚡ changed" : status}
                </span>
              </div>
            ))}
          </div>
        )}

        {replayData?.error && (
          <div style={{ marginTop: 10, padding: "8px 12px", background: "#F9E7E1", border: "1.5px solid #B4231844", borderRadius: 4, fontSize: 12, color: "#B42318" }}>
            {replayData.error}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "#9A7A60", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{label}</div>
      {children}
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
      <span style={{ fontSize: 11, color: "#9A7A60", minWidth: 80 }}>{label}</span>
      {children}
    </div>
  );
}

function Divider() {
  return <div style={{ height: 1, background: "#E0D6C4", marginBottom: 12 }} />;
}

function ContradictionHistoryPanel({ items }) {
  const [open, setOpen] = useState(false);
  if (!items) return null;
  const count = items.length;
  const labelColor = count === 0 ? "#9A7A60" : "#9A6C00";
  return (
    <div style={{ background: "#FAF7F2", border: `1.5px solid ${labelColor}44`, borderRadius: 3, padding: "12px 18px", marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }} onClick={() => setOpen(o => !o)}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", textTransform: "uppercase", letterSpacing: 1 }}>
          ⚠ Contradiction History
        </span>
        <span style={{ padding: "2px 10px", borderRadius: 3, fontSize: 11, fontWeight: 700, background: labelColor + "22", color: labelColor, border: `1px solid ${labelColor}55` }}>
          {count} events
        </span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#9A7A60" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ marginTop: 12 }}>
          {count === 0 ? (
            <div style={{ fontSize: 12, color: "#9A7A60", textAlign: "center", padding: "12px 0" }}>
              No contradictions detected yet — the system self-corrects before they accumulate.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {items.map(c => {
                const m = AGENT_META[c.agent] || { color: "#9A7A60", icon: "?", label: c.agent };
                const lvlColor = c.reflect_level === "full" ? "#C06040" : c.reflect_level === "light" ? "#9A6C00" : "#9A7A60";
                return (
                  <div key={c.id} style={{ background: "#F4F0E8", border: "1px solid #9A6C0033", borderRadius: 4, padding: "9px 13px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                      <span style={{ fontSize: 11, color: "#9A7A60", fontFamily: "monospace" }}>
                        {c.timestamp?.slice(0, 19).replace("T", " ")}
                      </span>
                      <span style={{ background: m.color + "22", color: m.color, border: `1px solid ${m.color}55`, borderRadius: 3, padding: "1px 7px", fontSize: 11, fontWeight: 700 }}>
                        {m.icon} {m.label}
                      </span>
                      <span style={{ background: lvlColor + "22", color: lvlColor, border: `1px solid ${lvlColor}55`, borderRadius: 3, padding: "1px 7px", fontSize: 10 }}>
                        → {c.reflect_level} reflect
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "#2E2010", marginBottom: 4, lineHeight: 1.4 }}>
                      <span style={{ color: "#9A7A60" }}>Q: </span>{(c.query || "").slice(0, 120)}{(c.query || "").length > 120 ? "…" : ""}
                    </div>
                    {c.response_snip && (
                      <div style={{ fontSize: 11, color: "#9A7A60", fontStyle: "italic", lineHeight: 1.4 }}>
                        "{(c.response_snip || "").slice(0, 100)}…"
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AgentStatsPanel({ agents }) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(agents || {});
  if (entries.length === 0) return null;

  return (
    <div style={{ background: "#FAF7F2", border: "1.5px solid #E0D6C4", borderRadius: 3, padding: "12px 18px", marginBottom: 16 }}>
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
        onClick={() => setOpen(o => !o)}
      >
        <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", textTransform: "uppercase", letterSpacing: 1 }}>
          Agent Breakdown
        </div>
        <span style={{ fontSize: 11, color: "#9A7A60" }}>{entries.length} agents</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#9A7A60" }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ marginTop: 12, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
            <thead>
              <tr>
                {["Agent", "Decisions", "Stability", "Weight", "Confidence", "Cal Error", "Avg Regret"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "4px 10px", color: "#9A7A60", fontWeight: 700, borderBottom: "1px solid #E0D6C4", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries
                .sort(([, a], [, b]) => b.count - a.count)
                .map(([id, s]) => {
                  const m = AGENT_META[id] || { color: "#9A7A60", icon: "?", label: id };
                  const stabilityColor = s.stability >= 0.85 ? "#15803D" : s.stability >= 0.65 ? "#9A6C00" : "#B42318";
                  const regretColor    = s.avg_regret < 0.1  ? "#15803D" : s.avg_regret < 0.25  ? "#9A6C00" : "#B42318";
                  const calColor       = s.cal_error < 0.1   ? "#15803D" : s.cal_error < 0.25   ? "#9A6C00" : "#B42318";
                  return (
                    <tr key={id} style={{ borderBottom: "1px solid #E0D6C411" }}>
                      <td style={{ padding: "6px 10px" }}>
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 4,
                          background: m.color + "22", color: m.color,
                          border: `1px solid ${m.color}44`, borderRadius: 3,
                          padding: "1px 7px", fontWeight: 700,
                        }}>
                          {m.icon} {m.label}
                        </span>
                      </td>
                      <td style={{ padding: "6px 10px", color: "#2E2010", fontWeight: 700 }}>{s.count}</td>
                      <td style={{ padding: "6px 10px" }}>
                        <span style={{ color: stabilityColor, fontWeight: 700 }}>{Math.round(s.stability * 100)}%</span>
                      </td>
                      <td style={{ padding: "6px 10px", color: "#9A7A60" }}>{s.weight?.toFixed(3)}</td>
                      <td style={{ padding: "6px 10px", color: "#9A7A60" }}>{s.confidence?.toFixed(3)}</td>
                      <td style={{ padding: "6px 10px" }}>
                        <span style={{ color: calColor }}>{s.cal_error > 0 ? s.cal_error.toFixed(3) : "—"}</span>
                      </td>
                      <td style={{ padding: "6px 10px" }}>
                        <span style={{ color: regretColor }}>{s.avg_regret > 0 ? s.avg_regret.toFixed(3) : "—"}</span>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export default function DecisionTimeline() {
  const [data,           setData]           = useState(null);
  const [drift,          setDrift]          = useState(null);
  const [contradictions, setContradictions] = useState(null);
  const [selected,       setSelected]       = useState(null);
  const [filter,         setFilter]         = useState("all");
  const [search,         setSearch]         = useState("");
  const [loading,        setLoading]        = useState(false);
  const [visibleCount,   setVisibleCount]   = useState(50);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dR, drR, cR] = await Promise.all([
        fetch(`${API}/decisions?limit=100`),
        fetch(`${API}/learning/drift`),
        fetch(`${API}/contradictions?limit=50`),
      ]);
      setData(await dR.json());
      setDrift(drR.ok ? await drR.json() : null);
      setContradictions(cR.ok ? await cR.json() : []);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const decisions = data?.decisions || [];
  const stats     = data?.stats     || {};
  const agents    = data?.agents    || {};

  const filtered = decisions.filter(d => {
    if (filter === "conflicts" && !d.conflict) return false;
    if (filter === "reflect"   && !d.reflect)  return false;
    if (search) {
      const q = search.toLowerCase();
      if (!d.task?.toLowerCase().includes(q) &&
          !d.action?.toLowerCase().includes(q) &&
          !d.brain_agent?.toLowerCase().includes(q) &&
          !d.final_agent?.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const PAGE_SIZE = 50;
  const visible   = filtered.slice(0, visibleCount);

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      {/* Page header */}
      <PageHeader title="Decisions" subtitle="Every routing decision — what the brain chose, what the router wanted, where they diverged.">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {[
            { label: "Total",     value: stats.total     || 0, color: "#9A7A60" },
            { label: "Conflicts", value: stats.conflicts  || 0, color: stats.conflicts > 0 ? "#B42318" : "#9A7A60" },
            { label: "Reflect",   value: `${Math.round((stats.reflect_rate || 0) * 100)}%`, color: "#BE185D" },
            { label: "Conflict %",value: `${Math.round((stats.conflict_rate || 0) * 100)}%`, color: stats.conflict_rate > 0.1 ? "#9A6C00" : "#15803D" },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ background: "#FAF7F2", border: "1.5px solid #E0D6C4", borderRadius: 4, padding: "6px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 16, fontWeight: 800, color }}>{value}</div>
              <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 1 }}>{label}</div>
            </div>
          ))}
          <button onClick={load} disabled={loading} className="nav-btn" style={{
            background: "transparent", border: "1px solid #E0D6C4", color: "#5C4030",
            padding: "7px 16px", borderRadius: 16, fontSize: 12, fontWeight: 600,
            cursor: "pointer", fontFamily: "inherit",
          }}>
            {loading ? "…" : "↻ Refresh"}
          </button>
        </div>
      </PageHeader>

      {/* Drift monitor */}
      <DriftMonitorPanel drift={drift} />

      {/* Contradiction history */}
      <ContradictionHistoryPanel items={contradictions} />

      {/* Filter bar */}
      <div style={{
        background: "#FAF7F2", border: "1.5px solid #E0D6C4", borderRadius: 4,
        padding: "10px 14px", marginBottom: 14, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
      }}>
        {[
          { id: "all",       label: `All (${decisions.length})`,                           color: "#9A7A60" },
          { id: "conflicts", label: `⚡ Conflicts (${decisions.filter(d => d.conflict).length})`, color: "#B42318" },
          { id: "reflect",   label: `🔥 Reflect (${decisions.filter(d => d.reflect).length})`,   color: "#BE185D" },
        ].map(f => (
          <button key={f.id} onClick={() => { setFilter(f.id); setVisibleCount(PAGE_SIZE); }} style={{
            padding: "5px 14px", borderRadius: 7, fontSize: 12, fontWeight: 700,
            background: filter === f.id ? f.color + "22" : "transparent",
            border:     filter === f.id ? `1.5px solid ${f.color}88` : "1.5px solid #E0D6C4",
            color:      filter === f.id ? f.color : "#9A7A60",
            cursor: "pointer", fontFamily: "inherit",
          }}>
            {f.label}
          </button>
        ))}
        <input
          value={search}
          onChange={e => { setSearch(e.target.value); setVisibleCount(PAGE_SIZE); }}
          placeholder="Search tasks, agents, actions…"
          style={{
            marginLeft: "auto", background: "#F4F0E8", border: "1.5px solid #E0D6C4",
            borderRadius: 4, color: "#2E2010", padding: "5px 12px", fontSize: 12,
            fontFamily: "inherit", outline: "none", width: 220,
          }}
        />
      </div>

      {/* Agent stats */}
      <AgentStatsPanel agents={agents} />

      {/* Main split */}
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>

        {/* Decision feed */}
        <div style={{ flex: "0 0 58%", display: "flex", flexDirection: "column", gap: 6 }}>
          {filtered.length === 0 ? (
            <div style={{ textAlign: "center", color: "#9A7A60", fontSize: 14, padding: "50px 0" }}>
              <div style={{ fontSize: 28, marginBottom: 10 }}>🧠</div>
              {decisions.length === 0
                ? "No decisions logged yet — send a chat message to start."
                : "No decisions match this filter."}
            </div>
          ) : visible.map(d => {
            const isSelected = selected?.id === d.id;
            const m = AGENT_META[d.brain_agent] || { color: "#9A7A60" };
            return (
              <div
                key={d.id}
                onClick={() => setSelected(isSelected ? null : d)}
                style={{
                  background: isSelected ? "#F4F0E8" : "#FAF7F2",
                  border: isSelected ? `1.5px solid ${m.color}66` : d.conflict ? "1.5px solid #B4231844" : "1.5px solid #E0D6C4",
                  borderLeft: d.conflict ? "4px solid #B42318" : isSelected ? `4px solid ${m.color}` : "4px solid #E0D6C4",
                  borderRadius: 4, padding: "12px 15px",
                  cursor: "pointer", transition: "all .15s",
                }}
              >
                {/* Top row */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: "#9A7A60", fontFamily: "monospace" }}>
                    {d.timestamp?.slice(11, 19) || ""}
                  </span>
                  <AgentChip id={d.brain_agent} />
                  <ActionChip action={d.action} />
                  {d.conflict && (
                    <span style={{ fontSize: 11, color: "#B42318", fontWeight: 700, padding: "1px 7px", background: "#B4231822", border: "1px solid #B4231844", borderRadius: 3 }}>
                      ⚡ CONFLICT
                    </span>
                  )}
                  {d.reflect && (
                    <span style={{ fontSize: 11, color: "#BE185D", fontWeight: 700 }}>🔥</span>
                  )}
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "#9A7A60" }}>
                    #{d.id} · {d.duration_ms}ms
                  </span>
                </div>

                {/* Task text */}
                <div style={{ fontSize: 12, color: "#2E2010", marginBottom: 6, lineHeight: 1.4 }}>
                  {(d.task || "").slice(0, 100)}{(d.task || "").length > 100 ? "…" : ""}
                </div>

                {/* Bottom row */}
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 11, color: "#9A7A60" }}>Brain→</span>
                  <AgentChip id={d.brain_agent} size={11} />
                  {d.router_agent && d.router_agent !== "none" && (
                    <>
                      <span style={{ fontSize: 11, color: "#9A7A60" }}>Router→</span>
                      <AgentChip id={d.router_agent} size={11} />
                      {!d.conflict
                        ? <span style={{ fontSize: 11, color: "#15803D", fontWeight: 700 }}>✓</span>
                        : <span style={{ fontSize: 11, color: "#B42318", fontWeight: 700 }}>✗</span>}
                    </>
                  )}
                  <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 8 }}>
                    {d.regret > 0 && <RegretBar value={d.regret} width={40} />}
                    <ConfidenceBar value={d.confidence || 0.67} width={60} />
                  </span>
                </div>
              </div>
            );
          })}
          {filtered.length > visibleCount && (
            <button
              onClick={() => setVisibleCount(c => c + PAGE_SIZE)}
              style={{
                marginTop: 8, padding: "8px 0", width: "100%",
                background: "#FAF7F2", border: "1px solid #E0D6C4",
                borderRadius: 3, color: "#9A7A60", fontSize: 12,
                cursor: "pointer", fontFamily: "inherit",
              }}
            >
              Show {Math.min(PAGE_SIZE, filtered.length - visibleCount)} more
              &nbsp;·&nbsp; {filtered.length - visibleCount} remaining
            </button>
          )}
        </div>

        {/* Inspector */}
        <div style={{ flex: "0 0 40%", position: "sticky", top: 0, display: "flex", flexDirection: "column", minHeight: 400 }}>
          <BrainInspector decision={selected} />
        </div>

      </div>
    </div>
  );
}
