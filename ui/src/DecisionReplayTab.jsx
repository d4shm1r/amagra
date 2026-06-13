import { useState, useEffect, useCallback } from "react";
import { T, FONT_MONO } from "./theme";
import { RefreshBtn, EmptyState } from "./ObsShared";

const AGENT_COLOR = {
  python_dev:         "#1E5A8A",
  ai_ml:              "#1E5A8A",
  it_networking:      "#0F766E",
  dotnet_dev:         "#B05B3B",
  knowledge_learning: "#7E3F8F",
  terse:              "#9A7A60",
};
const aColor = (a) => AGENT_COLOR[a] || T.muted;

function AgentBadge({ agent }) {
  return (
    <span style={{
      fontFamily: FONT_MONO, fontSize: 10, fontWeight: 700,
      color: aColor(agent),
      background: aColor(agent) + "20",
      border: `1px solid ${aColor(agent)}40`,
      borderRadius: 3, padding: "1px 7px",
    }}>{agent}</span>
  );
}

function DiffBadge({ changed }) {
  if (!changed) return (
    <span style={{
      fontFamily: FONT_MONO, fontSize: 9,
      color: T.success || "#2E7D32",
    }}>same agent</span>
  );
  return (
    <span style={{
      fontFamily: FONT_MONO, fontSize: 9, fontWeight: 700,
      color: T.warn || "#A16207",
    }}>⚑ agent changed</span>
  );
}

// ── Side-by-side comparison ───────────────────────────────────
function ComparePanel({ original, replay, agent_changed, onClose }) {
  return (
    <div style={{
      marginTop: 10,
      border: `1px solid ${T.border}`,
      borderRadius: 4,
      overflow: "hidden",
      position: "relative",
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        background: T.surface2 || "#F4F0E8",
        borderBottom: `1px solid ${T.border}`,
        padding: "8px 14px",
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: T.text }}>
          Replay comparison
        </span>
        <DiffBadge changed={agent_changed} />
        <button
          onClick={onClose}
          style={{
            marginLeft: "auto", background: "transparent",
            border: "none", color: T.muted,
            cursor: "pointer", fontSize: 14, lineHeight: 1, padding: 0,
          }}
        >✕</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
        {/* Original */}
        <div style={{
          padding: "12px 16px",
          borderRight: `1px solid ${T.border}`,
        }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
          }}>
            <span style={{
              fontSize: 9, textTransform: "uppercase", letterSpacing: "0.1em",
              color: T.muted, fontFamily: FONT_MONO,
            }}>Original</span>
            {original?.agent && <AgentBadge agent={original.agent} />}
            {original?.duration_ms && (
              <span style={{ fontSize: 9, color: T.muted, fontFamily: FONT_MONO, marginLeft: "auto" }}>
                {original.duration_ms}ms
              </span>
            )}
          </div>
          <div style={{
            fontSize: 12, color: T.text, lineHeight: 1.6,
            whiteSpace: "pre-wrap", wordBreak: "break-word",
            maxHeight: 320, overflowY: "auto",
          }}>
            {original?.response || <span style={{ color: T.muted }}>Not available</span>}
          </div>
        </div>

        {/* Replay */}
        <div style={{ padding: "12px 16px" }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
          }}>
            <span style={{
              fontSize: 9, textTransform: "uppercase", letterSpacing: "0.1em",
              color: T.accent, fontFamily: FONT_MONO,
            }}>Replay</span>
            {replay?.agent && <AgentBadge agent={replay.agent} />}
            {replay?.duration_ms && (
              <span style={{ fontSize: 9, color: T.muted, fontFamily: FONT_MONO, marginLeft: "auto" }}>
                {replay.duration_ms}ms
              </span>
            )}
          </div>
          <div style={{
            fontSize: 12, color: T.text, lineHeight: 1.6,
            whiteSpace: "pre-wrap", wordBreak: "break-word",
            maxHeight: 320, overflowY: "auto",
          }}>
            {replay?.response}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── History row ───────────────────────────────────────────────
function HistoryRow({ entry, replayState, onReplay }) {
  const ts = entry.ts
    ? new Date(entry.ts).toLocaleString(undefined, {
        month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    : "—";

  const isReplaying = replayState?.loading;
  const hasResult   = replayState?.result;

  return (
    <div style={{
      borderBottom: `1px solid ${T.border}`,
      padding: "12px 0",
    }}>
      {/* Header row */}
      <div style={{
        display: "flex", alignItems: "flex-start", gap: 10,
        marginBottom: hasResult ? 0 : 0,
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 12, color: T.text, lineHeight: 1.5,
            marginBottom: 4,
            overflow: "hidden", textOverflow: "ellipsis",
            display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          }}>
            {entry.user}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AgentBadge agent={entry.agent} />
            <span style={{
              fontSize: 10, color: T.muted, fontFamily: FONT_MONO,
            }}>{ts}</span>
            {entry.duration_ms && (
              <span style={{ fontSize: 10, color: T.muted, fontFamily: FONT_MONO }}>
                {entry.duration_ms}ms
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => onReplay(entry)}
          disabled={isReplaying}
          style={{
            flexShrink: 0,
            background: isReplaying ? T.surface2 : T.accent + "18",
            border: `1px solid ${isReplaying ? T.border : T.accent + "55"}`,
            borderRadius: 4, padding: "5px 14px",
            color: isReplaying ? T.muted : T.accent,
            fontSize: 11, fontFamily: "inherit",
            cursor: isReplaying ? "not-allowed" : "pointer",
            transition: "background 0.1s",
          }}
        >
          {isReplaying ? "Replaying…" : "↻ Replay"}
        </button>
      </div>

      {/* Comparison panel */}
      {hasResult && (
        <ComparePanel
          original={replayState.result.original || {
            agent: entry.agent,
            response: entry.response,
            duration_ms: entry.duration_ms,
          }}
          replay={replayState.result.replay}
          agent_changed={replayState.result.agent_changed}
          onClose={() => onReplay(null)}
        />
      )}

      {replayState?.error && (
        <div style={{
          marginTop: 8, fontSize: 11, color: T.error,
          fontFamily: FONT_MONO,
        }}>
          Replay failed: {replayState.error}
        </div>
      )}
    </div>
  );
}

// ── Main tab ─────────────────────────────────────────────────
export default function DecisionReplayTab() {
  const [history,    setHistory]    = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [replaying,  setReplaying]  = useState({}); // entry.id → {loading, result, error}
  const [search,     setSearch]     = useState("");

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch("http://localhost:8000/history");
      if (r.ok) {
        const d = await r.json();
        setHistory((d.history || []).slice().reverse());
      }
    } catch (_) {}
    setLoading(false);
  }, []);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleReplay = useCallback(async (entry) => {
    if (entry === null) {
      // close all
      setReplaying({});
      return;
    }
    const key = entry.id ?? entry.ts;
    setReplaying(prev => ({ ...prev, [key]: { loading: true } }));
    try {
      const r = await fetch("http://localhost:8000/ask/replay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query:      entry.user,
          session_id: entry.id ?? null,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setReplaying(prev => ({ ...prev, [key]: { loading: false, result: d } }));
    } catch (e) {
      setReplaying(prev => ({
        ...prev,
        [key]: { loading: false, error: e.message },
      }));
    }
  }, []);

  const q = search.trim().toLowerCase();
  const visible = history.filter(e =>
    !q || e.user?.toLowerCase().includes(q) || e.agent?.toLowerCase().includes(q)
  );

  return (
    <div style={{ color: T.text, fontFamily: "inherit" }}>

      {/* ── Header ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, marginBottom: 16,
      }}>
        <span style={{ fontSize: 16, fontWeight: 700 }}>Decision Replay</span>
        <span style={{ fontSize: 11, color: T.muted }}>
          {history.length} sessions
        </span>
        <div style={{ marginLeft: "auto" }}>
          <RefreshBtn onClick={fetchHistory} />
        </div>
      </div>

      <div style={{
        fontSize: 12, color: T.muted, marginBottom: 14, lineHeight: 1.6,
        background: T.surface2 || "#FAF7F2",
        border: `1px solid ${T.border}`,
        borderRadius: 4, padding: "10px 14px",
      }}>
        Re-run any past query with the <em>current</em> agent set. Detects agent routing
        changes and lets you compare old vs new response side-by-side.
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Filter by query or agent…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{
          width: "100%", boxSizing: "border-box",
          background: T.surface2 || "#FAF7F2",
          border: `1px solid ${T.border}`,
          borderRadius: 4, padding: "6px 12px",
          color: T.text, fontFamily: FONT_MONO, fontSize: 11,
          outline: "none", marginBottom: 12,
        }}
      />

      {!loading && visible.length === 0 && (
        <EmptyState msg={
          history.length === 0
            ? "No session history yet — send a message in Chat"
            : "No sessions match the filter"
        } />
      )}

      <div>
        {visible.map(entry => {
          const key = entry.id ?? entry.ts;
          return (
            <HistoryRow
              key={key}
              entry={entry}
              replayState={replaying[key]}
              onReplay={handleReplay}
            />
          );
        })}
      </div>

    </div>
  );
}
