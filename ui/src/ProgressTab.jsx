import { useState, useEffect, useCallback } from "react";
import { BUILD_PHASES, ROADMAP, LAUNCH_CHECKLIST } from "./constants";
import { T } from "./theme";
import { PageHeader } from "./ObsShared";

// ── Open issues only — resolved items live in Version History ─────────────────
const ISSUES = [
  { id: 1,  sev: "info",    title: "Feedback coverage near zero",                              detail: "No real user ratings collected yet. The critic gate now provides grounded quality scores (F5 fixed), but 👍/👎 ratings from the Chat tab are a stronger signal — even 20 real ratings begins validating the critic's calibration.", status: "known" },
  { id: 4,  sev: "info",    title: "Contradiction false-positive rate unknown",                detail: "contradictions.db entries are mostly false positives (F8). Real precision is unknown — needs a hold-out sample from sessions.db labeled manually.", status: "tracked" },
  { id: 19, sev: "info",    title: "Tool loop not auto-invoked in default chat",               detail: "The structured tool loop ships (tools/tool_loop.py, POST /tools/run) and the file/sandbox/web tools are wired into it. Remaining polish: auto-invoking the loop inside the default specialist-agent chat flow — gated on phi4-mini reliably emitting tool-call JSON, so it's a dedicated endpoint for now.", status: "tracked" },
];

const SEV_META = {
  info:    { color: "#0F766E", label: "Info",    bg: "#0F766E11" },
  warning: { color: "#9A6C00", label: "Warning", bg: "#9A6C0011" },
  ok:      { color: "#15803D", label: "OK",      bg: "#15803D11" },
  error:   { color: "#B42318", label: "Error",   bg: "#B4231811" },
};
const STATUS_META = {
  open:     { color: "#B42318", label: "Open" },
  known:    { color: "#9A6C00", label: "Known" },
  tracked:  { color: "#0F766E", label: "Tracked" },
  partial:  { color: "#C2410C", label: "Partial" },
};
const PRIO_COLOR = { high: "#B42318", medium: "#9A6C00", low: "#9A7A60" };

const CHECKLIST_KEY = "amagra_launch_checklist_v1";

// ── Current Phase block ───────────────────────────────────────────────────────
function CurrentPhase({ phase }) {
  const doneItems  = phase.items.filter(i => i.includes("✅"));
  const pendItems  = phase.items.filter(i => !i.includes("✅"));
  const pct        = Math.round((doneItems.length / phase.items.length) * 100);

  return (
    <div style={{
      background: T.surface,
      border: `2px solid ${phase.color}55`,
      borderRadius: 14, padding: "18px 22px", marginBottom: 20,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <span style={{
          fontSize: 9, fontWeight: 800, letterSpacing: "0.1em", textTransform: "uppercase",
          padding: "2px 8px", borderRadius: 3,
          background: `${phase.color}22`, color: phase.color,
          border: `1px solid ${phase.color}44`,
        }}>NOW</span>
        <span style={{
          fontSize: 9, fontWeight: 700, fontFamily: "monospace",
          color: phase.color, background: `${phase.color}18`,
          border: `1px solid ${phase.color}40`, padding: "1px 6px", borderRadius: 3,
        }}>{phase.version}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.text, flex: 1 }}>
          {phase.title}
        </span>
        <span style={{
          fontSize: 22, fontWeight: 800, fontFamily: "monospace",
          color: pct === 100 ? T.success : phase.color, lineHeight: 1,
        }}>{pct}%</span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: T.border, borderRadius: 2, marginBottom: 12 }}>
        <div style={{
          height: 4, borderRadius: 2, width: `${pct}%`,
          background: pct === 100 ? T.success : phase.color,
          transition: "width .4s ease",
        }} />
      </div>

      <div style={{ fontSize: 11, color: T.muted, lineHeight: 1.55, marginBottom: 14 }}>
        {phase.summary}
      </div>

      {/* Items */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px 24px" }}>
        {phase.items.map((item, i) => {
          const done = item.includes("✅");
          const text = item.replace(" ✅", "");
          return (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <span style={{
                fontSize: 11, color: done ? T.success : phase.color,
                flexShrink: 0, marginTop: 1, fontFamily: "monospace",
              }}>{done ? "✓" : "□"}</span>
              <span style={{
                fontSize: 11, lineHeight: 1.5,
                color: done ? T.text : T.muted,
              }}>{text}</span>
            </div>
          );
        })}
      </div>

      {/* Next phase preview */}
      {(() => {
        const next = ROADMAP.find(p => p.status === "planned" && !p.type);
        if (!next) return null;
        return (
          <div style={{
            marginTop: 14, paddingTop: 12,
            borderTop: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <span style={{ fontSize: 10, color: T.muted }}>Up next →</span>
            <span style={{
              fontSize: 9, fontFamily: "monospace",
              color: next.color, background: `${next.color}18`,
              border: `1px solid ${next.color}40`, padding: "1px 6px", borderRadius: 3,
            }}>{next.version}</span>
            <span style={{ fontSize: 11, color: T.muted }}>{next.title}</span>
          </div>
        );
      })()}
    </div>
  );
}

// ── Launch Checklist ──────────────────────────────────────────────────────────
function LaunchChecklist() {
  const [checked, setChecked] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(CHECKLIST_KEY) || "[]")); }
    catch { return new Set(); }
  });
  // Auto-detected status from the backend, keyed by checklist item id.
  const [auto, setAuto] = useState({});
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/launch/readiness")
      .then(r => r.json())
      .then(d => setAuto(d.items || {}))
      .catch(() => {});
  }, []);

  // An item is done if the server verified it, otherwise fall back to the
  // manual checkbox. Auto-detected items can't be toggled by hand.
  const isDone = (item) => (item.id in auto ? auto[item.id].done : checked.has(item.id));

  const toggle = (id) => {
    if (id in auto) return;  // server-verified — not manually editable
    setChecked(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      localStorage.setItem(CHECKLIST_KEY, JSON.stringify([...next]));
      return next;
    });
  };

  const allItems   = LAUNCH_CHECKLIST.flatMap(g => g.items);
  const totalDone  = allItems.filter(isDone).length;
  const totalCount = allItems.length;
  const overallPct = Math.round((totalDone / totalCount) * 100);
  const autoCount  = allItems.filter(i => i.id in auto).length;

  return (
    <div style={{ background: T.surface, border: `2px solid #C2410C33`, borderRadius: 14, padding: "18px 22px", marginBottom: 20 }}>
      <div
        onClick={() => setCollapsed(c => !c)}
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}
      >
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 2 }}>
            Launch Readiness
          </div>
          <div style={{ fontSize: 11, color: T.muted }}>
            {totalDone} of {totalCount} items complete
            {autoCount > 0 && <span> · {autoCount} auto-detected</span>}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 26, fontWeight: 800, fontFamily: "monospace", color: overallPct === 100 ? T.success : "#C2410C", lineHeight: 1 }}>
              {overallPct}%
            </div>
          </div>
          <span style={{ fontSize: 11, color: T.muted }}>{collapsed ? "▼" : "▲"}</span>
        </div>
      </div>

      {/* Overall bar */}
      <div style={{ height: 3, background: T.border, borderRadius: 2, marginTop: 10, marginBottom: collapsed ? 0 : 18 }}>
        <div style={{
          height: 3, borderRadius: 2, width: `${overallPct}%`,
          background: overallPct === 100 ? T.success : "linear-gradient(90deg, #C2410C, #9A6C00)",
          transition: "width .4s ease",
        }} />
      </div>

      {!collapsed && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {LAUNCH_CHECKLIST.map(gate => {
            const gateDone  = gate.items.filter(isDone).length;
            const gateTotal = gate.items.length;
            const gatePct   = Math.round((gateDone / gateTotal) * 100);
            const allDone   = gateDone === gateTotal;
            return (
              <div key={gate.id} style={{
                background: T.bg, borderRadius: 8,
                border: `1px solid ${allDone ? gate.color + "55" : gate.color + "22"}`,
                padding: "12px 14px", opacity: allDone ? 0.85 : 1,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 10, fontWeight: 800, color: gate.color, background: `${gate.color}18`, border: `1px solid ${gate.color}40`, padding: "2px 8px", borderRadius: 3, letterSpacing: "0.06em", textTransform: "uppercase", flexShrink: 0 }}>
                    {allDone ? "✓ " : ""}{gate.label}
                  </span>
                  <span style={{ fontSize: 11, color: T.muted, flex: 1 }}>{gate.description}</span>
                  <span style={{ fontSize: 11, fontFamily: "monospace", color: allDone ? T.success : gate.color, fontWeight: 700, flexShrink: 0 }}>
                    {gateDone}/{gateTotal}
                  </span>
                </div>
                <div style={{ height: 2, background: T.border, borderRadius: 1, marginBottom: 10 }}>
                  <div style={{ height: 2, borderRadius: 1, width: `${gatePct}%`, background: allDone ? T.success : gate.color, transition: "width .3s ease" }} />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  {gate.items.map(item => {
                    const done   = isDone(item);
                    const isAuto = item.id in auto;
                    return (
                      <div key={item.id} onClick={() => toggle(item.id)} title={isAuto ? auto[item.id].detail : ""} style={{ display: "flex", alignItems: "flex-start", gap: 9, cursor: isAuto ? "default" : "pointer", padding: "5px 8px", borderRadius: 5, background: done ? `${gate.color}0D` : "transparent" }}>
                        <div style={{ width: 14, height: 14, borderRadius: 3, flexShrink: 0, marginTop: 1, border: `1.5px solid ${done ? gate.color : T.border}`, background: done ? gate.color : "transparent", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          {done && <span style={{ fontSize: 9, color: "#111", fontWeight: 800, lineHeight: 1 }}>✓</span>}
                        </div>
                        <span style={{ fontSize: 12, lineHeight: 1.55, color: done ? T.muted : T.text, textDecoration: done ? "line-through" : "none", textDecorationColor: T.muted, flex: 1 }}>
                          {item.text}
                        </span>
                        {isAuto && (
                          <span style={{ fontSize: 8, fontWeight: 800, letterSpacing: "0.06em", flexShrink: 0, marginTop: 2, padding: "1px 5px", borderRadius: 3, textTransform: "uppercase", color: done ? T.success : "#9A6C00", background: done ? `${T.success}14` : "#9A6C0014", border: `1px solid ${done ? T.success + "44" : "#9A6C0040"}` }}>
                            {done ? "✓ Live" : "Auto"}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color, sub }) {
  return (
    <div style={{ background: T.bg, borderRadius: 4, padding: "12px 16px", border: `1px solid ${color}22` }}>
      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "monospace" }}>{value}</div>
      <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function SectionHead({ title }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>
      {title}
    </div>
  );
}

function Card({ children, mb = 20, accent }) {
  return (
    <div style={{ background: T.surface, border: `2px solid ${accent || T.border}`, borderRadius: 14, padding: "18px 22px", marginBottom: mb }}>
      {children}
    </div>
  );
}

function buildFeedbackStats(entries) {
  const byAgent = {};
  for (const e of entries) {
    if (!byAgent[e.agent]) byAgent[e.agent] = { up: 0, down: 0 };
    if (e.rating === 1)  byAgent[e.agent].up++;
    if (e.rating === -1) byAgent[e.agent].down++;
  }
  return byAgent;
}

export default function ProgressTab() {
  const [metrics,          setMetrics]          = useState(null);
  const [memStats,         setMemStats]         = useState(null);
  const [atRisk,           setAtRisk]           = useState([]);
  const [atRiskOpen,       setAtRiskOpen]       = useState(false);
  const [pruning,          setPruning]          = useState(false);
  const [pruneResult,      setPruneResult]      = useState(null);
  const [consolidating,    setConsolidating]    = useState(false);
  const [consolidateResult,setConsolidateResult]= useState(null);
  const [feedback,         setFeedback]         = useState([]);

  const refresh = useCallback(() => {
    fetch("http://localhost:8000/metrics").then(r => r.json()).then(setMetrics).catch(() => {});
    fetch("http://localhost:8000/memory/stats").then(r => r.json()).then(setMemStats).catch(() => {});
    fetch("http://localhost:8000/memory/at-risk?n=20").then(r => r.json()).then(d => setAtRisk(d.at_risk || [])).catch(() => {});
    fetch("http://localhost:8000/feedback?limit=500").then(r => r.json()).then(d => setFeedback(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const runPrune = async () => {
    setPruning(true); setPruneResult(null);
    try {
      const d = await fetch("http://localhost:8000/memory/prune", { method: "POST" }).then(r => r.json());
      setPruneResult(d); refresh();
    } catch { setPruneResult({ error: "Request failed" }); }
    setPruning(false);
  };

  const runConsolidate = async () => {
    setConsolidating(true); setConsolidateResult(null);
    try {
      const d = await fetch("http://localhost:8000/memory/consolidate", { method: "POST" }).then(r => r.json());
      setConsolidateResult(d); refresh();
    } catch { setConsolidateResult({ error: "Request failed" }); }
    setConsolidating(false);
  };

  const mem          = memStats || metrics?.memory;
  const backend      = memStats?.backend;
  const currentPhase = ROADMAP.find(p => p.status === "next");

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      <PageHeader title="Progress" subtitle="Build phases, open issues, launch readiness, and memory health." />

      {/* ── Current phase ── */}
      {currentPhase && <CurrentPhase phase={currentPhase} />}

      {/* ── Open issues ── */}
      <Card mb={20}>
        <SectionHead title={`Open Issues — ${ISSUES.length} remaining`} />
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {ISSUES.map(issue => {
            const sm  = SEV_META[issue.sev]       || SEV_META.info;
            const stm = STATUS_META[issue.status] || STATUS_META.known;
            return (
              <div key={issue.id + issue.title} style={{ background: sm.bg, border: `1px solid ${sm.color}33`, borderRadius: 3, padding: "10px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: `${sm.color}22`, color: sm.color, border: `1px solid ${sm.color}44` }}>{sm.label}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: T.text, flex: 1 }}>{issue.title}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: `${stm.color}18`, color: stm.color, border: `1px solid ${stm.color}40` }}>{stm.label}</span>
                </div>
                <div style={{ fontSize: 12, color: T.muted, lineHeight: 1.5 }}>{issue.detail}</div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── System metrics ── */}
      {metrics && (
        <Card mb={20}>
          <SectionHead title="System Metrics" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 10 }}>
            <StatCard label="Memories"    value={mem?.total ?? "—"}                                                                    color="#1E5A8A" sub={backend ? backend.engine?.split(" ")[0] : "SQLite"} />
            <StatCard label="Tasks Done"  value={metrics.tasks?.done ?? 0}                                                             color="#15803D" />
            <StatCard label="Traces"      value={metrics.traces?.total ?? 0}                                                           color="#0F766E" />
            <StatCard label="Avg Latency" value={metrics.traces?.avg_latency_ms ? Math.round(metrics.traces.avg_latency_ms / 1000) + "s" : "—"} color="#9A6C00" />
            <StatCard label="Prunable"    value={mem?.prune_candidates ?? 0}                                                           color={(mem?.prune_candidates ?? 0) > 0 ? "#B42318" : "#15803D"} sub="low quality + never used" />
          </div>
          {backend && (
            <div style={{ marginTop: 10, fontSize: 11, color: T.muted, display: "flex", gap: 16 }}>
              <span>Backend: <span style={{ color: "#1E5A8A" }}>{backend.type}</span></span>
              <span>Engine: <span style={{ color: T.muted }}>{backend.engine}</span></span>
              <span>Vectors: <span style={{ color: T.muted }}>{backend.total}</span></span>
            </div>
          )}
        </Card>
      )}

      {/* ── Memory health ── */}
      {mem && (
        <Card mb={20}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <SectionHead title="Memory Health" />
            <div style={{ display: "flex", gap: 8 }}>
              <a href="http://localhost:8000/memory/export.csv" download="memories.csv"
                style={{ padding: "4px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700, fontFamily: "inherit", cursor: "pointer", background: "#0F766E18", color: "#0F766E", border: "1px solid #0F766E40", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}>
                ⬇ CSV
              </a>
              <button onClick={runConsolidate} disabled={consolidating}
                style={{ padding: "4px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700, fontFamily: "inherit", cursor: consolidating ? "not-allowed" : "pointer", background: "#1E5A8A18", color: "#1E5A8A", border: "1px solid #1E5A8A40" }}>
                {consolidating ? "Running…" : "⊕ Consolidate"}
              </button>
              <button onClick={runPrune} disabled={pruning || (mem.prune_candidates ?? 0) === 0}
                style={{ padding: "4px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700, fontFamily: "inherit", cursor: pruning || (mem.prune_candidates ?? 0) === 0 ? "not-allowed" : "pointer", background: (mem.prune_candidates ?? 0) > 0 ? "#B4231818" : "#E0D6C4", color: (mem.prune_candidates ?? 0) > 0 ? "#B42318" : "#9A7A60", border: `1px solid ${(mem.prune_candidates ?? 0) > 0 ? "#B4231840" : "#E0D6C4"}` }}>
                {pruning ? "Pruning…" : "✂ Prune"}
              </button>
            </div>
          </div>

          {consolidateResult && (
            <div style={{ marginBottom: 10, padding: "7px 12px", borderRadius: 4, background: consolidateResult.error ? "#F9E7E1" : "#F0EDF6", border: `1px solid ${consolidateResult.error ? "#B4231855" : "#1E5A8A44"}`, fontSize: 12, color: consolidateResult.error ? "#B42318" : "#1E5A8A" }}>
              {consolidateResult.error ? `Error: ${consolidateResult.error}` : `Removed ${consolidateResult.removed} near-duplicates · ${consolidateResult.remaining} memories remaining`}
            </div>
          )}
          {pruneResult && (
            <div style={{ marginBottom: 10, padding: "7px 12px", borderRadius: 4, background: pruneResult.error ? "#F9E7E1" : "#E7F2E6", border: `1px solid ${pruneResult.error ? "#B4231855" : "#15803D33"}`, fontSize: 12, color: pruneResult.error ? "#B42318" : "#15803D" }}>
              {pruneResult.error ? `Error: ${pruneResult.error}` : `Deleted ${pruneResult.deleted} entries · ${pruneResult.remaining} remaining`}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(140px,1fr))", gap: 8, marginBottom: 12 }}>
            {Object.entries(mem.by_type || {}).sort((a, b) => b[1].count - a[1].count).map(([type, d]) => {
              const tc = { reflection: "#7E3F8F", failure: "#B42318", code: "#0F766E", lesson: "#15803D", procedural: "#9A6C00", episodic: "#1E5A8A", chat: "#9A7A60", seed: "#9A7A60", project: "#C2410C" };
              const c = tc[type] || "#9A7A60";
              return (
                <div key={type} style={{ background: T.bg, borderRadius: 4, padding: "10px 12px", border: `1px solid ${c}33` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: c }}>{type}</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>{d.count}</span>
                  </div>
                  <div style={{ height: 3, background: T.border, borderRadius: 2, marginBottom: 4 }}>
                    <div style={{ height: 3, width: `${Math.round((d.avg_quality || 0) * 100)}%`, background: c, borderRadius: 2 }} />
                  </div>
                  <div style={{ fontSize: 10, color: T.muted }}>q̄ {d.avg_quality?.toFixed(2)} · ×{d.avg_used?.toFixed(1)}</div>
                </div>
              );
            })}
          </div>

          <div style={{ display: "flex", gap: 16, fontSize: 11, color: T.muted, marginBottom: 10 }}>
            <span>Total: <span style={{ color: T.text }}>{mem.total}</span></span>
            <span>Never recalled: <span style={{ color: (mem.never_used ?? 0) > 100 ? T.warn : T.text }}>{mem.never_used}</span></span>
            <span>Prunable: <span style={{ color: (mem.prune_candidates ?? 0) > 0 ? T.error : T.success }}>{mem.prune_candidates}</span></span>
          </div>

          {atRisk !== null && (
            <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }} onClick={() => setAtRiskOpen(o => !o)}>
                <span style={{ fontSize: 11, fontWeight: 700, color: T.warn }}>⚠ At Risk</span>
                <span style={{ fontSize: 11, color: T.muted }}>{atRisk.length} memories (q 0.55–0.70, used ≤ 1×)</span>
                <span style={{ marginLeft: "auto", fontSize: 11, color: T.muted }}>{atRiskOpen ? "▲" : "▼"}</span>
              </div>
              {atRiskOpen && (
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                  {atRisk.length === 0 ? (
                    <div style={{ fontSize: 12, color: T.muted, padding: "6px 0" }}>No at-risk memories right now.</div>
                  ) : atRisk.map(m => {
                    const q = m.quality || 0;
                    const dc = q < 0.60 ? T.error : T.warn;
                    return (
                      <div key={m.id} style={{ background: T.bg, border: `1px solid ${dc}33`, borderRadius: 7, padding: "7px 11px", display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 36, height: 4, background: T.border, borderRadius: 2, overflow: "hidden", flexShrink: 0 }}>
                          <div style={{ width: `${Math.round(((q - 0.55) / 0.15) * 100)}%`, height: "100%", background: dc, borderRadius: 2 }} />
                        </div>
                        <span style={{ fontSize: 10, color: dc, fontFamily: "monospace", fontWeight: 700, minWidth: 38 }}>{q.toFixed(3)}</span>
                        <span style={{ fontSize: 10, color: T.muted, minWidth: 30 }}>{m.agent?.replace(/_/g, " ")}</span>
                        <span style={{ fontSize: 10, color: T.muted, minWidth: 24 }}>{m.type}</span>
                        <span style={{ fontSize: 11, color: T.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.preview}</span>
                        <span style={{ fontSize: 10, color: T.muted, flexShrink: 0 }}>×{m.use_count}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* ── Launch readiness (collapsible) ── */}
      <LaunchChecklist />

      {/* ── Feedback loop ── */}
      {(() => {
        const total     = feedback.length;
        const totalUp   = feedback.filter(f => f.rating === 1).length;
        const totalDown = feedback.filter(f => f.rating === -1).length;
        const byAgent   = buildFeedbackStats(feedback);
        const agentRows = Object.entries(byAgent).sort((a, b) => (b[1].up + b[1].down) - (a[1].up + a[1].down));
        return (
          <Card mb={0}>
            <SectionHead title="Feedback Loop" />
            {total === 0 ? (
              <div style={{ padding: "20px 0", textAlign: "center" }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>👍 👎</div>
                <div style={{ fontSize: 13, color: T.muted }}>No ratings yet.</div>
                <div style={{ fontSize: 11, color: T.muted, marginTop: 4 }}>
                  Use the thumbs buttons under any response in the Chat tab to start collecting feedback.
                </div>
              </div>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 14 }}>
                  <StatCard label="Total Ratings" value={total}     color="#1E5A8A" />
                  <StatCard label="Positive 👍"   value={totalUp}   color="#15803D" sub={total > 0 ? `${Math.round((totalUp/total)*100)}%` : ""} />
                  <StatCard label="Negative 👎"   value={totalDown} color="#B42318" sub={total > 0 ? `${Math.round((totalDown/total)*100)}%` : ""} />
                </div>
                {agentRows.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                    {agentRows.map(([agent, d]) => {
                      const tot = d.up + d.down;
                      const pct = tot > 0 ? Math.round((d.up / tot) * 100) : 0;
                      const barColor = pct >= 70 ? "#15803D" : pct >= 40 ? "#9A6C00" : "#B42318";
                      return (
                        <div key={agent} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 10px", background: T.bg, borderRadius: 4, border: `1px solid ${T.border}` }}>
                          <span style={{ fontSize: 11, color: T.mutedLt, minWidth: 140, fontFamily: "monospace" }}>{agent.replace(/_/g," ")}</span>
                          <div style={{ flex: 1, height: 4, background: T.border, borderRadius: 2 }}>
                            <div style={{ width: `${pct}%`, height: 4, background: barColor, borderRadius: 2, transition: "width .3s" }} />
                          </div>
                          <span style={{ fontSize: 10, color: T.success, minWidth: 28, textAlign: "right" }}>👍{d.up}</span>
                          <span style={{ fontSize: 10, color: T.error,   minWidth: 28, textAlign: "right" }}>👎{d.down}</span>
                          <span style={{ fontSize: 10, color: barColor,  minWidth: 32, textAlign: "right", fontFamily: "monospace" }}>{pct}%</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </Card>
        );
      })()}
    </div>
  );
}
