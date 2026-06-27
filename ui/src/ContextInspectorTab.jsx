import { useState, useEffect, useCallback } from "react";
import { AGENTS } from "./constants";

import { API } from "./api";

const AGENT_META = Object.fromEntries(
  AGENTS.map(a => [a.id, { icon: a.icon, color: a.color, label: a.label.replace(" Dev", "").replace(" & ", "/") }])
);

// ── Primitive display components ──────────────────────────────

function AgentChip({ id }) {
  const m = AGENT_META[id] || { icon: "?", color: "#9A7A60", label: id };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 9px", borderRadius: 3, fontSize: 11,
      background: m.color + "22", color: m.color,
      border: `1px solid ${m.color}55`, fontWeight: 700, whiteSpace: "nowrap",
    }}>
      {m.icon} {m.label}
    </span>
  );
}

function ScoreBar({ value, width = 80 }) {
  const pct = Math.round((value || 0) * 100);
  const c   = pct >= 70 ? "#15803D" : pct >= 45 ? "#9A6C00" : "#B42318";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width, height: 4, background: "#E0D6C4", borderRadius: 2, overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", width: `${pct}%`, height: "100%", background: c, borderRadius: 2 }} />
      </span>
      <span style={{ fontSize: 11, color: c, fontWeight: 700 }}>{pct}%</span>
    </span>
  );
}

function Mono({ children, color = "#1E5A8A" }) {
  return <span style={{ fontFamily: "monospace", fontSize: 11, color }}>{children}</span>;
}

function SectionHeader({ label, color = "#9A7A60", count }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 700, color, textTransform: "uppercase",
      letterSpacing: 1.2, marginBottom: 8, display: "flex", alignItems: "center", gap: 6,
    }}>
      {label}
      {count != null && (
        <span style={{ fontWeight: 400, color: "#9A7A60", textTransform: "none", letterSpacing: 0 }}>
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
      <span style={{ fontSize: 11, color: "#9A7A60", minWidth: 90, flexShrink: 0, paddingTop: 1 }}>{label}</span>
      <span style={{ fontSize: 12, color: "#2E2010" }}>{children}</span>
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
        background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 4,
        padding: "10px 14px", marginBottom: 18, display: "flex", alignItems: "center", gap: 12,
      }}>
        <span style={{ fontSize: 10, color: "#9A7A60", fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
          Build
        </span>
        <Mono color="#9A6C00">#{snap._snapshot_id}</Mono>
        <span style={{ height: 14, width: 1, background: "#E0D6C4" }} />
        <Mono color="#9A7A60">{(snap.request_id || "").slice(0, 16)}…</Mono>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#9A7A60" }}>
          {snap.timestamp?.slice(0, 19).replace("T", " ")} UTC
        </span>
      </div>

      {/* Input */}
      <Panel color="#0F766E">
        <SectionHeader label="Input" color="#0F766E" />
        <Row label="Query">
          <span style={{ fontStyle: "italic", color: "#2E2010", lineHeight: 1.5 }}>
            "{(input.query || "").slice(0, 200)}"
          </span>
        </Row>
        {input.normalized_query && (
          <Row label="Normalized"><Mono>{input.normalized_query}</Mono></Row>
        )}
      </Panel>

      {/* Routing */}
      <Panel color="#C48808">
        <SectionHeader label="Routing" color="#C48808" />
        <Row label="Agent"><AgentChip id={routing.agent} /></Row>
        <Row label="Action">
          <Mono color="#1E5A8A">{routing.action}</Mono>
          <span style={{ color: "#9A7A60", fontSize: 11, marginLeft: 8 }}>{routing.complexity}</span>
        </Row>
        <Row label="Confidence"><ScoreBar value={routing.confidence} /></Row>
        {routing.reason && <Row label="Reason"><span style={{ fontSize: 11, color: "#9A7A60" }}>{routing.reason}</span></Row>}
      </Panel>

      {/* Memory injection */}
      <Panel color="#7E3F8F">
        <SectionHeader label="Memory Injection" color="#7E3F8F" count={`${mem.length} retrieved`} />
        {mem.length === 0 ? (
          <div style={{ fontSize: 12, color: "#9A7A60", fontStyle: "italic" }}>No memories retrieved.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {mem.map((m, i) => (
              <div key={i} style={{
                background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 3,
                padding: "7px 11px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                  <ScoreBar value={m.score} width={50} />
                  <span style={{ fontSize: 10, color: "#9A7A60" }}>{m.agent?.replace(/_/g, " ")}</span>
                  <span style={{ fontSize: 10, color: "#7E3F8F55", background: "#7E3F8F11", borderRadius: 3, padding: "1px 5px" }}>
                    {m.type}
                  </span>
                  <Mono color="#E0D6C4" style={{ marginLeft: "auto" }}>#{m.id}</Mono>
                </div>
                <div style={{ fontSize: 11, color: "#9A7A60", fontStyle: "italic", lineHeight: 1.4 }}>
                  {m.preview}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* Prompt */}
      <Panel color="#9A6C00">
        <SectionHeader label="Prompt" color="#9A6C00" />
        <Row label="Agent"><span style={{ fontSize: 12, color: "#2E2010" }}>{prompt.agent}</span></Row>
        <Row label="Hash"><Mono color="#9A6C00">{prompt.hash}</Mono></Row>
        <Row label="Tokens"><span style={{ fontSize: 12, color: "#2E2010" }}>{prompt.token_count?.toLocaleString()}</span></Row>
      </Panel>

      {/* Tools */}
      {(tools.available?.length > 0 || tools.invoked?.length > 0) && (
        <Panel color="#0F766E">
          <SectionHeader label="Tools" color="#0F766E" />
          <Row label="Available">
            {tools.available.map(t => (
              <span key={t} style={{ background: "#0F766E11", color: "#0F766E", border: "1px solid #0F766E33", borderRadius: 4, padding: "1px 7px", fontSize: 11, marginRight: 4 }}>{t}</span>
            ))}
          </Row>
          {tools.invoked?.length > 0 && (
            <Row label="Invoked">
              {tools.invoked.map((t, i) => (
                <span key={i} style={{ background: "#15803D11", color: "#15803D", border: "1px solid #15803D33", borderRadius: 4, padding: "1px 7px", fontSize: 11, marginRight: 4 }}>{t}</span>
              ))}
            </Row>
          )}
        </Panel>
      )}

      {/* Model */}
      <Panel color="#9A7A60">
        <SectionHeader label="Model" color="#9A7A60" />
        <Row label="Name"><Mono color="#2E2010">{model.name}</Mono></Row>
        <Row label="Temp"><Mono color="#9A7A60">{model.temperature}</Mono></Row>
        <Row label="Max tokens"><Mono color="#9A7A60">{model.max_tokens}</Mono></Row>
        <Row label="Context"><Mono color="#9A7A60">{model.context_window?.toLocaleString()}</Mono></Row>
      </Panel>

      {/* Output */}
      <Panel color="#1E5A8A">
        <SectionHeader label="Output" color="#1E5A8A" />
        <Row label="Response hash"><Mono color="#1E5A8A">{output.response_hash}</Mono></Row>
        <Row label="Tokens"><span style={{ fontSize: 12, color: "#2E2010" }}>{output.response_tokens?.toLocaleString()}</span></Row>
      </Panel>

      {/* Evaluation */}
      {hasEval && (
        <Panel color="#BE185D">
          <SectionHeader label="Evaluation" color="#BE185D" />
          <Row label="Initial score"><ScoreBar value={evaluation.reflection_score} /></Row>
          <Row label="Final score"><ScoreBar value={evaluation.reflection_score_final} /></Row>
          <Row label="Delta">
            <span style={{
              fontSize: 12, fontWeight: 700,
              color: evaluation.reflection_delta > 0 ? "#15803D" : evaluation.reflection_delta < 0 ? "#B42318" : "#9A7A60",
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

  if (loading) return <div style={{ padding: 24, color: "#9A7A60", fontSize: 13 }}>Comparing builds…</div>;
  if (!diff || diff.error) return (
    <div style={{ padding: 24, color: "#B42318", fontSize: 13 }}>{diff?.error || "Diff unavailable"}</div>
  );

  function DiffField({ label, field }) {
    if (!field) return null;
    const changed = field.changed;
    return (
      <div style={{
        display: "flex", alignItems: "flex-start", gap: 8,
        marginBottom: 5, padding: "4px 8px", borderRadius: 3,
        background: changed ? "#B4231809" : "transparent",
        border: `1px solid ${changed ? "#B4231833" : "transparent"}`,
      }}>
        <span style={{ fontSize: 11, color: "#9A7A60", minWidth: 100, flexShrink: 0 }}>{label}</span>
        {changed ? (
          <span style={{ fontSize: 11, display: "flex", gap: 6, alignItems: "center" }}>
            <Mono color="#B42318">{String(field.from)}</Mono>
            <span style={{ color: "#9A7A60" }}>→</span>
            <Mono color="#15803D">{String(field.to)}</Mono>
          </span>
        ) : (
          <span style={{ fontSize: 11, color: "#9A7A60", fontStyle: "italic" }}>unchanged</span>
        )}
      </div>
    );
  }

  const memChanged = diff.memory?.changed;

  return (
    <div style={{ padding: "18px 20px", overflowY: "auto", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, alignItems: "center" }}>
        <div style={{ background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 7, padding: "7px 12px", flex: 1 }}>
          <div style={{ fontSize: 10, color: "#9A7A60", marginBottom: 2 }}>Build A</div>
          <Mono color="#9A6C00">#{idA}</Mono>
          <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 2 }}>{diff.a?.timestamp?.slice(0, 16).replace("T", " ")}</div>
        </div>
        <span style={{ fontSize: 16, color: "#9A7A60" }}>⇄</span>
        <div style={{ background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 7, padding: "7px 12px", flex: 1 }}>
          <div style={{ fontSize: 10, color: "#9A7A60", marginBottom: 2 }}>Build B</div>
          <Mono color="#9A6C00">#{idB}</Mono>
          <div style={{ fontSize: 10, color: "#9A7A60", marginTop: 2 }}>{diff.b?.timestamp?.slice(0, 16).replace("T", " ")}</div>
        </div>
      </div>

      {/* Routing diff */}
      <Panel color="#C48808">
        <SectionHeader label="Routing" color="#C48808" />
        <DiffField label="Agent"      field={diff.routing?.agent} />
        <DiffField label="Confidence" field={diff.routing?.confidence} />
        <DiffField label="Action"     field={diff.routing?.action} />
      </Panel>

      {/* Prompt diff */}
      <Panel color="#9A6C00">
        <SectionHeader label="Prompt" color="#9A6C00" />
        <DiffField label="Hash"   field={diff.prompt?.hash} />
        <DiffField label="Tokens" field={diff.prompt?.token_count} />
      </Panel>

      {/* Memory diff */}
      <Panel color="#7E3F8F">
        <SectionHeader label="Memory Injection" color="#7E3F8F" />
        <div style={{ fontSize: 11, marginBottom: 6, color: memChanged ? "#B42318" : "#9A7A60" }}>
          A: {diff.memory?.count_a} memories · B: {diff.memory?.count_b} memories
          {memChanged && <span style={{ color: "#B42318", marginLeft: 6 }}>⚡ changed</span>}
        </div>
        {diff.memory?.added?.length > 0 && (
          <div style={{ fontSize: 11, color: "#15803D", marginBottom: 3 }}>
            + added memory IDs: {diff.memory.added.join(", ")}
          </div>
        )}
        {diff.memory?.removed?.length > 0 && (
          <div style={{ fontSize: 11, color: "#B42318" }}>
            − removed memory IDs: {diff.memory.removed.join(", ")}
          </div>
        )}
        {!memChanged && <div style={{ fontSize: 11, color: "#9A7A60", fontStyle: "italic" }}>unchanged</div>}
      </Panel>

      {/* Model diff */}
      <Panel color="#9A7A60">
        <SectionHeader label="Model" color="#9A7A60" />
        <DiffField label="Name"        field={diff.model?.name} />
        <DiffField label="Temperature" field={diff.model?.temperature} />
      </Panel>

      {/* Output diff */}
      <Panel color="#1E5A8A">
        <SectionHeader label="Output" color="#1E5A8A" />
        <DiffField label="Response hash" field={diff.output?.response_hash} />
        {diff.output?.same_response !== undefined && (
          <div style={{ fontSize: 11, marginTop: 4 }}>
            {diff.output.same_response
              ? <span style={{ color: "#15803D" }}>✓ identical response</span>
              : <span style={{ color: "#9A6C00" }}>⚡ response changed</span>}
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
    background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 3,
    color: "#2E2010", padding: "5px 9px", fontSize: 11, fontFamily: "inherit",
    outline: "none", width: "100%", boxSizing: "border-box",
  };

  return (
    <div style={{
      background: "#F7F3EC", borderBottom: "1px solid #0F766E33",
      padding: "14px 18px",
    }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 12, gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#0F766E" }}>⑂ Fork & Modify</span>
        <span style={{ fontSize: 11, color: "#9A7A60" }}>
          — one variable at a time
        </span>
        <button onClick={onClose} style={{
          marginLeft: "auto", background: "transparent", border: "none",
          color: "#9A7A60", cursor: "pointer", fontSize: 13, fontFamily: "inherit",
        }}>✕</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
        {/* Agent override */}
        <div>
          <label style={{ fontSize: 10, color: "#9A7A60", display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
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
          <label style={{ fontSize: 10, color: "#9A7A60", display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
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
          <label style={{ fontSize: 10, color: "#9A7A60", display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: 1 }}>
            Exclude memories ({excludedMems.size} excluded)
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {mems.map(m => {
              const excl = excludedMems.has(m.id);
              return (
                <div key={m.id} onClick={() => toggleMem(m.id)} style={{
                  display: "flex", alignItems: "center", gap: 8, cursor: "pointer",
                  background: excl ? "#B4231809" : "#F4F0E8",
                  border: `1px solid ${excl ? "#B4231844" : "#E0D6C4"}`,
                  borderRadius: 3, padding: "5px 9px",
                }}>
                  <span style={{ fontSize: 11, color: excl ? "#B42318" : "#15803D", fontWeight: 700, minWidth: 12 }}>
                    {excl ? "✕" : "✓"}
                  </span>
                  <ScoreBar value={m.score} width={36} />
                  <span style={{ fontSize: 10, color: "#9A7A60", fontFamily: "monospace" }}>#{m.id}</span>
                  <span style={{ fontSize: 10, color: excl ? "#B4231899" : "#9A7A60", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
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
          background: running ? "#E0D6C4" : "#0F766E22",
          border: `1px solid ${running ? "#E0D6C4" : "#0F766E55"}`,
          color: running ? "#9A7A60" : "#0F766E",
          borderRadius: 3, padding: "6px 16px", cursor: running ? "not-allowed" : "pointer",
          fontFamily: "inherit", fontSize: 12, fontWeight: 700, whiteSpace: "nowrap",
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
        padding: "8px 18px", background: "#0F766E0A", borderBottom: "1px solid #0F766E33",
        display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
      }}>
        <span style={{ fontSize: 11, color: "#0F766E", fontWeight: 700 }}>⑂ Fork result</span>
        <span style={{ fontSize: 10, color: "#9A7A60" }}>
          #{original_snapshot_id} → #{fork_snapshot_id}
        </span>
        {overrides_applied?.note && (
          <span style={{ fontSize: 10, color: "#9A6C00", background: "#9A6C0011", borderRadius: 3, padding: "1px 6px" }}>
            {overrides_applied.note}
          </span>
        )}
        <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 700,
          color: responseChanged ? "#9A6C00" : "#15803D" }}>
          {responseChanged ? "⚡ response changed" : "✓ identical response"}
        </span>
        <button onClick={onViewFork} title="Open fork snapshot in Inspector" style={{
          background: "transparent", border: "1px solid #E0D6C4",
          borderRadius: 3, color: "#9A7A60", fontSize: 10, padding: "2px 8px",
          cursor: "pointer", fontFamily: "inherit",
        }}>open ⊙</button>
        <button onClick={onClose} style={{
          background: "transparent", border: "none",
          color: "#9A7A60", cursor: "pointer", fontSize: 13, fontFamily: "inherit",
        }}>✕</button>
      </div>

      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {/* Split: original | fork */}
        <div style={{ display: "flex", gap: 0, flex: "0 0 auto", maxHeight: "45%" }}>
          <div style={{
            flex: 1, borderRight: "1px solid #E0D6C4", borderBottom: "1px solid #E0D6C4",
            padding: "12px 16px", overflowY: "auto",
          }}>
            <div style={{ fontSize: 10, color: "#9A6C00", fontWeight: 700, marginBottom: 8, display: "flex", gap: 6, alignItems: "center" }}>
              ORIGINAL #{original_snapshot_id}
              {original_agent && <span style={{ color: "#9A7A60", fontWeight: 400 }}>· {original_agent.replace(/_/g, " ")}</span>}
            </div>
            <div style={{ fontSize: 12, color: "#2E2010", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
              {original_response_preview || <span style={{ color: "#9A7A60", fontStyle: "italic" }}>preview not available (pre-fork snapshot)</span>}
            </div>
          </div>
          <div style={{
            flex: 1, borderBottom: "1px solid #E0D6C4",
            padding: "12px 16px", overflowY: "auto",
            background: responseChanged ? "#0F766E05" : "transparent",
          }}>
            <div style={{ fontSize: 10, color: "#0F766E", fontWeight: 700, marginBottom: 8, display: "flex", gap: 6, alignItems: "center" }}>
              FORK #{fork_snapshot_id}
              {fork_agent && <span style={{ color: "#9A7A60", fontWeight: 400 }}>· {fork_agent.replace(/_/g, " ")}</span>}
              {agentChanged && <span style={{ color: "#9A6C00", fontSize: 9 }}>agent changed</span>}
            </div>
            <div style={{ fontSize: 12, color: "#2E2010", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
              {response}
            </div>
          </div>
        </div>

        {/* Execution diff */}
        <div style={{ flex: 1, overflowY: "auto", borderTop: "1px solid #E0D6C4" }}>
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
  const m        = AGENT_META[agent] || { color: "#9A7A60", icon: "?" };
  const isA      = compareA === snap._snapshot_id;
  const isB      = compareB === snap._snapshot_id;

  let borderColor = "#E0D6C4";
  if (selected) borderColor = m.color + "88";
  else if (isA) borderColor = "#9A6C0088";
  else if (isB) borderColor = "#0F766E88";

  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? "#F4F0E8" : "#F4F0E8",
        border: `1.5px solid ${borderColor}`,
        borderLeft: `3px solid ${selected ? m.color : isA ? "#9A6C00" : isB ? "#0F766E" : "#E0D6C4"}`,
        borderRadius: 7, padding: "9px 12px", cursor: "pointer",
        transition: "all .1s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 10, color: "#9A7A60", fontFamily: "monospace" }}>
          {snap.timestamp?.slice(11, 19)}
        </span>
        {agent && <AgentChip id={agent} />}
        {snap.routing?.action && (
          <span style={{ fontSize: 10, color: "#9A7A60", background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 3, padding: "1px 5px" }}>
            {snap.routing.action}
          </span>
        )}
        <span style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
          {isA && <span style={{ fontSize: 9, color: "#9A6C00", fontWeight: 700 }}>A</span>}
          {isB && <span style={{ fontSize: 9, color: "#0F766E", fontWeight: 700 }}>B</span>}
          {snap.parent_context_id && (
            <span title="Fork" style={{ fontSize: 9, color: "#0F766E", fontWeight: 700 }}>⑂</span>
          )}
          <span style={{ fontSize: 10, color: "#9A7A60" }}>#{snap._snapshot_id}</span>
        </span>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        {snap.routing?.confidence != null && <ScoreBar value={snap.routing.confidence} width={50} />}
        <span style={{ fontSize: 10, color: "#9A7A60" }}>{mem} mem</span>
        {hasEval && (
          <span style={{ fontSize: 10, color: "#BE185D", background: "#BE185D11", border: "1px solid #BE185D33", borderRadius: 3, padding: "1px 5px" }}>
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
        background: "#FAF7F2", borderRight: "1px solid #E0D6C4",
      }}>
        {/* Toolbar */}
        <div style={{ padding: "12px 14px", borderBottom: "1px solid #E0D6C4" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#2E2010" }}>Context Inspector</span>
            <span style={{ marginLeft: "auto", fontSize: 11, color: "#9A7A60" }}>{snapshots.length}</span>
            <button onClick={load} style={{
              background: "transparent", border: "1px solid #E0D6C4", borderRadius: 3,
              color: "#9A7A60", fontSize: 11, padding: "2px 8px", cursor: "pointer", fontFamily: "inherit",
            }}>↻</button>
          </div>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search query, agent, action…"
            style={{
              width: "100%", background: "#F4F0E8", border: "1px solid #E0D6C4",
              borderRadius: 3, color: "#2E2010", padding: "5px 10px",
              fontSize: 11, fontFamily: "inherit", outline: "none", boxSizing: "border-box",
            }}
          />
        </div>

        {/* Diff mode banner */}
        {diffMode && (
          <div style={{ padding: "8px 14px", background: "#9A6C0011", borderBottom: "1px solid #9A6C0033", fontSize: 11 }}>
            <span style={{ color: "#9A6C00", fontWeight: 700 }}>Diff mode — </span>
            <span style={{ color: "#9A7A60" }}>
              {!compareA ? "click A" : !compareB ? "click B" : `comparing #${compareA} ↔ #${compareB}`}
            </span>
            <button onClick={exitDiff} style={{
              float: "right", background: "transparent", border: "none",
              color: "#9A7A60", cursor: "pointer", fontSize: 11, fontFamily: "inherit",
            }}>✕ cancel</button>
          </div>
        )}

        {/* Snapshot rows */}
        <div style={{ overflowY: "auto", flex: 1, padding: "8px 10px", display: "flex", flexDirection: "column", gap: 5 }}>
          {loading && <div style={{ color: "#9A7A60", fontSize: 12, padding: 8 }}>Loading…</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ color: "#9A7A60", fontSize: 12, padding: 16, textAlign: "center" }}>
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
          padding: "10px 18px", borderBottom: "1px solid #E0D6C4",
          display: "flex", alignItems: "center", gap: 10, background: "#FAF7F2",
        }}>
          {diffMode && compareA && compareB ? (
            <>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#2E2010" }}>
                Diff — build <span style={{ color: "#9A6C00" }}>#{compareA}</span>
                {" "}↔ <span style={{ color: "#0F766E" }}>#{compareB}</span>
              </span>
              <button onClick={exitDiff} style={{
                marginLeft: "auto", background: "transparent", border: "1px solid #E0D6C4",
                borderRadius: 3, color: "#9A7A60", fontSize: 11, padding: "2px 10px",
                cursor: "pointer", fontFamily: "inherit",
              }}>✕ exit diff</button>
            </>
          ) : selected ? (
            <>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#2E2010" }}>
                Build <span style={{ color: "#9A6C00" }}>#{selected._snapshot_id}</span>
              </span>
              <span style={{ fontSize: 11, color: "#9A7A60" }}>{selected.routing?.agent?.replace(/_/g, " ")}</span>
              {selected.parent_context_id && (
                <span style={{ fontSize: 10, color: "#0F766E", background: "#0F766E11",
                  border: "1px solid #0F766E33", borderRadius: 3, padding: "1px 6px" }}>⑂ fork</span>
              )}
              <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                <button onClick={runReplay} disabled={forkRunning} title="Re-run same input (determinism check)" style={{
                  background: "transparent", border: "1px solid #E0D6C4",
                  borderRadius: 3, color: "#9A7A60", fontSize: 11, padding: "2px 8px",
                  cursor: forkRunning ? "not-allowed" : "pointer", fontFamily: "inherit",
                }}>↻ Replay</button>
                <button onClick={openFork} style={{
                  background: forkOpen ? "#0F766E22" : "transparent",
                  border: `1px solid ${forkOpen ? "#0F766E55" : "#E0D6C4"}`,
                  borderRadius: 3, color: forkOpen ? "#0F766E" : "#9A7A60",
                  fontSize: 11, padding: "2px 10px",
                  cursor: "pointer", fontFamily: "inherit", fontWeight: forkOpen ? 700 : 400,
                }}>⑂ Fork</button>
                <button onClick={enterDiff} style={{
                  background: "#9A6C0011", border: "1px solid #9A6C0044",
                  borderRadius: 3, color: "#9A6C00", fontSize: 11, padding: "2px 10px",
                  cursor: "pointer", fontFamily: "inherit", fontWeight: 700,
                }}>⇄ Compare</button>
              </span>
            </>
          ) : (
            <span style={{ fontSize: 12, color: "#9A7A60" }}>
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
                <div style={{ padding: "10px 18px", background: "#0F766E0A", borderBottom: "1px solid #0F766E33",
                  fontSize: 12, color: "#0F766E", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>↻</span>
                  Running fork…
                </div>
              )}
              {forkResult?.error && (
                <div style={{ padding: "8px 18px", background: "#B4231809", borderBottom: "1px solid #B4231833",
                  fontSize: 12, color: "#B42318" }}>
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
              alignItems: "center", justifyContent: "center", color: "#9A7A60",
            }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>⊙</div>
              <div style={{ fontSize: 13 }}>
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
