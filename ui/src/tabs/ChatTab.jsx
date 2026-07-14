import { useState, useRef, useCallback, useEffect } from "react";
import { API } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AGENTS, PROGRESS_STEPS, AGENT_ID_REVERSE } from "@/config/constants";
import AgentContextPanel from "@/components/panels/AgentContextPanel";
import { T, LAYOUT, FONT_DISPLAY } from "@/styles/theme";

// ── Signal Pill ────────────────────────────────────────────────
function Pill({ label, color, title }) {
  return (
    <span title={title} style={{
      background: `${color}1A`, border: `1px solid ${color}44`,
      color, borderRadius: 4, padding: "1px 7px",
      fontSize: 10, fontFamily: "monospace", fontWeight: 700,
      whiteSpace: "nowrap", cursor: title ? "help" : undefined,
    }}>
      {label}
    </span>
  );
}

// ── Typing indicator ───────────────────────────────────────────
function Thinking({ step }) {
  return (
    <div style={{
      display: "flex", gap: 10, alignItems: "center",
      padding: "12px 16px",
      background: T.surface, border: `1.5px solid ${T.warn}22`,
      borderRadius: "4px 10px 10px 10px", maxWidth: 320,
    }}>
      <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 7, height: 7, borderRadius: "50%", background: T.warn,
            animation: `dotBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
      <span style={{ fontSize: 12, color: T.warn }}>{PROGRESS_STEPS[step]}</span>
    </div>
  );
}

// ── Routing-decision animation ─────────────────────────────────
function RoutingStrip({ msg }) {
  const agent = AGENTS.find(a => a.id === msg.agent);
  if (!msg.streaming || msg.text?.length > 0) return null;
  const domain     = msg.signal_domain;
  const agentLabel = agent ? `${agent.icon} ${agent.label}` : (msg.agent ? msg.agent.replace(/_/g, " ") : null);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      marginBottom: 10, fontSize: 11, color: T.muted,
      animation: "routeFadeIn 0.25s ease-out",
    }}>
      <span style={{ color: T.accent, fontSize: 13, animation: "routePulse 1.6s ease-in-out infinite" }}>◈</span>
      {!domain && !agentLabel && <span style={{ color: T.muted }}>analyzing query…</span>}
      {domain && <span style={{ color: T.mutedLt, animation: "routeFadeIn 0.25s ease-out" }}>{domain.replace(/_/g, " ")}</span>}
      {domain && agentLabel && <span style={{ color: T.muted, animation: "routeFadeIn 0.3s ease-out" }}>→</span>}
      {agentLabel && <span style={{ color: agent?.color || T.accent2, fontWeight: 600, animation: "routeFadeIn 0.35s ease-out" }}>{agentLabel}</span>}
      {msg.complexity && msg.complexity !== "simple" && (
        <span style={{ color: T.muted, marginLeft: 2, animation: "routeFadeIn 0.4s ease-out" }}>· {msg.complexity}</span>
      )}
    </div>
  );
}

// ── Pipeline banner ────────────────────────────────────────────
function PipelineBanner({ agents }) {
  if (!agents?.length) return null;
  return (
    <div style={{
      marginBottom: 8, padding: "5px 10px",
      background: T.bg, border: `1px solid ${T.border}`,
      borderRadius: 4, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap",
    }}>
      <span style={{ fontSize: 10, color: T.muted, fontWeight: 700, fontFamily: "monospace" }}>PIPELINE</span>
      {agents.map(a => {
        const ag = AGENTS.find(x => x.id === a);
        return (
          <span key={a} style={{
            background: `${ag?.color || T.muted}1A`, border: `1px solid ${ag?.color || T.muted}44`,
            color: ag?.color || T.muted, borderRadius: 4, padding: "1px 7px",
            fontSize: 10, fontFamily: "monospace", fontWeight: 700,
          }}>{ag?.icon} {a.replace(/_/g, " ")}</span>
        );
      })}
    </div>
  );
}

export default function ChatTab({
  apiStatus, onLogAdd, onQueryComplete, onLitNode,
  onActivityChange, onCoherenceUpdate, forcedAgent,
  onForcedAgentChange, onInspect, defaultReflectMode,
  seedPrompt, onSeedConsumed,
  enterToSend = true, showTimestamps = true,
}) {
  const [messages,      setMessages]      = useState([]);
  const [input,         setInput]         = useState("");
  const [loading,       setLoading]       = useState(false);
  const [pinnedContext, setPinnedContext] = useState("");
  const [copiedIdx,     setCopiedIdx]    = useState(null);
  const [progressStep,  setProgressStep] = useState(0);
  const [feedbackMap,   setFeedbackMap]  = useState({});
  const [feedbackAck,   setFeedbackAck]  = useState({});
  const [coherence,     setCoherence]    = useState(null);
  const [expandedMem,   setExpandedMem]  = useState({});
  const [expandedCoa,   setExpandedCoa]  = useState({});
  const [reflectMode,   setReflectMode]  = useState(defaultReflectMode ?? "");

  // Onboarding hands off a guided first prompt: prefill the input (don't
  // auto-send), then clear the seed so it isn't re-applied on later renders.
  useEffect(() => {
    if (seedPrompt) {
      setInput(seedPrompt);
      onSeedConsumed?.();
    }
  }, [seedPrompt, onSeedConsumed]);
  const [lastMeta,      setLastMeta]     = useState(null);
  const [currentThreadId, setCurrentThreadId] = useState(() => {
    try { return localStorage.getItem("amagra_thread_id") || null; } catch { return null; }
  });
  const [threads,       setThreads]     = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);
  // Side panel: "" = collapsed (default) — opens only when the user asks for it.
  const [sideTab, setSideTabRaw] = useState(() => {
    try { return localStorage.getItem("chat_side_v1") || ""; } catch { return ""; }
  });
  const setSideTab = useCallback((val) => {
    setSideTabRaw(prev => {
      const next = typeof val === "function" ? val(prev) : val;
      try { localStorage.setItem("chat_side_v1", next); } catch {}
      return next;
    });
  }, []);
  const [pillFocus,     setPillFocus]   = useState(false);
  const [liveEvents,    setLiveEvents]  = useState([]);

  const chatEndRef      = useRef(null);
  const progressRef     = useRef(null);
  const isProcessingRef = useRef(false);
  const abortRef        = useRef(null);
  const textareaRef     = useRef(null);
  const fileInputRef    = useRef(null);

  const online = apiStatus === "online";

  // Panel shortcuts: Ctrl+Shift+T threads · Ctrl+Shift+C context · Ctrl+Shift+O advanced
  useEffect(() => {
    const handler = (e) => {
      if (!(e.ctrlKey || e.metaKey) || !e.shiftKey) return;
      const map = { t: "threads", c: "context", o: "advanced" };
      const panel = map[e.key.toLowerCase()];
      if (panel) {
        e.preventDefault();
        setSideTab(prev => prev === panel ? "" : panel);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setSideTab]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const fetchCoherence = useCallback(() => {
    if (!online) return;
    fetch(`${API}/coherence`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) { setCoherence(d); onCoherenceUpdate?.(d); } })
      .catch(() => {});
  }, [online, onCoherenceUpdate]);

  useEffect(() => { fetchCoherence(); }, [fetchCoherence]);

  const fetchThreads = useCallback(() => {
    if (!online) return;
    fetch(`${API}/threads?limit=20`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.threads) setThreads(d.threads); })
      .catch(() => {});
  }, [online]);

  useEffect(() => {
    fetchThreads();
    const id = setInterval(fetchThreads, 15000);
    return () => clearInterval(id);
  }, [fetchThreads]);

  // Live events for context tab
  useEffect(() => {
    const fn = () => {
      fetch(`${API}/cos/events?n=5`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.events) setLiveEvents(d.events.slice(0, 4)); })
        .catch(() => {});
    };
    fn();
    const id = setInterval(fn, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (loading) {
      progressRef.current = setInterval(
        () => setProgressStep(s => (s + 1) % PROGRESS_STEPS.length), 10000
      );
    } else {
      if (progressRef.current) { clearInterval(progressRef.current); progressRef.current = null; }
      setProgressStep(0);
    }
    return () => { if (progressRef.current) clearInterval(progressRef.current); };
  }, [loading]);

  const autoResize = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }, []);

  const handleInputChange = useCallback((e) => {
    setInput(e.target.value);
    autoResize();
  }, [autoResize]);

  const handleStop = useCallback(() => { abortRef.current?.abort(); }, []);

  const [editingIndex, setEditingIndex] = useState(null);

  const clearChat = useCallback(() => {
    if (!messages.length) return;
    if (window.confirm("Clear all messages?")) {
      setMessages([]); setFeedbackMap({});
      setExpandedMem({}); setExpandedCoa({});
    }
  }, [messages.length]);

  const newThread = useCallback(() => {
    setCurrentThreadId(null);
    try { localStorage.removeItem("amagra_thread_id"); } catch {}
    setMessages([]); setFeedbackMap({});
    setExpandedMem({}); setExpandedCoa({});
  }, []);

  const switchThread = useCallback((id) => {
    setCurrentThreadId(id);
    try { localStorage.setItem("amagra_thread_id", id); } catch {}
    setMessages([]); setFeedbackMap({});
    setExpandedMem({}); setExpandedCoa({});
  }, []);

  // Driven by the ☰ AppLauncher (which rehomed the Threads/Context/Advanced rail).
  useEffect(() => {
    const onPanel  = (e) => setSideTab(e.detail || "");
    const onNew    = () => newThread();
    const onSwitch = (e) => { if (e.detail) switchThread(e.detail); };
    window.addEventListener("amagra:chat-panel",   onPanel);
    window.addEventListener("amagra:new-thread",   onNew);
    window.addEventListener("amagra:switch-thread", onSwitch);
    return () => {
      window.removeEventListener("amagra:chat-panel",   onPanel);
      window.removeEventListener("amagra:new-thread",   onNew);
      window.removeEventListener("amagra:switch-thread", onSwitch);
    };
  }, [setSideTab, newThread, switchThread]);

  const handleFileSelect = useCallback(async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const file of files) {
      const name = file.name;
      setAttachedFiles(prev => {
        if (prev.some(f => f.name === name)) return prev;
        return [...prev, { name, status: "uploading", chunks: 0 }];
      });
      try {
        const fd = new FormData();
        fd.append("file", file);
        const r = await fetch(`${API}/documents/upload`, { method: "POST", body: fd });
        if (r.ok) {
          const res = await r.json();
          setAttachedFiles(prev => prev.map(f => f.name === name ? { ...f, status: "ready", chunks: res.chunks_stored } : f));
        } else {
          setAttachedFiles(prev => prev.map(f => f.name === name ? { ...f, status: "error" } : f));
        }
      } catch {
        setAttachedFiles(prev => prev.map(f => f.name === name ? { ...f, status: "error" } : f));
      }
    }
  }, []);

  const sendMessage = useCallback(async (overrideText = null, opts = {}) => {
    const useOverride = typeof overrideText === "string";
    const raw = (useOverride ? overrideText : input).trim();
    if (!raw || isProcessingRef.current) return;
    const text = pinnedContext.trim() ? `[Context: ${pinnedContext.trim()}] ${raw}` : raw;
    isProcessingRef.current = true;
    if (!useOverride) {
      setInput("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    }
    setLoading(true); onActivityChange(70);

    const userTs = new Date().toLocaleTimeString();
    if (opts.appendUser !== false) {
      setMessages(prev => [...prev, { role: "user", text: raw, ts: userTs }]);
    }
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    const streamTs = new Date().toLocaleTimeString();
    setMessages(prev => [...prev, { role: "agent", text: "", streaming: true, agent: null, ts: streamTs }]);

    const t0 = Date.now();
    try {
      const r = await fetch(`${API}/ask/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          force_agent: forcedAgent || null,
          force_reflect_level: reflectMode || null,
          thread_id: currentThreadId || null,
          context_files: attachedFiles.filter(f => f.status === "ready").map(f => f.name),
        }),
        signal: abortRef.current.signal,
      });
      if (!r.ok) {
        let detail = `HTTP ${r.status}`;
        try { const b = await r.json(); detail = b.detail || JSON.stringify(b); }
        catch { detail = await r.text().catch(() => "Server error"); }
        throw new Error(detail);
      }

      const reader  = r.body.getReader();
      const decoder = new TextDecoder();
      let   buf     = "";
      let   accText = "";
      let   agentId = null;
      let   doneMeta = {};

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let ev;
          try { ev = JSON.parse(line.slice(6)); } catch { continue; }

          if (ev.type === "routing") {
            const rawId = ev.agent || "knowledge_learning";
            agentId = AGENT_ID_REVERSE[rawId] || rawId;
            setMessages(prev => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.streaming) {
                next[next.length - 1] = {
                  ...last, agent: agentId,
                  complexity:       ev.complexity       || "simple",
                  model_tier:       ev.model_tier       || "fast",
                  signal_domain:    ev.signal_domain    || "general",
                  signal_shape:     ev.signal_shape     || "explanation",
                  signal_verbosity: ev.signal_verbosity || "normal",
                  signal_conf:      ev.signal_conf      || 0,
                  action:           ev.action           || "unknown",
                  confidence:       ev.confidence       || 0.67,
                };
              }
              return next;
            });
          } else if (ev.type === "token") {
            accText += ev.text;
            setMessages(prev => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.streaming) next[next.length - 1] = { ...last, text: accText };
              return next;
            });
          } else if (ev.type === "done") {
            doneMeta = ev;
          } else if (ev.type === "error") {
            throw new Error(ev.detail || "Streaming error");
          }
        }
      }

      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      const finalAgent = agentId || AGENT_ID_REVERSE[doneMeta.agent] || doneMeta.agent || "knowledge_learning";
      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.streaming) {
          next[next.length - 1] = {
            ...last, streaming: false, agent: finalAgent, elapsed,
            text:     accText || last.text,
            signal_domain:    doneMeta.signal_domain    || last.signal_domain    || "general",
            signal_shape:     doneMeta.signal_shape     || last.signal_shape     || "explanation",
            signal_verbosity: doneMeta.signal_verbosity || last.signal_verbosity || "normal",
            signal_conf:      doneMeta.signal_conf      ?? last.signal_conf      ?? 0,
            action:           doneMeta.action           || last.action           || "unknown",
            complexity:       doneMeta.complexity       || last.complexity       || "simple",
            confidence:       doneMeta.confidence       ?? last.confidence       ?? 0.67,
            reflect_level:    doneMeta.reflect_level    || "none",
            memories_used:    doneMeta.memories_used    || [],
            contradiction_detected: false,
            gram_winner: "", gram_log: "",
            weight_before: 0, weight_after: 0, weight_delta: 0,
            pipeline_agents: [], pipeline_responses: [],
            context_id: "",
          };
        }
        return next;
      });

      setLastMeta({
        agent:         finalAgent,
        signal_domain: doneMeta.signal_domain || "general",
        signal_conf:   doneMeta.signal_conf   || 0,
        complexity:    doneMeta.complexity    || "simple",
        model_tier:    doneMeta.model_tier    || "fast",
        reflect_level: doneMeta.reflect_level || "none",
        memories_used: doneMeta.memories_used || [],
        elapsed,
      });

      onLitNode("coordinator");
      setTimeout(() => { onLitNode(finalAgent); setTimeout(() => onLitNode(null), 2500); }, 800);
      onQueryComplete(); fetchCoherence();
      onLogAdd(`▸ ${finalAgent.replace(/_/g, " ")} responded (${elapsed}s)`, AGENTS.find(a => a.id === finalAgent)?.color || T.success);
    } catch (err) {
      if (err.name === "AbortError") {
        setMessages(prev => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.streaming) next[next.length - 1] = { ...last, streaming: false, stoppedEarly: true };
          return next;
        });
      } else {
        setMessages(prev => prev.filter(m => !m.streaming));
        setMessages(prev => [...prev, {
          role: "error",
          text: `❌ ${err.message}\n\nIf the LLM is offline: ollama serve — then ai-start`,
          ts: new Date().toLocaleTimeString(),
        }]);
      }
    }
    onActivityChange(100); setTimeout(() => onActivityChange(0), 300);
    setLoading(false); isProcessingRef.current = false; abortRef.current = null;
  }, [input, pinnedContext, forcedAgent, reflectMode, currentThreadId, onLogAdd, onQueryComplete, onLitNode, onActivityChange, fetchCoherence, fetchThreads]);

  // Re-run the last user prompt, replacing the last agent reply.
  const handleRegenerate = useCallback(async () => {
    if (isProcessingRef.current) return;
    let lastUserIdx = -1;
    messages.forEach((m, i) => { if (m.role === "user") lastUserIdx = i; });
    if (lastUserIdx < 0) return;
    const lastUserText = messages[lastUserIdx].text;
    setMessages(prev => prev.slice(0, lastUserIdx + 1));  // drop the old reply
    if (currentThreadId) {
      try {
        const tc = await fetch(`${API}/threads/${currentThreadId}/turns`).then(r => r.json());
        const keep = Math.max(0, (tc.turns?.length || 0) - 1);
        await fetch(`${API}/threads/${currentThreadId}/truncate?keep=${keep}`, { method: "POST" });
      } catch { /* best effort */ }
    }
    sendMessage(lastUserText, { appendUser: false });
  }, [messages, currentThreadId, sendMessage]);

  // Edit a prior user message: drop it + everything after, then resend the new text.
  const handleEditResend = useCallback(async (uiIndex, newText) => {
    const t = (newText || "").trim();
    if (!t || isProcessingRef.current) return;
    let keep = 0;
    for (let i = 0; i < uiIndex; i++) if (messages[i]?.role === "user") keep++;
    setMessages(prev => prev.slice(0, uiIndex));
    if (currentThreadId) {
      try { await fetch(`${API}/threads/${currentThreadId}/truncate?keep=${keep}`, { method: "POST" }); }
      catch { /* best effort */ }
    }
    sendMessage(t, { appendUser: true });
  }, [messages, currentThreadId, sendMessage]);

  const startEdit = useCallback((uiIndex) => {
    setEditingIndex(uiIndex);
    setInput(messages[uiIndex]?.text || "");
    setTimeout(() => textareaRef.current?.focus(), 0);
  }, [messages]);

  const cancelEdit = useCallback(() => { setEditingIndex(null); setInput(""); }, []);

  // Send button / Enter: route to edit-resend when editing, else a normal send.
  const handleSendClick = useCallback(() => {
    if (editingIndex != null) {
      const idx = editingIndex; const txt = input;
      setEditingIndex(null); setInput("");
      handleEditResend(idx, txt);
    } else {
      sendMessage();
    }
  }, [editingIndex, input, handleEditResend, sendMessage]);

  const handleKeyDown = e => {
    // enterToSend: Enter sends, Shift+Enter = newline.
    // Off: Enter = newline, Ctrl/Cmd+Enter sends.
    const sendCombo = enterToSend
      ? (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey)
      : (e.key === "Enter" && (e.ctrlKey || e.metaKey));
    if (sendCombo) { e.preventDefault(); handleSendClick(); }
    else if (e.key === "Escape" && editingIndex != null) { e.preventDefault(); cancelEdit(); }
  };

  const handleApplySuggestion = useCallback((suggestion) => {
    setInput(suggestion.query || suggestion.title || "");
    if (suggestion.agent && suggestion.agent !== "auto") onForcedAgentChange(suggestion.agent);
    setTimeout(() => { autoResize(); textareaRef.current?.focus(); }, 60);
  }, [onForcedAgentChange, autoResize]);

  const copyMessage = (idx, text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx); setTimeout(() => setCopiedIdx(null), 1500);
    });
  };

  const sendFeedback = useCallback(async (msgIdx, rating) => {
    const msg = messages[msgIdx];
    if (!msg || msg.role !== "agent") return;
    const query = [...messages].slice(0, msgIdx).reverse().find(m => m.role === "user")?.text || "";
    setFeedbackMap(prev => ({ ...prev, [msgIdx]: rating }));
    setFeedbackAck(prev => ({ ...prev, [msgIdx]: rating > 0 ? "positive" : "negative" }));
    setTimeout(() => setFeedbackAck(prev => ({ ...prev, [msgIdx]: null })), 3500);
    try {
      await fetch(`${API}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, response: msg.text, agent: msg.agent || "unknown", rating }),
      });
    } catch { /* fire-and-forget */ }
  }, [messages]);

  const exportSession = () => {
    const msgs = messages.filter(m => m.role !== "error");
    if (!msgs.length) { alert("No messages to export."); return; }
    const md = msgs.map(m =>
      `### ${m.role === "user" ? "You" : (m.agent || "agent").replace(/_/g, " ").toUpperCase()}\n${m.text}`
    ).join("\n\n---\n\n");
    const blob = new Blob([`# AMAGRA Session — ${new Date().toLocaleDateString()}\n\n${md}`], { type: "text/markdown" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a");
    a.href = url; a.download = `session-${new Date().toISOString().slice(0, 10)}.md`; a.click();
    URL.revokeObjectURL(url);
  };

  const exportSessionPDF = () => {
    const msgs = messages.filter(m => m.role !== "error");
    if (!msgs.length) { alert("No messages to export."); return; }
    const rows = msgs.map(m => {
      const who = m.role === "user" ? "You" : (m.agent || "agent").replace(/_/g, " ").toUpperCase();
      const clr = m.role === "user" ? "#444" : "#E7F2E6";
      const txt = (m.text || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      return `<div style="margin-bottom:16px;page-break-inside:avoid"><strong style="color:${clr}">${who}</strong><pre style="white-space:pre-wrap;font-family:inherit;margin:4px 0 0;line-height:1.5">${txt}</pre></div>`;
    }).join('<hr style="border:none;border-top:1px solid #ddd;margin:12px 0"/>');
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>AMAGRA Session ${new Date().toLocaleDateString()}</title>
<style>body{font-family:system-ui,sans-serif;font-size:13px;color:#222;max-width:760px;margin:0 auto;padding:24px}h1{font-size:16px;margin-bottom:20px}@media print{body{padding:0}}</style>
</head><body><h1>AMAGRA Session — ${new Date().toLocaleString()}</h1>${rows}</body></html>`;
    const win = window.open("", "_blank");
    if (!win) { alert("Allow pop-ups to export as PDF."); return; }
    win.document.write(html); win.document.close(); win.focus();
    setTimeout(() => win.print(), 400);
  };

  const visibleAgents = AGENTS.filter(a => a.id !== "coordinator");
  const canSend = !loading && !!input.trim() && online;

  // ── Sidebar section label ──────────────────────────────────────
  const SideLabel = ({ children }) => (
    <div style={{
      fontSize: 9, fontWeight: 700, color: T.muted,
      textTransform: "uppercase", letterSpacing: "0.10em",
      marginBottom: 7,
    }}>{children}</div>
  );

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "row", animation: "fadeIn .2s", overflow: "hidden" }}>

      {/* ══════════════════════════════════════════════════════════
          Chat column
      ══════════════════════════════════════════════════════════ */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>

        {/* ── Message list ── */}
        <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          <div style={{
            // The thread and the composer below must share one measure, or the
            // input visibly disagrees with the messages above it. Both read
            // LAYOUT.reading — the app's prose measure. Never a local number.
            maxWidth: LAYOUT.reading, margin: "0 auto", padding: "24px 24px 14px",
            display: "flex", flexDirection: "column", gap: 14,
          }}>

            {/* ── Empty state ── */}
            {messages.length === 0 && (
              <div style={{ paddingTop: 56, textAlign: "center" }}>

                {/* Gold AMAGRA logo — inert brand mark, not selectable or clickable */}
                <div style={{
                  fontSize: 44, fontWeight: 600, letterSpacing: "0.06em",
                  fontFamily: FONT_DISPLAY,
                  background: "linear-gradient(135deg, #6C4C00 0%, #9A6C00 18%, #C48808 36%, #DEB838 52%, #C48808 68%, #9A6C00 84%, #6C4C00 100%)",
                  WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
                  backgroundClip: "text", marginBottom: 14, lineHeight: 1,
                  userSelect: "none", WebkitUserSelect: "none", pointerEvents: "none",
                }}>
                  AMAGRA
                </div>

                {/* Brand line — lead with trust, not machinery */}
                <div style={{
                  fontSize: 16, fontWeight: 500, color: T.text, marginBottom: 5,
                  fontFamily: FONT_DISPLAY, letterSpacing: "0.005em",
                  userSelect: "none", WebkitUserSelect: "none", pointerEvents: "none",
                }}>
                  The AI you can trust with long-term work.
                </div>
                <div style={{
                  fontSize: 12, color: T.muted, maxWidth: 420, margin: "0 auto 28px", lineHeight: 1.65,
                  userSelect: "none", WebkitUserSelect: "none", pointerEvents: "none",
                }}>
                  Ask anything. The right specialist answers, remembers your work, and shows you
                  exactly how it got there.
                </div>

                {!online && (
                  <div style={{ fontSize: 11, color: T.error, marginBottom: 36 }}>
                    ⚠ Backend offline — run <code style={{ background: "#B4231818", padding: "1px 5px", borderRadius: 3 }}>ai-start</code>
                  </div>
                )}

              </div>
            )}

            {/* ── Messages ── */}
            {messages.map((msg, i) => {
              if (msg.role === "user") return (
                <div key={i} className="user-msg-row" style={{ display: "flex", justifyContent: "flex-end", alignItems: "flex-start", gap: 4 }}>
                  {!loading && (
                    <button
                      onClick={() => startEdit(i)}
                      title="Edit & resend"
                      className="edit-msg-btn"
                      style={{
                        background: "transparent", border: "none", cursor: "pointer",
                        color: editingIndex === i ? T.accent : T.muted, fontSize: 12,
                        padding: "4px 4px", marginTop: 6, fontFamily: "inherit",
                        opacity: editingIndex === i ? 1 : 0.55,
                      }}
                    >✎</button>
                  )}
                  <div style={{
                    maxWidth: "75%",
                    background: T.surface2,
                    border: `1.5px solid ${editingIndex === i ? T.accent : T.border}`,
                    borderRadius: "10px 10px 4px 10px", padding: "11px 16px",
                  }}>
                    <div className="msg-content" style={{ wordBreak: "break-word" }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                    </div>
                    {showTimestamps && <div style={{ marginTop: 4, fontSize: 10, color: T.muted, textAlign: "right" }}>{msg.ts}</div>}
                  </div>
                </div>
              );

              if (msg.role === "error") return (
                <div key={i} style={{
                  padding: "11px 15px",
                  background: "#F9E7E1", border: `1.5px solid ${T.error}44`,
                  borderRadius: 8, color: T.error, fontSize: 13, whiteSpace: "pre-wrap",
                }}>{msg.text}</div>
              );

              const agent      = AGENTS.find(a => a.id === msg.agent);
              const ac         = agent?.color || T.success;
              const isPipeline = msg.pipeline_agents?.length > 0;

              return (
                <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", animation: "fadeIn .3s ease both" }}>
                  <div style={{
                    width: 36, height: 36, flexShrink: 0, marginTop: 2,
                    background: `${ac}18`, border: `2px solid ${ac}66`,
                    borderRadius: 8, display: "flex", alignItems: "center",
                    justifyContent: "center", fontSize: 16,
                  }}>
                    {isPipeline ? "⊕" : (agent?.icon || "∴")}
                  </div>

                  <div style={{ flex: 1, maxWidth: "87%" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: ac, letterSpacing: "0.04em" }}>
                        {isPipeline ? "PIPELINE" : (msg.agent || "agent").replace(/_/g, " ").toUpperCase()}
                      </span>
                      {msg.elapsed && <span style={{ fontSize: 11, color: T.muted }}>{msg.elapsed}s</span>}
                      {showTimestamps && <span style={{ fontSize: 11, color: T.muted }}>{msg.ts}</span>}
                      {msg.complexity === "compound" && !isPipeline && <Pill label="compound" color={T.warn} />}
                    </div>

                    <div style={{
                      position: "relative", background: T.surface,
                      border: `1.5px solid ${ac}22`,
                      borderRadius: "4px 10px 10px 10px", padding: "13px 15px",
                    }}>
                      <div style={{ position: "absolute", top: 8, right: 8, display: msg.streaming ? "none" : "flex", gap: 2 }}>
                        <ActionBtn onClick={() => sendFeedback(i, 1)} title="Good response" active={feedbackMap[i] === 1} dim={feedbackMap[i] === -1} activeColor={T.success}>👍</ActionBtn>
                        <ActionBtn onClick={() => sendFeedback(i, -1)} title="Bad response" active={feedbackMap[i] === -1} dim={feedbackMap[i] === 1} activeColor={T.error}>👎</ActionBtn>
                        <ActionBtn onClick={() => copyMessage(i, msg.text)} title="Copy" active={copiedIdx === i} activeColor={T.success}>{copiedIdx === i ? "✓" : "⊞"}</ActionBtn>
                        {i === messages.length - 1 && !loading && (
                          <ActionBtn onClick={handleRegenerate} title="Regenerate response" activeColor={T.accent}>↻</ActionBtn>
                        )}
                      </div>

                      {feedbackAck[i] && (
                        <div style={{
                          fontSize: 10, color: feedbackAck[i] === "positive" ? T.success : T.accent2,
                          marginBottom: 6, display: "flex", alignItems: "center", gap: 5,
                          animation: "fbFadeOut 3.5s ease-out forwards",
                        }}>
                          <span>◈</span>
                          <span>{feedbackAck[i] === "positive"
                            ? "Got it — routing adjusted for future queries like this."
                            : "Got it — I'll improve on this."
                          }</span>
                        </div>
                      )}

                      <PipelineBanner agents={msg.pipeline_agents} />
                      <RoutingStrip msg={msg} />

                      <div className="msg-content" style={{ wordBreak: "break-word", paddingRight: 72 }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text || " "}</ReactMarkdown>
                        {msg.streaming && (
                          <span style={{
                            display: "inline-block", width: 8, height: 14,
                            background: T.accent, marginLeft: 2, verticalAlign: "text-bottom",
                            animation: "cursorBlink .7s step-end infinite",
                          }} />
                        )}
                        {msg.stoppedEarly && (
                          <span style={{ fontSize: 10, color: T.muted, marginLeft: 6, fontStyle: "italic" }}>(stopped)</span>
                        )}
                      </div>

                      {!msg.streaming && msg.signal_domain && (
                        <div style={{ marginTop: 10, borderTop: `1px solid ${ac}18`, paddingTop: 8 }}>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
                            <Pill label={msg.signal_domain.replace(/_/g, " ")} color="#0E7490" title={`domain · ${Math.round((msg.signal_conf||0)*100)}% confidence`} />
                            <Pill label={msg.signal_shape}     color="#7E3F8F" />
                            <Pill label={msg.signal_verbosity} color={T.success} />
                            <Pill label={`${Math.round((msg.signal_conf||0)*100)}% sig`}  color={T.warn} title="Signal routing confidence" />
                            <Pill label={`${Math.round((msg.confidence||0)*100)}% conf`} color="#0E7490" title="Agent confidence" />
                            {msg.reflect_level && msg.reflect_level !== "none" && (
                              <Pill label={`${msg.reflect_level} reflect`} color={msg.reflect_level === "full" ? "#C06040" : T.warn} />
                            )}
                            {msg.gram_winner && (
                              <Pill label={`GRAM→${msg.gram_winner}`} color={msg.gram_winner === "B" ? T.success : T.muted} title={msg.gram_log || ""} />
                            )}
                            {msg.contradiction_detected && (
                              <Pill label="⚠ conflict" color={T.error} title="Response may contradict stored memory" />
                            )}
                            {msg.weight_delta !== 0 && msg.weight_after > 0 && (
                              <span title={`Weight: ${msg.weight_before?.toFixed(4)} → ${msg.weight_after?.toFixed(4)}`} style={{
                                background: msg.weight_delta > 0 ? `${T.success}18` : `${T.error}18`,
                                border: `1px solid ${msg.weight_delta > 0 ? T.success : T.error}44`,
                                color: msg.weight_delta > 0 ? T.success : T.error,
                                borderRadius: 4, padding: "1px 7px",
                                fontSize: 10, fontFamily: "monospace", fontWeight: 700,
                                animation: "weightFade 2.5s ease-out forwards",
                              }}>
                                {msg.weight_delta > 0 ? "↑" : "↓"} w {msg.weight_delta > 0 ? "+" : ""}{msg.weight_delta?.toFixed(4)}
                              </span>
                            )}
                            <div style={{ marginLeft: "auto", display: "flex", gap: 2 }}>
                              {msg.context_id && (
                                <ActionBtn onClick={() => onInspect?.(msg.context_id)} title={`Inspect: ${msg.context_id}`}>⊙ ctx</ActionBtn>
                              )}
                              <ActionBtn onClick={() => setExpandedCoa(p => ({ ...p, [i]: !p[i] }))} active={expandedCoa[i]} activeColor="#0E7490">
                                {expandedCoa[i] ? "▲ CoA" : "▼ CoA"}
                              </ActionBtn>
                            </div>
                          </div>

                          {expandedCoa[i] && (
                            <div style={{
                              marginTop: 7, background: T.bg, border: `1px solid ${T.border}`,
                              borderRadius: 4, padding: "9px 12px",
                              fontSize: 11, fontFamily: "monospace",
                            }}>
                              <div style={{ color: T.warn, marginBottom: 6, fontSize: 10, fontWeight: 700 }}>▸ AUTHORIZATION TRAJECTORY</div>
                              <div style={{ display: "flex", flexDirection: "column", gap: 5, color: T.muted }}>
                                <div><span style={{ color: "#0E7490" }}>1 NORMALIZE</span>{"  "}domain=<span style={{ color: T.text }}>{msg.signal_domain}</span>{"  "}shape=<span style={{ color: T.text }}>{msg.signal_shape}</span>{"  "}verbosity=<span style={{ color: T.text }}>{msg.signal_verbosity}</span>{"  "}conf=<span style={{ color: T.text }}>{msg.signal_conf?.toFixed(2)}</span></div>
                                <div><span style={{ color: "#7E3F8F" }}>2 CLASSIFY</span>{"  "}action=<span style={{ color: T.text }}>{msg.action}</span>{"  "}complexity=<span style={{ color: T.text }}>{msg.complexity}</span></div>
                                <div><span style={{ color: T.success }}>3 SELECT</span>{"  "}agent=<span style={{ color: ac }}>{msg.agent?.replace(/_/g," ")}</span>{"  "}confidence=<span style={{ color: T.text }}>{msg.confidence?.toFixed(2)}</span>{msg.pipeline_agents?.length > 0 && <span style={{ color: T.warn }}>{"  "}pipeline=[{msg.pipeline_agents.join(", ")}]</span>}</div>
                                <div><span style={{ color: msg.reflect_level === "full" ? "#C06040" : msg.reflect_level === "light" ? T.warn : T.muted }}>4 AUTHORIZE</span>{"  "}reflect=<span style={{ color: T.text }}>{msg.reflect_level || "none"}</span>{msg.gram_winner && <span style={{ color: T.success }}>{"  "}gram={msg.gram_winner}{msg.gram_log ? ` (${msg.gram_log.slice(0, 60)})` : ""}</span>}{msg.contradiction_detected && <span style={{ color: T.error }}>{"  "}⚠ contradiction→full</span>}</div>
                              </div>
                            </div>
                          )}

                          {msg.memories_used?.length > 0 && !msg.streaming && (
                            <div style={{ marginTop: 8, borderTop: `1px solid ${T.border}`, paddingTop: 6 }}>
                              {msg.memories_used.slice(0, expandedMem[i] ? undefined : 2).map((m, mi) => (
                                <div key={mi} style={{ display: "flex", gap: 6, alignItems: "flex-start", marginBottom: 4 }}>
                                  <span style={{ color: T.accent, fontSize: 10, flexShrink: 0, marginTop: 2, opacity: 0.7 }}>◈</span>
                                  <span style={{ color: T.muted, fontSize: 10, lineHeight: 1.5 }}>
                                    <span style={{ color: T.mutedLt, fontWeight: 600 }}>Remembered</span>{" · "}
                                    {(m.content || "").slice(0, 110)}{m.content?.length > 110 ? "…" : ""}
                                  </span>
                                </div>
                              ))}
                              {msg.memories_used.length > 2 && (
                                <button onClick={() => setExpandedMem(p => ({ ...p, [i]: !p[i] }))} style={{ background: "transparent", border: "none", color: T.muted, fontSize: 10, cursor: "pointer", padding: "2px 0", fontFamily: "inherit" }}>
                                  {expandedMem[i] ? "▲ show fewer" : `▼ ${msg.memories_used.length - 2} more memories`}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {loading && !messages.some(m => m.streaming) && <Thinking step={progressStep} />}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* ── Pill input ── */}
        <div style={{ flexShrink: 0, padding: "0 20px 18px", maxWidth: LAYOUT.reading, margin: "0 auto", width: "100%", boxSizing: "border-box" }}>
          {editingIndex != null && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
              padding: "6px 14px", background: `${T.accent}12`,
              border: `1px solid ${T.accent}44`, borderRadius: 8,
              fontSize: 11, color: T.accent,
            }}>
              <span style={{ flex: 1 }}>✎ Editing your message — resending replaces it and everything after.</span>
              <button onClick={cancelEdit} style={{
                background: "transparent", border: "none", cursor: "pointer",
                color: T.muted, fontSize: 11, fontFamily: "inherit",
              }}>✕ Cancel (Esc)</button>
            </div>
          )}
          <div style={{
            display: "flex", alignItems: "flex-end", gap: 10,
            background: "#FCFAF7",
            border: `1px solid ${pillFocus ? "#C48808" : "rgba(196,136,8,0.30)"}`,
            borderRadius: 28, padding: "9px 9px 9px 22px",
            // Single outline only — a soft gold glow on focus, never a second
            // concentric ring (which read as "a form inside a form").
            boxShadow: pillFocus
              ? "0 8px 30px rgba(196,136,8,0.18), 0 2px 10px rgba(72,52,28,0.08)"
              : "0 2px 10px rgba(72,52,28,0.06)",
            transition: "border-color .18s ease, box-shadow .18s ease",
          }}>
            <textarea
              ref={textareaRef}
              className="chat-composer-input"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onFocus={() => setPillFocus(true)}
              onBlur={() => setPillFocus(false)}
              placeholder={online ? "Ask anything…" : "⚠ Backend offline — run ai-start"}
              rows={1}
              disabled={!online}
              style={{
                flex: 1, background: "transparent", border: "none",
                color: T.text, fontSize: 14, fontFamily: "inherit",
                resize: "none", outline: "none", lineHeight: 1.6,
                padding: "4px 0", overflowY: "auto", maxHeight: 160,
                display: "block",
              }}
            />
            {loading && (
              <button onClick={handleStop} title="Stop" style={{
                height: 36, padding: "0 14px", flexShrink: 0,
                background: "#F9E7E1", border: `1.5px solid ${T.error}66`,
                borderRadius: 20, fontSize: 11, cursor: "pointer",
                color: T.error, fontWeight: 700, fontFamily: "inherit",
                whiteSpace: "nowrap",
              }}>✕ Stop</button>
            )}
            <button
              onClick={handleSendClick}
              disabled={!canSend}
              title={editingIndex != null ? "Resend edited message (Enter)" : "Send (Enter)"}
              style={{
                width: 38, height: 38, flexShrink: 0, borderRadius: "50%",
                // Elegant white face with a crisp gold ring — premium and calm.
                // Stays fully legible when empty (a softer glow, never faint or
                // greyed out); active state just warms up the ring and glow.
                background: "#FFFFFF",
                border: `1.5px solid ${canSend ? "#C48808" : "#C4880877"}`,
                fontSize: 16, fontWeight: 700,
                cursor: canSend ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: canSend ? "#B27A05" : "#C48808CC",
                boxShadow: canSend
                  ? "0 3px 14px rgba(196,136,8,0.28)"
                  : "0 1px 5px rgba(72,52,28,0.08)",
                transition: "all .18s ease",
              }}>↑</button>
          </div>
        </div>

      </div>{/* ── end chat column ── */}


      {/* ══════════════════════════════════════════════════════════
          Side panel — the quiet icon rail moved into the ☰ launcher
          (v1.6.3); the expanded panel still opens on demand.
      ══════════════════════════════════════════════════════════ */}
      {false && (
        <div style={{
          width: 44, flexShrink: 0,
          display: "flex", flexDirection: "column", alignItems: "center",
          gap: 4, paddingTop: 10,
          background: T.surface, borderLeft: `1px solid ${T.border}`,
        }}>
          {[
            { id: "threads",  icon: "☰", label: "Threads",  key: "T" },
            { id: "context",  icon: "◈", label: "Context",  key: "C" },
            { id: "advanced", icon: "⚙", label: "Advanced", key: "O" },
          ].map(p => (
            <button key={p.id}
              onClick={() => setSideTab(p.id)}
              title={`${p.label}  (Ctrl+Shift+${p.key})`}
              className="nav-btn"
              style={{
                width: 32, height: 32, borderRadius: 8,
                border: "none", background: "transparent",
                color: T.muted, fontSize: 14, cursor: "pointer",
                fontFamily: "inherit", lineHeight: 1,
              }}
            >{p.icon}</button>
          ))}
        </div>
      )}

      {sideTab && (
      <div style={{
        width: 280, flexShrink: 0,
        display: "flex", flexDirection: "column",
        background: T.surface, borderLeft: `1px solid ${T.border}`,
        overflow: "hidden",
        animation: "fadeIn .15s",
      }}>

        {/* Tab bar */}
        <div style={{ display: "flex", alignItems: "stretch", flexShrink: 0, borderBottom: `1px solid ${T.border}` }}>
          {["Threads", "Context", "Advanced"].map(tab => {
            const key = tab.toLowerCase();
            const active = sideTab === key;
            return (
              <button key={tab} onClick={() => setSideTab(key)} style={{
                flex: 1, padding: "9px 4px",
                background: active ? T.bg : "transparent",
                border: "none", borderBottom: `2px solid ${active ? T.accent : "transparent"}`,
                color: active ? T.text : T.muted,
                fontSize: 11, fontWeight: active ? 700 : 400,
                cursor: "pointer", fontFamily: "inherit",
                transition: "color .12s",
              }}>{tab}</button>
            );
          })}
          <button
            onClick={() => setSideTab("")}
            title="Hide panel"
            className="nav-btn"
            style={{
              width: 30, border: "none", borderBottom: "2px solid transparent",
              background: "transparent", color: T.muted,
              fontSize: 13, cursor: "pointer", fontFamily: "inherit",
            }}
          >»</button>
        </div>

        {/* ── Threads tab ── */}
        {sideTab === "threads" && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: "8px 12px", borderBottom: `1px solid ${T.border}`, display: "flex", gap: 6, flexShrink: 0 }}>
              <button onClick={newThread} style={{
                flex: 1, padding: "5px 0", background: `${T.accent}14`,
                border: `1px solid ${T.accent}44`, borderRadius: 6,
                color: T.accent, fontSize: 11, fontWeight: 600,
                cursor: "pointer", fontFamily: "inherit",
              }}>+ New Thread</button>
              {messages.length > 0 && (
                <button onClick={clearChat} style={{
                  padding: "5px 10px", background: "transparent",
                  border: `1px solid ${T.border}`, borderRadius: 6,
                  color: T.muted, fontSize: 11, cursor: "pointer", fontFamily: "inherit",
                }}>× Clear</button>
              )}
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
              {threads.length === 0 && (
                <div style={{ fontSize: 11, color: T.muted, padding: "14px 14px", fontStyle: "italic" }}>No threads yet.</div>
              )}
              {threads.map(t => {
                const active = t.id === currentThreadId;
                return (
                  <div key={t.id} onClick={() => switchThread(t.id)} style={{
                    padding: "8px 14px", cursor: "pointer",
                    background: active ? `${T.accent}14` : "transparent",
                    borderLeft: `2px solid ${active ? T.accent : "transparent"}`,
                    borderBottom: `1px solid ${T.border}22`,
                    transition: "background 0.1s",
                  }}
                    onMouseEnter={e => { if (!active) e.currentTarget.style.background = `${T.border}22`; }}
                    onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
                  >
                    <div style={{ fontSize: 12, color: active ? T.text : T.mutedLt, fontWeight: active ? 600 : 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", lineHeight: 1.4 }}>
                      {t.title || "Untitled"}
                    </div>
                    <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>
                      {t.turn_count} turn{t.turn_count !== 1 ? "s" : ""}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Context tab ── */}
        {sideTab === "context" && (
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>

            {/* Coherence strip */}
            {coherence && (() => {
              const c = coherence.C;
              const color = c >= 0.82 ? T.success : c >= 0.70 ? T.warn : T.error;
              return (
                <div style={{ padding: "10px 14px", borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>
                  <SideLabel>Coherence</SideLabel>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 11, color: T.muted }}>
                    <span style={{ fontVariantNumeric: "tabular-nums", color, fontWeight: 700 }}>C(t) {c?.toFixed(3)}</span>
                    <span>mem <span style={{ color: T.mutedLt }}>{coherence.mem_n}</span></span>
                    <span>reflect <span style={{ color: T.mutedLt }}>{Math.round((coherence.reflection_rate || 0) * 100)}%</span></span>
                    <span>conflict <span style={{ color: T.mutedLt }}>{Math.round((coherence.conflict_rate || 0) * 100)}%</span></span>
                  </div>
                </div>
              );
            })()}

            {/* Live events */}
            {liveEvents.length > 0 && (
              <div style={{ padding: "10px 14px", borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>
                <SideLabel>Live Events</SideLabel>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  {liveEvents.map((ev, i) => {
                    const et    = ev.type || ev.event_type || "event";
                    const u     = et.toUpperCase();
                    const color = u.includes("FAIL") || u.includes("ERROR") ? T.error
                                : u.includes("WARN") || u.includes("BREACH") ? T.warn
                                : u.includes("PASS") || u.includes("COMPLET") ? T.success
                                : T.accent;
                    const label = et.replace(/[._]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
                    const tsRaw = ev.ts || ev.timestamp || 0;
                    const age   = tsRaw ? Math.round(Date.now() / 1000 - tsRaw) : null;
                    return (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 7 }}>
                        <span style={{ width: 5, height: 5, borderRadius: "50%", background: color, flexShrink: 0 }} />
                        <span style={{ fontSize: 11, color: T.mutedLt, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
                        {age != null && age < 3600 && (
                          <span style={{ fontSize: 9, color: T.muted, flexShrink: 0 }}>
                            {age < 60 ? `${age}s` : `${Math.floor(age / 60)}m`}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Agent context panel */}
            <div style={{ flex: 1, minHeight: 0 }}>
              <AgentContextPanel
                lastMeta={lastMeta}
                onApply={handleApplySuggestion}
              />
            </div>
          </div>
        )}

        {/* ── Advanced tab ── */}
        {sideTab === "advanced" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "14px", display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Pinned context */}
            <div>
              <SideLabel>Pinned Context</SideLabel>
              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                background: T.bg, border: `1px solid ${T.border}`,
                borderRadius: 8, padding: "6px 10px",
              }}>
                <span style={{ fontSize: 10, color: T.warn, flexShrink: 0 }}>◆</span>
                <input
                  value={pinnedContext}
                  onChange={e => setPinnedContext(e.target.value)}
                  placeholder="e.g. Working on .NET login page…"
                  style={{ flex: 1, background: "transparent", border: "none", color: T.muted, fontSize: 11, outline: "none", fontFamily: "inherit" }}
                />
                {pinnedContext && (
                  <button onClick={() => setPinnedContext("")} style={{ background: "transparent", border: "none", color: T.error, cursor: "pointer", fontSize: 12, flexShrink: 0 }}>✕</button>
                )}
              </div>
            </div>

            {/* Reasoning */}
            <div>
              <SideLabel>Reasoning</SideLabel>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {[
                  { val: "",      label: "⚡ Auto",  title: "Brain decides",          activeColor: T.warn },
                  { val: "none",  label: "Fast",     title: "No reflection",          activeColor: T.success },
                  { val: "light", label: "Check",    title: "Grounded eval",          activeColor: T.warn },
                  { val: "full",  label: "Deep",     title: "Full reflection",        activeColor: "#C06040" },
                ].map(({ val, label, title, activeColor }) => {
                  const active = reflectMode === val;
                  return (
                    <button key={val} onClick={() => setReflectMode(val)} title={title} style={{
                      padding: "4px 10px", borderRadius: 6, fontSize: 11,
                      fontFamily: "inherit", cursor: "pointer", fontWeight: active ? 700 : 400,
                      border: `1px solid ${active ? activeColor + "55" : T.border}`,
                      background: active ? `${activeColor}22` : T.bg,
                      color: active ? activeColor : T.muted,
                    }}>{label}</button>
                  );
                })}
              </div>
            </div>

            {/* Agent */}
            <div>
              <SideLabel>Agent</SideLabel>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                <button onClick={() => onForcedAgentChange(null)} title="Auto-route" style={{
                  padding: "4px 10px", borderRadius: 6, fontSize: 11, fontFamily: "inherit",
                  border: `1px solid ${!forcedAgent ? T.warn + "55" : T.border}`,
                  background: !forcedAgent ? `${T.warn}22` : T.bg,
                  color: !forcedAgent ? T.warn : T.muted,
                  fontWeight: !forcedAgent ? 700 : 400, cursor: "pointer",
                }}>◈ Auto</button>
                {visibleAgents.map(a => (
                  <button key={a.id} onClick={() => onForcedAgentChange(forcedAgent === a.id ? null : a.id)} title={a.focus} style={{
                    padding: "4px 10px", borderRadius: 6, fontSize: 11, fontFamily: "inherit", cursor: "pointer",
                    border: `1px solid ${forcedAgent === a.id ? a.color + "55" : a.color + "18"}`,
                    background: forcedAgent === a.id ? `${a.color}22` : T.bg,
                    color: forcedAgent === a.id ? a.color : T.muted,
                    fontWeight: forcedAgent === a.id ? 700 : 400,
                  }}>{a.icon} {a.label.split(" ")[0]}</button>
                ))}
              </div>
            </div>

            {/* File attach */}
            <div>
              <SideLabel>Context Files</SideLabel>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={!online}
                style={{
                  width: "100%", padding: "7px 12px", borderRadius: 8,
                  background: T.bg, border: `1px dashed ${T.border}`,
                  color: T.muted, fontSize: 11, cursor: online ? "pointer" : "not-allowed",
                  fontFamily: "inherit", textAlign: "left",
                }}>
                ⊕ Attach file…
              </button>
              <input ref={fileInputRef} type="file" multiple
                accept=".txt,.md,.py,.js,.ts,.jsx,.tsx,.json,.yaml,.yml,.html,.css,.sh,.sql,.csv,.pdf,.toml,.rst"
                onChange={handleFileSelect} style={{ display: "none" }} />
              {attachedFiles.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                  {attachedFiles.map(f => (
                    <div key={f.name} style={{
                      display: "flex", alignItems: "center", gap: 6,
                      background: f.status === "error" ? `${T.error}15` : f.status === "uploading" ? T.surface2 : `${T.accent}15`,
                      border: `1px solid ${f.status === "error" ? `${T.error}55` : f.status === "uploading" ? T.border : `${T.accent}44`}`,
                      borderRadius: 6, padding: "4px 8px", fontSize: 11,
                    }}>
                      <span style={{ color: f.status === "error" ? T.error : f.status === "uploading" ? T.muted : T.accent, fontSize: 12, flexShrink: 0 }}>
                        {f.status === "uploading" ? "⟳" : f.status === "error" ? "⚠" : "▤"}
                      </span>
                      <span style={{ color: T.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                      {f.status === "ready" && f.chunks > 0 && <span style={{ color: T.muted, fontSize: 9, flexShrink: 0 }}>{f.chunks}c</span>}
                      <button onClick={() => setAttachedFiles(prev => prev.filter(x => x.name !== f.name))}
                        style={{ background: "none", border: "none", cursor: "pointer", color: T.muted, padding: "0 2px", fontSize: 12, lineHeight: 1, flexShrink: 0 }}>×</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Export */}
            <div>
              <SideLabel>Export Session</SideLabel>
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={exportSession} disabled={!messages.length} style={{
                  flex: 1, padding: "6px 0", borderRadius: 6, fontSize: 11, fontFamily: "inherit",
                  background: messages.length ? `${T.success}12` : T.bg,
                  border: `1px solid ${messages.length ? `${T.success}44` : T.border}`,
                  color: messages.length ? T.success : T.muted,
                  cursor: messages.length ? "pointer" : "not-allowed", fontWeight: 600,
                }}>↓ Markdown</button>
                <button onClick={exportSessionPDF} disabled={!messages.length} style={{
                  flex: 1, padding: "6px 0", borderRadius: 6, fontSize: 11, fontFamily: "inherit",
                  background: messages.length ? "#0F766E12" : T.bg,
                  border: `1px solid ${messages.length ? "#0F766E44" : T.border}`,
                  color: messages.length ? "#0F766E" : T.muted,
                  cursor: messages.length ? "pointer" : "not-allowed", fontWeight: 600,
                }}>⎙ PDF</button>
              </div>
            </div>

          </div>
        )}

      </div>
      )}{/* ── end side panel ── */}

    </div>
  );
}

// ── Micro button ───────────────────────────────────────────────
function ActionBtn({ onClick, title, active, dim, activeColor = "#15803D", children }) {
  return (
    <button onClick={onClick} title={title} style={{
      background: "transparent", border: "none", cursor: "pointer",
      fontSize: 11, padding: "2px 5px", borderRadius: 4,
      color: active ? activeColor : "#9A7A60",
      opacity: dim ? 0.3 : 1, fontFamily: "inherit",
    }}>
      {children}
    </button>
  );
}
