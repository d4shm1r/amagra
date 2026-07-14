import { useState, useEffect, useCallback } from "react";
import { PageHeader, Section, Well, Pill, StatStrip } from "@/components/ui";
import { T, GOLD, TYPE } from "@/styles/theme";

import { API } from "@/lib/api";
import { AGENTS } from "@/config/constants";

// Color carries STATUS here, never category. Series (coverage signals, agent
// share, node/edge types, causal stages) are told apart by their labels — they
// all read in one gold voice, graded by rank so the eye still gets a hierarchy.
// The only saturated colors left are good/warn/bad, so when something IS red it
// actually means something.
const RAMP = [GOLD.g4, GOLD.g3, GOLD.g2, "#D9C89A", "#E3D6B4", "#EADFC6"];
const rank = i => RAMP[Math.min(i, RAMP.length - 1)];

// Status ink for bare numerals. The theme's amber `warn` is the same hue as the
// brand gold on this cream canvas — as a number's only signal it reads as
// decoration, not caution. So the middle tier is neutral ink: green = good,
// ink = unremarkable, red = look here. (Warning *sentences* still use T.warn:
// their words carry the meaning, the color only tints it.)
const OK = T.success, MID = T.mutedLt, BAD = T.error;

const VERDICT_META = {
  core:       { color: T.success, label: "CORE",       desc: "Essential — high volume, reliable routing" },
  narrow:     { color: T.accent2, label: "NARROW",     desc: "Specialized but low volume — survives if domain is real" },
  struggling: { color: T.error,   label: "STRUGGLING", desc: "High conflict + regret — routing unreliable" },
  redundant:  { color: T.muted,   label: "REDUNDANT",  desc: "Domain overlaps with higher-quality agent" },
};

// Unicode marks from constants.js AGENTS — never emoji (palette rule). The
// per-agent colors are deliberately dropped: in this tab an agent is a row
// label, not a series, so it stays in text ink with a gold mark.
const AGENT_META = Object.fromEntries(
  AGENTS.map(a => [a.id, { icon: a.icon }])
);

// Luxury numerals: the UI typeface with tabular figures — never a code font.
const NUM = { fontVariantNumeric: "tabular-nums" };

// Section / Well / Pill / StatStrip come from ObsShared — the shared component
// layer. Only what is genuinely Analysis-specific stays local below.

function CovBar({ label, pct, color = T.accent }) {
  const p = Math.round((pct || 0) * 100);
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ ...TYPE.caption, color: T.mutedLt }}>{label}</span>
        <span style={{ ...TYPE.caption, ...NUM, color: T.accentText, fontWeight: 700 }}>{p}%</span>
      </div>
      <div style={{ height: 5, background: T.border, borderRadius: 999, overflow: "hidden" }}>
        <div style={{ width: `${p}%`, height: "100%", background: color, borderRadius: 999, transition: "width .4s" }} />
      </div>
    </div>
  );
}

function VerdictBadge({ verdict }) {
  const m = VERDICT_META[verdict] || { color: T.muted, label: verdict?.toUpperCase() || "?" };
  return <Pill color={m.color} strong>{m.label}</Pill>;
}

/** Agent name + mark, one chip shape wherever an agent is named. */
function AgentChip({ id, bold = true }) {
  const m = AGENT_META[id] || { icon: "·" };
  return (
    <span style={{ ...TYPE.caption, display: "inline-flex", alignItems: "center", gap: 7, color: T.text, fontWeight: bold ? 700 : 400 }}>
      <span style={{ color: T.accent }}>{m.icon}</span>
      <span>{id?.replace(/_/g, " ")}</span>
    </span>
  );
}

function SpecializationTable({ data }) {
  if (!data) return null;
  const agents = Object.entries(data).sort((a, b) => b[1].total_decisions - a[1].total_decisions);
  const maxN   = Math.max(...agents.map(([, r]) => r.total_decisions), 1);

  /** One metric: label above, value below. Reads without a header row. */
  const Metric = ({ label, value, color = T.text, sub }) => (
    <div style={{ minWidth: 74 }}>
      <div style={{ ...TYPE.micro, color: T.muted, marginBottom: 3 }}>{label}</div>
      <div style={{ ...TYPE.small, ...NUM, color, fontWeight: 700 }}>
        {value}{sub && <span style={{ color: T.muted, fontWeight: 400 }}> {sub}</span>}
      </div>
    </div>
  );

  return (
    <>
      {/* An agent is a card, not a table row. Eight columns could never fit —
          the Note always pushed the row into a horizontal scroll and got
          truncated anyway. Now the identity + verdict sit on the top line, the
          numbers wrap as label/value pairs, and the note gets a full line of its
          own where it can actually be read. Nothing scrolls sideways.
          Static on purpose: a readout, not a control — so no hover. */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {agents.map(([id, r], i) => {
          const crc = r.conflict_rate >= 0.40 ? BAD : r.conflict_rate >= 0.20 ? MID : OK;
          const qc  = r.avg_quality_proxy >= 0.78 ? OK : r.avg_quality_proxy >= 0.70 ? MID : BAD;
          return (
            <Well key={id} style={{ padding: "14px 18px" }}>
              {/* Identity line: who, how much, and the verdict */}
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
                <span style={{ ...TYPE.small, display: "inline-flex", alignItems: "center", gap: 7, color: T.text, fontWeight: 700 }}>
                  <span style={{ color: T.accent }}>{(AGENT_META[id] || { icon: "·" }).icon}</span>
                  {id.replace(/_/g, " ")}
                </span>
                <span style={{ ...TYPE.caption, ...NUM, color: T.accentText, fontWeight: 700 }}>
                  {r.total_decisions} <span style={{ color: T.muted, fontWeight: 400 }}>decisions</span>
                </span>
                {/* Share of total volume — ranking without a column */}
                <span style={{ flex: "1 1 90px", maxWidth: 220, height: 4, background: T.border, borderRadius: 999, overflow: "hidden" }}>
                  <span style={{ display: "block", width: `${(r.total_decisions / maxN) * 100}%`, height: "100%", background: rank(i), borderRadius: 999 }} />
                </span>
                <span style={{ marginLeft: "auto" }}><VerdictBadge verdict={r.verdict} /></span>
              </div>

              {/* Metrics — wrap instead of scroll */}
              <div style={{ display: "flex", gap: 28, flexWrap: "wrap", rowGap: 12 }}>
                <Metric label="Conflict"   value={`${(r.conflict_rate * 100).toFixed(0)}%`} color={crc} />
                <Metric label="Quality"    value={r.avg_quality_proxy.toFixed(3)} color={qc} />
                <Metric label="Regret"     value={r.avg_regret.toFixed(4)} color={T.mutedLt} />
                <Metric label="Top domain" value={r.top_domain} color={T.mutedLt}
                  sub={`(${(r.top_domain_pct * 100).toFixed(0)}%)`} />
              </div>

              {/* The note, in full — no ellipsis */}
              {r.verdict_reason && (
                <div style={{ ...TYPE.caption, color: T.muted, marginTop: 12, paddingTop: 10, borderTop: `1px solid ${T.border}` }}>
                  {r.verdict_reason}
                </div>
              )}
            </Well>
          );
        })}
      </div>

      {/* Legend — one verdict per line so the pill and its meaning stay paired */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(430px, 1fr))", gap: "10px 24px", marginTop: 16 }}>
        {Object.entries(VERDICT_META).map(([k, m]) => (
          <span key={k} style={{ display: "inline-flex", alignItems: "baseline", gap: 10 }}>
            <span style={{ minWidth: 88, flexShrink: 0 }}><Pill color={m.color}>{m.label}</Pill></span>
            <span style={{ ...TYPE.caption, color: T.muted }}>{m.desc}</span>
          </span>
        ))}
      </div>
    </>
  );
}

function CounterfactualPanel({ candidates }) {
  if (!candidates?.length) return (
    <div style={{ ...TYPE.small, color: T.muted, fontStyle: "italic", padding: "10px 0" }}>
      No high-priority counterfactual candidates yet.
    </div>
  );
  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {candidates.map(c => {
          const pColor = c.priority === "high" ? BAD : MID;
          return (
            <Well key={c.decision_id} style={{ padding: "9px 14px", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ ...TYPE.micro, ...NUM, color: T.muted, minWidth: 30 }}>#{c.decision_id}</span>
              <Pill color={pColor}>{c.priority}</Pill>
              <AgentChip id={c.original_agent} />
              <span style={{ color: T.accent }}>→</span>
              {c.suggested_alt
                ? <AgentChip id={c.suggested_alt} />
                : <span style={{ ...TYPE.caption, color: T.muted }}>no alt</span>}
              <span style={{ ...TYPE.micro, ...NUM, color: T.muted }}>regret {c.regret?.toFixed(4)}</span>
              {c.conflict && <Pill color={T.error}>conflict</Pill>}
              <span style={{ ...TYPE.caption, flex: 1, minWidth: 120, color: T.mutedLt, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.query}
              </span>
            </Well>
          );
        })}
      </div>
      <div style={{ ...TYPE.caption, marginTop: 12, color: T.muted }}>
        Invoke with <code style={{ ...NUM, color: T.accentText }}>POST /analysis/counterfactual/&#123;id&#125;?alt_agent=X&dry_run=false</code>.
        Statistical claims require 400+ real sessions.
      </div>
    </>
  );
}

function GraphStatsPanel({ graph }) {
  if (!graph) return null;
  const s = graph.stats || {};
  const nodeTypes = s.by_node_type || {};
  const edgeTypes = s.by_edge_type || {};

  // Tallies are counts, not categories: one gold voice, share bar for weight.
  const Tally = ({ heading, entries }) => {
    const rows = Object.entries(entries).sort((a, b) => b[1] - a[1]);
    const max  = Math.max(...rows.map(([, n]) => n), 1);
    return (
      <div style={{ flex: "1 1 220px" }}>
        <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.1em", color: T.muted, marginBottom: 8 }}>{heading}</div>
        <Well style={{ padding: "4px 14px" }}>
          {rows.map(([t, n], i, arr) => (
            <div key={t} style={{
              padding: "8px 0",
              borderBottom: i < arr.length - 1 ? `1px solid ${T.border}66` : "none",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ ...TYPE.caption, color: T.mutedLt, fontWeight: 700 }}>{t}</span>
                <span style={{ ...TYPE.caption, ...NUM, color: T.text }}>{n}</span>
              </div>
              <div style={{ height: 3, background: T.border, borderRadius: 999, overflow: "hidden" }}>
                <div style={{ width: `${(n / max) * 100}%`, height: "100%", background: rank(i), borderRadius: 999 }} />
              </div>
            </div>
          ))}
        </Well>
      </div>
    );
  };

  return (
    <>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        <Pill color={T.accent}>{graph.version}</Pill>
        {[
          [graph.trace_count, "traces"], [s.node_count, "nodes"],
          [s.edge_count, "edges"], [s.avg_degree, "avg degree"],
        ].map(([v, l]) => (
          <span key={l} style={{ ...TYPE.caption, color: T.muted }}>
            <span style={{ ...NUM, color: T.text, fontWeight: 700 }}>{v}</span> {l}
          </span>
        ))}
      </div>
      {s.node_count ? (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Tally heading="Nodes" entries={nodeTypes} />
          <Tally heading="Edges" entries={edgeTypes} />
        </div>
      ) : (
        <div style={{ ...TYPE.small, color: T.muted, fontStyle: "italic" }}>
          Graph is empty — Rebuild to construct it from the current traces.
        </div>
      )}
    </>
  );
}

function CausalPathPanel() {
  const [decisionId, setDecisionId] = useState("");
  const [path,       setPath]       = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState("");

  const query = async () => {
    const id = parseInt(decisionId, 10);
    if (!id) return;
    setLoading(true); setError(""); setPath(null);
    try {
      const r = await fetch(`${API}/data/causal/${id}`);
      if (!r.ok) { setError(`Not found: decision ${id}`); setLoading(false); return; }
      // The endpoint answers 200 with an {error} body when the decision isn't in
      // the graph — surface that instead of silently rendering nothing.
      const d = await r.json();
      if (d.error) setError(d.error);
      else setPath(d);
    } catch { setError("Request failed"); }
    setLoading(false);
  };

  const FLAG_COLORS = { routing_conflict: BAD, high_regret: BAD, low_quality: BAD, low_relevance_memory: MID };

  return (
    <>
      {/* Input and button are one control: same 38px height, same pill radius,
          baseline-aligned — the button no longer floats above a taller field. */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14, alignItems: "center" }}>
        <input value={decisionId} onChange={e => setDecisionId(e.target.value)}
          onKeyDown={e => e.key === "Enter" && query()}
          onFocus={e => { e.target.style.borderColor = T.accent; }}
          onBlur={e => { e.target.style.borderColor = T.border; }}
          placeholder="Decision ID (e.g. 172)" type="number"
          style={{
            ...TYPE.small, ...NUM, width: 180, height: 38, padding: "0 16px", borderRadius: 999,
            background: T.surface2, border: `1px solid ${T.border}`, color: T.text,
            fontFamily: "inherit", outline: "none", transition: "border-color 140ms ease",
          }} />
        <button className="btn-ghost" onClick={query} disabled={loading || !decisionId}
          style={{ ...TYPE.caption, fontWeight: 700, height: 38, padding: "0 24px", opacity: decisionId ? 1 : 0.55 }}>
          {loading ? "Tracing…" : "Trace"}
        </button>
      </div>
      {error && <div style={{ ...TYPE.small, color: T.error, marginBottom: 10 }}>{error}</div>}
      {path && !path.error && (
        <Well style={{ padding: "16px 18px" }}>
          {/* Causal flags */}
          {path.causal_flags?.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
              {path.causal_flags.map((f, i) => (
                <Pill key={i} color={FLAG_COLORS[f.type] || T.muted} strong>
                  {f.type.replace(/_/g, " ")}
                </Pill>
              ))}
            </div>
          )}
          {/* Path steps — the stages are a sequence, not eight categories, so the
              rail runs in one gold voice. Only a REJECTED that actually rejected
              someone earns a status color: the red then means "a conflict happened
              here", instead of being permanent decoration. */}
          {[
            { label: "QUERY",      content: `"${(path.query || "").slice(0,100)}"` },
            { label: "SIGNAL",     content: `domain=${path.signal?.domain} shape=${path.signal?.shape} conf=${path.signal?.conf?.toFixed(2)}` },
            { label: "ACTION",     content: `${path.action} / ${path.complexity}` },
            { label: "SELECTED",   content: path.selected_agent || "—" },
            { label: "REJECTED",   tone: path.rejected_agents?.length ? T.error : null,
              content: path.rejected_agents?.length ? path.rejected_agents.join(", ") : "none (no conflict)" },
            { label: "MEMORY",     content: `${path.memories_retrieved} records retrieved` + (path.top_memories?.length ? ` (top: ${path.top_memories.slice(0,2).map(m => `${m.mem_type}@${m.agent} score=${m.score?.toFixed(2)}`).join(", ")})` : "") },
            { label: "OUTCOME",    content: `quality=${path.outcome?.quality_proxy?.toFixed(3)}  regret=${path.outcome?.regret?.toFixed(4)}  conf=${path.outcome?.confidence?.toFixed(2)}  ${path.outcome?.duration_ms}ms` },
            { label: "REFLECTION", content: path.reflection?.triggered ? `YES (${path.reflection?.reflect_type})` : "none" },
          ].map((step, i, arr) => {
            const tone = step.tone || T.accent;
            return (
              <div key={step.label} style={{ display: "flex", gap: 14, alignItems: "flex-start", paddingBottom: i < arr.length - 1 ? 10 : 0 }}>
                {/* Gold rail: stage label, then a connector dot threading the path */}
                <span style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.08em", color: step.tone || T.accentText, minWidth: 74, textAlign: "right", paddingTop: 3 }}>
                  {step.label}
                </span>
                <span style={{ display: "flex", flexDirection: "column", alignItems: "center", alignSelf: "stretch", paddingTop: 5 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: tone, flexShrink: 0 }} />
                  {i < arr.length - 1 && <span style={{ flex: 1, width: 1, background: T.border, marginTop: 3 }} />}
                </span>
                <span style={{ ...TYPE.small, ...NUM, color: T.text, lineHeight: 1.5, flex: 1, minWidth: 0 }}>{step.content}</span>
              </div>
            );
          })}
          {/* Causal flag detail */}
          {path.causal_flags?.length > 0 && (
            <div style={{ marginTop: 12, borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
              {path.causal_flags.map((f, i) => (
                <div key={i} style={{ ...TYPE.caption, color: FLAG_COLORS[f.type] || T.muted, marginBottom: 4 }}>
                  ↳ {f.detail}
                </div>
              ))}
            </div>
          )}
        </Well>
      )}
    </>
  );
}

// ── Memory Backend Panel ──────────────────────────────────────

function MemoryBackendPanel({ backend, onRefresh }) {
  const [bench,      setBench]      = useState(null);
  const [benching,   setBenching]   = useState(false);
  const [promoting,  setPromoting]  = useState(false);
  const [promoteMsg, setPromoteMsg] = useState(null);

  async function runBench() {
    setBenching(true);
    setBench(null);
    try {
      const r = await fetch(`${API}/analysis/memory_backend/bench?n=7`);
      if (r.ok) setBench(await r.json());
    } catch {}
    setBenching(false);
  }

  async function promote() {
    setPromoting(true);
    setPromoteMsg(null);
    try {
      const r = await fetch(`${API}/analysis/memory_backend/promote`, { method: "POST" });
      const d = await r.json();
      setPromoteMsg(d.promoted
        ? `Promoted to FAISSBackend (${d.backend?.total ?? "?"} entries)`
        : "Already on optimal backend — no promotion needed");
      onRefresh();
    } catch (e) {
      setPromoteMsg(`Error: ${e.message}`);
    }
    setPromoting(false);
  }

  if (!backend) return null;

  const isFaiss   = backend.type === "FAISSBackend";
  const isSqlite  = backend.type === "SQLiteBackend";
  const threshold = backend.promote_threshold || 800;
  const total     = backend.total || 0;
  const progress  = Math.min(100, Math.round((total / threshold) * 100));
  const typeColor = isFaiss ? OK : T.accentText;
  const driftOk   = (backend.drift_pct ?? 0) <= 5;

  const searchPassing = bench?.search_passing || bench?.raw_vector_ok;
  const searchColor   = bench ? (searchPassing ? OK : BAD) : T.muted;
  const totalColor    = bench ? (bench.total_p50_ms < 200 ? OK : MID) : T.muted;

  // Sub-tile numeral — sits below the 22px metric tier (StatCard) used above.
  const statNum = { ...TYPE.subtitle, ...NUM, fontWeight: 800 };

  const Tile = ({ value, label, sub, color = T.text, tone = T.border }) => (
    <div style={{ background: T.surface2, borderRadius: 12, padding: "12px 16px", border: `1px solid ${tone}` }}>
      <div style={{ ...statNum, color }}>{value}</div>
      <div style={{ ...TYPE.caption, color: T.muted, marginTop: 3 }}>{label}</div>
      {sub && <div style={{ ...TYPE.micro, color, marginTop: 3 }}>{sub}</div>}
    </div>
  );

  return (
    <Section
      title="Memory Backend"
      action={<>
        <Pill color={backend.fan_out_warning ? T.error : typeColor} strong>{backend.type}</Pill>
        <button className="btn-ghost" onClick={runBench} disabled={benching}
          style={{ ...TYPE.caption, fontWeight: 700, padding: "6px 16px" }}>
          {benching ? "Running…" : "Benchmark"}
        </button>
        {isSqlite && (
          <button className="btn-ghost" onClick={promote} disabled={promoting}
            style={{ ...TYPE.caption, fontWeight: 700, padding: "6px 16px" }}>
            {promoting ? "Promoting…" : "Promote to FAISS"}
          </button>
        )}
      </>}
    >
      {/* Info grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12, marginBottom: 14 }}>
        <Tile value={total.toLocaleString()} label="Total entries" />
        {isFaiss && backend.index_ntotal != null && (
          <Tile value={backend.index_ntotal.toLocaleString()} label="FAISS index vectors"
            color={driftOk ? OK : BAD} tone={driftOk ? T.border : `${BAD}44`}
            sub={`${backend.drift_pct}% drift`} />
        )}
        {isFaiss && backend.index_size_mb != null && (
          <Tile value={`${backend.index_size_mb} MB`} label="Index file size" />
        )}
        {bench && bench.search_p50_ms != null && (
          <Tile value={`${bench.search_p50_ms} ms`} label={`Vector search P50 (target ≤${bench.search_target_ms}ms)`}
            color={searchColor} tone={`${searchColor}33`}
            sub={`${searchPassing ? "Passing" : "Above target"} · P95 ${bench.search_p95_ms}ms`} />
        )}
        {bench && bench.total_p50_ms != null && (
          <Tile value={`${bench.total_p50_ms} ms`} label="Full pipeline P50"
            color={totalColor} tone={`${totalColor}33`} sub="embed + search + re-rank" />
        )}
      </div>

      {/* Promotion threshold bar (SQLite only) */}
      {isSqlite && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
            <span style={{ ...TYPE.caption, color: T.mutedLt }}>Fan-out threshold ({total} / {threshold} entries)</span>
            <span style={{ ...TYPE.caption, ...NUM, color: progress >= 100 ? BAD : T.accentText, fontWeight: 700 }}>{progress}%</span>
          </div>
          <div style={{ height: 5, background: T.border, borderRadius: 999, overflow: "hidden" }}>
            <div style={{ width: `${progress}%`, height: "100%", background: progress >= 100 ? T.error : T.accent, borderRadius: 999, transition: "width .4s" }} />
          </div>
          {progress >= 80 && (
            <div style={{ ...TYPE.caption, color: T.warn, marginTop: 6 }}>
              Approaching FAISS threshold — auto-promote triggers at {threshold} entries
            </div>
          )}
        </div>
      )}

      {/* Engine detail */}
      <div style={{ ...TYPE.caption, color: T.muted, lineHeight: 1.6 }}>
        Engine: <span style={{ color: T.accentText, fontWeight: 700 }}>{backend.engine || "—"}</span>
        {isFaiss && <span style={{ color: T.success, marginLeft: 12 }}>O(log n) ANN · thread-safe · incremental updates</span>}
        {isSqlite && <span style={{ color: T.mutedLt, marginLeft: 12 }}>O(n) cosine scan · auto-promotes at {threshold} entries</span>}
      </div>

      {/* Benchmark summary */}
      {bench && (
        <Well tone={`${searchColor}33`} style={{ marginTop: 12, padding: "10px 14px", background: `${searchColor}0D` }}>
          <span style={{ ...TYPE.caption, color: searchColor, fontWeight: 700 }}>
            {searchPassing ? "Vector search passing" : "Vector search above target"}
          </span>
          <span style={{ ...TYPE.caption, color: T.muted, marginLeft: 10 }}>
            {bench.n_queries} queries · {bench.entry_count} entries · {bench.embed_note}
          </span>
        </Well>
      )}
      {promoteMsg && (
        <Well tone={`${T.success}33`} style={{ marginTop: 12, padding: "10px 14px", background: `${T.success}10` }}>
          <span style={{ ...TYPE.caption, color: T.success }}>{promoteMsg}</span>
        </Well>
      )}
    </Section>
  );
}


// ── Main component ────────────────────────────────────────────

export default function DataTab() {
  const [stats,    setStats]    = useState(null);
  const [spec,     setSpec]     = useState(null);
  const [cands,    setCands]    = useState(null);
  const [backend,  setBackend]  = useState(null);
  const [graphStats, setGraphStats] = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sR, spR, cR, bR, gR] = await Promise.all([
        fetch(`${API}/data/stats`),
        fetch(`${API}/analysis/specialization`),
        fetch(`${API}/analysis/counterfactual/candidates?n=8`),
        fetch(`${API}/analysis/memory_backend`),
        fetch(`${API}/data/graph/stats`),
      ]);
      if (sR.ok)  setStats(await sR.json());
      if (spR.ok) setSpec(await spR.json());
      if (cR.ok)  { const d = await cR.json(); setCands(d.candidates || []); }
      if (bR.ok)  setBackend(await bR.json());
      if (gR.ok)  setGraphStats(await gR.json());
    } catch {
      setStats(null);
    }
    setLoading(false);
  }, []);

  const rebuild = async () => {
    setRebuilding(true);
    try {
      const [sR, spR, gR] = await Promise.all([
        fetch(`${API}/data/stats?rebuild=true`),
        fetch(`${API}/analysis/specialization?rebuild=true`),
        fetch(`${API}/data/graph/stats?rebuild=true`),
      ]);
      if (sR.ok)  setStats(await sR.json());
      if (spR.ok) setSpec(await spR.json());
      if (gR.ok)  setGraphStats(await gR.json());
    } catch {}
    setRebuilding(false);
  };

  useEffect(() => { load(); }, [load]);

  const btn = { ...TYPE.caption, fontWeight: 700, padding: "8px 20px", textDecoration: "none" };

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      {/* Header */}
      <PageHeader
        center
        title="Analysis"
        subtitle="Every routing decision joined with memory, reflection, and session data — where agents specialize, where routing goes wrong, and why a given answer came out the way it did."
      >
        <a href={`${API}/data/traces.jsonl`} download="trace_dataset.jsonl" className="btn-ghost" style={btn}>
          Export JSONL
        </a>
        <button className="btn-ghost" onClick={rebuild} disabled={rebuilding} style={btn}>
          {rebuilding ? "Rebuilding…" : "Rebuild"}
        </button>
        <button className="btn-ghost" onClick={load} disabled={loading} style={btn}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </PageHeader>

      {/* Section stack — spacing comes from the gap, not per-card margins */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Dataset headline numbers — one inline strip, nothing else in this card */}
      {stats && (
        <Section title="Dataset" hint="traces joined across routing, memory, reflection and feedback">
          {/* One gold voice across the strip, like the Releases stat bar. Regret
              is the lone exception: it goes red once it crosses the threshold,
              because that's the number you're supposed to notice. */}
          <StatStrip items={[
            { label: "Total traces",   value: stats.total },
            { label: "Real sessions",  value: stats.real_sessions },
            { label: "Eval decisions", value: stats.eval_decisions },
            { label: "Avg quality",    value: stats.avg_quality_proxy?.toFixed(3) },
            { label: "Avg memories/q", value: stats.avg_memories_per_query?.toFixed(1), sub: "fan-out signal" },
            { label: "Avg regret",     value: stats.avg_regret?.toFixed(4), color: stats.avg_regret > 0.1 ? BAD : undefined },
          ]} />
        </Section>
      )}

      {/* Coverage + distribution — the two breakdowns, side by side */}
      {stats && (
        <Section title="Composition" hint="what the traces carry, and who they were routed to">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 28 }}>
            <div>
              <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.1em", color: T.muted, marginBottom: 12 }}>Signal Coverage</div>
              {stats.coverage && [
                ["Has response",   stats.coverage.response_pct],
                ["Has memory",     stats.coverage.memory_pct],
                ["Has reflection", stats.coverage.reflection_pct],
                ["Has conflict",   stats.coverage.conflict_pct],
                ["Has feedback",   stats.coverage.feedback_pct],
              ].map(([lbl, pct]) => (
                <CovBar key={lbl} label={lbl} pct={pct} />
              ))}
            </div>
            <div>
              <div style={{ ...TYPE.eyebrow, fontWeight: 600, letterSpacing: "0.1em", color: T.muted, marginBottom: 12 }}>Agent Distribution</div>
              {stats.agent_distribution && Object.entries(stats.agent_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([agent, n], i) => {
                  const pct = n / stats.total;
                  return (
                    <div key={agent} style={{ marginBottom: 9 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ ...TYPE.caption, color: T.mutedLt }}>{agent.replace(/_/g, " ")}</span>
                        <span style={{ ...TYPE.caption, ...NUM, color: T.text, fontWeight: 700 }}>{n} <span style={{ color: T.muted, fontWeight: 400 }}>({(pct*100).toFixed(0)}%)</span></span>
                      </div>
                      <div style={{ height: 5, background: T.border, borderRadius: 999, overflow: "hidden" }}>
                        <div style={{ width: `${pct*100}%`, height: "100%", background: rank(i), borderRadius: 999 }} />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </Section>
      )}

      {/* Specialization table */}
      {spec && (
        <Section title="Agent Specialization Index" hint="who is carrying real volume, and who is only surviving on overlap">
          <SpecializationTable data={spec} />
        </Section>
      )}

      {/* Counterfactual candidates */}
      {cands !== null && (
        <Section title="Counterfactual Candidates" hint="high-regret and conflict decisions worth re-running with the alternative agent">
          <CounterfactualPanel candidates={cands} />
        </Section>
      )}

      {/* Decision graph stats */}
      {graphStats && (
        <Section title="Decision Graph" hint="the trace store as a graph — what links to what">
          <GraphStatsPanel graph={graphStats} />
        </Section>
      )}

      {/* Causal path explorer */}
      <Section title="Causal Path Explorer" hint="inspect why a specific decision was made — routing, memory, outcome">
        <CausalPathPanel />
      </Section>

      {/* Memory backend status */}
      <MemoryBackendPanel backend={backend} onRefresh={load} />

      </div>
    </div>
  );
}
