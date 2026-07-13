import { useState, useEffect, useCallback } from "react";
import { AGENTS } from "./constants";
import { PageHeader } from "./ObsShared";
import { T, SEM, TYPE } from "./theme";
import TracesTab from "./TracesTab";

import { API } from "./api";

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
  build:    T.accent,
  debug:    T.error,
  explain:  SEM.blue,
  compare:  SEM.teal,
  research: SEM.magenta,
  lookup:   T.accent2,
  plan:     "#047857",
  unknown:  T.muted,
};

function AgentChip({ id, size = 12 }) {
  const m = AGENT_META[id] || { icon: "?", color: T.muted, label: id };
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
  const c = ACTION_COLORS[action] || T.muted;
  return (
    <span style={{
      padding: "1px 7px", borderRadius: 3, ...TYPE.caption,
      background: c + "22", color: c, border: `1px solid ${c}44`, fontWeight: 600,
    }}>
      {action}
    </span>
  );
}

function ConfidenceBar({ value, width = 80 }) {
  const pct = Math.round((value || 0) * 100);
  const c = pct >= 70 ? T.success : pct >= 45 ? T.accent2 : T.error;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{
        width, height: 5, background: T.border, borderRadius: 3, overflow: "hidden",
        display: "inline-block",
      }}>
        <span style={{ display: "block", width: `${pct}%`, height: "100%", background: c, borderRadius: 3 }} />
      </span>
      <span style={{ ...TYPE.caption, color: c, fontWeight: 700 }}>{pct}%</span>
    </span>
  );
}

function RegretBar({ value, width = 60 }) {
  const v = value || 0;
  const pct = Math.min(100, Math.round(v * 100 / 0.5));   // 0.5 = full red
  const c = v < 0.1 ? T.success : v < 0.25 ? T.accent2 : T.error;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width, height: 4, background: T.border, borderRadius: 2, overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", width: `${pct}%`, height: "100%", background: c, borderRadius: 2 }} />
      </span>
      <span style={{ ...TYPE.caption, color: c, fontWeight: 700 }}>{v.toFixed(3)}</span>
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
  const instColor   = instability < 0.4 ? T.success : instability < 0.7 ? T.accent2 : T.error;
  const label       = healthy ? "STABLE" : instability >= 0.8 ? "UNSTABLE — learning frozen" : "DEGRADING";
  const labelColor  = healthy ? T.success : instability >= 0.8 ? T.error : T.accent2;

  return (
    <div className="lux-card" style={{
      // Health state keeps its colored edge; everything else is the shared card.
      borderColor: `${labelColor}44`,
      padding: "12px 18px", marginBottom: 16,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <div style={{ ...TYPE.caption, fontWeight: 700, color: T.muted, textTransform: "uppercase", letterSpacing: 1 }}>
          System Drift
        </div>
        <span style={{
          padding: "2px 10px", borderRadius: 3, ...TYPE.caption, fontWeight: 700,
          background: labelColor + "22", color: labelColor, border: `1px solid ${labelColor}55`,
        }}>
          {label}
        </span>
        <span style={{ marginLeft: "auto", ...TYPE.caption, color: T.muted }}>
          instability {instPct}%
        </span>
      </div>

      {/* Instability bar */}
      <div style={{ height: 5, background: T.border, borderRadius: 3, overflow: "hidden", marginBottom: 12 }}>
        <div style={{ width: `${instPct}%`, height: "100%", background: instColor, borderRadius: 3, transition: "width 0.4s" }} />
      </div>

      {/* Signals row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: flags.length > 0 ? 10 : 0 }}>
        {[
          { label: "regret mean", value: regret.toFixed(3), threshold: 0.3, v: regret },
          { label: "max cal error", value: maxCalErr > 0 ? maxCalErr.toFixed(3) : "—", threshold: 0.25, v: maxCalErr },
          { label: "weight var", value: variance.toFixed(5), threshold: 0.05, v: variance },
        ].map(({ label, value, threshold, v }) => {
          const c = v < threshold * 0.5 ? T.muted : v < threshold ? T.accent2 : T.error;
          return (
            <div key={label} style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 4, padding: "6px 12px", flex: "1 1 120px" }}>
              <div style={{ ...TYPE.micro, color: T.muted, marginBottom: 2 }}>{label}</div>
              <div style={{ ...TYPE.body, fontWeight: 800, color: c }}>{value}</div>
            </div>
          );
        })}
      </div>

      {/* Flags */}
      {flags.map((f, i) => (
        <div key={i} style={{
          background: `${T.error}11`, border: `1px solid ${T.error}44`, borderRadius: 7,
          padding: "6px 12px", ...TYPE.caption, color: T.error, marginTop: 4, lineHeight: 1.5,
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
    <div className="lux-card" style={{
      flex: 1, padding: 24, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", color: T.muted, ...TYPE.small,
    }}>
      <div style={{ fontSize: 28, marginBottom: 10 }}>🧠</div>
      Select a decision to inspect
    </div>
  );

  const m = AGENT_META[decision.brain_agent] || { color: T.muted };
  const rm = AGENT_META[decision.router_agent];
  const agree = !decision.conflict;

  return (
    <div className="lux-card" style={{
      flex: 1, padding: "18px 20px", overflowY: "auto",
    }}>
      {/* Header */}
      <div style={{ ...TYPE.caption, fontWeight: 700, color: T.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
        Brain Inspector · #{decision.id}
      </div>

      {/* Task */}
      <div style={{ ...TYPE.small, color: T.text, marginBottom: 14, lineHeight: 1.5, background: T.surface2, borderRadius: 4, padding: "10px 12px", border: `1px solid ${T.border}` }}>
        "{decision.task}"
      </div>

      {/* Intent */}
      <Section label="Intent">
        <Row label="Action"><ActionChip action={decision.action} /></Row>
        <Row label="Complexity">
          <span style={{ ...TYPE.caption, color: decision.complexity === "compound" ? SEM.magenta : decision.complexity === "ambiguous" ? T.accent2 : T.success, fontWeight: 700 }}>
            {decision.complexity}
          </span>
        </Row>
        <Row label="Confidence"><ConfidenceBar value={decision.confidence || 0.67} /></Row>
        {decision.regret != null && (
          <Row label="Regret">
            <RegretBar value={decision.regret} />
            {decision.regret > 0.25 && (
              <span style={{ ...TYPE.micro, color: T.error, marginLeft: 4 }}>suboptimal route</span>
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
                  ? <span style={{ ...TYPE.caption, color: T.success, fontWeight: 700 }}>✓ agree</span>
                  : <span style={{ ...TYPE.caption, color: T.error, fontWeight: 700 }}>⚡ conflict</span>}
              </span>
            : <span style={{ ...TYPE.caption, color: T.muted }}>no match (brain decides)</span>}
        </Row>
        <Row label="Final"><AgentChip id={decision.final_agent} /></Row>
      </Section>

      <Divider />

      {/* Reflection */}
      <Section label="Reflection Gate">
        <Row label="Triggered">
          {decision.reflect
            ? <span style={{ ...TYPE.caption, color: SEM.magenta, fontWeight: 700 }}>YES · {decision.reflect_type}</span>
            : <span style={{ ...TYPE.caption, color: T.muted }}>No</span>}
        </Row>
        {decision.reflect_level && decision.reflect_level !== "none" && (
          <Row label="Level">
            <span style={{
              padding: "1px 8px", borderRadius: 3, ...TYPE.caption, fontWeight: 700,
              background: decision.reflect_level === "full" ? `${SEM.clay}22` : `${T.accent2}22`,
              color:      decision.reflect_level === "full" ? SEM.clay   : T.accent2,
              border: `1px solid ${decision.reflect_level === "full" ? `${SEM.clay}55` : `${T.accent2}55`}`,
            }}>
              {decision.reflect_level}
            </span>
          </Row>
        )}
        {decision.reflect && (
          <Row label="Why">
            <span style={{ ...TYPE.caption, color: T.muted }}>
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
        <Row label="Duration"><span style={{ ...TYPE.caption, color: SEM.teal, fontWeight: 700 }}>{decision.duration_ms}ms</span></Row>
        <Row label="Time"><span style={{ ...TYPE.caption, color: T.muted }}>{decision.timestamp?.slice(0, 19).replace("T", " ")}</span></Row>
      </Section>

      <Divider />

      {/* Replay */}
      <div style={{ marginTop: 4 }}>
        <button
          onClick={handleReplay}
          disabled={loading}
          style={{
            width: "100%", padding: "9px 0", background: loading ? T.surface2 : "#E7F2E6",
            border: `1.5px solid ${loading ? T.border : `${T.success}66`}`, borderRadius: 4,
            color: loading ? T.muted : T.success, ...TYPE.small, fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer", fontFamily: "inherit",
          }}
        >
          {loading ? "▷ Replaying…" : "▶ REPLAY — compare then vs now"}
        </button>

        {replayData && !replayData.error && (
          <div style={{ marginTop: 12, background: T.surface2, border: `1.5px solid ${T.success}33`, borderRadius: 4, padding: "12px 14px" }}>
            <div style={{ ...TYPE.caption, fontWeight: 700, color: T.success, marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Replay Result</div>
            {[
              ["Agent",          decision.brain_agent,               replayData.now?.agent,                replayData.diff?.agent],
              ["Action",         decision.action,                    replayData.now?.action,               replayData.diff?.action],
              ["Confidence",     (decision.confidence || 0.67).toFixed(2), replayData.now?.confidence?.toFixed(2), replayData.diff?.confidence],
              ["Reflect",        String(decision.reflect),           String(replayData.now?.reflect),      replayData.diff?.reflect],
              ["Reflect Level",  decision.reflect_level || "none",   replayData.now?.reflect_level || "none", replayData.diff?.reflect_level],
            ].map(([label, then, now, status]) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <span style={{ ...TYPE.caption, color: T.muted, minWidth: 70 }}>{label}</span>
                <span style={{ ...TYPE.caption, color: T.muted }}>{then}</span>
                <span style={{ ...TYPE.caption, color: T.muted }}>→</span>
                <span style={{ ...TYPE.caption, color: T.text, fontWeight: 600 }}>{now}</span>
                <span style={{ ...TYPE.caption, marginLeft: "auto", fontWeight: 700,
                  color: status === "same" ? T.success : status === "improved" ? SEM.teal : T.error }}>
                  {status === "same" ? "✓ same" : status === "improved" ? "↑ better" : status === "declined" ? "↓ worse" : status === "changed" ? "⚡ changed" : status}
                </span>
              </div>
            ))}
          </div>
        )}

        {replayData?.error && (
          <div style={{ marginTop: 10, padding: "8px 12px", background: "#F9E7E1", border: `1.5px solid ${T.error}44`, borderRadius: 4, ...TYPE.caption, color: T.error }}>
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
      <div style={{ ...TYPE.micro, fontWeight: 700, color: T.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{label}</div>
      {children}
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
      <span style={{ ...TYPE.caption, color: T.muted, minWidth: 80 }}>{label}</span>
      {children}
    </div>
  );
}

function Divider() {
  return <div style={{ height: 1, background: T.border, marginBottom: 12 }} />;
}

function ContradictionHistoryPanel({ items }) {
  const [open, setOpen] = useState(false);
  if (!items) return null;
  const count = items.length;
  const labelColor = count === 0 ? T.muted : T.accent2;
  return (
    <div className="lux-card" style={{ padding: "12px 18px", marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }} onClick={() => setOpen(o => !o)}>
        <span style={{ ...TYPE.caption, fontWeight: 700, color: T.muted, textTransform: "uppercase", letterSpacing: 1 }}>
          ⚠ Contradiction History
        </span>
        <span style={{ padding: "2px 10px", borderRadius: 3, ...TYPE.caption, fontWeight: 700, background: labelColor + "22", color: labelColor, border: `1px solid ${labelColor}55` }}>
          {count} events
        </span>
        <span style={{ marginLeft: "auto", ...TYPE.caption, color: T.muted }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ marginTop: 12 }}>
          {count === 0 ? (
            <div style={{ ...TYPE.caption, color: T.muted, textAlign: "center", padding: "12px 0" }}>
              No contradictions detected yet — the system self-corrects before they accumulate.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {items.map(c => {
                const m = AGENT_META[c.agent] || { color: T.muted, icon: "?", label: c.agent };
                const lvlColor = c.reflect_level === "full" ? SEM.clay : c.reflect_level === "light" ? T.accent2 : T.muted;
                return (
                  <div key={c.id} style={{ background: T.surface2, border: `1px solid ${T.accent2}33`, borderRadius: 4, padding: "9px 13px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                      <span style={{ ...TYPE.caption, color: T.muted, fontFamily: "monospace" }}>
                        {c.timestamp?.slice(0, 19).replace("T", " ")}
                      </span>
                      <span style={{ background: m.color + "22", color: m.color, border: `1px solid ${m.color}55`, borderRadius: 3, padding: "1px 7px", ...TYPE.caption, fontWeight: 700 }}>
                        {m.icon} {m.label}
                      </span>
                      <span style={{ background: lvlColor + "22", color: lvlColor, border: `1px solid ${lvlColor}55`, borderRadius: 3, padding: "1px 7px", ...TYPE.micro }}>
                        → {c.reflect_level} reflect
                      </span>
                    </div>
                    <div style={{ ...TYPE.caption, color: T.text, marginBottom: 4, lineHeight: 1.4 }}>
                      <span style={{ color: T.muted }}>Q: </span>{(c.query || "").slice(0, 120)}{(c.query || "").length > 120 ? "…" : ""}
                    </div>
                    {c.response_snip && (
                      <div style={{ ...TYPE.caption, color: T.muted, fontStyle: "italic", lineHeight: 1.4 }}>
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
    <div className="lux-card" style={{ padding: "12px 18px", marginBottom: 16 }}>
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
        onClick={() => setOpen(o => !o)}
      >
        <div style={{ ...TYPE.caption, fontWeight: 700, color: T.muted, textTransform: "uppercase", letterSpacing: 1 }}>
          Agent Breakdown
        </div>
        <span style={{ ...TYPE.caption, color: T.muted }}>{entries.length} agents</span>
        <span style={{ marginLeft: "auto", ...TYPE.caption, color: T.muted }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ marginTop: 12, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", ...TYPE.caption }}>
            <thead>
              <tr>
                {["Agent", "Decisions", "Stability", "Weight", "Confidence", "Cal Error", "Avg Regret"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "4px 10px", color: T.muted, fontWeight: 700, borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries
                .sort(([, a], [, b]) => b.count - a.count)
                .map(([id, s]) => {
                  const m = AGENT_META[id] || { color: T.muted, icon: "?", label: id };
                  const stabilityColor = s.stability >= 0.85 ? T.success : s.stability >= 0.65 ? T.accent2 : T.error;
                  const regretColor    = s.avg_regret < 0.1  ? T.success : s.avg_regret < 0.25  ? T.accent2 : T.error;
                  const calColor       = s.cal_error < 0.1   ? T.success : s.cal_error < 0.25   ? T.accent2 : T.error;
                  return (
                    <tr key={id} style={{ borderBottom: `1px solid ${T.border}11` }}>
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
                      <td style={{ padding: "6px 10px", color: T.text, fontWeight: 700 }}>{s.count}</td>
                      <td style={{ padding: "6px 10px" }}>
                        <span style={{ color: stabilityColor, fontWeight: 700 }}>{Math.round(s.stability * 100)}%</span>
                      </td>
                      <td style={{ padding: "6px 10px", color: T.muted }}>{s.weight?.toFixed(3)}</td>
                      <td style={{ padding: "6px 10px", color: T.muted }}>{s.confidence?.toFixed(3)}</td>
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
  const [view,           setView]           = useState("history");   // "history" | "live"
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
      <PageHeader
        title="Decisions"
        subtitle={view === "live"
          ? "Live routing signal log — agent selected, signal domain, confidence, and reason."
          : "Every routing decision — what the brain chose, what the router wanted, where they diverged."}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* History / Live view toggle */}
          <div style={{ display: "flex", border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden" }}>
            {[
              { id: "history", label: "History" },
              { id: "live",    label: "Live"    },
            ].map((v, i) => (
              <button key={v.id} onClick={() => setView(v.id)} className="nav-btn" style={{
                padding: "6px 14px", ...TYPE.caption, fontFamily: "inherit",
                fontWeight: view === v.id ? 700 : 500,
                background: view === v.id ? `${T.accent}22` : "transparent",
                color: view === v.id ? T.accent2 : T.muted,
                border: "none", borderLeft: i ? `1px solid ${T.border}` : "none",
                cursor: "pointer",
              }}>{v.label}</button>
            ))}
          </div>

          {view === "history" && [
            { label: "Total",     value: stats.total     || 0, color: T.muted },
            { label: "Conflicts", value: stats.conflicts  || 0, color: stats.conflicts > 0 ? T.error : T.muted },
            { label: "Reflect",   value: `${Math.round((stats.reflect_rate || 0) * 100)}%`, color: SEM.magenta },
            { label: "Conflict %",value: `${Math.round((stats.conflict_rate || 0) * 100)}%`, color: stats.conflict_rate > 0.1 ? T.accent2 : T.success },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ background: T.surface, border: `1.5px solid ${T.border}`, borderRadius: 4, padding: "6px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 16, fontWeight: 800, color }}>{value}</div>
              <div style={{ ...TYPE.micro, color: T.muted, marginTop: 1 }}>{label}</div>
            </div>
          ))}
          {view === "history" && (
            <button onClick={load} disabled={loading} className="nav-btn" style={{
              background: "transparent", border: `1px solid ${T.border}`, color: T.mutedLt,
              padding: "7px 16px", borderRadius: 16, ...TYPE.caption, fontWeight: 600,
              cursor: "pointer", fontFamily: "inherit",
            }}>
              {loading ? "…" : "↻ Refresh"}
            </button>
          )}
        </div>
      </PageHeader>

      {/* Live view: folded-in routing signal log (formerly the Trace tab) */}
      {view === "live" && <TracesTab embedded />}

      {/* History view: full decision feed + inspector */}
      {view === "history" && <>

      {/* Drift monitor */}
      <DriftMonitorPanel drift={drift} />

      {/* Contradiction history */}
      <ContradictionHistoryPanel items={contradictions} />

      {/* Filter bar */}
      <div style={{
        background: T.surface, border: `1.5px solid ${T.border}`, borderRadius: 4,
        padding: "10px 14px", marginBottom: 14, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
      }}>
        {[
          { id: "all",       label: `All (${decisions.length})`,                           color: T.muted },
          { id: "conflicts", label: `⚡ Conflicts (${decisions.filter(d => d.conflict).length})`, color: T.error },
          { id: "reflect",   label: `🔥 Reflect (${decisions.filter(d => d.reflect).length})`,   color: SEM.magenta },
        ].map(f => (
          <button key={f.id} onClick={() => { setFilter(f.id); setVisibleCount(PAGE_SIZE); }} style={{
            padding: "5px 14px", borderRadius: 7, ...TYPE.caption, fontWeight: 700,
            background: filter === f.id ? f.color + "22" : "transparent",
            border:     filter === f.id ? `1.5px solid ${f.color}88` : `1.5px solid ${T.border}`,
            color:      filter === f.id ? f.color : T.muted,
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
            marginLeft: "auto", background: T.surface2, border: `1.5px solid ${T.border}`,
            borderRadius: 4, color: T.text, padding: "5px 12px", ...TYPE.caption,
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
            <div style={{ textAlign: "center", color: T.muted, ...TYPE.body, padding: "50px 0" }}>
              <div style={{ fontSize: 28, marginBottom: 10 }}>🧠</div>
              {decisions.length === 0
                ? "No decisions logged yet — send a chat message to start."
                : "No decisions match this filter."}
            </div>
          ) : visible.map(d => {
            const isSelected = selected?.id === d.id;
            const m = AGENT_META[d.brain_agent] || { color: T.muted };
            return (
              <div
                key={d.id}
                onClick={() => setSelected(isSelected ? null : d)}
                style={{
                  background: isSelected ? T.surface2 : T.surface,
                  border: isSelected ? `1.5px solid ${m.color}66` : d.conflict ? `1.5px solid ${T.error}44` : `1.5px solid ${T.border}`,
                  borderLeft: d.conflict ? `4px solid ${T.error}` : isSelected ? `4px solid ${m.color}` : `4px solid ${T.border}`,
                  borderRadius: 4, padding: "12px 15px",
                  cursor: "pointer", transition: "all .15s",
                }}
              >
                {/* Top row */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ ...TYPE.caption, color: T.muted, fontFamily: "monospace" }}>
                    {d.timestamp?.slice(11, 19) || ""}
                  </span>
                  <AgentChip id={d.brain_agent} />
                  <ActionChip action={d.action} />
                  {d.conflict && (
                    <span style={{ ...TYPE.caption, color: T.error, fontWeight: 700, padding: "1px 7px", background: `${T.error}22`, border: `1px solid ${T.error}44`, borderRadius: 3 }}>
                      ⚡ CONFLICT
                    </span>
                  )}
                  {d.reflect && (
                    <span style={{ ...TYPE.caption, color: SEM.magenta, fontWeight: 700 }}>🔥</span>
                  )}
                  <span style={{ marginLeft: "auto", ...TYPE.caption, color: T.muted }}>
                    #{d.id} · {d.duration_ms}ms
                  </span>
                </div>

                {/* Task text */}
                <div style={{ ...TYPE.caption, color: T.text, marginBottom: 6, lineHeight: 1.4 }}>
                  {(d.task || "").slice(0, 100)}{(d.task || "").length > 100 ? "…" : ""}
                </div>

                {/* Bottom row */}
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ ...TYPE.caption, color: T.muted }}>Brain→</span>
                  <AgentChip id={d.brain_agent} size={11} />
                  {d.router_agent && d.router_agent !== "none" && (
                    <>
                      <span style={{ ...TYPE.caption, color: T.muted }}>Router→</span>
                      <AgentChip id={d.router_agent} size={11} />
                      {!d.conflict
                        ? <span style={{ ...TYPE.caption, color: T.success, fontWeight: 700 }}>✓</span>
                        : <span style={{ ...TYPE.caption, color: T.error, fontWeight: 700 }}>✗</span>}
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
                background: T.surface, border: `1px solid ${T.border}`,
                borderRadius: 3, color: T.muted, ...TYPE.caption,
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
      </>}
    </div>
  );
}
