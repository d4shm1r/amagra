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
import { T, SEM, RADIUS } from "@/styles/theme";
import { AGENTS as BASE_AGENTS } from "@/config/constants";
import { PageHeader } from "@/components/ui";

import { API } from "@/lib/api";

// Layout positions for the hexagonal mind map (unique to this component).
// icon/color come from constants.js; only x/y/size/center/shortLabel live here.
const LAYOUT = {
  coordinator:        { x: 50, y: 50, size: 96, center: true,  label: "Coordinator" },
  it_networking:      { x: 50, y: 9,  size: 76, label: "Networking"  },
  python_dev:         { x: 84, y: 30, size: 76, label: "Python"      },
  dotnet_dev:         { x: 84, y: 70, size: 76, label: ".NET"        },
  knowledge_learning: { x: 50, y: 91, size: 76, label: "Knowledge"   },
  ai_ml:              { x: 16, y: 70, size: 76, label: "AI / ML"     },
  terse:              { x: 16, y: 30, size: 76, label: "Terse"       },
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
          0%,100% { transform: translate(-50%,-50%) scale(1);   }
          50%      { transform: translate(-50%,-50%) scale(1.09); }
        }
        @keyframes lineFlow {
          from { stroke-dashoffset: 32 }
          to   { stroke-dashoffset: 0  }
        }
        @keyframes mmFadeIn {
          from { opacity: 0; transform: translateX(10px) }
          to   { opacity: 1; transform: none }
        }
        @keyframes mmHalo {
          0%,100% { transform: translate(-50%,-50%) scale(1);    opacity: .55 }
          50%      { transform: translate(-50%,-50%) scale(1.22); opacity: .08 }
        }
        @keyframes mmOrbit { to { transform: translate(-50%,-50%) rotate(360deg); } }
        .mm-node { transition: box-shadow .3s ease, background .3s ease, border-color .3s ease, transform .3s cubic-bezier(.22,1,.36,1); }
        .mm-node:hover { transform: translate(-50%,-50%) scale(1.07) !important; cursor: pointer; filter: brightness(1.05); }
        .mm-refresh{
          position:relative; overflow:hidden; margin-left:auto; padding:7px 20px; border-radius:40px;
          font-family:inherit; font-size:11.5px; font-weight:600; letter-spacing:-0.01em;
          color:#5C4030; border:2px solid transparent; cursor:pointer;
          background:linear-gradient(#FCFAF7,#FCFAF7) padding-box, linear-gradient(145deg,#FFE880,#DEB838,#C48808) border-box;
          box-shadow:4px 4px 10px rgba(72,52,28,0.11),-2px -2px 7px rgba(255,255,255,0.80),inset 0 1px 1px rgba(255,255,255,0.94),inset 0 -1px 2px rgba(138,99,36,0.06);
          transition:transform 200ms cubic-bezier(0.22,1,0.36,1), box-shadow 200ms ease-out, color 140ms ease;
        }
        .mm-refresh::before{content:'';position:absolute;top:0;left:0;right:0;bottom:50%;background:linear-gradient(180deg,rgba(255,255,255,0.46) 0%,rgba(255,255,255,0) 100%);border-radius:40px 40px 0 0;pointer-events:none;z-index:1;}
        .mm-refresh:hover{color:#6C4C00;transform:translateY(-1px);box-shadow:6px 6px 16px rgba(62,44,20,0.17),-2px -2px 8px rgba(255,255,255,0.94),inset 0 1px 1px rgba(255,255,255,0.94),inset 0 -1px 2px rgba(138,99,36,0.10),0 0 24px rgba(196,136,8,0.13);}
      `}</style>

      <PageHeader
        center
        title="Mind Map"
        subtitle="The live agent routing network — the Coordinator and its specialists, lit as decisions flow through them."
      />

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
        <button className="mm-refresh" onClick={() => { setSelected(null); loadData(); }}>
          ↻ Refresh
        </button>
      </div>

      <div style={{ display: "flex", gap: 14, alignItems: "stretch", height: 600 }}>

        {/* ── Map canvas ── */}
        <div style={{
          flex: 1, position: "relative", height: "100%",
          background: `
            radial-gradient(circle at 1px 1px, ${T.border}44 1px, transparent 0) 0 0 / 24px 24px,
            radial-gradient(ellipse at 50% 44%, ${T.surface} 0%, ${T.bg} 82%)`,
          border: `1px solid ${T.border}`, borderRadius: RADIUS.lg, overflow: "hidden",
          boxShadow: `inset 0 1px 3px ${T.border}66, inset 0 0 60px ${T.accent}0a`,
        }}>

          {/* Decorative orbital rings behind the network */}
          {[420, 300, 190].map((d, i) => (
            <div key={d} style={{
              position: "absolute", left: "50%", top: "50%", width: d, height: d,
              transform: "translate(-50%,-50%)", borderRadius: "50%",
              border: `1px solid ${T.accent}${["10", "16", "1e"][i]}`, pointerEvents: "none",
            }} />
          ))}

          {/* SVG: connection lines + animated routing line */}
          <svg width="100%" height="100%" style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}>
            <defs>
              <filter id="mmGlow" x="-60%" y="-60%" width="220%" height="220%">
                <feGaussianBlur stdDeviation="3" result="b" />
                <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {AGENTS.filter(a => !a.center).map(a => {
              const isHighlighted = selected?.id === a.id || litNode === a.id;
              return (
                <line key={a.id}
                  x1="50%" y1="50%"
                  x2={`${a.x}%`} y2={`${a.y}%`}
                  stroke={isHighlighted ? `${a.color}66` : `${T.accent}1c`}
                  strokeWidth={isHighlighted ? 2 : 1.25}
                  strokeDasharray="5,6"
                  filter={isHighlighted ? "url(#mmGlow)" : undefined}
                  style={{ transition: "stroke 0.3s, stroke-width 0.3s" }}
                />
              );
            })}

            {animLine && (() => {
              const c = getCoords(animLine.from, animLine.to);
              if (!c) return null;
              const col = animLine.conflict ? SEM.clay : animLine.color;
              return (
                <g>
                  {/* soft halo underlay */}
                  <line
                    x1={`${c.x1}%`} y1={`${c.y1}%`} x2={`${c.x2}%`} y2={`${c.y2}%`}
                    stroke={col} strokeWidth="7" strokeLinecap="round"
                    style={{ opacity: 0.16 }}
                  />
                  {/* flowing dashed core */}
                  <line
                    x1={`${c.x1}%`} y1={`${c.y1}%`} x2={`${c.x2}%`} y2={`${c.y2}%`}
                    stroke={col} strokeWidth="2.5" strokeLinecap="round" strokeDasharray="11,7"
                    filter="url(#mmGlow)"
                    style={{ animation: "lineFlow 0.5s linear infinite", opacity: 0.95 }}
                  />
                  {/* traveling pulse */}
                  <circle r="4.5" fill={col} filter="url(#mmGlow)">
                    <animate attributeName="cx" values={`${c.x1}%;${c.x2}%`} dur="0.85s" repeatCount="indefinite" />
                    <animate attributeName="cy" values={`${c.y1}%;${c.y2}%`} dur="0.85s" repeatCount="indefinite" />
                  </circle>
                </g>
              );
            })()}
          </svg>

          {/* Coordinator core halo */}
          <div style={{
            position: "absolute", left: "50%", top: "50%", width: 160, height: 160,
            transform: "translate(-50%,-50%)", borderRadius: "50%", pointerEvents: "none",
            background: `radial-gradient(circle, ${T.accent}26 0%, transparent 68%)`,
            animation: "mmHalo 3.4s ease-in-out infinite",
          }} />

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
                  background: isLit || isSelected
                    ? `radial-gradient(circle at 34% 27%, ${agent.color}42, ${agent.color}16)`
                    : `radial-gradient(circle at 34% 27%, ${agent.color}1e, ${agent.color}08)`,
                  border: `2px solid ${isSelected ? agent.color : isLit ? agent.color + "cc" : agent.color + "4d"}`,
                  borderRadius: agent.center ? 22 : 16,
                  backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexDirection: "column", textAlign: "center",
                  color: agent.color,
                  boxShadow: (isLit
                    ? `0 0 30px ${agent.color}cc, 0 4px 14px ${agent.color}55`
                    : isSelected
                      ? `0 0 20px ${agent.color}88, 0 4px 12px ${agent.color}44`
                      : highConflict
                        ? `0 0 16px ${SEM.clay}77`
                        : s.count > 0
                          ? `0 0 ${8 + usageFrac * 24}px ${agent.color}44`
                          : `0 2px 8px ${T.border}66`)
                    + `, inset 0 1px 2px rgba(255,255,255,0.55)`,
                  animation: isLit ? "nodePulse .7s ease-in-out infinite" : "none",
                  zIndex: isSelected ? 10 : 2,
                }}>
                <div style={{ fontSize: agent.center ? 24 : 18, filter: `drop-shadow(0 1px 2px ${agent.color}55)` }}>{agent.icon}</div>
                <div style={{ fontSize: agent.center ? 9.5 : 8.5, fontWeight: 800, lineHeight: 1.3,
                  letterSpacing: "0.02em", padding: "0 4px",
                  color: isLit || isSelected ? agent.color : agent.color + "cc" }}>
                  {agent.label}
                </div>
                {s.count > 0 && (
                  <div style={{ fontSize: 8.5, marginTop: 3,
                    background: highConflict ? `${SEM.clay}26` : `${agent.color}22`,
                    color: highConflict ? SEM.clay : agent.color,
                    border: `1px solid ${highConflict ? SEM.clay : agent.color}33`,
                    borderRadius: 99, padding: "1px 6px", fontWeight: 800 }}>
                    {s.count}{highConflict ? " ⚡" : ""}
                  </div>
                )}
              </div>
            );
          })}

          {/* Replay badge */}
          {!selected && decisions.length > 0 && (
            <div style={{ position: "absolute", bottom: 12, left: 14, fontSize: 10, fontWeight: 600,
              color: T.accent2, background: `${T.surface}cc`, border: `1px solid ${T.accent}33`,
              padding: "4px 10px", borderRadius: 99, backdropFilter: "blur(4px)",
              boxShadow: `0 2px 8px ${T.border}66` }}>
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
            <div className="lux-card" style={{
              padding: 14, flex: 1, display: "flex", flexDirection: "column" }}>
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
