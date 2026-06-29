import { useState } from "react";
import { T, LUX, GOLD, FONT_DISPLAY } from "./theme";

import { API } from "./api";

// Consensus Engine — ask several models the same thing, then show how much they
// AGREE. The debugger's divergence view turned into a trust feature: the result
// reads as "consensus" or "models disagree, here's where", never a bare pick.

const VERDICT = {
  consensus: { label: "Consensus",       color: T.success, blurb: "The models substantially agree." },
  partial:   { label: "Partial",         color: T.warn,    blurb: "Broad overlap, with some divergence." },
  divergent: { label: "Models disagree", color: T.error,   blurb: "The answers materially differ — read them side by side." },
  single:    { label: "Single answer",   color: T.muted,   blurb: "Only one answer — nothing to compare." },
  error:     { label: "Answers only",    color: T.muted,   blurb: "Agreement analysis unavailable (is Ollama running?)." },
};

// Prompts that actually reward a second opinion — seed the empty state.
const SEEDS = [
  "Is it safe to store JWTs in localStorage?",
  "Explain the CAP theorem in one paragraph.",
  "Worst-case time complexity of quicksort, and why?",
];

export default function ConsensusTab() {
  const [prompt, setPrompt]    = useState("");
  const [system, setSystem]    = useState("");
  const [synthesize, setSynth] = useState(true);
  const [loading, setLoading]  = useState(false);
  const [res, setRes]          = useState(null);
  const [err, setErr]          = useState(null);

  const run = async () => {
    if (!prompt.trim() || loading) return;
    setLoading(true); setErr(null); setRes(null);
    try {
      const r = await fetch(`${API}/consensus`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, system: system || null, synthesize }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setRes(await r.json());
    } catch (e) {
      setErr(e.message || "Request failed");
    }
    setLoading(false);
  };

  const v   = res ? (VERDICT[res.verdict] || VERDICT.error) : null;
  const pct = res?.agreement_score != null ? Math.round(res.agreement_score * 100) : null;

  return (
    <div style={{ animation: "fadeIn .2s" }}>
      {/* ── Header ── */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{
          margin: 0, fontSize: 30, fontWeight: 600, fontFamily: FONT_DISPLAY, letterSpacing: "0.01em",
          // Brighter gold than LUX.goldText — ends at deep gold g4, never the
          // dark-brown g5, so a short word reads luminous, not muddy.
          background: `linear-gradient(135deg, ${GOLD.g4} 0%, ${GOLD.g3} 28%, ${GOLD.g2} 50%, ${GOLD.g3} 72%, ${GOLD.g4} 100%)`,
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
          filter: "drop-shadow(0 1px 4px rgba(154,108,0,0.16))",
        }}>
          Consensus
        </h1>
        <p style={{ margin: "7px 0 0", fontSize: 13.5, color: T.mutedLt, lineHeight: 1.6, maxWidth: 660 }}>
          Ask several models the same question and see how much they agree — the full
          agreement shown, not hidden. When it matters, verify before you trust.
        </p>
      </div>

      {/* ── Composer ── */}
      <div className="lux-card" style={{ padding: 20, marginBottom: 22 }}>
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") run(); }}
          placeholder="Ask something worth verifying…"
          rows={3}
          style={{
            width: "100%", background: T.surface2, border: `1px solid ${T.border}`,
            borderRadius: 11, padding: "12px 14px", fontSize: 14.5, color: T.text,
            fontFamily: "inherit", resize: "vertical", outline: "none", lineHeight: 1.6,
          }}
        />
        <input
          value={system}
          onChange={e => setSystem(e.target.value)}
          placeholder="System prompt (optional)"
          style={{
            width: "100%", marginTop: 9, background: T.surface2, border: `1px solid ${T.border}`,
            borderRadius: 10, padding: "9px 14px", fontSize: 12, color: T.text,
            fontFamily: "inherit", outline: "none",
          }}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 14, flexWrap: "wrap" }}>
          {/* No disabled dimming — the button stays visually constant; it simply
              does nothing until there's a prompt to run. */}
          <button className="btn-ghost" onClick={run} disabled={!prompt.trim() || loading}
            style={{ padding: "10px 24px", fontSize: 13 }}>
            {loading ? "Consulting models…" : "Find consensus"}
          </button>
          <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: T.mutedLt, cursor: "pointer" }}>
            <input type="checkbox" checked={synthesize} onChange={e => setSynth(e.target.checked)}
              style={{ accentColor: T.accent, cursor: "pointer" }} />
            Synthesize a merged answer
          </label>
          <span style={{ marginLeft: "auto", fontSize: 11, color: T.muted }}>
            ⌘↵ to run · models from Settings → Model
          </span>
        </div>
      </div>

      {/* ── Empty state — seed prompts before the first run ── */}
      {!res && !loading && !err && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "32px 20px 8px" }}>
          <GaugeRing pct={null} color={T.border} idle />
          <div style={{ fontSize: 14, color: T.mutedLt, marginTop: 18, maxWidth: 420, lineHeight: 1.6 }}>
            Run a prompt across your models. You'll get one agreement score and every
            answer side by side — with the dissenters flagged.
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", marginTop: 18 }}>
            {SEEDS.map(s => (
              <button key={s} onClick={() => setPrompt(s)} className="lux-card lux-card-i"
                style={{ padding: "8px 14px", fontSize: 12, color: T.mutedLt, cursor: "pointer", fontFamily: "inherit" }}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 20px" }}>
          <GaugeRing pct={null} color={GOLD.g3} spinning />
          <div style={{ fontSize: 13, color: T.muted, marginTop: 16 }}>Consulting models…</div>
        </div>
      )}

      {err && (
        <div style={{ padding: "12px 16px", background: `${T.error}12`, border: `1.5px solid ${T.error}44`,
                      borderRadius: 10, color: T.error, fontSize: 13, marginBottom: 18 }}>
          {err}
        </div>
      )}

      {res && (
        <>
          {/* ── Verdict hero: gauge + read-out ── */}
          <div className="lux-card" style={{
            padding: 22, marginBottom: 16,
            display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap",
          }}>
            {pct != null && <GaugeRing pct={pct} color={v.color} />}
            <div style={{ flex: 1, minWidth: 240 }}>
              <span style={{
                display: "inline-block", fontSize: 12, fontWeight: 700, color: v.color,
                background: `${v.color}18`, border: `1px solid ${v.color}44`,
                borderRadius: 99, padding: "4px 14px", marginBottom: 9,
              }}>{v.label}</span>
              <div style={{ fontSize: 14.5, color: T.text, lineHeight: 1.55 }}>
                {res.summary || v.blurb}
              </div>
              {res.note && <div style={{ fontSize: 11.5, color: T.muted, marginTop: 6, fontStyle: "italic" }}>{res.note}</div>}
            </div>
          </div>

          {/* ── Synthesized consensus answer ── */}
          {res.consensus_answer && (
            <div className="lux-card" style={{ padding: 20, marginBottom: 22, borderLeft: `3px solid ${T.accent}` }}>
              <div style={{ fontSize: 10, fontWeight: 800, color: T.accent, textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: 10 }}>
                Consensus answer{res.synthesized_by ? ` · judged by ${res.synthesized_by}` : ""}
              </div>
              <div style={{ fontSize: 14.5, color: T.text, lineHeight: 1.68, whiteSpace: "pre-wrap" }}>
                {res.consensus_answer}
              </div>
              {res.contradiction_note && (
                <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${T.border}`, fontSize: 12.5, color: T.warn, lineHeight: 1.55 }}>
                  <strong style={{ color: T.warn }}>Where they differ:</strong> {res.contradiction_note}
                </div>
              )}
            </div>
          )}

          {/* ── Candidates — side by side ── */}
          <div style={{
            fontSize: 10, fontWeight: 800, color: T.accent, letterSpacing: "0.14em",
            textTransform: "uppercase", marginBottom: 14, display: "flex", alignItems: "center", gap: 12,
          }}>
            <span>{res.candidates.length} model{res.candidates.length !== 1 ? "s" : ""} consulted</span>
            <span style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${GOLD.g2}55 0%, ${T.border} 60%, transparent 100%)` }} />
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            gap: 14, alignItems: "start",
          }}>
            {res.candidates.map((c, i) => {
              const isRep  = i === res.representative_index;
              const isDis  = (res.dissenters || []).includes(i);
              const accent = c.error ? T.error : isDis ? T.warn : isRep ? T.success : T.border;
              const agr    = c.agreement != null ? Math.round(c.agreement * 100) : null;
              return (
                <div key={i} className="lux-card" style={{ padding: 16, borderTop: `3px solid ${accent}`, display: "flex", flexDirection: "column" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{c.provider}</span>
                    {isRep && <Tag color={T.success}>★ representative</Tag>}
                    {isDis && <Tag color={T.warn}>⚠ dissenter</Tag>}
                    {c.error && <Tag color={T.error}>error</Tag>}
                  </div>
                  {c.model && <div style={{ fontSize: 11, color: T.muted, marginBottom: 10 }}>{c.model}</div>}

                  {/* per-model agreement bar */}
                  {agr != null && (
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, marginBottom: 4 }}>
                        <span style={{ color: T.muted, letterSpacing: "0.04em" }}>AGREEMENT</span>
                        <span style={{ color: accent, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>{agr}%</span>
                      </div>
                      <div style={{ height: 5, borderRadius: 99, background: T.surface2, overflow: "hidden" }}>
                        <div style={{ width: `${agr}%`, height: "100%", borderRadius: 99, background: accent, transition: "width .4s ease-out" }} />
                      </div>
                    </div>
                  )}

                  <div style={{ fontSize: 13, color: c.error ? T.error : T.mutedLt, lineHeight: 1.6, whiteSpace: "pre-wrap", flex: 1 }}>
                    {c.error || c.output}
                  </div>

                  {(c.latency_ms != null || c.words != null) && (
                    <div style={{ display: "flex", gap: 14, marginTop: 12, paddingTop: 10, borderTop: `1px solid ${T.border}`,
                                  fontSize: 10.5, color: T.muted, fontVariantNumeric: "tabular-nums" }}>
                      {c.latency_ms != null && <span>{c.latency_ms}ms</span>}
                      {c.words != null && <span>{c.words} words</span>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── Circular agreement gauge ────────────────────────────────────
function GaugeRing({ pct, color, idle, spinning }) {
  const R = 38, SW = 7, C = 2 * Math.PI * R;
  const filled = pct != null ? C * (1 - pct / 100) : C * 0.72; // idle/spin: partial arc
  return (
    <div style={{ position: "relative", width: 96, height: 96, flexShrink: 0 }}>
      <svg width="96" height="96" viewBox="0 0 96 96" style={{ animation: spinning ? "spin 1.1s linear infinite" : "none" }}>
        <circle cx="48" cy="48" r={R} fill="none" stroke={T.surface2} strokeWidth={SW} />
        <circle
          cx="48" cy="48" r={R} fill="none" stroke={color} strokeWidth={SW} strokeLinecap="round"
          strokeDasharray={C} strokeDashoffset={filled}
          transform="rotate(-90 48 48)"
          style={{ transition: "stroke-dashoffset .6s cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      {!spinning && (
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          {idle ? (
            <span style={{ fontSize: 22, color: T.muted, fontFamily: FONT_DISPLAY }}>?</span>
          ) : (
            <>
              <span style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{pct}</span>
              <span style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginTop: 3 }}>agree</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Tag({ color, children }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, color, background: `${color}18`,
      border: `1px solid ${color}44`, borderRadius: 99, padding: "2px 9px",
    }}>{children}</span>
  );
}
