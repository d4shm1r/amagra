import { useState, useEffect, useCallback, useMemo } from "react";
import { T } from "./theme";
import { AGENTS } from "./constants";
import { PageHeader } from "./ObsShared";

const STATUS_META = {
  pass:    { color: T.success, bg: "#15803D14", label: "Pass",    sym: "✓" },
  partial: { color: T.warn,   bg: "#9A6C0014", label: "Partial", sym: "△" },
  fail:    { color: T.error,  bg: "#B4231814", label: "Fail",    sym: "✗" },
  running: { color: T.accent, bg: "#C4880814", label: "Running", sym: "◌" },
};

const STEP_META = {
  prompt:               { color: T.muted,   label: "Prompt"   },
  routing:              { color: T.accent,  label: "Route"    },
  generate:             { color: "#1E5A8A", label: "Generate" },
  critic_accept:        { color: T.success, label: "Critic ✓" },
  critic_reject:        { color: T.error,   label: "Critic ✗" },
  retry_accept:         { color: T.success, label: "Retry ✓"  },
  retry_no_improvement: { color: T.warn,    label: "Retry ✗"  },
  finish:               { color: T.muted,   label: "Done"     },
  error:                { color: T.error,   label: "Error"    },
};

const ROOT_CAUSE_META = {
  critic_misclassification: { color: T.error, label: "Critic miscalibration" },
  critic_threshold:         { color: T.warn,  label: "Threshold rejection"   },
  low_confidence:           { color: T.warn,  label: "Low confidence"        },
  routing_regret:           { color: T.warn,  label: "Routing regret"        },
  routing_conflict:         { color: T.warn,  label: "Routing conflict"      },
  exception:                { color: T.error, label: "Exception"             },
  none:                     { color: T.muted, label: ""                      },
};

function agentColor(id) {
  return AGENTS.find(a => a.id === id)?.color || T.muted;
}

// ── Relative time ──────────────────────────────────────────────
function relativeTime(ts) {
  if (!ts) return "—";
  const diff = Date.now() - new Date(ts).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60)  return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── Step timeline ──────────────────────────────────────────────
function StepTimeline({ steps }) {
  if (!steps?.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, paddingLeft: 4 }}>
      {steps.map((s, i) => {
        const meta   = STEP_META[s.name] || { color: T.muted, label: s.name };
        const isLast = i === steps.length - 1;
        return (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 12, position: "relative" }}>
            {!isLast && (
              <div style={{ position: "absolute", left: 7, top: 18, bottom: -4, width: 1, background: T.border }} />
            )}
            <div style={{
              width: 15, height: 15, borderRadius: "50%", flexShrink: 0, marginTop: 2,
              background: `${meta.color}1A`, border: `1.5px solid ${meta.color}88`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: meta.color }} />
            </div>
            <div style={{ paddingBottom: 14, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: meta.color }}>{meta.label}</span>
                <span style={{ fontSize: 10, color: T.muted, fontFamily: "monospace" }}>+{s.t}ms</span>
              </div>
              {s.data && Object.keys(s.data).length > 0 && (
                <div style={{
                  fontSize: 11, color: T.muted,
                  fontFamily: "'Consolas','Cascadia Code',monospace",
                  background: T.surface2, border: `1px solid ${T.border}`,
                  borderRadius: 4, padding: "4px 8px",
                  display: "inline-block", maxWidth: "100%",
                }}>
                  {Object.entries(s.data).map(([k, v]) => (
                    <span key={k} style={{ marginRight: 10 }}>
                      <span style={{ color: T.muted }}>{k}=</span>
                      <span style={{ color: T.mutedLt }}>{String(v)}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Threshold slider ───────────────────────────────────────────
function ThresholdSlider({ criticScore }) {
  const [threshold, setThreshold] = useState(70);
  if (criticScore == null) return null;
  const wouldPass = criticScore >= threshold / 100;
  const breakEven = Math.floor(criticScore * 100);
  return (
    <div style={{ marginTop: 14, padding: "12px 14px", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>
        Threshold Sensitivity
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <input
          type="range" min={40} max={95} step={1} value={threshold}
          onChange={e => setThreshold(Number(e.target.value))}
          style={{ flex: 1, accentColor: T.accent, cursor: "pointer" }}
        />
        <span style={{ fontSize: 12, fontFamily: "monospace", color: T.mutedLt, width: 34, textAlign: "right" }}>
          {(threshold / 100).toFixed(2)}
        </span>
      </div>
      <div style={{
        display: "flex", alignItems: "center", gap: 8, padding: "7px 10px",
        borderRadius: 4,
        background: wouldPass ? `${T.success}12` : `${T.error}12`,
        border: `1px solid ${wouldPass ? T.success : T.error}33`,
      }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: wouldPass ? T.success : T.error }}>
          {wouldPass ? "✓" : "✗"}
        </span>
        <span style={{ fontSize: 11, color: wouldPass ? T.success : T.error }}>
          At {(threshold / 100).toFixed(2)}, score {criticScore.toFixed(2)} would{" "}
          <b>{wouldPass ? "PASS" : "FAIL"}</b>
        </span>
      </div>
      {!wouldPass && (
        <div style={{ fontSize: 10, color: T.muted, marginTop: 6 }}>
          Break-even: <span style={{ color: T.warn, fontFamily: "monospace" }}>≤ {(breakEven / 100).toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}

// ── Replay result ──────────────────────────────────────────────
function ReplayResult({ trace }) {
  if (!trace) return null;
  const sm     = STATUS_META[trace.status] || STATUS_META.pass;
  const rcMeta = ROOT_CAUSE_META[trace.root_cause] || ROOT_CAUSE_META.none;
  const ac     = agentColor(trace.agent);
  return (
    <div style={{ marginTop: 10, padding: "10px 12px", background: `${sm.color}0A`, border: `1px solid ${sm.color}33`, borderRadius: 6 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
        Replay Result
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: sm.color, fontFamily: "monospace", background: sm.bg, border: `1px solid ${sm.color}44`, borderRadius: 4, padding: "2px 7px" }}>
          {sm.sym} {sm.label}
        </span>
        <span style={{ fontSize: 11, color: ac, fontFamily: "monospace" }}>
          {(trace.agent || "—").replace(/_/g, " ")}
        </span>
        {trace.critic_initial != null && (
          <span style={{ fontSize: 11, fontFamily: "monospace", color: trace.accepted_first ? T.success : T.error }}>
            score {trace.critic_initial?.toFixed(2)}
          </span>
        )}
        <span style={{ fontSize: 11, color: T.muted, fontFamily: "monospace" }}>{trace.duration_ms}ms</span>
      </div>
      {trace.root_cause && trace.root_cause !== "none" && (
        <div style={{ fontSize: 10, color: rcMeta.color, marginTop: 6 }}>{trace.root_cause_label || rcMeta.label}</div>
      )}
    </div>
  );
}

// ── Similar failures ───────────────────────────────────────────
function SimilarFailures({ rootCause, excludeRunId }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(`http://localhost:8000/runs/similar/${encodeURIComponent(rootCause)}?exclude=${encodeURIComponent(excludeRunId)}&limit=8`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [rootCause, excludeRunId]);

  const rcMeta = ROOT_CAUSE_META[rootCause] || ROOT_CAUSE_META.none;
  return (
    <div style={{ marginTop: 14, padding: "12px 14px", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10, display: "flex", justifyContent: "space-between" }}>
        <span>Similar Failures</span>
        {data?.total > 0 && <span style={{ color: rcMeta.color }}>{data.total} total</span>}
      </div>
      {loading ? (
        <div style={{ fontSize: 11, color: T.muted }}>Loading…</div>
      ) : !data?.runs?.length ? (
        <div style={{ fontSize: 11, color: T.muted }}>No other runs with this root cause.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {data.runs.map(r => {
            const sc = r.status === "pass" ? T.success : r.status === "fail" ? T.error : T.warn;
            const ss = r.status === "pass" ? "✓" : r.status === "fail" ? "✗" : "△";
            return (
              <div key={r.run_id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: `1px solid ${T.border}` }}>
                <span style={{ fontSize: 10, color: sc, fontFamily: "monospace", fontWeight: 700, flexShrink: 0 }}>{ss}</span>
                <span style={{ flex: 1, fontSize: 11, color: T.mutedLt, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.query}</span>
                {r.critic_initial != null && (
                  <span style={{ fontSize: 10, color: T.muted, fontFamily: "monospace", flexShrink: 0 }}>{r.critic_initial.toFixed(2)}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Expanded run detail ────────────────────────────────────────
function ExpandedRun({ runId, summary }) {
  const [detail,      setDetail]      = useState(null);
  const [replaying,   setReplaying]   = useState(false);
  const [replayTrace, setReplayTrace] = useState(null);
  const [replayError, setReplayError] = useState(null);
  const [showSimilar, setShowSimilar] = useState(false);

  useEffect(() => {
    fetch(`http://localhost:8000/runs/${runId}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setDetail(d); })
      .catch(() => {});
  }, [runId]);

  const data   = detail || summary;
  const rcMeta = ROOT_CAUSE_META[data.root_cause] || ROOT_CAUSE_META.none;
  const hasCause = data.root_cause && data.root_cause !== "none";
  const ac     = agentColor(data.agent);

  const handleReplay = () => {
    setReplaying(true); setReplayTrace(null); setReplayError(null);
    fetch(`http://localhost:8000/runs/${runId}/replay`, { method: "POST" })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail)))
      .then(d => { setReplayTrace(d.trace); setReplaying(false); })
      .catch(e => { setReplayError(String(e)); setReplaying(false); });
  };

  return (
    <div style={{
      borderBottom: `1px solid ${T.border}`,
      background: "#F7F3EC",
      padding: "18px 24px 22px",
      display: "grid",
      gridTemplateColumns: "1fr 300px",
      gap: 24,
    }}>
      {/* Left: timeline + actions */}
      <div>
        <SectionHead title="Execution Timeline" />
        {detail?.steps ? (
          <StepTimeline steps={detail.steps} />
        ) : (
          <div style={{ fontSize: 11, color: T.muted, marginTop: 4 }}>Loading…</div>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
          <ActionBtn onClick={handleReplay} disabled={replaying} color={T.accent}>
            {replaying ? "Replaying…" : "↺ Replay"}
          </ActionBtn>
          {hasCause && (
            <ActionBtn onClick={() => setShowSimilar(s => !s)} color={rcMeta.color} active={showSimilar}>
              {showSimilar ? "Hide similar" : "≋ Similar failures"}
            </ActionBtn>
          )}
        </div>

        {replayError && (
          <div style={{ marginTop: 8, fontSize: 11, color: T.error }}>Replay failed: {replayError}</div>
        )}
        {replayTrace && <ReplayResult trace={replayTrace} />}
        {showSimilar && hasCause && (
          <SimilarFailures rootCause={data.root_cause} excludeRunId={runId} />
        )}
      </div>

      {/* Right: metadata */}
      <div>
        <SectionHead title="Trace Details" />

        <MetaRow label="Agent"      value={(data.agent || "—").replace(/_/g, " ")} valueColor={ac} />
        <MetaRow label="Confidence" value={data.confidence?.toFixed(3)} />
        <MetaRow label="Regret"     value={data.regret?.toFixed(4)} />
        <MetaRow label="Complexity" value={data.complexity} />
        <MetaRow label="Reflect"    value={data.reflect_level} />
        {data.conflict && <MetaRow label="Conflict" value="brain overrode router" valueColor={T.warn} />}
        {data.run_id && (
          <div style={{ marginTop: 8, fontSize: 10, color: T.muted, fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.run_id}
          </div>
        )}

        {data.critic_initial != null && (
          <div style={{ marginTop: 12, padding: "10px 12px", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6 }}>
            <SectionHead title="Critic Gate" />
            <MetaRow label="Initial score"  value={data.critic_initial?.toFixed(3)}  valueColor={data.accepted_first ? T.success : T.error} />
            <MetaRow label="Threshold"      value={data.critic_threshold?.toFixed(2)} />
            {data.critic_retry != null && (
              <MetaRow label="Retry score"  value={data.critic_retry?.toFixed(3)}     valueColor={data.retry_improved ? T.success : T.warn} />
            )}
            <MetaRow label="Accepted first" value={data.accepted_first ? "yes" : "no"} valueColor={data.accepted_first ? T.success : T.error} />
          </div>
        )}

        <ThresholdSlider criticScore={data.critic_initial} />

        {hasCause && (
          <div style={{ marginTop: 12, padding: "10px 12px", background: `${rcMeta.color}0C`, border: `1px solid ${rcMeta.color}33`, borderRadius: 6 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: rcMeta.color, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>
              Root Cause
            </div>
            <div style={{ fontSize: 11, color: T.text, lineHeight: 1.5 }}>
              {data.root_cause_label || rcMeta.label}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Run row ────────────────────────────────────────────────────
function RunRow({ run, expanded, onToggle }) {
  const sm     = STATUS_META[run.status] || STATUS_META.pass;
  const rcMeta = ROOT_CAUSE_META[run.root_cause] || ROOT_CAUSE_META.none;
  const ac     = agentColor(run.agent);

  return (
    <div>
      <div
        onClick={onToggle}
        style={{
          display: "grid",
          gridTemplateColumns: "52px 1fr 120px 70px 72px 60px 28px",
          alignItems: "center",
          padding: "9px 16px",
          cursor: "pointer",
          borderBottom: `1px solid ${T.border}`,
          background: expanded ? "#F7F3EC" : "transparent",
          transition: "background 0.1s",
          gap: 10,
        }}
      >
        {/* Status badge */}
        <div style={{
          display: "flex", alignItems: "center", gap: 4,
          background: sm.bg, border: `1px solid ${sm.color}44`,
          borderRadius: 4, padding: "2px 6px", justifyContent: "center",
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: sm.color, fontFamily: "monospace" }}>{sm.sym}</span>
          <span style={{ fontSize: 9,  fontWeight: 600, color: sm.color }}>{sm.label}</span>
        </div>

        {/* Query + root cause */}
        <div style={{ overflow: "hidden", minWidth: 0 }}>
          <div style={{
            fontSize: 12, color: T.text, fontWeight: 500,
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {run.query || "—"}
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 2, alignItems: "center" }}>
            {run.root_cause && run.root_cause !== "none" && (
              <span style={{ fontSize: 10, color: rcMeta.color }}>{rcMeta.label}</span>
            )}
            {run.reflect_level && run.reflect_level !== "none" && (
              <span style={{
                fontSize: 9, padding: "0 5px", borderRadius: 3,
                background: run.reflect_level === "full" ? "#C0604018" : `${T.warn}18`,
                color: run.reflect_level === "full" ? "#C06040" : T.warn,
                border: `1px solid ${run.reflect_level === "full" ? "#C0604044" : `${T.warn}44`}`,
                fontFamily: "monospace",
              }}>{run.reflect_level}</span>
            )}
            {run.conflict && (
              <span style={{ fontSize: 9, color: T.warn, padding: "0 5px", borderRadius: 3, background: `${T.warn}14`, border: `1px solid ${T.warn}33`, fontFamily: "monospace" }}>
                conflict
              </span>
            )}
          </div>
        </div>

        {/* Agent */}
        <div style={{ fontSize: 11, color: ac, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {(run.agent || "—").replace(/_/g, " ")}
        </div>

        {/* Critic score */}
        <div style={{ fontSize: 11, fontFamily: "monospace" }}>
          {run.critic_initial != null ? (
            <span style={{ color: run.accepted_first ? T.success : T.error }}>
              {run.critic_initial.toFixed(2)}
            </span>
          ) : <span style={{ color: T.muted }}>—</span>}
        </div>

        {/* Duration */}
        <div style={{ fontSize: 11, color: T.muted, fontFamily: "monospace", textAlign: "right" }}>
          {run.duration_ms ? `${run.duration_ms}ms` : "—"}
        </div>

        {/* Time ago */}
        <div style={{ fontSize: 10, color: T.muted, textAlign: "right", whiteSpace: "nowrap" }}>
          {relativeTime(run.started_at || run.timestamp)}
        </div>

        {/* Chevron */}
        <div style={{ fontSize: 10, color: T.muted, textAlign: "center", transition: "transform 0.15s", transform: expanded ? "rotate(180deg)" : "none" }}>
          ▾
        </div>
      </div>
      {expanded && <ExpandedRun runId={run.run_id} summary={run} />}
    </div>
  );
}

// ── Table header ───────────────────────────────────────────────
function TableHeader() {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "52px 1fr 120px 70px 72px 60px 28px",
      padding: "7px 16px",
      borderBottom: `2px solid ${T.border}`,
      gap: 10,
    }}>
      {["Status", "Query", "Agent", "Score", "Duration", "When", ""].map(h => (
        <div key={h} style={{ fontSize: 9, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase" }}>
          {h}
        </div>
      ))}
    </div>
  );
}

// ── Agent distribution bar ─────────────────────────────────────
function AgentDistBar({ runs }) {
  const counts = {};
  for (const r of runs) {
    if (r.agent) counts[r.agent] = (counts[r.agent] || 0) + 1;
  }
  const total   = runs.length;
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);

  if (!entries.length) return null;
  return (
    <div style={{ display: "flex", gap: 1, height: 4, borderRadius: 2, overflow: "hidden", marginTop: 10 }}>
      {entries.map(([id, cnt]) => (
        <div
          key={id}
          title={`${id.replace(/_/g, " ")} — ${cnt} (${Math.round((cnt / total) * 100)}%)`}
          style={{
            flex: cnt,
            background: agentColor(id),
            cursor: "default",
          }}
        />
      ))}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────
export default function RunsTab() {
  const [runs,     setRuns]     = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [status,   setStatus]   = useState("all");
  const [agent,    setAgent]    = useState("all");
  const [search,   setSearch]   = useState("");

  const load = useCallback(() => {
    setLoading(true);
    fetch("http://localhost:8000/runs?limit=200")
      .then(r => r.ok ? r.json() : { runs: [] })
      .then(d => { setRuns(d.runs || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const total   = runs.length;
  const passing = runs.filter(r => r.status === "pass").length;
  const failing = runs.filter(r => r.status === "fail").length;
  const partial = runs.filter(r => r.status === "partial").length;
  const passRate = total > 0 ? Math.round((passing / total) * 100) : null;
  const avgMs    = total > 0 ? Math.round(runs.reduce((s, r) => s + (r.duration_ms || 0), 0) / total) : null;

  const agentOptions = useMemo(() => {
    const ids = [...new Set(runs.map(r => r.agent).filter(Boolean))].sort();
    return ids;
  }, [runs]);

  const filtered = useMemo(() => {
    let r = runs;
    if (status !== "all")  r = r.filter(x => x.status === status);
    if (agent  !== "all")  r = r.filter(x => x.agent  === agent);
    if (search.trim())     r = r.filter(x => (x.query || "").toLowerCase().includes(search.toLowerCase()));
    return r;
  }, [runs, status, agent, search]);

  const toggleExpand = id => setExpanded(e => e === id ? null : id);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", animation: "fadeIn .2s" }}>

      {/* ── Header ── */}
      <div style={{ padding: "16px 20px 12px", borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>

        {/* Title row */}
        <PageHeader title="Runs" subtitle="Every LLM invocation — generation path, critic decisions, failure traces.">
          <button
            onClick={load}
            className="nav-btn"
            style={{
              background: "transparent", border: `1px solid ${T.border}`,
              color: T.mutedLt, padding: "6px 16px", borderRadius: 16,
              fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
            }}
          >↻ Refresh</button>
        </PageHeader>

        {/* Stats bar */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
          <StatBtn value={total}   label="All"     color={T.muted}   active={status === "all"}     onClick={() => setStatus("all")} />
          <StatBtn value={passing} label="Pass"    color={T.success} active={status === "pass"}    onClick={() => setStatus("pass")} />
          <StatBtn value={partial} label="Partial" color={T.warn}    active={status === "partial"} onClick={() => setStatus("partial")} />
          <StatBtn value={failing} label="Fail"    color={T.error}   active={status === "fail"}    onClick={() => setStatus("fail")} />

          <div style={{ flex: 1 }} />

          {avgMs != null && (
            <div style={{ fontSize: 11, color: T.muted, fontFamily: "monospace" }}>
              avg <span style={{ color: T.mutedLt }}>{avgMs}ms</span>
            </div>
          )}
          {passRate != null && (
            <div style={{
              display: "flex", alignItems: "center", gap: 6,
              background: T.surface2, border: `1px solid ${T.border}`,
              borderRadius: 6, padding: "5px 12px",
            }}>
              <span style={{ fontSize: 11, color: T.muted }}>Pass rate</span>
              <span style={{
                fontSize: 14, fontWeight: 700, fontFamily: "monospace",
                color: passRate >= 90 ? T.success : passRate >= 70 ? T.warn : T.error,
              }}>{passRate}%</span>
            </div>
          )}
        </div>

        {/* Agent distribution bar */}
        <AgentDistBar runs={runs} />

        {/* Filters row */}
        <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center", flexWrap: "wrap" }}>
          {/* Search */}
          <div style={{
            flex: 1, minWidth: 180,
            display: "flex", alignItems: "center", gap: 6,
            background: T.surface2, border: `1px solid ${T.border}`,
            borderRadius: 6, padding: "5px 10px",
          }}>
            <span style={{ fontSize: 12, color: T.muted, flexShrink: 0 }}>⌕</span>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search queries…"
              style={{
                flex: 1, background: "transparent", border: "none",
                color: T.text, fontSize: 12, outline: "none", fontFamily: "inherit",
              }}
            />
            {search && (
              <button onClick={() => setSearch("")} style={{ background: "none", border: "none", color: T.muted, cursor: "pointer", fontSize: 13, lineHeight: 1, padding: 0 }}>✕</button>
            )}
          </div>

          {/* Agent filter */}
          <select
            value={agent}
            onChange={e => setAgent(e.target.value)}
            style={{
              background: T.surface2, border: `1px solid ${T.border}`,
              color: agent === "all" ? T.muted : agentColor(agent),
              borderRadius: 6, padding: "5px 10px",
              fontSize: 11, fontFamily: "inherit", cursor: "pointer", outline: "none",
            }}
          >
            <option value="all">All agents</option>
            {agentOptions.map(id => (
              <option key={id} value={id}>{id.replace(/_/g, " ")}</option>
            ))}
          </select>

          {/* Active filter count */}
          {filtered.length !== total && (
            <span style={{ fontSize: 11, color: T.muted }}>
              showing <span style={{ color: T.text, fontWeight: 600 }}>{filtered.length}</span> of {total}
            </span>
          )}
        </div>
      </div>

      {/* ── Table ── */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading ? (
          <div style={{ padding: "60px 0", textAlign: "center", color: T.muted, fontSize: 13 }}>
            Loading runs…
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "60px 0", textAlign: "center" }}>
            <div style={{ fontSize: 30, marginBottom: 10, opacity: 0.25 }}>⬡</div>
            <div style={{ fontSize: 13, color: T.muted }}>
              {total === 0
                ? "No runs yet — send a message in Chat to create the first run."
                : "No runs match the current filters."}
            </div>
            {(status !== "all" || agent !== "all" || search) && (
              <button
                onClick={() => { setStatus("all"); setAgent("all"); setSearch(""); }}
                style={{
                  marginTop: 12, background: "transparent",
                  border: `1px solid ${T.border}`, color: T.muted,
                  padding: "5px 14px", borderRadius: 6,
                  fontSize: 11, cursor: "pointer", fontFamily: "inherit",
                }}
              >Clear filters</button>
            )}
          </div>
        ) : (
          <>
            <TableHeader />
            {filtered.map(run => (
              <RunRow
                key={run.run_id}
                run={run}
                expanded={expanded === run.run_id}
                onToggle={() => toggleExpand(run.run_id)}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────
function StatBtn({ value, label, color, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 6,
      background: active ? `${color}18` : T.surface2,
      border: `1px solid ${active ? color + "55" : T.border}`,
      borderRadius: 6, padding: "5px 12px",
      cursor: "pointer", fontFamily: "inherit",
      transition: "all .1s",
    }}>
      <span style={{ fontSize: 14, fontWeight: 700, color, fontFamily: "monospace" }}>{value}</span>
      <span style={{ fontSize: 11, color: T.muted }}>{label}</span>
    </button>
  );
}

function ActionBtn({ children, onClick, disabled, color, active }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: active ? `${color}22` : `${color}14`,
      border: `1px solid ${color}${active ? "66" : "33"}`,
      color, padding: "5px 12px", borderRadius: 6,
      fontSize: 11, fontWeight: 600,
      cursor: disabled ? "not-allowed" : "pointer",
      fontFamily: "inherit", opacity: disabled ? 0.5 : 1,
      transition: "all .1s",
    }}>{children}</button>
  );
}

function MetaRow({ label, value, valueColor }) {
  if (value == null || value === "" || value === "none") return null;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
      <span style={{ fontSize: 11, color: T.muted }}>{label}</span>
      <span style={{ fontSize: 11, color: valueColor || T.mutedLt, fontFamily: "monospace", fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function SectionHead({ title }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>
      {title}
    </div>
  );
}
