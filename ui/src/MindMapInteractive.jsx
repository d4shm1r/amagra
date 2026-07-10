/**
 * Mind Map — live agent routing network.
 *
 * Previous version:
 *  - Listed 9 agents (3 deprecated: documents, personal_projects, research)
 *  - Ignored litNode prop from parent (used own internal state instead)
 *  - Used /history for stats (query counts only, no routing data)
 *  - No real-time activity
 *
 * This version:
 *  - 7 agents in hexagonal layout (coordinator + current 6 specialists)
 *  - Fetches /decisions for real routing data (conflict rates, regret, agent health)
 *  - Properly responds to litNode prop from App.js (Chat → MindMap live link)
 *  - Auto-replays recent decisions as animated routing lines (pauses when user interacts)
 *  - Node glow intensity reflects usage; orange glow = high conflict rate
 *  - Side panel shows recent decision feed when nothing is selected,
 *    or per-agent stats (weight, calibration, conflicts, recent queries) when selected
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { T, SEM } from "./theme";
import { AGENTS as BASE_AGENTS } from "./constants";

import { API } from "./api";

// Layout positions for the hexagonal mind map (unique to this component).
// icon/color come from constants.js; only x/y/size/center/shortLabel live here.
const LAYOUT = {
  coordinator:        { x: 50, y: 50, size: 80, center: true,  label: "Coordinator" },
  it_networking:      { x: 50, y: 7,  size: 64, label: "Networking"  },
  python_dev:         { x: 84, y: 29, size: 64, label: "Python"      },
  dotnet_dev:         { x: 84, y: 71, size: 64, label: ".NET"        },
  knowledge_learning: { x: 50, y: 93, size: 64, label: "Knowledge"   },
  ai_ml:              { x: 16, y: 71, size: 64, label: "AI / ML"     },
  terse:              { x: 16, y: 29, size: 64, label: "Terse"       },
};

const AGENTS = BASE_AGENTS
  .filter(a => LAYOUT[a.id])
  .map(a => ({ ...a, ...LAYOUT[a.id] }));

const VALID_IDS = new Set(AGENTS.map(a => a.id));

export default function MindMapInteractive({ onForceAgent, litNode: litNodeProp }) {
  const [decisions,   setDecisions]   = useState([]);
  const [agentHealth, setAgentHealth] = useState({});
  const [selected,    setSelected]    = useState(null);
  const [litNode,     setLitNode]     = useState(null);
  const [animLine,    setAnimLine]    = useState(null);
  const [replayIdx,   setReplayIdx]   = useState(0);
  const [online,      setOnline]      = useState(false);
  const [updatedAt,   setUpdatedAt]   = useState(null);

  const cycleRef   = useRef(null);
  const pauseRef   = useRef(false);   // true while parent-driven animation is running

  // ── Data fetch ────────────────────────────────────────────
  const loadData = useCallback(async () => {
    try {
      const r = await fetch(`${API}/decisions?limit=60`);
      if (!r.ok) throw new Error("not ok");
      const d = await r.json();
      setDecisions(d.decisions || []);
      setAgentHealth(d.agents   || {});
      setOnline(true);
      setUpdatedAt(new Date().toLocaleTimeString());
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 15_000);
    return () => clearInterval(id);
  }, [loadData]);

  // ── Respond to litNode prop (Chat → MindMap live link) ────
  // When Chat routes a query, App.js sets litNode prop:
  //   "coordinator" first → then the final agent → then null
  // We mirror that here and pause the auto-cycle briefly.
  useEffect(() => {
    if (!litNodeProp) return;

    pauseRef.current = true;
    setLitNode(litNodeProp);

    if (litNodeProp !== "coordinator" && VALID_IDS.has(litNodeProp)) {
      const agent = AGENTS.find(a => a.id === litNodeProp);
      setAnimLine({ from: "coordinator", to: litNodeProp, color: agent?.color || T.success, conflict: false });
      const clearLine = setTimeout(() => setAnimLine(null), 1000);
      return () => clearTimeout(clearLine);
    }

    const resumePause = setTimeout(() => {
      pauseRef.current = false;
      setLitNode(null);
    }, 4000);

    return () => clearTimeout(resumePause);
  }, [litNodeProp]);

  // ── Auto-replay recent decisions ─────────────────────────
  // Cycles through the last 10 decisions every 3.5 s, animating
  // each routing path. Pauses when the user selects a node or
  // when a parent-driven animation is playing.
  const showDecision = useCallback((dec) => {
    if (!dec) return;
    const agentId = dec.final_agent;
    if (!VALID_IDS.has(agentId) || agentId === "coordinator") return;
    const agent = AGENTS.find(a => a.id === agentId);

    setLitNode("coordinator");
    setAnimLine({ from: "coordinator", to: agentId, color: agent?.color || T.success, conflict: dec.conflict });

    const step2 = setTimeout(() => {
      setLitNode(agentId);
      setAnimLine(null);
    }, 700);
    const step3 = setTimeout(() => setLitNode(null), 2600);

    return () => { clearTimeout(step2); clearTimeout(step3); };
  }, []);

  // Start / restart replay cycle when decisions change or selection is cleared
  useEffect(() => {
    if (cycleRef.current) clearInterval(cycleRef.current);
    if (!decisions.length) return;

    const pool = decisions.slice(0, 10);

    cycleRef.current = setInterval(() => {
      if (pauseRef.current || selected) return;
      setReplayIdx(prev => {
        const next = (prev + 1) % pool.length;
        showDecision(pool[next]);
        return next;
      });
    }, 3500);

    return () => clearInterval(cycleRef.current);
  }, [decisions, selected, showDecision]);

  // ── Per-agent stats from decision log ────────────────────
  const agentStats = {};
  AGENTS.forEach(a => { agentStats[a.id] = { count: 0, conflicts: 0, regretSum: 0, queries: [] }; });
  decisions.forEach(d => {
    const id = d.final_agent;
    if (id && agentStats[id]) {
      const s = agentStats[id];
      s.count++;
      if (d.conflict)              s.conflicts++;
      if (d.regret)                s.regretSum += d.regret;
      if (d.task && s.queries.length < 3) s.queries.push(d.task);
    }
  });

  const totalDecisions = decisions.length;
  const recentFeed     = decisions.slice(0, 10);

  const selectedAgent  = AGENTS.find(a => a.id === selected?.id);
  const selStats       = selected ? agentStats[selected.id] : null;
  const selHealth      = selected ? agentHealth[selected.id] : null;

  const getCoords = (fromId, toId) => {
    const f = AGENTS.find(a => a.id === fromId);
    const t = AGENTS.find(a => a.id === toId);
    return f && t ? { x1: f.x, y1: f.y, x2: t.x, y2: t.y } : null;
  };

  const handleNodeClick = (agent) => {
    setSelected(prev => prev?.id === agent.id ? null : agent);
  };

  // ── Render ────────────────────────────────────────────────
  return (
    <div>
      <style>{`
        @keyframes nodePulse {
          0%,100% { transform: translate(-50%,-50%) scale(1);   opacity: 1 }
          50%      { transform: translate(-50%,-50%) scale(1.1); opacity: .75 }
        }
        @keyframes lineFlow {
          from { stroke-dashoffset: 20 }
          to   { stroke-dashoffset: 0  }
        }
        @keyframes mmFadeIn {
          from { opacity: 0; transform: translateX(10px) }
          to   { opacity: 1; transform: none }
        }
        .mm-node { transition: box-shadow 0.25s, background 0.25s, border-color 0.25s; }
        .mm-node:hover { filter: brightness(1.28) !important; cursor: pointer; }
      `}</style>

      {/* ── Header bar ── */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 99,
          background: online ? "#E7F2E6" : "#F9E7E1",
          color:      online ? T.success : T.error,
          border: `1px solid ${online ? `${T.success}44` : `${T.error}44`}` }}>
          {online ? "● LIVE" : "○ OFFLINE"}
        </div>
        {updatedAt && (
          <span style={{ fontSize: 11, color: T.muted }}>updated {updatedAt}</span>
        )}
        <span style={{ fontSize: 11, color: T.muted }}>
          · {totalDecisions} decisions
        </span>
        {selected && (
          <span style={{ fontSize: 11, color: T.accent2 }}>· replay paused</span>
        )}
        <button onClick={() => { setSelected(null); loadData(); }}
          style={{ marginLeft: "auto", background: "transparent", border: `1px solid ${T.border}`,
            borderRadius: 99, color: T.muted, padding: "5px 12px",
            fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
          ↻ Refresh
        </button>
      </div>

      <div style={{ display: "flex", gap: 14 }}>

        {/* ── Map canvas ── */}
        <div style={{
          flex: 1, position: "relative", height: 450,
          background: "radial-gradient(ellipse at 50% 50%, #E7F2E6 0%, #F7F3EC 72%)",
          border: `1px solid ${T.border}`, borderRadius: 14, overflow: "hidden",
        }}>

          {/* SVG: connection lines + animated routing line */}
          <svg width="100%" height="100%" style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}>
            {AGENTS.filter(a => !a.center).map(a => {
              const isHighlighted = selected?.id === a.id || litNode === a.id;
              return (
                <line key={a.id}
                  x1="50%" y1="50%"
                  x2={`${a.x}%`} y2={`${a.y}%`}
                  stroke={isHighlighted ? `${a.color}55` : T.surface}
                  strokeWidth={isHighlighted ? 2 : 1.5}
                  strokeDasharray="6,5"
                  style={{ transition: "stroke 0.3s, stroke-width 0.3s" }}
                />
              );
            })}

            {animLine && (() => {
              const c = getCoords(animLine.from, animLine.to);
              if (!c) return null;
              return (
                <line
                  x1={`${c.x1}%`} y1={`${c.y1}%`}
                  x2={`${c.x2}%`} y2={`${c.y2}%`}
                  stroke={animLine.conflict ? SEM.clay : animLine.color}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray="10,6"
                  style={{ animation: "lineFlow 0.45s linear infinite", opacity: 0.9 }}
                />
              );
            })()}
          </svg>

          {/* Agent nodes */}
          {AGENTS.map(agent => {
            const s              = agentStats[agent.id];
            const isLit          = litNode === agent.id;
            const isSelected     = selected?.id === agent.id;
            const conflictRate   = s.count > 0 ? s.conflicts / s.count : 0;
            const highConflict   = conflictRate > 0.40 && s.count >= 4;
            const usageFrac      = totalDecisions > 0 ? s.count / totalDecisions : 0;

            return (
              <div key={agent.id}
                className="mm-node"
                onClick={() => handleNodeClick(agent)}
                style={{
                  position: "absolute",
                  left: `${agent.x}%`, top: `${agent.y}%`,
                  transform: "translate(-50%,-50%)",
                  width: agent.size, height: agent.size,
                  background: isLit || isSelected ? `${agent.color}25` : `${agent.color}0e`,
                  border: `2px solid ${isSelected ? agent.color : isLit ? agent.color + "cc" : agent.color + "55"}`,
                  borderRadius: agent.center ? 16 : 10,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexDirection: "column", textAlign: "center",
                  color: agent.color,
                  boxShadow: isLit
                    ? `0 0 28px ${agent.color}cc`
                    : isSelected
                      ? `0 0 18px ${agent.color}88`
                      : highConflict
                        ? `0 0 16px ${SEM.clay}77`
                        : s.count > 0
                          ? `0 0 ${8 + usageFrac * 24}px ${agent.color}44`
                          : "none",
                  animation: isLit ? "nodePulse .65s ease-in-out infinite" : "none",
                  zIndex: isSelected ? 10 : 2,
                }}>
                <div style={{ fontSize: agent.center ? 20 : 15 }}>{agent.icon}</div>
                <div style={{ fontSize: agent.center ? 8.5 : 7.5, fontWeight: 700, lineHeight: 1.3,
                  padding: "0 4px", color: isLit || isSelected ? agent.color : agent.color + "bb" }}>
                  {agent.label}
                </div>
                {s.count > 0 && (
                  <div style={{ fontSize: 8, marginTop: 2,
                    background: highConflict ? `${SEM.clay}22` : `${agent.color}22`,
                    color: highConflict ? SEM.clay : agent.color,
                    borderRadius: 99, padding: "1px 5px", fontWeight: 700 }}>
                    {s.count}{highConflict ? " ⚡" : ""}
                  </div>
                )}
              </div>
            );
          })}

          {/* Replay badge */}
          {!selected && decisions.length > 0 && (
            <div style={{ position: "absolute", bottom: 10, left: 12, fontSize: 10,
              color: T.muted, background: `${T.surface2}99`, padding: "3px 8px", borderRadius: 99 }}>
              ↻ replaying recent decisions
            </div>
          )}
        </div>

        {/* ── Right panel ── */}
        <div style={{ width: 240, flexShrink: 0, display: "flex", flexDirection: "column" }}>

          {/* Selected agent detail */}
          {selected && selectedAgent ? (
            <div className="lux-card" style={{ padding: 14, animation: "mmFadeIn .18s ease", flex: 1 }}>

              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                <div style={{ width: 38, height: 38, background: `${selectedAgent.color}1a`,
                  border: `2px solid ${selectedAgent.color}`, borderRadius: 12,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>
                  {selectedAgent.icon}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: selectedAgent.color }}>{selectedAgent.label}</div>
                  <div style={{ fontSize: 10, color: T.muted }}>{selStats.count} decisions</div>
                </div>
                <button onClick={() => setSelected(null)}
                  style={{ background: "transparent", border: "none", color: T.muted,
                    cursor: "pointer", fontSize: 16, padding: "2px 4px", lineHeight: 1 }}>✕</button>
              </div>

              {/* 2×2 stats grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 12 }}>
                {[
                  { label: "Decisions", value: selStats.count },
                  { label: "Conflicts",
                    value: selStats.conflicts,
                    warn: selStats.count > 0 && selStats.conflicts / selStats.count > 0.40 },
                  { label: "Weight",
                    value: selHealth?.weight != null ? selHealth.weight.toFixed(3) : "—" },
                  { label: "Conf",
                    value: selHealth?.confidence != null ? `${Math.round(selHealth.confidence * 100)}%` : "—" },
                ].map(({ label, value, warn }) => (
                  <div key={label} style={{ background: T.surface2, borderRadius: 10, padding: "8px 10px",
                    border: warn ? `1px solid ${SEM.clay}33` : `1px solid ${T.border}` }}>
                    <div style={{ fontSize: 16, fontWeight: 800, color: warn ? SEM.clay : selectedAgent.color }}>
                      {value}
                    </div>
                    <div style={{ fontSize: 10, color: T.muted, marginTop: 1 }}>{label}</div>
                  </div>
                ))}
              </div>

              {/* Conflict rate bar */}
              {selStats.count > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 10, color: T.muted }}>Conflict rate</span>
                    <span style={{ fontSize: 10, color: T.muted }}>
                      {Math.round(selStats.conflicts / selStats.count * 100)}%
                    </span>
                  </div>
                  <div style={{ height: 4, background: T.border, borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", borderRadius: 2, transition: "width 0.4s",
                      width: `${(selStats.conflicts / selStats.count) * 100}%`,
                      background: selStats.conflicts / selStats.count > 0.40
                        ? `linear-gradient(90deg,${SEM.clay},${T.error})`
                        : selectedAgent.color }} />
                  </div>
                </div>
              )}

              {/* Usage share bar */}
              {totalDecisions > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 10, color: T.muted }}>Usage share</span>
                    <span style={{ fontSize: 10, color: T.muted }}>
                      {Math.round(selStats.count / totalDecisions * 100)}%
                    </span>
                  </div>
                  <div style={{ height: 4, background: T.border, borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", borderRadius: 2, transition: "width 0.4s",
                      width: `${(selStats.count / totalDecisions) * 100}%`,
                      background: selectedAgent.color }} />
                  </div>
                </div>
              )}

              {/* Recent queries */}
              {selStats.queries.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: T.muted,
                    letterSpacing: "0.1em", marginBottom: 5 }}>RECENT QUERIES</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {selStats.queries.map((q, i) => (
                      <div key={i} style={{ fontSize: 11, color: T.text, background: T.surface2,
                        borderRadius: 8, padding: "5px 8px", lineHeight: 1.4,
                        border: `1px solid ${selectedAgent.color}18` }}>
                        "{q.slice(0, 48)}{q.length > 48 ? "…" : ""}"
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selected.id !== "coordinator" && (
                <button onClick={() => { onForceAgent?.(selected.id); setSelected(null); }}
                  style={{ width: "100%", background: selectedAgent.color, border: "none",
                    borderRadius: 99, color: T.surface2, padding: "9px 0",
                    fontSize: 12, fontWeight: 800, cursor: "pointer", fontFamily: "inherit",
                    marginTop: "auto" }}>
                  💬 Chat with this agent
                </button>
              )}
            </div>

          ) : (
            /* Recent decisions feed */
            <div style={{ background: T.surface, border: `1px solid ${T.border}`,
              borderRadius: 12, padding: 12, flex: 1, display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: T.muted,
                letterSpacing: "0.1em", marginBottom: 8 }}>RECENT DECISIONS</div>
              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 5 }}>
                {recentFeed.length === 0 ? (
                  <div style={{ fontSize: 12, color: T.muted, textAlign: "center", paddingTop: 24 }}>
                    No decisions yet
                  </div>
                ) : recentFeed.map((d, i) => {
                  const agent = AGENTS.find(a => a.id === d.final_agent);
                  return (
                    <div key={i}
                      onClick={() => { const a = AGENTS.find(x => x.id === d.final_agent); if (a) handleNodeClick(a); }}
                      style={{ padding: "6px 8px", background: T.surface2,
                        border: `1px solid ${d.conflict ? `${SEM.clay}22` : (agent?.color || T.muted) + "22"}`,
                        borderRadius: 8, cursor: "pointer", transition: "border-color 0.18s" }}
                      onMouseEnter={e => e.currentTarget.style.borderColor = (agent?.color || T.muted) + "55"}
                      onMouseLeave={e => e.currentTarget.style.borderColor = d.conflict ? `${SEM.clay}22` : (agent?.color || T.muted) + "22"}>
                      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 3 }}>
                        <span style={{ fontSize: 12 }}>{agent?.icon || "?"}</span>
                        <span style={{ fontSize: 10, fontWeight: 700, color: agent?.color || T.muted }}>
                          {(d.final_agent || "").replace(/_/g, " ")}
                        </span>
                        {d.conflict
                          ? <span style={{ fontSize: 9, color: SEM.clay, marginLeft: "auto" }}>⚡ conflict</span>
                          : <span style={{ fontSize: 9, color: T.muted, marginLeft: "auto" }}>{d.action}</span>}
                      </div>
                      <div style={{ fontSize: 10, color: T.muted, overflow: "hidden",
                        textOverflow: "ellipsis", whiteSpace: "nowrap", lineHeight: 1.3 }}>
                        {(d.task || "—").slice(0, 44)}{(d.task || "").length > 44 ? "…" : ""}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Agent legend */}
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${T.border}` }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: T.muted,
                  letterSpacing: "0.1em", marginBottom: 6 }}>AGENT USAGE</div>
                {AGENTS.filter(a => !a.center && agentStats[a.id].count > 0)
                  .sort((a, b) => agentStats[b.id].count - agentStats[a.id].count)
                  .map(a => {
                    const s   = agentStats[a.id];
                    const pct = totalDecisions > 0 ? s.count / totalDecisions : 0;
                    return (
                      <div key={a.id} onClick={() => handleNodeClick(a)}
                        style={{ display: "flex", alignItems: "center", gap: 6,
                          marginBottom: 4, cursor: "pointer" }}>
                        <span style={{ fontSize: 12, flexShrink: 0 }}>{a.icon}</span>
                        <div style={{ flex: 1, height: 3, background: T.border, borderRadius: 2, overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${pct * 100}%`, background: a.color, borderRadius: 2 }} />
                        </div>
                        <span style={{ fontSize: 10, color: T.muted, minWidth: 22, textAlign: "right" }}>
                          {s.count}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
