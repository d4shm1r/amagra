import { useState, useEffect, useCallback } from "react";
import { AGENTS as AGENTS_LIST } from "@/config/constants";
import { T, GOLD, LUX, TYPE, EASE, DUR, FONT_DISPLAY, FONT_MONO } from "@/styles/theme";
import { PageHeader, MetricCard } from "@/components/ui";

import { API } from "@/lib/api";

// Keyed by id for O(1) lookup; label shortened for chip display
const AGENTS = Object.fromEntries(
  AGENTS_LIST.map(a => [a.id, { icon: a.icon, color: a.color, label: a.label.split(" ")[0] }])
);

// Status colours are semantic (status is meaning, not decoration); everything
// else in this tab runs on the gold/cream token system.
const TEAL = "#0F766E";
const STATUS = {
  pending:   { color: T.muted,   label: "pending",   dot: "○" },
  running:   { color: T.accent2, label: "running…",  dot: "●" },
  completed: { color: T.success, label: "done",      dot: "✓" },
  failed:    { color: T.error,   label: "failed",    dot: "✗" },
  paused:    { color: TEAL,      label: "paused",    dot: "⏸" },
};

function StatusBadge({ status, small = false }) {
  const s = STATUS[status] || STATUS.pending;
  return (
    <span style={{
      ...TYPE.micro, fontWeight: 700, letterSpacing: "0.02em",
      padding: small ? "2px 8px" : "3px 11px", borderRadius: 99,
      background: s.color + "16", color: s.color,
      border: `1px solid ${s.color}44`,
    }}>
      {s.dot} {s.label}
    </span>
  );
}

function AgentChip({ id }) {
  const a = AGENTS[id] || { icon: "?", color: T.muted, label: id };
  return (
    <span style={{
      ...TYPE.micro, fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 9px", borderRadius: 99,
      background: a.color + "16", color: a.color, border: `1px solid ${a.color}3a`,
    }}>
      {a.icon} {a.label}
    </span>
  );
}

function ProgressBar({ steps }) {
  if (!steps || steps.length === 0) return null;
  const done   = steps.filter(s => s.status === "completed").length;
  const failed = steps.filter(s => s.status === "failed").length;
  const total  = steps.length;
  const donePct   = Math.round((done   / total) * 100);
  const failedPct = Math.round((failed / total) * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
      <div style={{ flex: 1, height: 6, background: T.surface2, borderRadius: 99, overflow: "hidden", display: "flex" }}>
        <div style={{ width: `${donePct}%`,   height: "100%", background: T.success, transition: `width ${DUR.slow} ${EASE.out}` }} />
        <div style={{ width: `${failedPct}%`, height: "100%", background: T.error,   transition: `width ${DUR.slow} ${EASE.out}` }} />
      </div>
      <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
        {done}/{total}
      </span>
    </div>
  );
}

// Small pill action button — tinted by intent, consistent across the tab.
function PillBtn({ onClick, color = T.muted, children }) {
  return (
    <button onClick={onClick} style={{
      ...TYPE.caption, fontWeight: 700, padding: "3px 12px", borderRadius: 99,
      background: color + "14", color, border: `1px solid ${color}44`,
      cursor: "pointer", fontFamily: "inherit",
    }}>{children}</button>
  );
}

function StepCard({ step, onRetry, graphStatus }) {
  const [expanded, setExpanded] = useState(false);
  const s = STATUS[step.status] || STATUS.pending;

  return (
    <div style={{
      background: T.surface2,
      border: `1px solid ${s.color}26`,
      borderLeft: `3px solid ${s.color}`,
      borderRadius: 9, marginBottom: 7, overflow: "hidden",
    }}>
      {/* Step header */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 13px", cursor: "pointer" }}
        onClick={() => setExpanded(e => !e)}
      >
        <span style={{ fontSize: 13, color: s.color, fontWeight: 800, minWidth: 16 }}>{s.dot}</span>
        <span style={{ ...TYPE.caption, color: T.text, fontWeight: 700, flex: 1 }}>
          {step.step_id}
        </span>
        <AgentChip id={step.agent} />
        {step.output_data?.duration_ms && (
          <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted, fontVariantNumeric: "tabular-nums" }}>{step.output_data.duration_ms}ms</span>
        )}
        {step.status === "failed" && onRetry && graphStatus !== "running" && (
          <PillBtn onClick={e => { e.stopPropagation(); onRetry(step.step_id); }} color={T.error}>↺ retry</PillBtn>
        )}
        <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted }}>{expanded ? "▲" : "▼"}</span>
      </div>

      {expanded && (
        <div style={{ borderTop: `1px solid ${T.border}`, padding: "11px 13px" }}>
          {/* Prompt */}
          <div style={{ marginBottom: 10 }}>
            <Label>Task</Label>
            <div style={{ ...TYPE.caption, color: T.text, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "7px 11px", lineHeight: 1.55 }}>
              {step.prompt}
            </div>
          </div>

          {/* Dependencies */}
          {step.depends_on && step.depends_on.length > 0 && (
            <div style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted }}>depends on:</span>
              {step.depends_on.map(d => (
                <span key={d} style={{ ...TYPE.micro, fontWeight: 400, color: TEAL, background: TEAL + "16", padding: "1px 8px", borderRadius: 99, border: `1px solid ${TEAL}33` }}>{d}</span>
              ))}
            </div>
          )}

          {/* Output */}
          {step.output_data?.response && (
            <div style={{ marginBottom: 10 }}>
              <Label color={T.success}>Output</Label>
              <div style={{
                ...TYPE.caption, color: T.text, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8,
                padding: "8px 11px", maxHeight: 200, overflowY: "auto",
                lineHeight: 1.6, fontFamily: FONT_MONO, whiteSpace: "pre-wrap",
              }}>
                {step.output_data.response.slice(0, 1000)}
                {step.output_data.response.length > 1000 && "\n…(truncated)"}
              </div>
            </div>
          )}

          {/* Error */}
          {step.error && (
            <div style={{ ...TYPE.caption, padding: "7px 11px", background: `${T.error}12`, border: `1px solid ${T.error}44`, borderRadius: 8, color: T.error }}>
              {step.error}
            </div>
          )}

          {/* Attempt count */}
          {step.attempt > 1 && (
            <div style={{ ...TYPE.micro, fontWeight: 400, marginTop: 7, color: T.muted }}>attempt #{step.attempt}</div>
          )}
        </div>
      )}
    </div>
  );
}

function GoalCard({ goal, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const [detail,   setDetail]   = useState(null);
  const [, setRetrying] = useState(false);

  const gs = STATUS[goal.status] || STATUS.pending;

  const loadDetail = useCallback(async () => {
    try {
      const r = await fetch(`${API}/goals/${goal.id}`);
      setDetail(await r.json());
    } catch { setDetail(null); }
  }, [goal.id]);

  useEffect(() => {
    if (expanded) {
      loadDetail();
      // Poll while running
      if (goal.status === "running") {
        const t = setInterval(loadDetail, 6000);
        return () => clearInterval(t);
      }
    }
  }, [expanded, goal.status, loadDetail]);

  const handleRun = async () => {
    await fetch(`${API}/goals/${goal.id}/run`, { method: "POST" });
    onRefresh();
  };

  const handleRetry = async (stepId) => {
    setRetrying(true);
    await fetch(`${API}/goals/${goal.id}/retry/${stepId}`, { method: "POST" });
    await loadDetail();
    onRefresh();
    setRetrying(false);
  };

  const handleDelete = async () => {
    if (!window.confirm("Delete this goal?")) return;
    await fetch(`${API}/goals/${goal.id}`, { method: "DELETE" });
    onRefresh();
  };

  const stepsData  = detail?.steps || [];
  const totalSteps = goal.total_steps || 0;

  return (
    <div className="lux-card" style={{ marginBottom: 12, overflow: "hidden", borderLeft: `4px solid ${gs.color}`, padding: 0 }}>
      {/* Header */}
      <div style={{ padding: "14px 17px", cursor: "pointer" }} onClick={() => setExpanded(e => !e)}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 9 }}>
          <span style={{ ...TYPE.body, fontWeight: 700, color: T.text, flex: 1, lineHeight: 1.35 }}>
            {goal.goal.slice(0, 90)}{goal.goal.length > 90 ? "…" : ""}
          </span>
          <StatusBadge status={goal.status} />
          <span style={{ ...TYPE.caption, color: T.muted, fontVariantNumeric: "tabular-nums" }}>#{goal.id}</span>
        </div>

        {/* Progress */}
        {totalSteps > 0 && (
          <ProgressBar steps={
            Object.entries(goal.step_counts || {}).flatMap(([st, n]) =>
              Array.from({ length: n }, () => ({ status: st }))
            )
          } />
        )}

        {/* Footer row */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 9 }}>
          <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted }}>
            {totalSteps} step{totalSteps !== 1 ? "s" : ""}
          </span>
          {goal.created_at && (
            <span style={{ ...TYPE.micro, fontWeight: 400, color: T.muted }}>
              created {goal.created_at?.slice(0, 10)}
            </span>
          )}

          <span style={{ marginLeft: "auto", display: "flex", gap: 7 }}>
            {(goal.status === "pending" || goal.status === "paused") && (
              <PillBtn onClick={e => { e.stopPropagation(); handleRun(); }} color={T.success}>▶ run</PillBtn>
            )}
            {goal.status !== "running" && (
              <PillBtn onClick={e => { e.stopPropagation(); handleDelete(); }} color={T.muted}>✕</PillBtn>
            )}
          </span>
        </div>
      </div>

      {/* Expanded steps */}
      {expanded && (
        <div style={{ borderTop: `1px solid ${T.border}`, padding: "13px 15px", background: LUX.hover }}>
          {stepsData.length === 0 ? (
            <div style={{ ...TYPE.caption, color: T.muted, textAlign: "center", padding: "10px 0" }}>
              Loading steps…
            </div>
          ) : (
            stepsData.map(step => (
              <StepCard key={step.step_id} step={step} onRetry={handleRetry} graphStatus={goal.status} />
            ))
          )}
        </div>
      )}
    </div>
  );
}

function CreateGoalForm({ onCreated }) {
  const [goal,   setGoal]   = useState("");
  const [steps,  setSteps]  = useState([
    { id: "", agent: "python_dev", prompt: "", depends_on: [] },
  ]);
  const [error,  setError]  = useState("");
  const [saving, setSaving] = useState(false);

  const agentOptions = Object.entries(AGENTS).map(([id, a]) => (
    <option key={id} value={id}>{a.icon} {a.label}</option>
  ));

  const addStep    = () => setSteps(s => [...s, { id: "", agent: "python_dev", prompt: "", depends_on: [] }]);
  const removeStep = i => setSteps(s => s.filter((_, idx) => idx !== i));
  const updateStep = (i, field, value) =>
    setSteps(s => s.map((step, idx) => idx === i ? { ...step, [field]: value } : step));

  const handleSubmit = async () => {
    setError("");
    if (!goal.trim()) { setError("Goal is required"); return; }
    for (const [i, s] of steps.entries()) {
      if (!s.id.trim())     { setError(`Step ${i + 1}: ID is required`); return; }
      if (!s.prompt.trim()) { setError(`Step ${i + 1}: prompt is required`); return; }
    }
    setSaving(true);
    try {
      const r = await fetch(`${API}/goals/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: goal.trim(),
          steps: steps.map(s => ({
            id:         s.id.trim(),
            agent:      s.agent,
            prompt:     s.prompt.trim(),
            depends_on: s.depends_on,
          })),
        }),
      });
      const d = await r.json();
      if (!r.ok) { setError(d.detail || "Error creating goal"); return; }
      setGoal(""); setSteps([{ id: "", agent: "python_dev", prompt: "", depends_on: [] }]);
      onCreated(d.goal_id);
    } catch (e) {
      setError("Network error — is the server running?");
    } finally {
      setSaving(false);
    }
  };

  const inputBase = {
    ...TYPE.caption,
    background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 8,
    color: T.text, padding: "6px 10px", fontFamily: "inherit", outline: "none",
  };

  return (
    <div className="lux-card" style={{ padding: "18px 20px", marginBottom: 22 }}>
      <Label>New goal</Label>

      {/* Goal text */}
      <textarea
        value={goal}
        onChange={e => setGoal(e.target.value)}
        placeholder="Describe the overall goal…"
        rows={2}
        style={{
          ...TYPE.small, width: "100%", boxSizing: "border-box", marginBottom: 12,
          background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 10,
          color: T.text, padding: "10px 13px",
          fontFamily: "inherit", resize: "vertical", outline: "none",
        }}
      />

      {/* Steps */}
      {steps.map((step, i) => (
        <div key={i} style={{
          background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 10,
          padding: "11px 13px", marginBottom: 9,
        }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
            <input
              value={step.id}
              onChange={e => updateStep(i, "id", e.target.value)}
              placeholder="step-id (e.g. design)"
              style={{ ...inputBase, flex: "0 0 130px", background: T.surface }}
            />
            <select
              value={step.agent}
              onChange={e => updateStep(i, "agent", e.target.value)}
              style={{ ...inputBase, flex: "0 0 140px", background: T.surface }}
            >
              {agentOptions}
            </select>
            <input
              value={(step.depends_on || []).join(", ")}
              onChange={e => updateStep(i, "depends_on", e.target.value.split(",").map(x => x.trim()).filter(Boolean))}
              placeholder="depends_on (comma-sep)"
              style={{ ...inputBase, flex: 1, minWidth: 140, background: T.surface }}
            />
            {steps.length > 1 && (
              <button onClick={() => removeStep(i)} style={{
                ...TYPE.caption, background: "transparent", border: `1px solid ${T.border}`, borderRadius: 99,
                color: T.muted, padding: "5px 11px", cursor: "pointer",
              }}>✕</button>
            )}
          </div>
          <textarea
            value={step.prompt}
            onChange={e => updateStep(i, "prompt", e.target.value)}
            placeholder="What should this agent do?"
            rows={2}
            style={{ ...inputBase, width: "100%", boxSizing: "border-box", background: T.surface, resize: "vertical", lineHeight: 1.5 }}
          />
        </div>
      ))}

      <div style={{ display: "flex", gap: 8, marginTop: 6, alignItems: "center" }}>
        <button onClick={addStep} style={{
          ...TYPE.caption, fontWeight: 700, padding: "7px 15px", borderRadius: 99,
          background: LUX.goldTint, color: T.accent2, border: `1px solid ${GOLD.g2}44`,
          cursor: "pointer", fontFamily: "inherit",
        }}>
          + Add step
        </button>
        <button onClick={handleSubmit} disabled={saving} className="btn-ghost" style={{
          ...TYPE.small, fontWeight: 700, padding: "8px 22px", marginLeft: "auto",
        }}>
          {saving ? "Creating…" : "Create goal"}
        </button>
      </div>

      {error && (
        <div style={{ ...TYPE.caption, marginTop: 10, padding: "8px 12px", background: `${T.error}12`, border: `1px solid ${T.error}44`, borderRadius: 8, color: T.error }}>
          {error}
        </div>
      )}
    </div>
  );
}

export default function GoalTracker() {
  const [goals,   setGoals]   = useState([]);
  const [loading, setLoading] = useState(false);
  const [show,    setShow]    = useState(false);

  const fetchGoals = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/goals?limit=30`);
      const d = await r.json();
      setGoals(d.goals || []);
    } catch { setGoals([]); } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchGoals(); }, [fetchGoals]);

  useEffect(() => {
    const hasRunning = goals.some(g => g.status === "running");
    if (!hasRunning) return;
    const t = setInterval(fetchGoals, 8000);
    return () => clearInterval(t);
  }, [goals, fetchGoals]);

  const active  = goals.filter(g => g.status === "running");
  const pending = goals.filter(g => g.status === "pending" || g.status === "paused");
  const done    = goals.filter(g => g.status === "completed");
  const failed  = goals.filter(g => g.status === "failed");

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      {/* Header */}
      <PageHeader center title="Goals" subtitle="Multi-step goals — each step runs a specialist agent in sequence.">
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setShow(s => !s)} className="btn-ghost" style={{
            ...TYPE.small, fontWeight: 700, padding: "9px 18px",
          }}>
            {show ? "✕ Cancel" : "+ New goal"}
          </button>
          <button onClick={fetchGoals} className="btn-ghost" style={{
            ...TYPE.small, fontWeight: 700, padding: "9px 18px",
          }}>
            ↻ Refresh
          </button>
        </div>
      </PageHeader>

      {/* Summary tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 22 }}>
        <MetricCard label="Active"  value={active.length}  color={active.length ? T.accent2 : T.text} />
        <MetricCard label="Done"    value={done.length}    color={T.success} />
        <MetricCard label="Failed"  value={failed.length}  color={failed.length ? T.error : T.text} />
        <MetricCard label="Pending" value={pending.length} />
      </div>

      {/* Create form */}
      {show && <CreateGoalForm onCreated={() => { setShow(false); fetchGoals(); }} />}

      {/* Goal list */}
      {goals.length === 0 && !loading ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "52px 20px" }}>
          <div style={{
            width: 64, height: 64, borderRadius: 16, background: LUX.goldTint,
            border: `1px solid ${GOLD.g2}44`, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 28, color: T.accent, fontFamily: FONT_DISPLAY,
          }}>◎</div>
          <div style={{ ...TYPE.body, color: T.mutedLt, marginTop: 18, maxWidth: 400 }}>
            No goals yet. Create one to run a multi-step task, where each step hands off
            to the right specialist agent.
          </div>
        </div>
      ) : (
        goals.map(g => <GoalCard key={g.id} goal={g} onRefresh={fetchGoals} />)
      )}
    </div>
  );
}

// ── Small uppercase label ────────────────────────────────────────
function Label({ children, color = T.muted }) {
  return (
    <div style={{ ...TYPE.eyebrow, fontWeight: 700, letterSpacing: "0.1em", color, marginBottom: 4 }}>
      {children}
    </div>
  );
}
