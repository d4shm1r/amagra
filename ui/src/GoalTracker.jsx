import { useState, useEffect, useCallback } from "react";
import { AGENTS as AGENTS_LIST } from "./constants";
import { PageHeader } from "./ObsShared";

const API = "http://localhost:8000";

// Keyed by id for O(1) lookup; label shortened for chip display
const AGENTS = Object.fromEntries(
  AGENTS_LIST.map(a => [a.id, { icon: a.icon, color: a.color, label: a.label.split(" ")[0] }])
);

const STATUS = {
  pending:   { color: "#9A7A60", bg: "#E0D6C4",  label: "pending",   dot: "○" },
  running:   { color: "#9A6C00", bg: "#F5EDD6",  label: "running…",  dot: "●" },
  completed: { color: "#15803D", bg: "#E7F2E6",  label: "done",      dot: "✓" },
  failed:    { color: "#B42318", bg: "#F9E7E1",  label: "failed",    dot: "✗" },
  paused:    { color: "#0F766E", bg: "#E8EEF6",  label: "paused",    dot: "⏸" },
};

function StatusBadge({ status, small = false }) {
  const s = STATUS[status] || STATUS.pending;
  return (
    <span style={{
      padding: small ? "1px 7px" : "2px 10px",
      borderRadius: 3, fontSize: small ? 10 : 11, fontWeight: 700,
      background: s.bg, color: s.color,
      border: `1px solid ${s.color}44`,
    }}>
      {s.dot} {s.label}
    </span>
  );
}

function AgentChip({ id }) {
  const a = AGENTS[id] || { icon: "?", color: "#9A7A60", label: id };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 3,
      padding: "1px 8px", borderRadius: 3, fontSize: 11, fontWeight: 700,
      background: a.color + "22", color: a.color, border: `1px solid ${a.color}44`,
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
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 5, background: "#E0D6C4", borderRadius: 3, overflow: "hidden", display: "flex" }}>
        <div style={{ width: `${donePct}%`,   height: "100%", background: "#15803D" }} />
        <div style={{ width: `${failedPct}%`, height: "100%", background: "#B42318" }} />
      </div>
      <span style={{ fontSize: 10, color: "#9A7A60", whiteSpace: "nowrap" }}>
        {done}/{total}
      </span>
    </div>
  );
}

function StepCard({ step, onRetry, graphStatus }) {
  const [expanded, setExpanded] = useState(false);
  const s = STATUS[step.status] || STATUS.pending;
  const a = AGENTS[step.agent] || { icon: "?", color: "#9A7A60" };

  return (
    <div style={{
      background: "#F4F0E8",
      border: `1px solid ${s.color}33`,
      borderLeft: `3px solid ${s.color}`,
      borderRadius: 4, marginBottom: 6, overflow: "hidden",
    }}>
      {/* Step header */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 12px", cursor: "pointer" }}
        onClick={() => setExpanded(e => !e)}
      >
        <span style={{ fontSize: 13, color: s.color, fontWeight: 800, minWidth: 16 }}>{s.dot}</span>
        <span style={{ fontSize: 12, color: "#2E2010", fontWeight: 700, flex: 1 }}>
          {step.step_id}
        </span>
        <AgentChip id={step.agent} />
        {step.output_data?.duration_ms && (
          <span style={{ fontSize: 10, color: "#9A7A60" }}>{step.output_data.duration_ms}ms</span>
        )}
        {step.status === "failed" && onRetry && graphStatus !== "running" && (
          <button
            onClick={e => { e.stopPropagation(); onRetry(step.step_id); }}
            style={{
              padding: "2px 10px", borderRadius: 3, fontSize: 11, fontWeight: 700,
              background: "#B4231822", color: "#B42318", border: "1px solid #B4231844",
              cursor: "pointer", fontFamily: "inherit",
            }}
          >
            ↺ retry
          </button>
        )}
        <span style={{ fontSize: 11, color: "#9A7A60" }}>{expanded ? "▲" : "▼"}</span>
      </div>

      {expanded && (
        <div style={{ borderTop: "1px solid #E0D6C4", padding: "10px 12px" }}>
          {/* Prompt */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, color: "#9A7A60", marginBottom: 3, textTransform: "uppercase", letterSpacing: 1 }}>Task</div>
            <div style={{ fontSize: 12, color: "#2E2010", background: "#FAF7F2", borderRadius: 3, padding: "6px 10px", lineHeight: 1.5 }}>
              {step.prompt}
            </div>
          </div>

          {/* Dependencies */}
          {step.depends_on && step.depends_on.length > 0 && (
            <div style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 10, color: "#9A7A60" }}>depends on:</span>
              {step.depends_on.map(d => (
                <span key={d} style={{ fontSize: 10, color: "#0F766E", background: "#0F766E22", padding: "1px 6px", borderRadius: 4 }}>{d}</span>
              ))}
            </div>
          )}

          {/* Output */}
          {step.output_data?.response && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, color: "#15803D", marginBottom: 3, textTransform: "uppercase", letterSpacing: 1 }}>Output</div>
              <div style={{
                fontSize: 11, color: "#2E2010", background: "#FAF7F2", borderRadius: 3,
                padding: "8px 10px", maxHeight: 200, overflowY: "auto",
                lineHeight: 1.6, fontFamily: "monospace", whiteSpace: "pre-wrap",
              }}>
                {step.output_data.response.slice(0, 1000)}
                {step.output_data.response.length > 1000 && "\n…(truncated)"}
              </div>
            </div>
          )}

          {/* Error */}
          {step.error && (
            <div style={{ padding: "6px 10px", background: "#F9E7E1", border: "1px solid #B4231844", borderRadius: 3, fontSize: 11, color: "#B42318" }}>
              {step.error}
            </div>
          )}

          {/* Attempt count */}
          {step.attempt > 1 && (
            <div style={{ marginTop: 6, fontSize: 10, color: "#9A7A60" }}>attempt #{step.attempt}</div>
          )}
        </div>
      )}
    </div>
  );
}

function GoalCard({ goal, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const [detail,   setDetail]   = useState(null);
  const [retrying, setRetrying] = useState(false);

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

  const stepsData = detail?.steps || [];
  const totalSteps = goal.total_steps || 0;

  return (
    <div style={{
      background: "#FAF7F2",
      border: `1.5px solid ${gs.color}44`,
      borderLeft: `4px solid ${gs.color}`,
      borderRadius: 3, marginBottom: 10, overflow: "hidden",
    }}>
      {/* Header */}
      <div
        style={{ padding: "13px 16px", cursor: "pointer" }}
        onClick={() => setExpanded(e => !e)}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 7 }}>
          <span style={{ fontSize: 14, fontWeight: 800, color: "#2E2010", flex: 1 }}>
            {goal.goal.slice(0, 90)}{goal.goal.length > 90 ? "…" : ""}
          </span>
          <StatusBadge status={goal.status} />
          <span style={{ fontSize: 11, color: "#9A7A60" }}>#{goal.id}</span>
        </div>

        {/* Progress */}
        {totalSteps > 0 && (
          <ProgressBar steps={
            Object.entries(goal.step_counts || {}).flatMap(([st, n]) =>
              Array.from({length: n}, () => ({status: st}))
            )
          } />
        )}

        {/* Footer row */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 7 }}>
          <span style={{ fontSize: 10, color: "#9A7A60" }}>
            {totalSteps} step{totalSteps !== 1 ? "s" : ""}
          </span>
          {goal.created_at && (
            <span style={{ fontSize: 10, color: "#9A7A60" }}>
              created {goal.created_at?.slice(0, 10)}
            </span>
          )}

          <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            {(goal.status === "pending" || goal.status === "paused") && (
              <button onClick={e => { e.stopPropagation(); handleRun(); }} style={{
                padding: "3px 12px", borderRadius: 3, fontSize: 11, fontWeight: 700,
                background: "#15803D22", color: "#15803D", border: "1px solid #15803D44",
                cursor: "pointer", fontFamily: "inherit",
              }}>
                ▶ run
              </button>
            )}
            {goal.status !== "running" && (
              <button onClick={e => { e.stopPropagation(); handleDelete(); }} style={{
                padding: "3px 10px", borderRadius: 3, fontSize: 11, fontWeight: 700,
                background: "transparent", color: "#9A7A60", border: "1px solid #E0D6C4",
                cursor: "pointer", fontFamily: "inherit",
              }}>
                ✕
              </button>
            )}
          </span>
        </div>
      </div>

      {/* Expanded steps */}
      {expanded && (
        <div style={{ borderTop: "1px solid #E0D6C4", padding: "12px 14px" }}>
          {stepsData.length === 0 ? (
            <div style={{ color: "#9A7A60", fontSize: 12, textAlign: "center", padding: "10px 0" }}>
              Loading steps…
            </div>
          ) : (
            stepsData.map(step => (
              <StepCard
                key={step.step_id}
                step={step}
                onRetry={handleRetry}
                graphStatus={goal.status}
              />
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

  const addStep = () => setSteps(s => [
    ...s,
    { id: "", agent: "python_dev", prompt: "", depends_on: [] },
  ]);

  const removeStep = i => setSteps(s => s.filter((_, idx) => idx !== i));

  const updateStep = (i, field, value) =>
    setSteps(s => s.map((step, idx) => idx === i ? {...step, [field]: value} : step));

  const handleSubmit = async () => {
    setError("");
    if (!goal.trim()) { setError("Goal is required"); return; }
    for (const [i, s] of steps.entries()) {
      if (!s.id.trim())     { setError(`Step ${i+1}: ID is required`); return; }
      if (!s.prompt.trim()) { setError(`Step ${i+1}: prompt is required`); return; }
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
      setGoal(""); setSteps([{id:"",agent:"python_dev",prompt:"",depends_on:[]}]);
      onCreated(d.goal_id);
    } catch (e) {
      setError("Network error — is the server running?");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="lux-card" style={{ padding: "16px 18px", marginBottom: 20 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#9A7A60", marginBottom: 12, textTransform: "uppercase", letterSpacing: 1 }}>
        New Goal
      </div>

      {/* Goal text */}
      <textarea
        value={goal}
        onChange={e => setGoal(e.target.value)}
        placeholder="Describe the overall goal…"
        rows={2}
        style={{
          width: "100%", boxSizing: "border-box",
          background: "#F4F0E8", border: "1.5px solid #E0D6C4", borderRadius: 4,
          color: "#2E2010", padding: "8px 12px", fontSize: 13,
          fontFamily: "inherit", resize: "vertical", marginBottom: 12,
          outline: "none",
        }}
      />

      {/* Steps */}
      {steps.map((step, i) => (
        <div key={i} style={{
          background: "#F4F0E8", border: "1px solid #E0D6C4", borderRadius: 4,
          padding: "10px 12px", marginBottom: 8,
        }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
            <input
              value={step.id}
              onChange={e => updateStep(i, "id", e.target.value)}
              placeholder="step-id (e.g. design)"
              style={{
                flex: "0 0 130px", background: "#FAF7F2", border: "1px solid #E0D6C4",
                borderRadius: 3, color: "#2E2010", padding: "5px 8px",
                fontSize: 12, fontFamily: "inherit", outline: "none",
              }}
            />
            <select
              value={step.agent}
              onChange={e => updateStep(i, "agent", e.target.value)}
              style={{
                flex: "0 0 130px", background: "#FAF7F2", border: "1px solid #E0D6C4",
                borderRadius: 3, color: "#2E2010", padding: "5px 8px",
                fontSize: 12, fontFamily: "inherit", outline: "none",
              }}
            >
              {agentOptions}
            </select>
            <input
              value={(step.depends_on || []).join(", ")}
              onChange={e => updateStep(i, "depends_on",
                e.target.value.split(",").map(x => x.trim()).filter(Boolean)
              )}
              placeholder="depends_on (comma-sep)"
              style={{
                flex: 1, background: "#FAF7F2", border: "1px solid #E0D6C4",
                borderRadius: 3, color: "#2E2010", padding: "5px 8px",
                fontSize: 12, fontFamily: "inherit", outline: "none",
              }}
            />
            {steps.length > 1 && (
              <button onClick={() => removeStep(i)} style={{
                background: "transparent", border: "1px solid #E0D6C4", borderRadius: 3,
                color: "#9A7A60", padding: "5px 10px", cursor: "pointer", fontSize: 12,
              }}>✕</button>
            )}
          </div>
          <textarea
            value={step.prompt}
            onChange={e => updateStep(i, "prompt", e.target.value)}
            placeholder="What should this agent do?"
            rows={2}
            style={{
              width: "100%", boxSizing: "border-box",
              background: "#FAF7F2", border: "1px solid #E0D6C4", borderRadius: 3,
              color: "#2E2010", padding: "6px 8px", fontSize: 12,
              fontFamily: "inherit", resize: "vertical", outline: "none",
            }}
          />
        </div>
      ))}

      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button onClick={addStep} style={{
          padding: "6px 14px", borderRadius: 7, fontSize: 12, fontWeight: 700,
          background: "#E0D6C4", color: "#9A7A60", border: "1.5px solid #E0D6C4",
          cursor: "pointer", fontFamily: "inherit",
        }}>
          + Add Step
        </button>
        <button onClick={handleSubmit} disabled={saving} style={{
          padding: "6px 20px", borderRadius: 7, fontSize: 12, fontWeight: 700,
          background: saving ? "#F4F0E8" : "#E7F2E6", color: saving ? "#9A7A60" : "#15803D",
          border: `1.5px solid ${saving ? "#E0D6C4" : "#15803D66"}`,
          cursor: saving ? "not-allowed" : "pointer", fontFamily: "inherit",
          marginLeft: "auto",
        }}>
          {saving ? "Creating…" : "Create Goal"}
        </button>
      </div>

      {error && (
        <div style={{ marginTop: 8, padding: "6px 10px", background: "#F9E7E1", border: "1px solid #B4231844", borderRadius: 3, fontSize: 12, color: "#B42318" }}>
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

  useEffect(() => {
    fetchGoals();
    // Poll while any goal is running
  }, [fetchGoals]);

  useEffect(() => {
    const hasRunning = goals.some(g => g.status === "running");
    if (!hasRunning) return;
    const t = setInterval(fetchGoals, 8000);
    return () => clearInterval(t);
  }, [goals, fetchGoals]);

  const active    = goals.filter(g => g.status === "running");
  const pending   = goals.filter(g => g.status === "pending" || g.status === "paused");
  const done      = goals.filter(g => g.status === "completed");
  const failed    = goals.filter(g => g.status === "failed");

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      {/* Header */}
      <PageHeader title="Goals" subtitle="Multi-step goals — each step runs a specialist agent in sequence.">
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "Active",  value: active.length,  color: "#9A6C00" },
            { label: "Done",    value: done.length,    color: "#15803D" },
            { label: "Failed",  value: failed.length,  color: failed.length > 0 ? "#B42318" : "#9A7A60" },
            { label: "Pending", value: pending.length, color: "#9A7A60" },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ background: "#FAF7F2", border: "1.5px solid #E0D6C4", borderRadius: 4, padding: "6px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 16, fontWeight: 800, color }}>{value}</div>
              <div style={{ fontSize: 10, color: "#9A7A60" }}>{label}</div>
            </div>
          ))}
          <button onClick={() => setShow(s => !s)} style={{
            padding: "8px 16px", borderRadius: 4, fontSize: 12, fontWeight: 700,
            background: show ? "#E7F2E6" : "#E0D6C4",
            border: show ? "1.5px solid #15803D66" : "1.5px solid #E0D6C4",
            color: show ? "#15803D" : "#9A7A60",
            cursor: "pointer", fontFamily: "inherit",
          }}>
            {show ? "✕ Cancel" : "+ New Goal"}
          </button>
          <button onClick={fetchGoals} disabled={loading} style={{
            background: "#E0D6C4", border: "1.5px solid #E0D6C4", color: "#9A7A60",
            padding: "8px 14px", borderRadius: 4, fontSize: 12, fontWeight: 700,
            cursor: "pointer", fontFamily: "inherit",
          }}>
            {loading ? "…" : "↻"}
          </button>
        </div>
      </PageHeader>

      {/* Create form */}
      {show && (
        <CreateGoalForm onCreated={id => { setShow(false); fetchGoals(); }} />
      )}

      {/* Goal list */}
      {goals.length === 0 && !loading ? (
        <div style={{ textAlign: "center", color: "#9A7A60", fontSize: 14, padding: "60px 0" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🎯</div>
          No goals yet — create one to execute a multi-step task.
        </div>
      ) : (
        goals.map(g => (
          <GoalCard key={g.id} goal={g} onRefresh={fetchGoals} />
        ))
      )}
    </div>
  );
}
