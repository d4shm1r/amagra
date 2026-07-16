import { useState, useEffect, useCallback, useRef } from "react";
import { T, LUX, GOLD, FONT_DISPLAY, FONT_MONO, Z } from "@/styles/theme";

// First-run setup wizard. Shown once (gated by localStorage in App), it walks a
// new user through the only two things that can block a first answer: Ollama
// running, and the required models present. Then it hands off a guided first
// prompt into Chat.
//
// Props:
//   apiBase    — API origin (e.g. http://localhost:8000)
//   onDismiss  — mark onboarding complete and close the overlay
//   onStart    — (promptText) => seed Chat with this prompt and navigate there

import { API as API_BASE } from "@/lib/api";

const FIRST_PROMPTS = [
  "What can you help me with?",
  "Explain how your memory works in one paragraph.",
  "Write a Python function that deduplicates a list while preserving order.",
];

function Bar({ percent }) {
  return (
    <div style={{ height: 6, borderRadius: 99, background: T.surface2, overflow: "hidden" }}>
      <div style={{
        height: "100%",
        width: `${percent ?? 0}%`,
        background: `linear-gradient(90deg, ${GOLD.g4}, ${GOLD.g2})`,
        transition: "width 0.25s ease",
      }} />
    </div>
  );
}

export default function Onboarding({ apiBase = API_BASE, onDismiss, onStart }) {
  const [status, setStatus]   = useState(null);   // /setup/status payload
  const [loading, setLoading] = useState(true);
  const [pulling, setPulling] = useState({});     // model -> { percent, status, error, done }
  const esRef = useRef({});

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${apiBase}/setup/status`, { signal: AbortSignal.timeout(6000) });
      setStatus(await r.json());
    } catch {
      setStatus({ ollama: "offline", ready: false, required: [], missing: [], hint: "Could not reach the API on :8000." });
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  // Clean up any open pull streams on unmount.
  useEffect(() => () => { Object.values(esRef.current).forEach(es => es?.close?.()); }, []);

  const pull = useCallback((model) => {
    setPulling(p => ({ ...p, [model]: { percent: 0, status: "starting…", error: null, done: false } }));

    // EventSource can't POST, so stream via fetch + ReadableStream reader.
    fetch(`${apiBase}/setup/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    }).then(async (resp) => {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const events = buf.split("\n\n");
        buf = events.pop() ?? "";
        for (const evt of events) {
          const line = evt.split("\n").find(l => l.startsWith("data: "));
          if (!line) continue;
          let msg;
          try { msg = JSON.parse(line.slice(6)); } catch { continue; }
          if (msg.type === "error") {
            setPulling(p => ({ ...p, [model]: { ...p[model], error: msg.detail } }));
          } else if (msg.type === "done") {
            setPulling(p => ({ ...p, [model]: { ...p[model], percent: 100, status: "done", done: true } }));
            fetchStatus();
          } else if (msg.type === "progress") {
            setPulling(p => ({ ...p, [model]: { ...p[model], percent: msg.percent ?? p[model]?.percent ?? 0, status: msg.status } }));
          }
        }
      }
    }).catch((e) => {
      setPulling(p => ({ ...p, [model]: { ...p[model], error: String(e) } }));
    });
  }, [apiBase, fetchStatus]);

  const ready = status?.ready;

  return (
    <div style={overlay}>
      <div style={card}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontFamily: FONT_DISPLAY, fontSize: 40, fontWeight: 600, ...LUX.goldText }}>
            Welcome to Amagra
          </div>
          <div style={{ color: T.mutedLt, marginTop: 8, fontSize: 15, lineHeight: 1.5 }}>
            Your private AI workspace. It runs entirely on your own computer —
            nothing you ask leaves your machine. Let's get it ready.
          </div>
        </div>

        {/* Step 1 — Engine */}
        <Step
          n={1}
          title="Starting the engine"
          done={status && status.ollama === "online"}
          loading={loading}
        >
          {status?.ollama === "online" ? (
            <span style={{ color: T.success }}>Ready — the local engine is running.</span>
          ) : (
            <div>
              <div style={{ color: T.error, marginBottom: 8 }}>The local engine isn't running yet.</div>
              <div style={{ color: T.mutedLt, fontSize: 13 }}>
                Amagra uses a free, on-device engine called Ollama. Open a terminal,
                paste the line below, then come back and re-check:
              </div>
              <code style={codeBlock}>ollama serve</code>
              <button style={ghostBtn} onClick={fetchStatus}>Re-check</button>
            </div>
          )}
        </Step>

        {/* Step 2 — Model download */}
        <Step
          n={2}
          title="Getting the AI model"
          done={status && status.ollama === "online" && status.missing?.length === 0}
          loading={loading}
          disabled={status?.ollama !== "online"}
        >
          {status?.ollama !== "online" ? (
            <span style={{ color: T.muted }}>Waiting for the engine…</span>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ color: T.mutedLt, fontSize: 13, marginBottom: 2 }}>
                {status.missing?.length === 0
                  ? "Everything Amagra needs is already installed."
                  : "Download the model Amagra thinks with — a one-time setup. It stays on your computer."}
              </div>
              {(status.required || []).map((m) => {
                const isMissing = (status.missing || []).includes(m);
                const pp = pulling[m];
                return (
                  <div key={m} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                      <code style={{ fontFamily: FONT_MONO, fontSize: 13, color: T.text }}>{m}</code>
                      {!isMissing ? (
                        <span style={{ color: T.success, fontSize: 13 }}>✓ installed</span>
                      ) : pp && !pp.error && !pp.done ? (
                        <span style={{ color: T.muted, fontSize: 12 }}>{pp.status} {pp.percent ? `· ${pp.percent}%` : ""}</span>
                      ) : (
                        <button style={ghostBtn} onClick={() => pull(m)} disabled={pp && !pp.error}>
                          {pp?.error ? "Retry" : "Download"}
                        </button>
                      )}
                    </div>
                    {isMissing && pp && !pp.error && <Bar percent={pp.percent} />}
                    {pp?.error && <div style={{ color: T.error, fontSize: 12 }}>{pp.error}</div>}
                  </div>
                );
              })}
            </div>
          )}
        </Step>

        {/* Step 3 — First prompt */}
        <Step n={3} title="Ask your first question" done={false} loading={false} disabled={!ready}>
          {!ready ? (
            <span style={{ color: T.muted }}>Finish the steps above to begin.</span>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ color: T.mutedLt, fontSize: 13, marginBottom: 2 }}>Pick one to start — or skip and explore.</div>
              {FIRST_PROMPTS.map((p) => (
                <button key={p} style={promptChip} onClick={() => { onStart?.(p); onDismiss?.(); }}>
                  {p}
                </button>
              ))}
            </div>
          )}
        </Step>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 24 }}>
          <button style={skipBtn} onClick={onDismiss}>Skip for now</button>
          <button
            style={{ ...primaryBtn, opacity: ready ? 1 : 0.5, cursor: ready ? "pointer" : "not-allowed" }}
            onClick={onDismiss}
            disabled={!ready}
          >
            Open dashboard →
          </button>
        </div>
      </div>
    </div>
  );
}

function Step({ n, title, done, loading, disabled, children }) {
  return (
    <div style={{ ...stepRow, opacity: disabled ? 0.55 : 1 }}>
      <div style={{ ...badge, background: done ? T.success : disabled ? T.surface2 : LUX.goldTint, color: done ? "#fff" : T.accent2 }}>
        {done ? "✓" : n}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, color: T.text, marginBottom: 6 }}>
          {title}{loading && !done ? " …" : ""}
        </div>
        {children}
      </div>
    </div>
  );
}

const overlay = {
  position: "fixed", inset: 0, zIndex: Z.modal,
  background: "rgba(46, 32, 16, 0.42)", backdropFilter: "blur(6px)",
  display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
};
const card = {
  width: "min(560px, 96vw)", maxHeight: "92vh", overflowY: "auto",
  background: T.surface, border: `1px solid ${T.border}`, borderRadius: 20,
  padding: "36px 40px", boxShadow: LUX.shadowLg,
};
const stepRow = { display: "flex", gap: 14, padding: "16px 0", borderTop: `1px solid ${T.border}` };
const badge = {
  width: 28, height: 28, borderRadius: 99, flexShrink: 0,
  display: "flex", alignItems: "center", justifyContent: "center",
  fontWeight: 700, fontSize: 14,
};
const codeBlock = {
  display: "block", fontFamily: FONT_MONO, fontSize: 13, color: T.text,
  background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 8,
  padding: "8px 12px", margin: "8px 0",
};
const ghostBtn = {
  fontSize: 13, fontWeight: 600, color: T.accent2, cursor: "pointer",
  background: "transparent", border: `1px solid ${T.accent}`, borderRadius: 8, padding: "5px 12px",
};
const promptChip = {
  textAlign: "left", fontSize: 14, color: T.text, cursor: "pointer",
  background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 10, padding: "10px 14px",
};
const skipBtn = { fontSize: 13, color: T.muted, background: "transparent", border: "none", cursor: "pointer" };
const primaryBtn = {
  fontSize: 14, fontWeight: 600, color: "#fff", background: T.accent,
  border: "none", borderRadius: 10, padding: "9px 18px",
};
