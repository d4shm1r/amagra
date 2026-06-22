import { useState, useCallback } from "react";
import { T, FONT_UI, FONT_DISPLAY, FONT_MONO } from "./theme";

const API = "http://localhost:8000";

// ── "Explain this project" ─────────────────────────────────────
// The payoff of the debugger→memory bridge: it reads accumulated, structured
// decisions and explains the project back to you. Two things it shows honestly:
//   · the gate — the LLM narrative only appears once the memory-recall benchmark
//     has passed; until then the recorded decisions are shown without synthesis.
//   · confidence — confirmed (you stated a reason) vs tentative (a bare choice).
export default function ExplainProjectTab() {
  const [project, setProject] = useState("");
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const explain = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API}/project/explain?project=${encodeURIComponent(project)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [project]);

  const allowed = data?.synthesis_allowed;

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", fontFamily: FONT_UI, color: T.text }}>
      <h1 style={{ fontFamily: FONT_DISPLAY, fontSize: 30, fontWeight: 600, color: T.accent,
                   margin: "0 0 4px", letterSpacing: 0.2 }}>
        Explain this project
      </h1>
      <p style={{ fontSize: 13, color: T.mutedLt, margin: "0 0 20px", lineHeight: 1.6 }}>
        A briefing built from the decisions you've recorded — what was chosen, and why.
      </p>

      {/* Project selector */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input
          value={project}
          onChange={e => setProject(e.target.value)}
          onKeyDown={e => e.key === "Enter" && explain()}
          placeholder="Project name (blank = all decisions)"
          style={{ flex: 1, padding: "9px 12px", borderRadius: 6, fontFamily: FONT_UI, fontSize: 13,
                   border: `1px solid ${T.border}`, background: T.surface, color: T.text }}
        />
        <button
          onClick={explain} disabled={loading}
          style={{ padding: "9px 20px", borderRadius: 6, fontFamily: FONT_UI, fontSize: 13, fontWeight: 600,
                   border: `1px solid ${T.accent}`, background: T.accent, color: "#fff",
                   cursor: loading ? "default" : "pointer" }}>
          {loading ? "Reading…" : "Explain"}
        </button>
      </div>

      {error && (
        <div style={{ padding: "10px 12px", borderRadius: 6, fontSize: 12.5, color: T.error,
                      background: `${T.error}0E`, border: `1px solid ${T.error}33` }}>
          {error} — is the API running on :8000?
        </div>
      )}

      {data && (
        <>
          {/* Counts */}
          <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
            {[
              ["Active",    data.counts.active,    T.text],
              ["Confirmed", data.counts.confirmed, T.success],
              ["Tentative", data.counts.tentative, T.warn],
            ].map(([label, n, c]) => (
              <div key={label} style={{ flex: 1, textAlign: "center", padding: "10px 0", borderRadius: 8,
                                        background: T.surface2, border: `1px solid ${T.border}` }}>
                <div style={{ fontFamily: FONT_DISPLAY, fontSize: 24, fontWeight: 600, color: c }}>{n}</div>
                <div style={{ fontSize: 10.5, color: T.muted, letterSpacing: 0.4, textTransform: "uppercase" }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Gate-aware summary */}
          <div style={{ borderRadius: 10, padding: "16px 18px", marginBottom: 18,
                        background: T.surface,
                        border: `1px solid ${allowed ? T.accent + "55" : T.border}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase",
                             color: allowed ? T.success : T.warn }}>
                {allowed ? "✓ Synthesis" : "◔ Synthesis gated"}
              </span>
            </div>
            {data.summary ? (
              <p style={{ fontSize: 14, lineHeight: 1.7, color: T.text, margin: 0 }}>{data.summary}</p>
            ) : (
              <p style={{ fontSize: 12.5, lineHeight: 1.6, color: T.muted, margin: 0, fontStyle: "italic" }}>
                {data.summary_note || "No summary."}
              </p>
            )}
          </div>

          {/* The recorded decisions — always shown (the user's own records) */}
          <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: 17, fontWeight: 600, color: T.mutedLt,
                       margin: "0 0 10px" }}>
            Recorded decisions
          </h2>
          {data.decisions.length === 0 ? (
            <p style={{ fontSize: 12.5, color: T.muted }}>
              None yet — make choices in the Prompt IDE's “Run Across Models” and tap “Remember this decision”.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {data.decisions.map(d => {
                const confirmed = d.provenance === "explicit";
                const model = d.chosen_model ? `${d.chosen_provider} / ${d.chosen_model}` : d.chosen_provider;
                const why = d.rationale || (d.rationale_tags || []).join(", ") || "no reason recorded";
                return (
                  <div key={d.id} style={{ borderRadius: 8, padding: "10px 12px", background: T.surface,
                                           border: `1px solid ${T.border}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                      <span style={{ fontFamily: FONT_MONO, fontSize: 12.5, fontWeight: 600, color: T.text }}>{model}</span>
                      <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: 0.3, textTransform: "uppercase",
                                     padding: "2px 7px", borderRadius: 10,
                                     color: confirmed ? T.success : T.warn,
                                     background: (confirmed ? T.success : T.warn) + "16" }}>
                        {confirmed ? "Confirmed" : "Tentative"}
                      </span>
                    </div>
                    <div style={{ fontSize: 12.5, color: T.mutedLt, marginTop: 4, lineHeight: 1.5 }}>{why}</div>
                    {d.prompt && (
                      <div style={{ fontSize: 11, color: T.muted, marginTop: 4, fontFamily: FONT_MONO,
                                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {d.prompt}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
