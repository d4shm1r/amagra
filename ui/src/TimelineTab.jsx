import { useState, useEffect, useCallback, useRef } from "react";
import { T as C } from "./theme";
import { PageHeader } from "./ObsShared";

const API = "http://localhost:8000";

const AGENT_META = {
  coordinator:        { label: "Coordinator",  icon: "👑", color: "#9A6C00" },
  it_networking:      { label: "Networking",   icon: "🌐", color: "#15803D" },
  python_dev:         { label: "Python Dev",   icon: "🐍", color: "#C48808" },
  dotnet_dev:         { label: ".NET / Blazor", icon: "⚡", color: "#7C3AED" },
  ai_ml:              { label: "AI & ML",      icon: "🤖", color: "#BE185D" },
  knowledge_learning: { label: "Knowledge",    icon: "📚", color: "#1E5A8A" },
  terse:              { label: "Terse",        icon: "🎯", color: "#9A6C00" },
};

function Badge({ label, color }) {
  return (
    <span style={{ background: `${color}22`, border: `1px solid ${color}55`,
      color, borderRadius: 4, padding: "2px 8px", fontSize: 10, fontWeight: 700,
      fontFamily: "monospace", whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

function Bar({ value, max = 1, color = C.success, width = 160, height = 10 }) {
  const pct = Math.min(1, Math.max(0, value / max));
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <rect x={0} y={0} width={width} height={height} fill="#E0D6C4" rx={3} />
      <rect x={0} y={0} width={width * pct} height={height} fill={color} rx={3} />
    </svg>
  );
}

// ── Coherence C(t) line chart ─────────────────────────────────
function CoherenceChart({ data }) {
  const [tip, setTip] = useState(null);

  if (!data || data.length < 2) {
    return (
      <div style={{ color: C.muted, textAlign: "center", padding: 30, fontSize: 12 }}>
        Collecting data — need 2+ decision windows
      </div>
    );
  }

  const W = 640, H = 200, PX = 42, PY = 22;
  const iW = W - 2 * PX, iH = H - 2 * PY;
  const xs = i => PX + (i / (data.length - 1)) * iW;
  const ys = v => PY + (1 - Math.max(0, Math.min(1, v))) * iH;

  const line = (key, col) => {
    const pts = data.map((d, i) => `${xs(i).toFixed(1)},${ys(d[key] ?? 0).toFixed(1)}`).join(" ");
    return <polyline key={key} points={pts} fill="none" stroke={col} strokeWidth={1.8}
      strokeLinejoin="round" strokeLinecap="round" />;
  };

  const ticks = [0, 0.25, 0.5, 0.75, 1.0];
  const xTicks = data.filter((_, i) => i % Math.max(1, Math.floor(data.length / 6)) === 0);

  return (
    <div style={{ position: "relative" }}>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }}
        onMouseLeave={() => setTip(null)}>
        {ticks.map(t => (
          <g key={t}>
            <line x1={PX} y1={ys(t)} x2={W - PX} y2={ys(t)} stroke={C.border} strokeDasharray="3,3" />
            <text x={PX - 5} y={ys(t) + 4} fill={C.muted} fontSize={9} textAnchor="end">{t.toFixed(2)}</text>
          </g>
        ))}
        {line("c_routing", C.accent)}
        {line("c_quality", "#7E3F8F")}
        {line("C", C.success)}
        {data.map((d, i) => (
          <circle key={i} cx={xs(i)} cy={ys(d.C ?? 0)} r={3} fill={C.success} opacity={0.85}
            style={{ cursor: "crosshair" }}
            onMouseEnter={() => setTip({ x: xs(i), y: ys(d.C ?? 0), d, i })} />
        ))}
        {xTicks.map(d => (
          <text key={d.window_idx} x={xs(d.window_idx)} y={H - 4}
            fill={C.muted} fontSize={8} textAnchor="middle">w{d.window_idx}</text>
        ))}
        <line x1={PX} y1={PY} x2={PX} y2={H - PY} stroke={C.border} />
        <line x1={PX} y1={H - PY} x2={W - PX} y2={H - PY} stroke={C.border} />
        {[["C(t)", C.success], ["C_routing", C.accent], ["C_quality", "#7E3F8F"]].map(([lbl, col], li) => (
          <g key={lbl} transform={`translate(${PX + li * 140}, ${PY - 8})`}>
            <line x1={0} y1={0} x2={16} y2={0} stroke={col} strokeWidth={1.8} />
            <text x={20} y={4} fill={C.muted} fontSize={9}>{lbl}</text>
          </g>
        ))}
        {tip && (
          <g>
            <line x1={tip.x} y1={PY} x2={tip.x} y2={H - PY} stroke="#1F140822" strokeDasharray="2,2" />
            <rect x={tip.x + 6} y={tip.y - 28} width={98} height={32} rx={3} fill="#FAF7F2" stroke={C.border} />
            <text x={tip.x + 10} y={tip.y - 15} fill={C.success} fontSize={9} fontFamily="monospace">
              C={tip.d.C?.toFixed(4)}
            </text>
            <text x={tip.x + 10} y={tip.y - 4} fill={C.muted} fontSize={8} fontFamily="monospace">
              w{tip.i} · cr={tip.d.c_routing?.toFixed(2)} cq={tip.d.c_quality?.toFixed(2)}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

// ── Routing accuracy milestones ───────────────────────────────
function AccuracyMilestones() {
  const milestones = [
    { label: "Action-first baseline (50-prompt)",        pct: 70, color: C.error,   note: "15 misroutes — structural" },
    { label: "Signal-first routing (50-prompt)",         pct: 92, color: C.warn,    note: "4 misroutes — boundary" },
    { label: "Signal + brain + LLM (100-prompt)",        pct: 97, color: C.success, note: "Full pipeline" },
    { label: "QuerySignal only — ablation (100-prompt)", pct: 99, color: C.accent,  note: "<2s, no LLM calls" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {milestones.map(m => (
        <div key={m.label}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 12, color: "#2E2010" }}>{m.label}</span>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <span style={{ fontSize: 11, color: C.muted }}>{m.note}</span>
              <span style={{ fontFamily: "monospace", fontWeight: 700, color: m.color, fontSize: 13 }}>{m.pct}%</span>
            </div>
          </div>
          <div style={{ width: "100%", height: 10, background: "#E0D6C4", borderRadius: 3, overflow: "hidden" }}>
            <div style={{ width: `${m.pct}%`, height: "100%", background: m.color, borderRadius: 3 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Drift health panel ────────────────────────────────────────
function DriftHealth({ drift }) {
  if (!drift) return null;

  const detectors = [
    {
      key:   "calibration_drift",
      label: "Calibration Drift",
      desc:  "confidence vs reflection divergence > 0.25",
      hit:   drift.flags?.some(f => f.type === "calibration_drift"),
      value: (() => {
        const errs = drift.calibration_errors || {};
        const vals = Object.values(errs);
        return vals.length ? Math.max(...vals).toFixed(3) : "–";
      })(),
      unit:  "max err",
    },
    {
      key:   "regret_explosion",
      label: "Regret Explosion",
      desc:  "mean routing regret (50) > 0.30",
      hit:   drift.flags?.some(f => f.type === "regret_explosion"),
      value: (drift.regret_mean_50 ?? 0).toFixed(4),
      unit:  "mean regret",
    },
    {
      key:   "weight_volatility",
      label: "Weight Volatility",
      desc:  "agent weight variance > 0.05",
      hit:   drift.flags?.some(f => f.type === "weight_volatility"),
      value: (drift.weight_variance ?? 0).toFixed(5),
      unit:  "variance",
    },
  ];

  return (
    <div style={{ background: drift.healthy ? "#E7F2E6" : "#F9E7E1",
      border: `1px solid ${drift.healthy ? "#15803D33" : "#B4231833"}`,
      borderRadius: 4, padding: "14px 18px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%",
          background: drift.healthy ? C.success : C.error }} />
        <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010" }}>
          System Drift Health
        </div>
        <Badge label={drift.healthy ? "ALL CLEAR" : `${drift.flags?.length || 0} FLAG${drift.flags?.length !== 1 ? "S" : ""}`}
          color={drift.healthy ? C.success : C.error} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
        {detectors.map(d => (
          <div key={d.key} style={{ background: d.hit ? "#B4231810" : "#F4F0E8",
            border: `1px solid ${d.hit ? "#B4231844" : "#E0D6C4"}`, borderRadius: 4,
            padding: "12px 14px" }}>
            <div style={{ display: "flex", align: "center", gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 12, lineHeight: 1 }}>{d.hit ? "🔴" : "🟢"}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: d.hit ? C.error : "#2E2010" }}>
                {d.label}
              </span>
            </div>
            <div style={{ fontFamily: "monospace", fontSize: 20, fontWeight: 700,
              color: d.hit ? C.error : C.success, marginBottom: 4 }}>{d.value}</div>
            <div style={{ fontSize: 10, color: C.muted }}>{d.unit}</div>
            <div style={{ fontSize: 10, color: C.muted, marginTop: 4, lineHeight: 1.4 }}>{d.desc}</div>
          </div>
        ))}
      </div>
      {drift.flags?.length > 0 && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 4 }}>
          {drift.flags.map((f, i) => (
            <div key={i} style={{ fontSize: 11, color: C.error, background: "#B4231810",
              border: "1px solid #B4231822", borderRadius: 3, padding: "5px 10px" }}>
              {f.detail}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Agent specialization table ────────────────────────────────
function SpecializationTable({ spec }) {
  if (!spec || Object.keys(spec).length === 0) return (
    <div style={{ color: C.muted, fontSize: 12 }}>No specialization data available.</div>
  );

  const VERDICT_COLOR = {
    core:       C.success,
    narrow:     C.accent,
    struggling: C.error,
    redundant:  C.warn,
  };

  const rows = Object.entries(spec)
    .map(([agent, s]) => ({ agent, ...s }))
    .sort((a, b) => (b.decisions || 0) - (a.decisions || 0));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ display: "grid",
        gridTemplateColumns: "160px 80px 80px 80px 80px 80px 1fr",
        gap: 8, padding: "6px 10px", fontSize: 10, color: C.muted, fontWeight: 700,
        fontFamily: "monospace", borderBottom: `1px solid ${C.border}` }}>
        {["AGENT","VERDICT","DECISIONS","CONFLICT","REGRET","QUALITY","DOMAINS"].map(h => (
          <span key={h}>{h}</span>
        ))}
      </div>
      {rows.map((r, i) => {
        const verdict  = r.verdict || "narrow";
        const vcol     = VERDICT_COLOR[verdict] || C.muted;
        const conflict = r.conflict_rate ?? 0;
        const regret   = r.avg_regret ?? 0;
        const quality  = r.avg_quality_proxy ?? 0;
        const meta     = AGENT_META[r.agent] || { label: r.agent, icon: "🤖", color: "#9A7A60" };
        const domains  = Object.keys(r.domains || {}).slice(0, 3).join(", ");
        return (
          <div key={r.agent} style={{ display: "grid",
            gridTemplateColumns: "160px 80px 80px 80px 80px 80px 1fr",
            gap: 8, padding: "8px 10px", alignItems: "center",
            background: i % 2 === 0 ? "#F4F0E866" : "transparent",
            borderRadius: 3 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: meta.color }}>
              {meta.icon} {meta.label}
            </span>
            <span style={{ background: `${vcol}22`, border: `1px solid ${vcol}55`,
              color: vcol, borderRadius: 3, padding: "1px 7px", fontSize: 10,
              fontFamily: "monospace", fontWeight: 700 }}>
              {verdict}
            </span>
            <span style={{ fontFamily: "monospace", fontSize: 12, color: "#2E2010" }}>
              {r.decisions || 0}
            </span>
            <span style={{ fontFamily: "monospace", fontSize: 11,
              color: conflict > 0.4 ? C.error : conflict > 0.2 ? C.warn : C.success }}>
              {Math.round(conflict * 100)}%
            </span>
            <span style={{ fontFamily: "monospace", fontSize: 11,
              color: regret > 0.15 ? C.error : regret > 0.08 ? C.warn : C.muted }}>
              {regret.toFixed(3)}
            </span>
            <span style={{ fontFamily: "monospace", fontSize: 11,
              color: quality >= 0.82 ? C.success : quality >= 0.68 ? C.warn : C.error }}>
              {quality.toFixed(3)}
            </span>
            <span style={{ fontSize: 10, color: C.muted, overflow: "hidden",
              textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {domains || "–"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Contradictions feed ───────────────────────────────────────
function ContradictionsFeed({ items }) {
  const [expanded, setExp] = useState(null);

  if (!items || items.length === 0) return (
    <div style={{ color: C.muted, fontSize: 12 }}>No contradiction events recorded.</div>
  );

  const LEVEL_COLOR = { low: C.warn, medium: C.warn, high: C.error };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>
        Queries where the agent self-corrected — reflect_level indicates correction intensity.
      </div>
      {items.slice(0, 12).map(ev => {
        const isOpen = expanded === ev.id;
        const meta   = AGENT_META[ev.agent] || { label: ev.agent, icon: "🤖", color: "#9A7A60" };
        const lv     = ev.reflect_level || "low";
        const lcol   = LEVEL_COLOR[lv] || C.muted;
        return (
          <div key={ev.id}
            onClick={() => setExp(isOpen ? null : ev.id)}
            style={{ background: "#FAF7F2", border: `1px solid ${isOpen ? lcol + "44" : C.border}`,
              borderRadius: 4, padding: "8px 12px", cursor: "pointer",
              transition: "border-color 0.15s" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 10, color: C.muted, fontFamily: "monospace", whiteSpace: "nowrap" }}>
                {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "–"}
              </span>
              <span style={{ background: `${meta.color}22`, color: meta.color,
                borderRadius: 3, padding: "1px 6px", fontSize: 10, fontFamily: "monospace" }}>
                {meta.icon} {meta.label}
              </span>
              <span style={{ background: `${lcol}22`, color: lcol,
                borderRadius: 3, padding: "1px 6px", fontSize: 10, fontFamily: "monospace" }}>
                {lv}
              </span>
              <span style={{ flex: 1, fontSize: 12, color: "#2E2010", overflow: "hidden",
                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {(ev.query || "").slice(0, 80)}
              </span>
              <span style={{ fontSize: 10, color: C.muted }}>{isOpen ? "▲" : "▼"}</span>
            </div>
            {isOpen && ev.response_snip && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${C.border}`,
                fontSize: 11, color: "#2E2010CC", lineHeight: 1.5,
                fontFamily: "Charter, 'Source Serif Pro', Georgia, serif" }}>
                {ev.response_snip}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Recent decisions table ────────────────────────────────────
function DecisionsTable({ decisions }) {
  const [page, setPage] = useState(0);
  const PAGE = 8;

  if (!decisions || decisions.length === 0) return (
    <div style={{ color: C.muted, fontSize: 12 }}>No decisions recorded yet.</div>
  );

  const pageData = decisions.slice(page * PAGE, (page + 1) * PAGE);
  const pages    = Math.ceil(decisions.length / PAGE);

  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {["#", "Task", "Agent", "Action", "Conflict", "Regret", "Time"].map(h => (
                <th key={h} style={{ padding: "5px 8px", textAlign: "left",
                  fontFamily: "monospace", fontSize: 10, color: C.muted, fontWeight: 700 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.map((d, i) => {
              const meta    = AGENT_META[d.final_agent] || { label: d.final_agent || "?", icon: "🤖", color: "#9A7A60" };
              const regret  = parseFloat(d.regret || 0);
              const conflict = d.has_conflict;
              const ts = d.timestamp ? new Date(d.timestamp).toLocaleTimeString() : "–";
              return (
                <tr key={d.id || i} style={{ borderBottom: `1px solid #E0D6C422`,
                  background: i % 2 === 0 ? "#F4F0E844" : "transparent" }}>
                  <td style={{ padding: "6px 8px", fontFamily: "monospace", color: C.muted }}>
                    {d.id || "–"}
                  </td>
                  <td style={{ padding: "6px 8px", color: "#2E2010", maxWidth: 220,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {(d.task || "").slice(0, 60)}
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    <span style={{ color: meta.color, fontSize: 11 }}>{meta.icon} {meta.label}</span>
                  </td>
                  <td style={{ padding: "6px 8px", fontFamily: "monospace", color: "#7E3F8F", fontSize: 10 }}>
                    {d.action || "–"}
                  </td>
                  <td style={{ padding: "6px 8px", textAlign: "center" }}>
                    {conflict
                      ? <span style={{ color: C.error, fontSize: 12 }}>✕</span>
                      : <span style={{ color: C.success, fontSize: 12 }}>✓</span>}
                  </td>
                  <td style={{ padding: "6px 8px", fontFamily: "monospace",
                    color: regret > 0.2 ? C.error : regret > 0.08 ? C.warn : C.muted }}>
                    {regret.toFixed(3)}
                  </td>
                  <td style={{ padding: "6px 8px", fontFamily: "monospace", color: C.muted, fontSize: 10 }}>
                    {ts}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div style={{ display: "flex", gap: 4, marginTop: 8, alignItems: "center" }}>
          <button disabled={page === 0} onClick={() => setPage(p => p - 1)}
            style={{ background: "#FAF7F2", border: `1px solid ${C.border}`, color: page === 0 ? C.muted : "#2E2010",
              borderRadius: 3, padding: "4px 10px", fontSize: 11, cursor: page === 0 ? "default" : "pointer",
              fontFamily: "inherit" }}>‹</button>
          <span style={{ fontSize: 11, color: C.muted }}>page {page + 1} of {pages}</span>
          <button disabled={page === pages - 1} onClick={() => setPage(p => p + 1)}
            style={{ background: "#FAF7F2", border: `1px solid ${C.border}`,
              color: page === pages - 1 ? C.muted : "#2E2010",
              borderRadius: 3, padding: "4px 10px", fontSize: 11,
              cursor: page === pages - 1 ? "default" : "pointer", fontFamily: "inherit" }}>›</button>
          <span style={{ fontSize: 10, color: C.muted, marginLeft: 4 }}>{decisions.length} total</span>
        </div>
      )}
    </div>
  );
}

// ── Auto-refresh countdown ────────────────────────────────────
function RefreshTimer({ onRefresh, interval = 30 }) {
  const [secs, setSecs] = useState(interval);
  const ref = useRef(null);

  useEffect(() => {
    setSecs(interval);
    ref.current = setInterval(() => {
      setSecs(s => {
        if (s <= 1) { onRefresh(); return interval; }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(ref.current);
  }, [onRefresh, interval]);

  const pct = ((interval - secs) / interval) * 100;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <svg width={20} height={20} style={{ flexShrink: 0 }}>
        <circle cx={10} cy={10} r={8} fill="none" stroke="#E0D6C4" strokeWidth={2} />
        <circle cx={10} cy={10} r={8} fill="none" stroke={C.success} strokeWidth={2}
          strokeDasharray={`${2 * Math.PI * 8}`}
          strokeDashoffset={`${2 * Math.PI * 8 * (1 - pct / 100)}`}
          transform="rotate(-90 10 10)" strokeLinecap="round" />
      </svg>
      <span style={{ fontSize: 11, color: C.muted }}>
        refresh in {secs}s
      </span>
      <button onClick={() => { onRefresh(); setSecs(interval); }}
        style={{ background: "#15803D22", border: `1px solid #15803D66`, color: C.success,
          padding: "4px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700,
          cursor: "pointer", fontFamily: "inherit" }}>
        ↺ Now
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────
export default function TimelineTab() {
  const [dynamics,  setDynamics]  = useState([]);
  const [cohState,  setCohState]  = useState(null);
  const [agentH,    setAgentH]    = useState([]);
  const [memCoh,    setMemCoh]    = useState([]);
  const [failures,  setFailures]  = useState(null);
  const [drift,     setDrift]     = useState(null);
  const [spec,      setSpec]      = useState(null);
  const [contras,   setContras]   = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [err,       setErr]       = useState(null);

  const load = useCallback(async () => {
    try {
      const [dyn, coh, dec, mem, fail, drift_, contra] = await Promise.all([
        fetch(`${API}/coherence/dynamics?window=20`).then(r => r.json()).catch(() => []),
        fetch(`${API}/coherence?window=20`).then(r => r.json()).catch(() => null),
        fetch(`${API}/decisions?limit=80`).then(r => r.json()).catch(() => ({})),
        fetch(`${API}/coherence/memory`).then(r => r.json()).catch(() => []),
        fetch(`${API}/analysis/failures?limit=295`).then(r => r.json()).catch(() => null),
        fetch(`${API}/learning/drift`).then(r => r.json()).catch(() => null),
        fetch(`${API}/contradictions?limit=20`).then(r => r.json()).catch(() => []),
      ]);

      setDynamics(Array.isArray(dyn) ? dyn : []);
      setCohState(coh && !coh.error ? coh : null);

      const ah = dec?.agent_health || [];
      setAgentH(Array.isArray(ah) ? ah.sort((a, b) => (b.weight || 0) - (a.weight || 0)) : []);
      setDecisions(Array.isArray(dec?.decisions) ? dec.decisions : []);

      setMemCoh(Array.isArray(mem) ? mem : []);
      setFailures(fail && !fail.error ? fail : null);
      setDrift(drift_ && !drift_.error ? drift_ : null);
      setContras(Array.isArray(contra) ? contra : []);
      setErr(null);

      // Specialization is slow (trace rebuild) — fire separately, non-blocking
      fetch(`${API}/analysis/specialization`)
        .then(r => r.json())
        .then(d => setSpec(d && !d.error ? d : null))
        .catch(() => {});

    } catch (e) {
      setErr(`Failed to load: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ color: C.muted, padding: 40, textAlign: "center" }}>Loading timeline data…</div>;
  if (err)     return <div style={{ color: C.error, padding: 20, fontFamily: "monospace" }}>{err}</div>;

  const C_val    = cohState?.C ?? 0;
  const cohColor = C_val >= 0.82 ? C.success : C_val >= 0.70 ? C.warn : C.error;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, animation: "fadeIn .2s" }}>

      {/* ── Header ── */}
      <PageHeader title="Learning Timeline" subtitle="Coherence dynamics, drift health, and how the system learns over time.">
        <RefreshTimer onRefresh={load} interval={30} />
      </PageHeader>

      {/* ── Drift health ── */}
      {drift && <DriftHealth drift={drift} />}

      {/* ── Top coherence metric cards ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
        {[
          { label: "Coherence C(t)", value: C_val.toFixed(4),
            sub: `routing ${cohState?.c_routing?.toFixed(2) ?? "–"} · calib ${cohState?.c_calib?.toFixed(2) ?? "–"}`,
            color: cohColor },
          { label: "Decisions logged", value: cohState?.n_decisions ?? "–",
            sub: `window of ${cohState?.window ?? 20}`, color: C.accent },
          { label: "Conflict rate",   value: `${Math.round((cohState?.conflict_rate ?? 0) * 100)}%`,
            sub: "brain vs router", color: (cohState?.conflict_rate ?? 0) > 0.35 ? C.error : C.warn },
          { label: "Reflection rate", value: `${Math.round((cohState?.reflection_rate ?? 0) * 100)}%`,
            sub: "triggers / decisions", color: C.warn },
          { label: "Memories",        value: cohState?.mem_n ?? "–",
            sub: `avg q ${cohState?.mem_avg_quality?.toFixed(3) ?? "–"}`, color: "#7E3F8F" },
          { label: "Reflection gain", value: cohState?.G_r_n > 0
              ? `${cohState.G_r_mean >= 0 ? "+" : ""}${cohState.G_r_mean?.toFixed(4)}` : "–",
            sub: `n=${cohState?.G_r_n ?? 0}  ${Math.round((cohState?.G_r_positive ?? 0) * 100)}% improved`,
            color: (cohState?.G_r_mean ?? 0) >= 0 ? C.success : C.error },
        ].map(m => (
          <div key={m.label} style={{ background: C.surface, border: `1px solid ${C.border}`,
            borderRadius: 4, padding: "14px 16px" }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>{m.label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "monospace", color: m.color }}>{m.value}</div>
            <div style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* ── Coherence dynamics chart ── */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010" }}>Coherence Dynamics — C(t)</div>
          <div style={{ display: "flex", gap: 6 }}>
            <Badge label={`${dynamics.length} windows`} color={C.muted} />
            <Badge label="w=20" color={C.muted} />
          </div>
        </div>
        <CoherenceChart data={dynamics} />
        <div style={{ fontSize: 11, color: C.muted, marginTop: 8 }}>
          Each window = 20 decisions with 50% overlap.
          C(t) = (C_routing + C_calib + C_quality) / 3. Hover dots for window detail.
        </div>
      </div>

      {/* ── Routing accuracy milestones ── */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010", marginBottom: 14 }}>Routing Accuracy — Progress</div>
        <AccuracyMilestones />
        <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <Badge label="McNemar χ²=5.88  p=0.015" color={C.success} />
          <Badge label="95% CI: 7–37 pts" color={C.success} />
          <Badge label="terse 0%→100% architectural signal" color={C.accent} />
        </div>
      </div>

      {/* ── Specialization table ── */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010" }}>
            Agent Specialization
            <span style={{ fontSize: 11, color: C.muted, fontWeight: 400, marginLeft: 8 }}>
              derived from trace dataset
            </span>
          </div>
          {!spec && <span style={{ fontSize: 11, color: C.muted }}>loading…</span>}
        </div>
        <SpecializationTable spec={spec} />
        <div style={{ fontSize: 10, color: C.muted, marginTop: 12 }}>
          Verdicts: <span style={{ color: C.success }}>core</span> = high volume, low conflict ·{" "}
          <span style={{ color: C.accent }}>narrow</span> = low volume, specialized ·{" "}
          <span style={{ color: C.error }}>struggling</span> = high conflict + regret ·{" "}
          <span style={{ color: C.warn }}>redundant</span> = domain overlap candidate
        </div>
      </div>

      {/* ── Agent health weights ── */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010", marginBottom: 14 }}>
          Agent Health — Live Weights
          <span style={{ fontSize: 11, color: C.muted, fontWeight: 400, marginLeft: 8 }}>sorted by weight</span>
        </div>
        {agentH.length === 0 ? (
          <div style={{ color: C.muted, fontSize: 12 }}>No agent health data yet.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {agentH.map((a, i) => {
              const w      = parseFloat(a.weight || 0);
              const conf   = parseFloat(a.confidence || 0);
              const regret = parseFloat(a.avg_regret || 0);
              const wColor = w >= 0.85 ? C.success : w >= 0.65 ? C.warn : C.error;
              return (
                <div key={a.agent} style={{ display: "grid",
                  gridTemplateColumns: "160px 1fr 70px 70px 70px",
                  gap: 10, alignItems: "center",
                  background: i % 2 === 0 ? "#F4F0E866" : "transparent",
                  borderRadius: 3, padding: "8px 10px" }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#2E2010" }}>
                    {(a.agent || "").replace(/_/g, " ")}
                  </span>
                  <Bar value={w} max={1.5} color={wColor} width={220} height={10} />
                  <span style={{ fontFamily: "monospace", fontSize: 11, color: wColor, textAlign: "right" }}>
                    {w.toFixed(3)}
                  </span>
                  <span style={{ fontFamily: "monospace", fontSize: 11, color: C.muted, textAlign: "right" }}>
                    c={conf.toFixed(2)}
                  </span>
                  <span style={{ fontFamily: "monospace", fontSize: 11,
                    color: regret > 0.1 ? C.error : C.muted, textAlign: "right" }}>
                    r={regret.toFixed(3)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Recent decisions table ── */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010", marginBottom: 14 }}>
          Recent Decisions
          <span style={{ fontSize: 11, color: C.muted, fontWeight: 400, marginLeft: 8 }}>
            ✓ = no conflict · ✕ = brain overrode router
          </span>
        </div>
        <DecisionsTable decisions={decisions} />
      </div>

      {/* ── Memory coherence ── */}
      {memCoh.length > 0 && (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010", marginBottom: 14 }}>
            Memory Coherence — Quality by Type
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {memCoh.map((m, i) => {
              const q      = parseFloat(m.avg_quality || 0);
              const qColor = q >= 0.80 ? C.success : q >= 0.65 ? C.warn : C.error;
              return (
                <div key={m.type} style={{ display: "grid",
                  gridTemplateColumns: "120px 1fr 60px 70px 70px",
                  gap: 10, alignItems: "center",
                  background: i % 2 === 0 ? "#F4F0E866" : "transparent",
                  borderRadius: 3, padding: "6px 10px" }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#2E2010" }}>{m.type}</span>
                  <Bar value={q} max={1} color={qColor} width={220} height={10} />
                  <span style={{ fontFamily: "monospace", fontSize: 11, color: qColor, textAlign: "right" }}>
                    {q.toFixed(3)}
                  </span>
                  <span style={{ fontSize: 10, color: C.muted, textAlign: "right" }}>n={m.count}</span>
                  <span style={{ fontSize: 10, textAlign: "right",
                    color: m.low_quality > 0 ? C.error : C.muted }}>
                    {m.low_quality > 0 ? `${m.low_quality} low` : "✓ clean"}
                  </span>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 10 }}>
            Prune gate: q &lt; 0.55 and use_count = 0. Outcome-weighted 👍/👎 adjusts in real time.
          </div>
        </div>
      )}

      {/* ── Contradictions feed ── */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010" }}>Self-Correction Events</div>
          {contras.length > 0 && <Badge label={`${contras.length} events`} color={C.warn} />}
        </div>
        <ContradictionsFeed items={contras} />
      </div>

      {/* ── Reflection gain ── */}
      {cohState?.G_r_n > 0 && (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010", marginBottom: 12 }}>
            Reflection Gain — G_r = s_final − s_initial
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px,1fr))", gap: 14 }}>
            {[
              { label: "Mean G_r",    value: `${cohState.G_r_mean >= 0 ? "+" : ""}${cohState.G_r_mean?.toFixed(4)}`, color: (cohState.G_r_mean ?? 0) >= 0 ? C.success : C.error },
              { label: "Std G_r",     value: (cohState.G_r_std ?? 0).toFixed(4),   color: C.muted },
              { label: "n reflected", value: cohState.G_r_n,                        color: C.accent },
              { label: "G_r > 0",     value: `${Math.round((cohState.G_r_positive ?? 0) * 100)}%`, color: C.warn },
            ].map(m => (
              <div key={m.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>{m.label}</div>
                <div style={{ fontFamily: "monospace", fontSize: 18, fontWeight: 700, color: m.color }}>{m.value}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 12 }}>
            Mean G_r ≥ 0 confirms reflection is non-destructive. Low positive fraction reflects near-ceiling pre-reflection quality.
          </div>
        </div>
      )}

      {/* ── Failure miner ── */}
      {failures && failures.total_decisions > 0 && (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, padding: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#2E2010" }}>Conflict Resolution Mining</div>
            <Badge label={`${failures.total_decisions} decisions analysed`} color={C.muted} />
          </div>

          {failures.conflict_by_agent && Object.keys(failures.conflict_by_agent).length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 8, fontWeight: 600 }}>
                Brain-Router Conflict Rate by Agent
                <span style={{ fontWeight: 400, marginLeft: 6 }}>— high rate = signal primitive gap</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {Object.entries(failures.conflict_by_agent)
                  .sort((a, b) => b[1].conflict_rate - a[1].conflict_rate)
                  .map(([agent, v], i) => {
                    const rate = v.conflict_rate || 0;
                    const col  = rate > 0.60 ? C.error : rate > 0.30 ? C.warn : C.success;
                    return (
                      <div key={agent} style={{ display: "grid",
                        gridTemplateColumns: "160px 1fr 60px 80px",
                        gap: 8, alignItems: "center",
                        background: i % 2 === 0 ? "#F4F0E866" : "transparent",
                        borderRadius: 3, padding: "5px 8px" }}>
                        <span style={{ fontSize: 11, color: "#2E2010" }}>{agent.replace(/_/g, " ")}</span>
                        <div style={{ width: "100%", height: 8, background: "#E0D6C4", borderRadius: 3, overflow: "hidden" }}>
                          <div style={{ width: `${rate * 100}%`, height: "100%", background: col, borderRadius: 3 }} />
                        </div>
                        <span style={{ fontFamily: "monospace", fontSize: 11, color: col, textAlign: "right" }}>
                          {Math.round(rate * 100)}%
                        </span>
                        <span style={{ fontSize: 10, color: C.muted, textAlign: "right" }}>
                          {v.conflicts}/{v.total}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {failures.regret_by_action && Object.keys(failures.regret_by_action).length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 8, fontWeight: 600 }}>High-Regret Actions</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {Object.entries(failures.regret_by_action).map(([action, v]) => (
                  <div key={action} style={{ background: "#F4F0E8", border: `1px solid ${C.border}`,
                    borderRadius: 3, padding: "5px 10px" }}>
                    <div style={{ fontSize: 10, color: C.muted }}>{action}</div>
                    <div style={{ fontFamily: "monospace", fontSize: 13, color: C.warn }}>
                      {v.count} × r={v.avg_regret.toFixed(3)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {failures.top_failures && failures.top_failures.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 8, fontWeight: 600 }}>Worst Decisions by Regret</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {failures.top_failures.slice(0, 5).map(f => (
                  <div key={f.id} style={{ background: "#F4F0E8", border: `1px solid ${C.border}`,
                    borderRadius: 3, padding: "5px 10px", fontSize: 11 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 2 }}>
                      <span style={{ fontFamily: "monospace", color: C.muted, fontSize: 10 }}>#{f.id}</span>
                      <Badge label={f.agent?.replace(/_/g, " ") || "?"} color={C.accent} />
                      <Badge label={f.action || "?"} color="#7E3F8F" />
                      <span style={{ marginLeft: "auto", fontFamily: "monospace",
                        color: parseFloat(f.regret) > 0.2 ? C.error : C.warn, fontWeight: 700 }}>
                        regret {parseFloat(f.regret || 0).toFixed(3)}
                      </span>
                    </div>
                    <div style={{ color: "#9A7A60", fontSize: 10 }}>{(f.task || "").slice(0, 90)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
