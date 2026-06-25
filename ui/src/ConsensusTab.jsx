import { useState } from "react";
import { T, LUX, GOLD, FONT_DISPLAY } from "./theme";

const API = "http://localhost:8000";

// Consensus Engine — ask several models the same thing, then show how much they
// AGREE. The debugger's divergence view turned into a trust feature: the result
// reads as "consensus" or "models disagree, here's where", never a bare pick.

const VERDICT = {
  consensus: { label: "Consensus",   color: T.success, blurb: "The models substantially agree." },
  partial:   { label: "Partial",     color: T.warn,    blurb: "Broad overlap, with some divergence." },
  divergent: { label: "Models disagree", color: T.error, blurb: "The answers materially differ — read them side by side." },
  single:    { label: "Single answer", color: T.muted,  blurb: "Only one answer — nothing to compare." },
  error:     { label: "Answers only",  color: T.muted,  blurb: "Agreement analysis unavailable (is Ollama running?)." },
};

export default function ConsensusTab() {
  const [prompt, setPrompt]       = useState("");
  const [system, setSystem]       = useState("");
  const [synthesize, setSynth]    = useState(true);
  const [loading, setLoading]     = useState(false);
  const [res, setRes]             = useState(null);
  const [err, setErr]             = useState(null);

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

  const v = res ? (VERDICT[res.verdict] || VERDICT.error) : null;
  const pct = res?.agreement_score != null ? Math.round(res.agreement_score * 100) : null;

  return (
    <div style={{ animation: "fadeIn .2s" }}>
      {/* ── Header ── */}
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ margin: 0, fontSize: 26, fontWeight: 600, fontFamily: FONT_DISPLAY, ...LUX.goldText }}>
          Consensus
        </h1>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: T.mutedLt, lineHeight: 1.6, maxWidth: 640 }}>
          Ask several models the same question and see how much they agree — with the
          full agreement shown, not hidden. When it matters, verify before you trust.
        </p>
      </div>

      {/* ── Composer ── */}
      <div className="lux-card" style={{ padding: 18, marginBottom: 22 }}>
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Ask something worth verifying…"
          rows={3}
          style={{
            width: "100%", background: T.surface2, border: `1px solid ${T.border}`,
            borderRadius: 10, padding: "11px 13px", fontSize: 14, color: T.text,
            fontFamily: "inherit", resize: "vertical", outline: "none", lineHeight: 1.6,
          }}
        />
        <input
          value={system}
          onChange={e => setSystem(e.target.value)}
          placeholder="System prompt (optional)"
          style={{
            width: "100%", marginTop: 8, background: T.surface2, border: `1px solid ${T.border}`,
            borderRadius: 10, padding: "8px 13px", fontSize: 12, color: T.text,
            fontFamily: "inherit", outline: "none",
          }}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 12 }}>
          <button className="btn-gold" onClick={run} disabled={!prompt.trim() || loading}
            style={{ padding: "9px 22px", fontSize: 13, opacity: (!prompt.trim() || loading) ? 0.55 : 1 }}>
            {loading ? "Consulting models…" : "Find consensus"}
          </button>
          <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: T.mutedLt, cursor: "pointer" }}>
            <input type="checkbox" checked={synthesize} onChange={e => setSynth(e.target.checked)}
              style={{ accentColor: T.accent, cursor: "pointer" }} />
            Synthesize a merged answer
          </label>
          <span style={{ marginLeft: "auto", fontSize: 11, color: T.muted }}>
            Uses the models configured in Settings → Model
          </span>
        </div>
      </div>

      {err && (
        <div style={{ padding: "11px 15px", background: "#F9E7E1", border: `1.5px solid ${T.error}44`,
                      borderRadius: 8, color: T.error, fontSize: 13, marginBottom: 18 }}>
          {err}
        </div>
      )}

      {res && (
        <>
          {/* ── Verdict ── */}
          <div className="lux-card" style={{ padding: 18, marginBottom: 18, display: "flex", alignItems: "center", gap: 18 }}>
            {pct != null && (
              <div style={{ textAlign: "center", flexShrink: 0, minWidth: 86 }}>
                <div style={{ fontSize: 34, fontWeight: 800, color: v.color, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>
                  {pct}<span style={{ fontSize: 16 }}>%</span>
                </div>
                <div style={{ fontSize: 9, color: T.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginTop: 4 }}>
                  agreement
                </div>
              </div>
            )}
            <div style={{ flex: 1 }}>
              <span style={{
                display: "inline-block", fontSize: 12, fontWeight: 700, color: v.color,
                background: `${v.color}18`, border: `1px solid ${v.color}44`,
                borderRadius: 99, padding: "3px 13px", marginBottom: 6,
              }}>{v.label}</span>
              <div style={{ fontSize: 13, color: T.mutedLt, lineHeight: 1.55 }}>
                {res.summary || v.blurb}
              </div>
              {res.note && <div style={{ fontSize: 11, color: T.muted, marginTop: 5, fontStyle: "italic" }}>{res.note}</div>}
            </div>
          </div>

          {/* ── Synthesized consensus answer ── */}
          {res.consensus_answer && (
            <div className="lux-card" style={{ padding: 18, marginBottom: 18, borderLeft: `3px solid ${T.accent}` }}>
              <div style={{ fontSize: 10, fontWeight: 800, color: T.accent, textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: 8 }}>
                Consensus answer{res.synthesized_by ? ` · judged by ${res.synthesized_by}` : ""}
              </div>
              <div style={{ fontSize: 14, color: T.text, lineHeight: 1.65, whiteSpace: "pre-wrap" }}>
                {res.consensus_answer}
              </div>
              {res.contradiction_note && (
                <div style={{ marginTop: 12, paddingTop: 10, borderTop: `1px solid ${T.border}`, fontSize: 12.5, color: T.warn, lineHeight: 1.55 }}>
                  <strong style={{ color: T.warn }}>Where they differ:</strong> {res.contradiction_note}
                </div>
              )}
            </div>
          )}

          {/* ── Candidates ── */}
          <div style={{ fontSize: 10, fontWeight: 800, color: T.accent, letterSpacing: "0.14em",
                        textTransform: "uppercase", marginBottom: 12 }}>
            {res.candidates.length} model{res.candidates.length !== 1 ? "s" : ""} consulted
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {res.candidates.map((c, i) => {
              const isRep   = i === res.representative_index;
              const isDis   = (res.dissenters || []).includes(i);
              const accent  = c.error ? T.error : isDis ? T.warn : isRep ? T.success : T.border;
              const agr     = c.agreement != null ? Math.round(c.agreement * 100) : null;
              return (
                <div key={i} className="lux-card" style={{ padding: 16, borderLeft: `3px solid ${accent}` }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>
                      {c.provider}{c.model ? ` · ${c.model}` : ""}
                    </span>
                    {isRep && <Tag color={T.success}>★ most representative</Tag>}
                    {isDis && <Tag color={T.warn}>⚠ dissenter</Tag>}
                    {c.error && <Tag color={T.error}>error</Tag>}
                    <span style={{ marginLeft: "auto", display: "flex", gap: 12, fontSize: 11, color: T.muted, fontVariantNumeric: "tabular-nums" }}>
                      {agr != null && <span style={{ color: accent, fontWeight: 700 }}>{agr}% match</span>}
                      {c.latency_ms != null && <span>{c.latency_ms}ms</span>}
                      {c.words != null && <span>{c.words}w</span>}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: c.error ? T.error : T.mutedLt, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                    {c.error || c.output}
                  </div>
                </div>
              );
            })}
          </div>
        </>
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
