import { useState, useEffect, useCallback } from "react";
import { AGENTS } from "./constants";
import { T, SEM, TYPE } from "./theme";

import { API } from "./api";

const AGENT_META = Object.fromEntries(
  AGENTS.map(a => [a.id, { icon: a.icon, color: a.color, label: a.label.replace(" Dev", "").replace(" & ", "/") }])
);

// ── Primitive display components ──────────────────────────────

function AgentChip({ id }) {
  const m = AGENT_META[id] || { icon: "?", color: T.muted, label: id };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 9px", borderRadius: 3, ...TYPE.caption,
      background: m.color + "22", color: m.color,
      border: `1px solid ${m.color}55`, fontWeight: 700, whiteSpace: "nowrap",
    }}>
      {m.icon} {m.label}
    </span>
  );
}

function ScoreBar({ value, width = 80 }) {
  const pct = Math.round((value || 0) * 100);
  const c   = pct >= 70 ? T.success : pct >= 45 ? T.accent2 : T.error;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width, height: 4, background: T.border, borderRadius: 2, overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", width: `${pct}%`, height: "100%", background: c, borderRadius: 2 }} />
      </span>
      <span style={{ ...TYPE.caption, color: c, fontWeight: 700 }}>{pct}%</span>
    </span>
  );
}

function Mono({ children, color = SEM.blue }) {
  return <span style={{ fontFamily: "monospace", ...TYPE.caption, color }}>{children}</span>;
}

function SectionHeader({ label, color = T.muted, count }) {
  return (
    <div style={{
      ...TYPE.micro, fontWeight: 700, color, textTransform: "uppercase",
      letterSpacing: 1.2, marginBottom: 8, display: "flex", alignItems: "center", gap: 6,
    }}>
      {label}
      {count != null && (
        <span style={{ fontWeight: 400, color: T.muted, textTransform: "none", letterSpacing: 0 }}>
          {count}
        </span>
      )}
    </div>
  );
}

function Panel({ color, children, style }) {
  return (
    <div style={{
      borderLeft: `3px solid ${color}55`,
      paddingLeft: 12, marginBottom: 16,
      ...style,
    }}>
      {children}
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 5 }}>
      <span style={{ ...TYPE.caption, color: T.muted, minWidth: 90, flexShrink: 0, paddingTop: 1 }}>{label}</span>
      <span style={{ ...TYPE.caption, color: T.text }}>{children}</span>
    </div>
  );
}

// ── Snapshot detail view ──────────────────────────────────────

function SnapshotDetail({ snap }) {
  const { input = {}, routing = {}, prompt = {}, memory = {},
          tools = {}, model = {}, output = {}, evaluation = {} } = snap;
  const mem = memory.retrieved || [];
  const hasEval = Object.keys(evaluation).length > 0;

  return (
    <div style={{ padding: "18px 20px", overflowY: "auto", height: "100%" }}>

      {/* Identity */}
      <div style={{
        background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 4,
        padding: "10px 14px", marginBottom: 18, display: "flex", alignItems: "center", gap: 12,
      }}>
        <span style={{ ...TYPE.micro, color: T.muted, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
          Build
        </span>
        <Mono color={T.accent2}>#{snap._snapshot_id}</Mono>
        <span style={{ height: 14, width: 1, background: T.border }} />
        <Mono color={T.muted}>{(snap.request_id || "").slice(0, 16)}…</Mono>
        <span style={{ marginLeft: "auto", ...TYPE.caption, color: T.muted }}>
          {snap.timestamp?.slice(0, 19).replace("T", " ")} UTC
        </span>
      </div>

      {/* Input */}
      <Panel color={SEM.teal}>
        <SectionHeader label="Input" color={SEM.teal} />
        <Row label="Query">
          <span style={{ fontStyle: "italic", color: T.text, lineHeight: 1.5 }}>
            "{(input.query || "").slice(0, 200)}"
          </span>
        </Row>
        {input.normalized_query && (
          <Row label="Normalized"><Mono>{input.normalized_query}</Mono></Row>
        )}
      </Panel>

      {/* Routing */}
      <Panel color={T.accent}>
        <SectionHeader label="Routing" color={T.accent} />
        <Row label="Agent"><AgentChip id={routing.agent} /></Row>
        <Row label="Action">
          <Mono color={SEM.blue}>{routing.action}</Mono>
          <span style={{ color: T.muted, ...TYPE.caption, marginLeft: 8 }}>{routing.complexity}</span>
        </Row>
        <Row label="Confidence"><ScoreBar value={routing.confidence} /></Row>
        {routing.reason && <Row label="Reason"><span style={{ ...TYPE.caption, color: T.muted }}>{routing.reason}</span></Row>}
      </Panel>

      {/* Memory injection */}
      <Panel color={SEM.purple}>
        <SectionHeader label="Memory Injection" color={SEM.purple} count={`${mem.length} retrieved`} />
        {mem.length === 0 ? (
          <div style={{ ...TYPE.caption, color: T.muted, fontStyle: "italic" }}>No memories retrieved.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {mem.map((m, i) => (
              <div key={i} style={{
                background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 3,
                padding: "7px 11px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                  <ScoreBar value={m.score} width={50} />
                  <span style={{ ...TYPE.micro, color: T.muted }}>{m.agent?.replace(/_/g, " ")}</span>
                  <span style={{ ...TYPE.micro, color: `${SEM.purple}55`, background: `${SEM.purple}11`, borderRadius: 3, padding: "1px 5px" }}>
                    {m.type}
                  </span>
                  <Mono color={T.border} style={{ marginLeft: "auto" }}>#{m.id}</Mono>
                </div>
                <div style={{ ...TYPE.caption, color: T.muted, fontStyle: "italic", lineHeight: 1.4 }}>
                  {m.preview}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* Prompt */}
      <Panel color={T.accent2}>
        <SectionHeader label="Prompt" color={T.accent2} />
        <Row label="Agent"><span style={{ ...TYPE.caption, color: T.text }}>{prompt.agent}</span></Row>
        <Row label="Hash"><Mono color={T.accent2}>{prompt.hash}</Mono></Row>
        <Row label="Tokens"><span style={{ ...TYPE.caption, color: T.text }}>{prompt.token_count?.toLocaleString()}</span></Row>
      </Panel>

      {/* Tools */}
      {(tools.available?.length > 0 || tools.invoked?.length > 0) && (
        <Panel color={SEM.teal}>
          <SectionHeader label="Tools" color={SEM.teal} />
          <Row label="Available">
            {tools.available.map(t => (
              <span key={t} style={{ background: `${SEM.teal}11`, color: SEM.teal, border: `1px solid ${SEM.teal}33`, borderRadius: 4, padding: "1px 7px", ...TYPE.caption, marginRight: 4 }}>{t}</span>
            ))}
          </Row>
          {tools.invoked?.length > 0 && (
            <Row label="Invoked">
              {tools.invoked.map((t, i) => (
                <span key={i} style={{ background: `${T.success}11`, color: T.success, border: `1px solid ${T.success}33`, borderRadius: 4, padding: "1px 7px", ...TYPE.caption, marginRight: 4 }}>{t}</span>
              ))}
            </Row>
          )}
        </Panel>
      )}

      {/* Model */}
      <Panel color={T.muted}>
        <SectionHeader label="Model" color={T.muted} />
        <Row label="Name"><Mono color={T.text}>{model.name}</Mono></Row>
        <Row label="Temp"><Mono color={T.muted}>{model.temperature}</Mono></Row>
        <Row label="Max tokens"><Mono color={T.muted}>{model.max_tokens}</Mono></Row>
        <Row label="Context"><Mono color={T.muted}>{model.context_window?.toLocaleString()}</Mono></Row>
      </Panel>

      {/* Output */}
      <Panel color={SEM.blue}>
        <SectionHeader label="Output" color={SEM.blue} />
        <Row label="Response hash"><Mono color={SEM.blue}>{output.response_hash}</Mono></Row>
        <Row label="Tokens"><span style={{ ...TYPE.caption, color: T.text }}>{output.response_tokens?.toLocaleString()}</span></Row>
      </Panel>

      {/* Evaluation */}
      {hasEval && (
        <Panel color={SEM.magenta}>
          <SectionHeader label="Evaluation" color={SEM.magenta} />
          <Row label="Initial score"><ScoreBar value={evaluation.reflection_score} /></Row>
          <Row label="Final score"><ScoreBar value={evaluation.reflection_score_final} /></Row>
          <Row label="Delta">
            <span style={{
              ...TYPE.caption, fontWeight: 700,
              color: evaluation.reflection_delta > 0 ? T.success : evaluation.reflection_delta < 0 ? T.error : T.muted,
            }}>
              {evaluation.reflection_delta > 0 ? "+" : ""}{evaluation.reflection_delta?.toFixed(3)}
            </span>
          </Row>
        </Panel>
      )}
    </div>
  );
}

// ── Diff view ─────────────────────────────────────────────────

function DiffView({ idA, idB, data: preloaded }) {
  const [diff, setDiff] = useState(preloaded || null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (preloaded) { setDiff(preloaded); return; }
    if (!idA || !idB) return;
    setLoading(true);
    fetch(`${API}/snapshots/diff/${idA}/${idB}`)
      .then(r => r.json())
      .then(d => { setDiff(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [idA, idB, preloaded]);

  if (loading) return <div style={{ padding: 24, color: T.muted, ...TYPE.small }}>Comparing builds…</div>;
  if (!diff || diff.error) return (
    <div style={{ padding: 24, color: T.error, ...TYPE.small }}>{diff?.error || "Diff unavailable"}</div>
  );

  function DiffField({ label, field }) {
    if (!field) return null;
    const changed = field.changed;
    return (
      <div style={{
        display: "flex", alignItems: "flex-start", gap: 8,
        marginBottom: 5, padding: "4px 8px", borderRadius: 3,
        background: changed ? `${T.error}09` : "transparent",
        border: `1px solid ${changed ? `${T.error}33` : "transparent"}`,
      }}>
        <span style={{ ...TYPE.caption, color: T.muted, minWidth: 100, flexShrink: 0 }}>{label}</span>
        {changed ? (
          <span style={{ ...TYPE.caption, display: "flex", gap: 6, alignItems: "center" }}>
            <Mono color={T.error}>{String(field.from)}</Mono>
            <span style={{ color: T.muted }}>→</span>
            <Mono color={T.success}>{String(field.to)}</Mono>
          </span>
        ) : (
          <span style={{ ...TYPE.caption, color: T.muted, fontStyle: "italic" }}>unchanged</span>
        )}
      </div>
    );
  }

  const memChanged = diff.memory?.changed;

  return (
    <div style={{ padding: "18px 20px", overflowY: "auto", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, alignItems: "center" }}>
        <div style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7, padding: "7px 12px", flex: 1 }}>
          <div style={{ ...TYPE.micro, color: T.muted, marginBottom: 2 }}>Build A</div>
          <Mono color={T.accent2}>#{idA}</Mono>
          <div style={{ ...TYPE.micro, color: T.muted, marginTop: 2 }}>{diff.a?.timestamp?.slice(0, 16).replace("T", " ")}</div>
        </div>
        <span style={{ fontSize: 16, color: T.muted }}>⇄</span>
        <div style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7, padding: "7px 12px", flex: 1 }}>
          <div style={{ ...TYPE.micro, color: T.muted, marginBottom: 2 }}>Build B</div>
          <Mono color={T.accent2}>#{idB}</Mono>
          <div style={{ ...TYPE.micro, color: T.muted, marginTop: 2 }}>{diff.b?.timestamp?.slice(0, 16).replace("T", " ")}</div>
        </div>
      </div>

      {/* Routing diff */}
      <Panel color={T.accent}>
        <SectionHeader label="Routing" color={T.accent} />
        <DiffField label="Agent"      field={diff.routing?.agent} />
        <DiffField label="Confidence" field={diff.routing?.confidence} />
        <DiffField label="Action"     field={diff.routing?.action} />
      </Panel>

      {/* Prompt diff */}
      <Panel color={T.accent2}>
        <SectionHeader label="Prompt" color={T.accent2} />
        <DiffField label="Hash"   field={diff.prompt?.hash} />
        <DiffField label="Tokens" field={diff.prompt?.token_count} />
      </Panel>

      {/* Memory diff */}
      <Panel color={SEM.purple}>
        <SectionHeader label="Memory Injection" color={SEM.purple} />
        <div style={{ ...TYPE.caption, marginBottom: 6, color: memChanged ? T.error : T.muted }}>
          A: {diff.memory?.count_a} memories · B: {diff.memory?.count_b} memories
          {memChanged && <span style={{ color: T.error, marginLeft: 6 }}>⚡ changed</span>}
        </div>
        {diff.memory?.added?.length > 0 && (
          <div style={{ ...TYPE.caption, color: T.success, marginBottom: 3 }}>
            + added memory IDs: {diff.memory.added.join(", ")}
          </div>
        )}
        {diff.memory?.removed?.length > 0 && (
          <div style={{ ...TYPE.caption, color: T.error }}>
            − removed memory IDs: {diff.memory.removed.join(", ")}
          </div>
        )}
        {!memChanged && <div style={{ ...TYPE.caption, color: T.muted, fontStyle: "italic" }}>unchanged</div>}
      </Panel>

      {/* Model diff */}
      <Panel color={T.muted}>
        <SectionHeader label="Model" color={T.muted} />
        <DiffField label="Name"        field={diff.model?.name} />
        <DiffField label="Temperature" field={diff.model?.temperature} />
      </Panel>

      {/* Output diff */}
      <Panel color={SEM.blue}>
        <SectionHeader label="Output" color={SEM.blue} />
        <DiffField label="Response hash" field={diff.output?.response_hash} />
        {diff.output?.same_response !== undefined && (
          <div style={{ ...TYPE.caption, marginTop: 4 }}>
            {diff.output.same_response
              ? <span style={{ color: T.success }}>✓ identical response</span>
              : <span style={{ color: T.accent2 }}>⚡ response changed</span>}
          </div>
        )}
      </Panel>
    </div>
  );
}

// ── Fork panel ────────────────────────────────────────────────

function ForkPanel({ snap, running, onRun, onClose }) {
  const [agentOverride,  setAgentOverride]  = useState("");
  const [reflectLevel,   setReflectLevel]   = useState("");
  const [excludedMems,   setExcludedMems]   = useState(new Set());
  const [note,           setNote]           = useState("");

  const mems = snap?.memory?.retrieved || [];

  const toggleMem = id => setExcludedMems(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const handleRun = () => onRun({
    agent_override:      agentOverride  || null,
    exclude_memory_ids:  [...excludedMems],
    force_reflect_level: reflectLevel   || null,
    note,
  });

  const inp = {
    background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 3,
    color: T.text, padding: "5px 9px", ...TYPE.caption, fontFamily: "inherit",
    outline: "none", width: "100%", boxSizing: "border-box",
  };

  return (
    <div style={{
      background: T.surface, borderBottom: `1px solid ${SEM.teal}33`,
      padding: "14px 18px",
    }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 12, gap: 8 }}>
        <span style={{ ...TYPE.caption, fontWeight: 700, color: SEM.teal }}>⑂ Fork & Modify</span>
        <span style={{ ...TYPE.caption, color: T.muted }}>
          — one variable at a time
        </span>
        <button onClick={onClose} style={{
          marginLeft: "auto", background: "transparent", border: "none",
          color: T.muted, cursor: "pointer", ...TYPE.small, fontFamily: "inherit",
        }}>✕</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
        {/* Agent override */}
        <div>
          <label style={{ ...TYPE.micro, color: T.muted, display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
            Agent override
          </label>
          <select value={agentOverride} onChange={e => setAgentOverride(e.target.value)} style={inp}>
            <option value="">— same ({snap?.routing?.agent || "auto"}) —</option>
            {AGENTS.map(a => (
              <option key={a.id} value={a.id}>{a.icon} {a.label}</option>
            ))}
          </select>
        </div>

        {/* Reflect level */}
        <div>
          <label style={{ ...TYPE.micro, color: T.muted, display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
            Reflect level
          </label>
          <select value={reflectLevel} onChange={e => setReflectLevel(e.target.value)} style={inp}>
            <option value="">— auto —</option>
            <option value="none">none</option>
            <option value="light">light</option>
            <option value="full">full</option>
          </select>
        </div>
      </div>

      {/* Memory exclusion */}
      {mems.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <label style={{ ...TYPE.micro, color: T.muted, display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: 1 }}>
            Exclude memories ({excludedMems.size} excluded)
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {mems.map(m => {
              const excl = excludedMems.has(m.id);
              return (
                <div key={m.id} onClick={() => toggleMem(m.id)} style={{
                  display: "flex", alignItems: "center", gap: 8, cursor: "pointer",
                  background: excl ? `${T.error}09` : T.surface2,
                  border: `1px solid ${excl ? `${T.error}44` : T.border}`,
                  borderRadius: 3, padding: "5px 9px",
                }}>
                  <span style={{ ...TYPE.caption, color: excl ? T.error : T.success, fontWeight: 700, minWidth: 12 }}>
                    {excl ? "✕" : "✓"}
                  </span>
                  <ScoreBar value={m.score} width={36} />
                  <span style={{ ...TYPE.micro, color: T.muted, fontFamily: "monospace" }}>#{m.id}</span>
                  <span style={{ ...TYPE.micro, color: excl ? `${T.error}99` : T.muted, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {m.preview}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="Fork label (optional)"
          style={{ ...inp, flex: 1 }}
        />
        <button onClick={handleRun} disabled={running} style={{
          background: running ? T.border : `${SEM.teal}22`,
          border: `1px solid ${running ? T.border : `${SEM.teal}55`}`,
          color: running ? T.muted : SEM.teal,
          borderRadius: 3, padding: "6px 16px", cursor: running ? "not-allowed" : "pointer",
          fontFamily: "inherit", ...TYPE.caption, fontWeight: 700, whiteSpace: "nowrap",
        }}>
          {running ? "Running…" : "▶ Run Fork"}
        </button>
      </div>
    </div>
  );
}

// ── Fork result split view ─────────────────────────────────────

function ForkResultView({ forkData, onClose, onViewFork }) {
  const { original_response_preview, response, diff,
          original_snapshot_id, fork_snapshot_id,
          original_agent, fork_agent, overrides_applied } = forkData;

  const responseChanged = diff?.output?.response_hash?.changed;
  const agentChanged    = diff?.routing?.agent?.changed;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Fork result header */}
      <div style={{
        padding: "8px 18px", background: `${SEM.teal}0A`, borderBottom: `1px solid ${SEM.teal}33`,
        display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
      }}>
        <span style={{ ...TYPE.caption, color: SEM.teal, fontWeight: 700 }}>⑂ Fork result</span>
        <span style={{ ...TYPE.micro, color: T.muted }}>
          #{original_snapshot_id} → #{fork_snapshot_id}
        </span>
        {overrides_applied?.note && (
          <span style={{ ...TYPE.micro, color: T.accent2, background: `${T.accent2}11`, borderRadius: 3, padding: "1px 6px" }}>
            {overrides_applied.note}
          </span>
        )}
        <span style={{ marginLeft: "auto", ...TYPE.caption, fontWeight: 700,
          color: responseChanged ? T.accent2 : T.success }}>
          {responseChanged ? "⚡ response changed" : "✓ identical response"}
        </span>
        <button onClick={onViewFork} title="Open fork snapshot in Inspector" style={{
          background: "transparent", border: `1px solid ${T.border}`,
          borderRadius: 3, color: T.muted, ...TYPE.micro, padding: "2px 8px",
          cursor: "pointer", fontFamily: "inherit",
        }}>open ⊙</button>
        <button onClick={onClose} style={{
          background: "transparent", border: "none",
          color: T.muted, cursor: "pointer", ...TYPE.small, fontFamily: "inherit",
        }}>✕</button>
      </div>

      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {/* Split: original | fork */}
        <div style={{ display: "flex", gap: 0, flex: "0 0 auto", maxHeight: "45%" }}>
          <div style={{
            flex: 1, borderRight: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}`,
            padding: "12px 16px", overflowY: "auto",
          }}>
            <div style={{ ...TYPE.micro, color: T.accent2, fontWeight: 700, marginBottom: 8, display: "flex", gap: 6, alignItems: "center" }}>
              ORIGINAL #{original_snapshot_id}
              {original_agent && <span style={{ color: T.muted, fontWeight: 400 }}>· {original_agent.replace(/_/g, " ")}</span>}
            </div>
            <div style={{ ...TYPE.caption, color: T.text, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
              {original_response_preview || <span style={{ color: T.muted, fontStyle: "italic" }}>preview not available (pre-fork snapshot)</span>}
            </div>
          </div>
          <div style={{
            flex: 1, borderBottom: `1px solid ${T.border}`,
            padding: "12px 16px", overflowY: "auto",
            background: responseChanged ? `${SEM.teal}05` : "transparent",
          }}>
            <div style={{ ...TYPE.micro, color: SEM.teal, fontWeight: 700, marginBottom: 8, display: "flex", gap: 6, alignItems: "center" }}>
              FORK #{fork_snapshot_id}
              {fork_agent && <span style={{ color: T.muted, fontWeight: 400 }}>· {fork_agent.replace(/_/g, " ")}</span>}
              {agentChanged && <span style={{ color: T.accent2, ...TYPE.micro }}>agent changed</span>}
            </div>
            <div style={{ ...TYPE.caption, color: T.text, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
              {response}
            </div>
          </div>
        </div>

        {/* Execution diff */}
        <div style={{ flex: 1, overflowY: "auto", borderTop: `1px solid ${T.border}` }}>
          <DiffView data={diff} />
        </div>
      </div>
    </div>
  );
}

// ── List item ─────────────────────────────────────────────────

function SnapRow({ snap, selected, compareA, compareB, onClick }) {
  const mem      = snap.memory?.retrieved?.length || 0;
  const hasEval  = Object.keys(snap.evaluation || {}).length > 0;
  const agent    = snap.routing?.agent;
  const m        = AGENT_META[agent] || { color: T.muted, icon: "?" };
  const isA      = compareA === snap._snapshot_id;
  const isB      = compareB === snap._snapshot_id;

  let borderColor = T.border;
  if (selected) borderColor = m.color + "88";
  else if (isA) borderColor = `${T.accent2}88`;
  else if (isB) borderColor = `${SEM.teal}88`;

  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? T.surface2 : T.surface2,
        border: `1.5px solid ${borderColor}`,
        borderLeft: `3px solid ${selected ? m.color : isA ? T.accent2 : isB ? SEM.teal : T.border}`,
        borderRadius: 7, padding: "9px 12px", cursor: "pointer",
        transition: "all .1s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <span style={{ ...TYPE.micro, color: T.muted, fontFamily: "monospace" }}>
          {snap.timestamp?.slice(11, 19)}
        </span>
        {agent && <AgentChip id={agent} />}
        {snap.routing?.action && (
          <span style={{ ...TYPE.micro, color: T.muted, background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 3, padding: "1px 5px" }}>
            {snap.routing.action}
          </span>
        )}
        <span style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
          {isA && <span style={{ ...TYPE.micro, color: T.accent2, fontWeight: 700 }}>A</span>}
          {isB && <span style={{ ...TYPE.micro, color: SEM.teal, fontWeight: 700 }}>B</span>}
          {snap.parent_context_id && (
            <span title="Fork" style={{ ...TYPE.micro, color: SEM.teal, fontWeight: 700 }}>⑂</span>
          )}
          <span style={{ ...TYPE.micro, color: T.muted }}>#{snap._snapshot_id}</span>
        </span>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        {snap.routing?.confidence != null && <ScoreBar value={snap.routing.confidence} width={50} />}
        <span style={{ ...TYPE.micro, color: T.muted }}>{mem} mem</span>
        {hasEval && (
          <span style={{ ...TYPE.micro, color: SEM.magenta, background: `${SEM.magenta}11`, border: `1px solid ${SEM.magenta}33`, borderRadius: 3, padding: "1px 5px" }}>
            eval
          </span>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export default function ContextInspectorTab({ contextId }) {
  const [snapshots,   setSnapshots]  = useState([]);
  const [selected,    setSelected]   = useState(null);
  const [compareA,    setCompareA]   = useState(null);
  const [compareB,    setCompareB]   = useState(null);
  const [diffMode,    setDiffMode]   = useState(false);
  const [search,      setSearch]     = useState("");
  const [loading,     setLoading]    = useState(false);
  const [forkOpen,    setForkOpen]   = useState(false);
  const [forkRunning, setForkRunning] = useState(false);
  const [forkResult,  setForkResult]  = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/snapshots?n=100`);
      const d = await r.json();
      setSnapshots(d.snapshots || []);
    } catch { setSnapshots([]); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Auto-select when navigated from ChatTab via context_id
  useEffect(() => {
    if (!contextId) return;
    const existing = snapshots.find(s => s.request_id === contextId);
    if (existing) {
      setSelected(existing);
      setDiffMode(false);
      return;
    }
    fetch(`${API}/snapshots/by-context/${contextId}`)
      .then(r => r.json())
      .then(snap => {
        if (!snap.error) {
          setSelected(snap);
          setDiffMode(false);
          setSnapshots(prev => {
            if (prev.find(s => s._snapshot_id === snap._snapshot_id)) return prev;
            return [snap, ...prev];
          });
        }
      })
      .catch(() => {});
  }, [contextId, snapshots]);

  const handleRowClick = (snap, e) => {
    if (diffMode) {
      if (!compareA) { setCompareA(snap._snapshot_id); return; }
      if (!compareB && snap._snapshot_id !== compareA) { setCompareB(snap._snapshot_id); return; }
    }
    setSelected(s => s?._snapshot_id === snap._snapshot_id ? null : snap);
  };

  const enterDiff = () => {
    setDiffMode(true);
    setForkOpen(false);
    setForkResult(null);
    setCompareA(selected?._snapshot_id || null);
    setCompareB(null);
  };

  const exitDiff = () => {
    setDiffMode(false);
    setCompareA(null);
    setCompareB(null);
  };

  const openFork = () => {
    setForkOpen(true);
    setForkResult(null);
    setDiffMode(false);
  };

  const runFork = useCallback(async (overrides) => {
    if (!selected?.request_id) return;
    setForkRunning(true);
    setForkResult(null);
    try {
      const r = await fetch(`${API}/replay/${selected.request_id}/fork`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(overrides),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        setForkResult({ error: err.detail || `HTTP ${r.status}` });
      } else {
        const data = await r.json();
        setForkResult(data);
        // Refresh snapshot list so the new fork appears
        load();
      }
    } catch (e) {
      setForkResult({ error: String(e) });
    }
    setForkRunning(false);
  }, [selected, load]);

  const runReplay = useCallback(async () => {
    if (!selected?.request_id) return;
    setForkRunning(true);
    setForkResult(null);
    setForkOpen(true);
    try {
      const r = await fetch(`${API}/replay/${selected.request_id}`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        setForkResult({ error: err.detail || `HTTP ${r.status}` });
      } else {
        const data = await r.json();
        setForkResult(data);
        load();
      }
    } catch (e) {
      setForkResult({ error: String(e) });
    }
    setForkRunning(false);
  }, [selected, load]);

  const handleViewFork = useCallback((forkData) => {
    if (!forkData?.fork_context_id) return;
    fetch(`${API}/snapshots/by-context/${forkData.fork_context_id}`)
      .then(r => r.json())
      .then(snap => {
        if (!snap.error) {
          setSelected(snap);
          setForkOpen(false);
          setForkResult(null);
          setSnapshots(prev => {
            if (prev.find(s => s._snapshot_id === snap._snapshot_id)) return prev;
            return [snap, ...prev];
          });
        }
      })
      .catch(() => {});
  }, []);

  const filtered = snapshots.filter(s => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      s.request_id?.toLowerCase().includes(q) ||
      s.routing?.agent?.toLowerCase().includes(q) ||
      s.routing?.action?.toLowerCase().includes(q) ||
      s.input?.query?.toLowerCase().includes(q)
    );
  });

  return (
    <div style={{ display: "flex", height: "100%", gap: 0 }}>

      {/* Left: snapshot list */}
      <div style={{
        width: 320, minWidth: 280, display: "flex", flexDirection: "column",
        background: T.surface, borderRight: `1px solid ${T.border}`,
      }}>
        {/* Toolbar */}
        <div style={{ padding: "12px 14px", borderBottom: `1px solid ${T.border}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ ...TYPE.small, fontWeight: 700, color: T.text }}>Context Inspector</span>
            <span style={{ marginLeft: "auto", ...TYPE.caption, color: T.muted }}>{snapshots.length}</span>
            <button onClick={load} style={{
              background: "transparent", border: `1px solid ${T.border}`, borderRadius: 3,
              color: T.muted, ...TYPE.caption, padding: "2px 8px", cursor: "pointer", fontFamily: "inherit",
            }}>↻</button>
          </div>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search query, agent, action…"
            style={{
              width: "100%", background: T.surface2, border: `1px solid ${T.border}`,
              borderRadius: 3, color: T.text, padding: "5px 10px",
              ...TYPE.caption, fontFamily: "inherit", outline: "none", boxSizing: "border-box",
            }}
          />
        </div>

        {/* Diff mode banner */}
        {diffMode && (
          <div style={{ padding: "8px 14px", background: `${T.accent2}11`, borderBottom: `1px solid ${T.accent2}33`, ...TYPE.caption }}>
            <span style={{ color: T.accent2, fontWeight: 700 }}>Diff mode — </span>
            <span style={{ color: T.muted }}>
              {!compareA ? "click A" : !compareB ? "click B" : `comparing #${compareA} ↔ #${compareB}`}
            </span>
            <button onClick={exitDiff} style={{
              float: "right", background: "transparent", border: "none",
              color: T.muted, cursor: "pointer", ...TYPE.caption, fontFamily: "inherit",
            }}>✕ cancel</button>
          </div>
        )}

        {/* Snapshot rows */}
        <div style={{ overflowY: "auto", flex: 1, padding: "8px 10px", display: "flex", flexDirection: "column", gap: 5 }}>
          {loading && <div style={{ color: T.muted, ...TYPE.caption, padding: 8 }}>Loading…</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ color: T.muted, ...TYPE.caption, padding: 16, textAlign: "center" }}>
              {snapshots.length === 0
                ? "No snapshots yet — send a chat message to generate the first build."
                : "No snapshots match the search."}
            </div>
          )}
          {filtered.map(snap => (
            <SnapRow
              key={snap._snapshot_id}
              snap={snap}
              selected={selected?._snapshot_id === snap._snapshot_id && !diffMode}
              compareA={compareA}
              compareB={compareB}
              onClick={e => handleRowClick(snap, e)}
            />
          ))}
        </div>
      </div>

      {/* Right: detail or diff */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Panel header */}
        <div style={{
          padding: "10px 18px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 10, background: T.surface,
        }}>
          {diffMode && compareA && compareB ? (
            <>
              <span style={{ ...TYPE.caption, fontWeight: 700, color: T.text }}>
                Diff — build <span style={{ color: T.accent2 }}>#{compareA}</span>
                {" "}↔ <span style={{ color: SEM.teal }}>#{compareB}</span>
              </span>
              <button onClick={exitDiff} style={{
                marginLeft: "auto", background: "transparent", border: `1px solid ${T.border}`,
                borderRadius: 3, color: T.muted, ...TYPE.caption, padding: "2px 10px",
                cursor: "pointer", fontFamily: "inherit",
              }}>✕ exit diff</button>
            </>
          ) : selected ? (
            <>
              <span style={{ ...TYPE.caption, fontWeight: 700, color: T.text }}>
                Build <span style={{ color: T.accent2 }}>#{selected._snapshot_id}</span>
              </span>
              <span style={{ ...TYPE.caption, color: T.muted }}>{selected.routing?.agent?.replace(/_/g, " ")}</span>
              {selected.parent_context_id && (
                <span style={{ ...TYPE.micro, color: SEM.teal, background: `${SEM.teal}11`,
                  border: `1px solid ${SEM.teal}33`, borderRadius: 3, padding: "1px 6px" }}>⑂ fork</span>
              )}
              <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                <button onClick={runReplay} disabled={forkRunning} title="Re-run same input (determinism check)" style={{
                  background: "transparent", border: `1px solid ${T.border}`,
                  borderRadius: 3, color: T.muted, ...TYPE.caption, padding: "2px 8px",
                  cursor: forkRunning ? "not-allowed" : "pointer", fontFamily: "inherit",
                }}>↻ Replay</button>
                <button onClick={openFork} style={{
                  background: forkOpen ? `${SEM.teal}22` : "transparent",
                  border: `1px solid ${forkOpen ? `${SEM.teal}55` : T.border}`,
                  borderRadius: 3, color: forkOpen ? SEM.teal : T.muted,
                  ...TYPE.caption, padding: "2px 10px",
                  cursor: "pointer", fontFamily: "inherit", fontWeight: forkOpen ? 700 : 400,
                }}>⑂ Fork</button>
                <button onClick={enterDiff} style={{
                  background: `${T.accent2}11`, border: `1px solid ${T.accent2}44`,
                  borderRadius: 3, color: T.accent2, ...TYPE.caption, padding: "2px 10px",
                  cursor: "pointer", fontFamily: "inherit", fontWeight: 700,
                }}>⇄ Compare</button>
              </span>
            </>
          ) : (
            <span style={{ ...TYPE.caption, color: T.muted }}>
              {diffMode
                ? "Select two builds to compare"
                : "Select a build to inspect"}
            </span>
          )}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {diffMode && compareA && compareB ? (
            <DiffView idA={compareA} idB={compareB} />
          ) : forkResult && !forkResult.error && forkOpen ? (
            <ForkResultView
              forkData={forkResult}
              onClose={() => { setForkResult(null); setForkOpen(false); }}
              onViewFork={() => handleViewFork(forkResult)}
            />
          ) : selected ? (
            <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              {forkOpen && (
                <ForkPanel
                  snap={selected}
                  running={forkRunning}
                  onRun={runFork}
                  onClose={() => { setForkOpen(false); setForkResult(null); }}
                />
              )}
              {forkRunning && (
                <div style={{ padding: "10px 18px", background: `${SEM.teal}0A`, borderBottom: `1px solid ${SEM.teal}33`,
                  ...TYPE.caption, color: SEM.teal, display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>↻</span>
                  Running fork…
                </div>
              )}
              {forkResult?.error && (
                <div style={{ padding: "8px 18px", background: `${T.error}09`, borderBottom: `1px solid ${T.error}33`,
                  ...TYPE.caption, color: T.error }}>
                  Fork error: {forkResult.error}
                </div>
              )}
              <div style={{ flex: 1, overflow: "hidden" }}>
                <SnapshotDetail snap={selected} />
              </div>
            </div>
          ) : (
            <div style={{
              height: "100%", display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", color: T.muted,
            }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>⊙</div>
              <div style={{ ...TYPE.small }}>
                {snapshots.length === 0
                  ? "Send a message to capture the first execution artifact."
                  : "Select a build from the list to inspect its execution context."}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
