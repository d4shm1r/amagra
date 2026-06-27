import { useState, useEffect, useCallback, useRef } from "react";
import { API } from "./api";
import { T, FONT_MONO } from "./theme";
import { RefreshBtn, PageHeader } from "./ObsShared";

// ── Layout constants ──────────────────────────────────────────
const NODE_W  = 210;
const NODE_H  = 82;
const H_GAP   = 60;
const V_GAP   = 18;
const PAD     = 32;

// ── Color maps ────────────────────────────────────────────────
const STATUS_COLOR = {
  pending:   "#9A7A60",
  running:   "#A16207",
  completed: "#2E7D32",
  failed:    "#B42318",
};

const STATUS_BG = {
  pending:   "#FAF7F2",
  running:   "#F5EDD6",
  completed: "#E7F2E6",
  failed:    "#F9E7E1",
};

const STATUS_BORDER = {
  pending:   "#E5DCCC",
  running:   "#A07010",
  completed: "#2A6030",
  failed:    "#803030",
};

const AGENT_COLOR = {
  python_dev:         "#1E5A8A",
  ai_ml:              "#1E5A8A",
  it_networking:      "#0F766E",
  dotnet_dev:         "#B05B3B",
  knowledge_learning: "#7E3F8F",
  terse:              "#9A7A60",
};

function sColor(s)  { return STATUS_COLOR[s]   || "#9A7A60"; }
function sBg(s)     { return STATUS_BG[s]       || "#FAF7F2"; }
function sBorder(s) { return STATUS_BORDER[s]   || "#E0D6C4"; }
function aColor(a)  { return AGENT_COLOR[a]     || T.muted; }


// ── Compute (x, y) for every node ────────────────────────────
function buildLayout(levels, nodeMap) {
  const maxNodes    = Math.max(1, ...levels.map(g => g.length));
  const canvasH     = PAD * 2 + maxNodes * (NODE_H + V_GAP) - V_GAP;
  const canvasW     = PAD * 2 + levels.length * (NODE_W + H_GAP) - H_GAP;
  const pos         = {};

  levels.forEach((group, li) => {
    const colH     = group.length * NODE_H + Math.max(0, group.length - 1) * V_GAP;
    const startY   = (canvasH - colH) / 2;
    const x        = PAD + li * (NODE_W + H_GAP);
    group.forEach((sid, i) => {
      pos[sid] = { x, y: startY + i * (NODE_H + V_GAP) };
    });
  });

  return { pos, canvasW, canvasH };
}


// ── SVG edge (cubic bezier) ───────────────────────────────────
function Edge({ srcPos, tgtPos, status }) {
  const sx = srcPos.x + NODE_W;
  const sy = srcPos.y + NODE_H / 2;
  const tx = tgtPos.x;
  const ty = tgtPos.y + NODE_H / 2;
  const mx = (sx + tx) / 2;
  const color = sColor(status);

  return (
    <path
      d={`M ${sx} ${sy} C ${mx} ${sy} ${mx} ${ty} ${tx} ${ty}`}
      fill="none"
      stroke={color}
      strokeWidth={1.5}
      strokeOpacity={0.55}
      strokeDasharray={status === "pending" ? "4 4" : undefined}
    />
  );
}


// ── SVG node (foreignObject for clean text layout) ────────────
function Node({ node, x, y, selected, onClick }) {
  const bg     = sBg(node.status);
  const border = sBorder(node.status);
  const sc     = sColor(node.status);
  const ac     = aColor(node.agent);
  const uPct   = Math.round(node.uncertainty * 100);

  return (
    <g
      transform={`translate(${x},${y})`}
      style={{ cursor: "pointer" }}
      onClick={onClick}
    >
      {/* selection ring */}
      {selected && (
        <rect
          x={-2} y={-2}
          width={NODE_W + 4} height={NODE_H + 4}
          rx={10} fill="none"
          stroke={T.accent} strokeWidth={1.5}
        />
      )}

      {/* background */}
      <rect
        width={NODE_W} height={NODE_H}
        rx={9}
        fill={bg}
        stroke={border}
        strokeWidth={1}
      />

      {/* left status bar */}
      <rect
        width={4} height={NODE_H}
        rx={2}
        fill={sc}
        opacity={0.9}
      />

      {/* content via foreignObject */}
      <foreignObject x={10} y={0} width={NODE_W - 16} height={NODE_H}>
        <div
          xmlns="http://www.w3.org/1999/xhtml"
          style={{
            height: NODE_H,
            display: "flex", flexDirection: "column",
            justifyContent: "space-between",
            padding: "8px 0 8px",
            boxSizing: "border-box",
          }}
        >
          {/* top: step_id + agent badge */}
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{
              fontFamily: FONT_MONO, fontSize: 9, color: T.muted,
              flexShrink: 0,
            }}>{node.id}</span>
            <span style={{
              marginLeft: "auto",
              fontFamily: FONT_MONO, fontSize: 9, fontWeight: 700,
              color: ac, whiteSpace: "nowrap", flexShrink: 0,
            }}>{node.agent}</span>
          </div>

          {/* description */}
          <div style={{
            fontSize: 11, color: T.text, lineHeight: 1.35,
            overflow: "hidden",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
          }}>
            {node.description}
          </div>

          {/* bottom: status + uncertainty bar + timing */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, color: sc,
              textTransform: "uppercase", letterSpacing: "0.06em",
            }}>{node.status}</span>
            <div style={{
              flex: 1, height: 3, borderRadius: 2,
              background: "#E5DCCC", overflow: "hidden",
            }}>
              <div style={{
                width: `${uPct}%`, height: "100%",
                background: uPct > 60 ? T.error : uPct > 35 ? T.warn : T.success,
              }} />
            </div>
            {node.elapsed_ms > 0 && (
              <span style={{
                fontFamily: FONT_MONO, fontSize: 9,
                color: node.elapsed_ms > 5000 ? T.warn : T.muted,
                flexShrink: 0,
              }}>{node.elapsed_ms < 1000
                ? `${Math.round(node.elapsed_ms)}ms`
                : `${(node.elapsed_ms / 1000).toFixed(1)}s`}</span>
            )}
            <span style={{
              fontFamily: FONT_MONO, fontSize: 9, color: T.muted,
              flexShrink: 0,
            }}>u {uPct}%</span>
          </div>
        </div>
      </foreignObject>
    </g>
  );
}


// ── Detail panel shown below the SVG ─────────────────────────
function NodeDetail({ node, onClose }) {
  if (!node) return null;

  const rows = [
    ["Agent",            node.agent],
    ["Action type",      node.action_type || "—"],
    ["Status",           node.status],
    ["Elapsed",          node.elapsed_ms > 0
      ? (node.elapsed_ms < 1000
          ? `${Math.round(node.elapsed_ms)} ms`
          : `${(node.elapsed_ms / 1000).toFixed(2)} s`)
      : "—"],
    ["Uncertainty",      `${Math.round(node.uncertainty * 100)}%`],
    ["Depends on",       node.depends_on?.join(", ") || "none"],
    ["Success criteria", node.success_criteria || "—"],
    ...(node.result_snippet ? [["Result", node.result_snippet]] : []),
  ];

  return (
    <div style={{
      marginTop: 12,
      background: T.surface2 || "#FAF7F2",
      border: `1px solid ${T.border}`,
      borderRadius: 12, padding: "14px 18px",
      position: "relative",
    }}>
      <button
        onClick={onClose}
        style={{
          position: "absolute", top: 10, right: 12,
          background: "transparent", border: "none", color: T.muted,
          cursor: "pointer", fontSize: 14, lineHeight: 1, padding: 0,
        }}
      >✕</button>

      <div style={{
        fontFamily: FONT_MONO, fontSize: 10, color: T.muted,
        textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8,
      }}>
        {node.id}
      </div>
      <div style={{ fontSize: 13, color: T.text, marginBottom: 12 }}>
        {node.description}
      </div>

      <table style={{
        width: "100%", borderCollapse: "collapse",
        fontSize: 11, fontFamily: FONT_MONO,
      }}>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} style={{ borderBottom: `1px solid ${T.border}22` }}>
              <td style={{ padding: "5px 12px 5px 0", color: T.muted, whiteSpace: "nowrap", verticalAlign: "top" }}>
                {k}
              </td>
              <td style={{ padding: "5px 0", color: T.text, wordBreak: "break-word" }}>
                {v}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


// ── Main component ────────────────────────────────────────────
export default function PlanGraphTab({ embedded = false } = {}) {
  const [data,       setData]       = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [selected,   setSelected]   = useState(null);
  const svgRef = useRef(null);

  const fetch_ = useCallback(async () => {
    try {
      setLoading(true);
      const r = await fetch(`${API}/plan/graph`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setData(d);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch_();
    const id = setInterval(fetch_, 15000);
    return () => clearInterval(id);
  }, [fetch_]);

  const hasGraph = data && data.nodes?.length > 0;
  const nodeMap  = hasGraph
    ? Object.fromEntries(data.nodes.map(n => [n.id, n]))
    : {};

  // levels array — use data.levels if present, else derive from node.level
  const levels = hasGraph
    ? (data.levels?.length
        ? data.levels
        : (() => {
            const byLvl = {};
            data.nodes.forEach(n => {
              (byLvl[n.level] = byLvl[n.level] || []).push(n.id);
            });
            return Object.keys(byLvl).sort((a, b) => a - b).map(k => byLvl[k]);
          })())
    : [];

  const { pos, canvasW, canvasH } = hasGraph
    ? buildLayout(levels, nodeMap)
    : { pos: {}, canvasW: 0, canvasH: 0 };

  const selectedNode = selected ? nodeMap[selected] : null;

  // Determine overall status bar distribution
  const statusCounts = hasGraph
    ? data.nodes.reduce((acc, n) => {
        acc[n.status] = (acc[n.status] || 0) + 1;
        return acc;
      }, {})
    : {};

  return (
    <div style={{ color: T.text, fontFamily: "inherit", padding: embedded ? "10px 14px 14px" : 0 }}>

      {/* ── Header (suppressed when embedded — the dashboard cell carries the title) ── */}
      {!embedded && (
      <PageHeader
        title="Plan Graph"
        subtitle={hasGraph && data.meta
          ? `${data.meta.mode} · ${data.meta.steps} steps · u ${Math.round(data.meta.uncertainty * 100)}% · ${data.meta.elapsed_ms}ms`
          : "Execution DAG — live step status, agents, dependencies"}
      >
        <RefreshBtn onClick={fetch_} />
      </PageHeader>
      )}

      {/* ── Status counts ── */}
      {hasGraph && Object.keys(statusCounts).length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
          {Object.entries(statusCounts).map(([s, n]) => (
            <span key={s} style={{
              fontSize: 10, fontWeight: 700, fontFamily: FONT_MONO,
              color: sColor(s), background: `${sColor(s)}18`,
              border: `1px solid ${sColor(s)}44`,
              borderRadius: 99, padding: "3px 11px",
            }}>
              {n} {s}
            </span>
          ))}
        </div>
      )}

      {/* ── Query label ── */}
      {hasGraph && data.meta?.query && (
        <div style={{
          marginBottom: 14,
          fontFamily: FONT_MONO, fontSize: 11,
          color: T.muted,
          background: T.surface2 || "#FAF7F2",
          border: `1px solid ${T.border}`,
          borderRadius: 10, padding: "8px 13px",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          <span style={{ color: T.accent, marginRight: 6 }}>query</span>
          {data.meta.query}
        </div>
      )}

      {/* ── Parallel groups legend ── */}
      {hasGraph && levels.length > 0 && (
        <div style={{
          display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap",
        }}>
          {levels.map((group, li) => (
            <div key={li} style={{
              background: T.surface2 || "#FAF7F2",
              border: `1px solid ${T.border}`,
              borderRadius: 99, padding: "3px 11px",
              fontSize: 10, fontFamily: FONT_MONO,
              color: T.muted,
            }}>
              <span style={{ color: T.accent }}>L{li}</span>
              {" "}
              {group.join(", ")}
              {group.length > 1 && (
                <span style={{ color: T.success, marginLeft: 5 }}>parallel</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── SVG canvas ── */}
      {error && (
        <div style={{ color: T.error, fontFamily: FONT_MONO, fontSize: 12, padding: "16px 0" }}>
          {error}
        </div>
      )}

      {!error && !hasGraph && !loading && (
        <div style={{
          padding: "40px 24px", textAlign: "center",
          display: "flex", flexDirection: "column", alignItems: "center", gap: 14,
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: 10,
            background: `${STATUS_COLOR.pending}18`,
            border: `1px solid ${STATUS_COLOR.pending}44`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 22,
          }}>⊢</div>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.text || "#2E2010" }}>
            No execution plan active
          </div>
          <div style={{ fontSize: 12, color: T.muted || "#9A7A60", maxWidth: 380, lineHeight: 1.6 }}>
            Send a <strong style={{ color: T.text || "#2E2010" }}>compound query</strong> from the Chat tab
            to generate a multi-step plan. The DAG will appear here with live step statuses,
            agent assignments, and dependency edges.
          </div>
          <div style={{
            display: "flex", flexDirection: "column", gap: 6, marginTop: 4,
            textAlign: "left", maxWidth: 360,
          }}>
            {[
              "Build a REST API with authentication and SQLite",
              "Analyse this CSV, find outliers, and write a report",
              "Set up a React app with routing and a dark mode toggle",
            ].map((example, i) => (
              <div key={i} style={{
                background: (T.surface2 || "#F4F0E8"),
                border: `1px solid ${T.border || "#E0D6C4"}`,
                borderRadius: 6, padding: "8px 14px",
                fontSize: 11, color: T.muted || "#9A7A60",
                fontFamily: FONT_MONO,
              }}>
                {example}
              </div>
            ))}
          </div>
          <div style={{ fontSize: 10, color: T.muted || "#9A7A60", marginTop: 4 }}>
            Compound queries trigger the planner — simple questions go direct to an agent.
          </div>
        </div>
      )}

      {hasGraph && (
        <div className="lux-card" style={{
          overflowX: "auto", padding: 0,
        }}>
          <svg
            ref={svgRef}
            width={canvasW}
            height={canvasH}
            style={{ display: "block" }}
          >
            {/* edges drawn first (behind nodes) */}
            {data.edges.map((e, i) => {
              const src = pos[e.source];
              const tgt = pos[e.target];
              if (!src || !tgt) return null;
              const tgtNode = nodeMap[e.target];
              return (
                <Edge
                  key={i}
                  srcPos={src}
                  tgtPos={tgt}
                  status={tgtNode?.status || "pending"}
                />
              );
            })}

            {/* nodes */}
            {data.nodes.map(node => {
              const p = pos[node.id];
              if (!p) return null;
              return (
                <Node
                  key={node.id}
                  node={node}
                  x={p.x}
                  y={p.y}
                  selected={selected === node.id}
                  onClick={() => setSelected(
                    selected === node.id ? null : node.id
                  )}
                />
              );
            })}

            {/* column level labels */}
            {levels.map((_, li) => (
              <text
                key={li}
                x={PAD + li * (NODE_W + H_GAP) + NODE_W / 2}
                y={canvasH - 6}
                textAnchor="middle"
                fontSize={9}
                fill={T.muted}
                fontFamily={FONT_MONO}
              >
                L{li}
              </text>
            ))}
          </svg>
        </div>
      )}

      {/* ── Node detail panel ── */}
      {selectedNode && (
        <NodeDetail
          node={selectedNode}
          onClose={() => setSelected(null)}
        />
      )}

    </div>
  );
}
