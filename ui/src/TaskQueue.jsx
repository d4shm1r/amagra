import { useState, useEffect, useRef } from "react";
import { T, SEM } from "./theme";
import { AGENTS } from "./constants";
import { PageHeader } from "./ObsShared";

import { API } from "./api";

const STATUS_COLOR = {
  pending: T.muted,
  running: T.accent2,
  done:    T.success,
  failed:  T.error,
};

const STATUS_BG = {
  pending: T.border,
  running: "#F5EDD6",
  done:    "#E7F2E6",
  failed:  "#F9E7E1",
};

// API returns agents as comma-separated string — parse safely
function parseAgents(agentsField) {
  if (!agentsField) return [];
  if (Array.isArray(agentsField)) return agentsField;
  return agentsField.split(",").map(a => a.trim()).filter(Boolean);
}

export default function TaskQueue() {
  const [title,          setTitle]          = useState("");
  const [prompt,         setPrompt]         = useState("");
  const [selectedAgents, setSelectedAgents] = useState([]);
  const [tasks,          setTasks]          = useState([]);
  const [queueRunning,   setQueueRunning]   = useState(false);
  const [expandedId,     setExpandedId]     = useState(null);
  const [expandedData,   setExpandedData]   = useState({});
  const [adding,         setAdding]         = useState(false);

  const refreshRef = useRef(null);

  // Load tasks on mount
  useEffect(() => {
    fetchStatus();
    return () => stopRefresh();
  }, []);

  const fetchStatus = async () => {
    try {
      const r    = await fetch(`${API}/tasks/status`);
      const data = await r.json();
      setTasks(data.tasks || []);

      const active = (data.tasks || []).some(
        t => t.status === "pending" || t.status === "running"
      );
      if (!active) {
        stopRefresh();
        setQueueRunning(false);
      }
    } catch (err) {
      console.error("fetchStatus:", err);
    }
  };

  const startRefresh = () => {
    if (refreshRef.current) return;
    refreshRef.current = setInterval(fetchStatus, 5000);
  };

  const stopRefresh = () => {
    if (refreshRef.current) {
      clearInterval(refreshRef.current);
      refreshRef.current = null;
    }
  };

  const toggleAgent = (id) => {
    setSelectedAgents(prev =>
      prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
    );
  };

  const addTask = async () => {
    if (!title.trim() || !prompt.trim() || selectedAgents.length === 0) return;
    setAdding(true);
    try {
      const r    = await fetch(`${API}/tasks/create`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ title: title.trim(), prompt: prompt.trim(), agents: selectedAgents }),
      });
      const data = await r.json();
      if (data.task_id) {
        setTitle("");
        setPrompt("");
        setSelectedAgents([]);
        await fetchStatus();
      }
    } catch (err) { console.error("addTask:", err); }
    setAdding(false);
  };

  const runAll = async () => {
    setQueueRunning(true);
    try {
      await fetch(`${API}/tasks/run`, { method: "POST" });
      startRefresh();
      await fetchStatus();
    } catch (err) {
      console.error("runAll:", err);
      setQueueRunning(false);
    }
  };

  const deleteTask = async (id, status) => {
    if (status === "running") return;
    try {
      await fetch(`${API}/tasks/${id}`, { method: "DELETE" });
      setTasks(prev => prev.filter(t => t.id !== id));
      if (expandedId === id) setExpandedId(null);
    } catch (err) { console.error("deleteTask:", err); }
  };

  const toggleExpand = async (task) => {
    if (expandedId === task.id) { setExpandedId(null); return; }
    if (task.status !== "done" && task.status !== "failed") return;
    if (expandedData[task.id]) { setExpandedId(task.id); return; }
    try {
      const r    = await fetch(`${API}/tasks/results/${task.id}`);
      const data = await r.json();
      setExpandedData(prev => ({ ...prev, [task.id]: data }));
      setExpandedId(task.id);
    } catch (err) { console.error("toggleExpand:", err); }
  };

  const counts = {
    pending: tasks.filter(t => t.status === "pending").length,
    running: tasks.filter(t => t.status === "running").length,
    done:    tasks.filter(t => t.status === "done").length,
    failed:  tasks.filter(t => t.status === "failed").length,
  };

  const canAddTask = title.trim() && prompt.trim() && selectedAgents.length > 0;

  return (
    <div>
      <style>{`
        @keyframes runningPulse {
          0%,100% { opacity:1 } 50% { opacity:.4 }
        }
        .task-row:hover { filter: brightness(1.05); }
      `}</style>

      <PageHeader title="Tasks" subtitle="Queue specialist work — each task runs the agent you choose and reports back." />

      {/* ── SECTION 1 — New Task Form ── */}
      <div className="lux-card" style={{ padding: 18, marginBottom: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.muted, marginBottom: 12, letterSpacing: 1 }}>
          + NEW TASK
        </div>

        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Task title (e.g. Write a backup script)"
          style={{ width: "100%", background: T.surface2, border: `1.5px solid ${T.border}`, borderRadius: 8, color: T.text, padding: "10px 14px", fontSize: 14, fontFamily: "inherit", outline: "none", marginBottom: 10 }}
          onFocus={e => e.target.style.borderColor = `${T.success}66`}
          onBlur={e => e.target.style.borderColor = T.border}
        />

        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          rows={4}
          placeholder="Full prompt — be specific. The agent will read exactly this."
          style={{ width: "100%", background: T.surface2, border: `1.5px solid ${T.border}`, borderRadius: 8, color: T.text, padding: "10px 14px", fontSize: 14, fontFamily: "inherit", outline: "none", resize: "vertical", lineHeight: 1.6, marginBottom: 10 }}
          onFocus={e => e.target.style.borderColor = `${T.success}66`}
          onBlur={e => e.target.style.borderColor = T.border}
        />

        {/* Agent selector */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: T.muted, marginBottom: 8 }}>Select agents (multi-select allowed):</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button
              onClick={() => setSelectedAgents(["coordinator"])}
              style={{
                padding: "5px 12px", borderRadius: 99, fontSize: 12, fontFamily: "inherit", cursor: "pointer",
                background: selectedAgents.length === 1 && selectedAgents[0] === "coordinator" ? T.accent2 : T.border,
                color:      selectedAgents.length === 1 && selectedAgents[0] === "coordinator" ? T.surface2  : T.muted,
                border: "none", fontWeight: 700,
              }}>
              ◈ Auto
            </button>
            {AGENTS.filter(a => a.id !== "coordinator").map(a => {
              const sel = selectedAgents.includes(a.id);
              return (
                <button key={a.id} onClick={() => toggleAgent(a.id)} style={{
                  padding: "5px 12px", borderRadius: 99, fontSize: 12, fontFamily: "inherit", cursor: "pointer",
                  background: sel ? a.color : T.surface,
                  color:      sel ? T.surface2 : a.color,
                  border: `1px solid ${a.color}${sel ? "" : "55"}`,
                  fontWeight: 600, whiteSpace: "nowrap",
                }}>
                  {a.icon} {a.label}
                </button>
              );
            })}
          </div>
        </div>

        <button
          onClick={addTask}
          disabled={!canAddTask || adding}
          style={{
            background: canAddTask && !adding ? T.success : T.border,
            border: "none", borderRadius: 99, color: canAddTask && !adding ? T.surface2 : T.muted,
            padding: "10px 24px", fontSize: 14, fontWeight: 800, cursor: canAddTask && !adding ? "pointer" : "not-allowed", fontFamily: "inherit",
          }}>
          {adding ? "Adding…" : "+ ADD TASK"}
        </button>
      </div>

      {/* ── SECTION 2 — Queue Controls ── */}
      <div className="lux-card" style={{ padding: "12px 16px", marginBottom: 14, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <button
          onClick={runAll}
          disabled={queueRunning || counts.pending === 0}
          className={queueRunning || counts.pending === 0 ? undefined : "btn-gold"}
          style={{
            padding: "10px 22px", fontSize: 14, fontWeight: 800, fontFamily: "inherit",
            cursor: queueRunning || counts.pending === 0 ? "not-allowed" : "pointer",
            ...(queueRunning || counts.pending === 0
              ? { background: T.border, color: T.muted, border: "none", borderRadius: 99 }
              : {}),
          }}>
          {queueRunning ? "⏳ Running…" : "▶ RUN ALL PENDING"}
        </button>

        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "pending", count: counts.pending, c: T.muted },
            { label: "running", count: counts.running, c: T.accent2 },
            { label: "done",    count: counts.done,    c: T.success },
            { label: "failed",  count: counts.failed,  c: T.error },
          ].map(x => (
            <div key={x.label} style={{ background: STATUS_BG[x.label], border: `1.5px solid ${x.c}44`, borderRadius: 99, padding: "5px 12px", fontSize: 12, fontWeight: 700, color: x.c }}>
              {x.count} {x.label}
            </div>
          ))}
        </div>

        <button onClick={fetchStatus} style={{ marginLeft: "auto", background: "transparent", border: `1.5px solid ${T.border}`, borderRadius: 99, color: T.muted, padding: "6px 12px", fontSize: 12, cursor: "pointer", fontFamily: "inherit" }}>
          ↻ Refresh
        </button>
      </div>

      {/* ── SECTION 3 — Task List ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {tasks.length === 0 && (
          <div style={{ textAlign: "center", color: T.muted, padding: "40px 0", fontSize: 15 }}>
            No tasks yet — create one above
          </div>
        )}

        {tasks.map(task => {
          const agentIds  = parseAgents(task.agents);
          const sc        = STATUS_COLOR[task.status] || T.muted;
          const sb        = STATUS_BG[task.status]    || T.border;
          const isExpanded = expandedId === task.id;
          const data      = expandedData[task.id];
          const canExpand = task.status === "done" || task.status === "failed";
          const canDelete = task.status !== "running";

          return (
            <div key={task.id} className="task-row" style={{ background: T.surface, border: `2px solid ${sc}33`, borderRadius: 12, overflow: "hidden", transition: "all .2s" }}>

              {/* Task header row */}
              <div
                onClick={() => canExpand && toggleExpand(task)}
                style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 10, cursor: canExpand ? "pointer" : "default" }}>

                {/* Status badge */}
                <div style={{ background: sb, border: `1.5px solid ${sc}66`, borderRadius: 99, padding: "3px 10px", fontSize: 11, fontWeight: 700, color: sc, flexShrink: 0, animation: task.status === "running" ? "runningPulse 1.5s infinite" : "none" }}>
                  {task.status === "running" ? "⏳ " : task.status === "done" ? "✓ " : task.status === "failed" ? "✗ " : "○ "}
                  {task.status.toUpperCase()}
                </div>

                {/* Title */}
                <div style={{ flex: 1, fontSize: 14, fontWeight: 600, color: T.text }}>{task.title}</div>

                {/* Agent icons */}
                <div style={{ display: "flex", gap: 4 }}>
                  {agentIds.map(id => {
                    const a = AGENTS.find(ag => ag.id === id);
                    return a ? (
                      <span key={id} title={a.label} style={{ fontSize: 16 }}>{a.icon}</span>
                    ) : null;
                  })}
                </div>

                {/* Timing */}
                {task.finished && task.started && (
                  <span style={{ fontSize: 11, color: T.muted, flexShrink: 0 }}>
                    {Math.round((new Date(task.finished) - new Date(task.started)) / 1000)}s
                  </span>
                )}

                {/* Expand hint */}
                {canExpand && (
                  <span style={{ fontSize: 13, color: T.muted, flexShrink: 0 }}>
                    {isExpanded ? "▲" : "▼"}
                  </span>
                )}

                {/* Delete button */}
                {canDelete && (
                  <button
                    onClick={e => { e.stopPropagation(); deleteTask(task.id, task.status); }}
                    title="Delete task"
                    style={{ background: "transparent", border: `1px solid ${T.error}44`, borderRadius: 99, color: T.error, padding: "3px 8px", cursor: "pointer", fontSize: 12, flexShrink: 0 }}>
                    🗑
                  </button>
                )}
              </div>

              {/* Expanded result panel */}
              {isExpanded && data && (
                <div style={{ borderTop: `2px solid ${sc}33`, padding: "14px 16px", background: task.status === "failed" ? "#F9E7E1" : T.surface2 }}>
                  {task.status === "done" && data.result && (
                    <div style={{ fontSize: 13, color: T.text, lineHeight: 1.75, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 400, overflowY: "auto" }}>
                      {data.result}
                    </div>
                  )}
                  {task.status === "failed" && data.error && (
                    <div style={{ fontSize: 13, color: T.error, fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                      {data.error}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
