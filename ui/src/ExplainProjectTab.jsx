import { useState, useCallback } from "react";
import { T, GOLD, LUX, TYPE, FONT_UI, FONT_DISPLAY, FONT_MONO } from "./theme";
import { PageHeader, MetricCard } from "./ObsShared";

import { API } from "./api";

// ── "Explain this project" ─────────────────────────────────────
// The payoff of the debugger→memory bridge: it reads accumulated, structured
// decisions and explains the project back to you. Two things it shows honestly:
//   · the gate — the LLM narrative only appears once the memory-recall benchmark
//     has passed; until then the recorded decisions are shown without synthesis.
//   · confidence — confirmed (you stated a reason) vs tentative (a bare choice).
export default function ExplainProjectTab() {
  // Default to the sticky project set in the Prompt IDE so the bridge and the
  // briefing share one project context out of the box.
  const [project, setProject] = useState(() => {
    try { return localStorage.getItem("amagra_project") || ""; } catch { return ""; }
  });
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
    <div style={{ fontFamily: FONT_UI, color: T.text }}>
      <PageHeader
        title="Explain this project"
        subtitle="A briefing built from the decisions you've recorded — what was chosen, and why."
        gold
      />

      {/* ── Composer ── */}
      <div className="lux-card" style={{ padding: 16, marginBottom: 22, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input
          value={project}
          onChange={e => setProject(e.target.value)}
          onKeyDown={e => e.key === "Enter" && explain()}
          placeholder="Project name (blank = all decisions)"
          style={{ ...TYPE.small, flex: 1, minWidth: 220, padding: "10px 13px", borderRadius: 10, fontFamily: FONT_UI,
                   border: `1px solid ${T.border}`, background: T.surface2, color: T.text, outline: "none" }}
        />
        {/* Ghost button, no disabled dimming — stays visually constant. */}
        <button onClick={explain} disabled={loading} className="btn-ghost"
          style={{ ...TYPE.small, fontWeight: 700, padding: "10px 24px", whiteSpace: "nowrap" }}>
          {loading ? "Reading…" : "Explain"}
        </button>
      </div>

      {error && (
        <div style={{ ...TYPE.small, padding: "12px 15px", borderRadius: 10, color: T.error,
                      background: `${T.error}12`, border: `1.5px solid ${T.error}44`, marginBottom: 18 }}>
          {error} — is the API running on :8000?
        </div>
      )}

      {/* ── Empty state ── */}
      {!data && !loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "40px 20px 8px" }}>
          <div style={{
            width: 64, height: 64, borderRadius: 16, background: LUX.goldTint,
            border: `1px solid ${GOLD.g2}44`, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 28, color: T.accent, fontFamily: FONT_DISPLAY,
          }}>❡</div>
          <div style={{ ...TYPE.body, color: T.text, marginTop: 18, maxWidth: 440 }}>
            Amagra reads the decisions you've recorded and briefs you back on the
            project — what was chosen, and why.
          </div>
          <div style={{ ...TYPE.caption, color: T.muted, marginTop: 10, maxWidth: 440, lineHeight: 1.6 }}>
            Record choices in the Prompt IDE's <em>Run Across Models</em> → <em>Remember this decision</em>.
            Then hit <strong style={{ color: T.accent2 }}>Explain</strong> above.
          </div>
        </div>
      )}

      {data && (
        <>
          {/* ── Counts ── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 20 }}>
            <MetricCard label="Active"    value={data.counts.active}    />
            <MetricCard label="Confirmed" value={data.counts.confirmed} color={T.success} sub="reason recorded" />
            <MetricCard label="Tentative" value={data.counts.tentative} color={T.warn}    sub="bare choice" />
          </div>

          {/* ── Gate-aware briefing ── */}
          <SectionLabel>Briefing</SectionLabel>
          <div className="lux-card" style={{ padding: "18px 20px", marginBottom: 24,
                        borderLeft: `3px solid ${allowed ? T.accent : T.warn}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <span style={{
                ...TYPE.eyebrow, letterSpacing: "0.1em",
                color: allowed ? T.success : T.warn,
                background: (allowed ? T.success : T.warn) + "16",
                border: `1px solid ${(allowed ? T.success : T.warn)}44`,
                borderRadius: 99, padding: "3px 11px",
              }}>
                {allowed ? "✓ Synthesis" : "◔ Synthesis gated"}
              </span>
              {!allowed && (
                <span style={{ ...TYPE.caption, color: T.muted, fontStyle: "italic" }}>
                  narrative unlocks once memory-recall passes its benchmark
                </span>
              )}
            </div>
            {data.summary ? (
              <p style={{ ...TYPE.lead, color: T.text, margin: 0 }}>{data.summary}</p>
            ) : (
              <p style={{ ...TYPE.small, color: T.muted, margin: 0, fontStyle: "italic" }}>
                {data.summary_note || "No summary — the records below are shown without synthesis."}
              </p>
            )}
          </div>

          {/* ── Recorded decisions ── */}
          <SectionLabel>
            Recorded decisions{data.decisions.length ? ` · ${data.decisions.length}` : ""}
          </SectionLabel>
          {data.decisions.length === 0 ? (
            <p style={{ ...TYPE.small, color: T.muted }}>
              None yet — make choices in the Prompt IDE's “Run Across Models” and tap “Remember this decision”.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {data.decisions.map(d => {
                const confirmed = d.provenance === "explicit";
                const accent = confirmed ? T.success : T.warn;
                const model = d.chosen_model ? `${d.chosen_provider} / ${d.chosen_model}` : d.chosen_provider;
                const why = d.rationale || (d.rationale_tags || []).join(", ") || "no reason recorded";
                return (
                  <div key={d.id} className="lux-card" style={{ padding: "13px 15px", borderLeft: `3px solid ${accent}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                      <span style={{ ...TYPE.small, fontFamily: FONT_MONO, fontWeight: 600, color: T.text }}>{model}</span>
                      <span style={{ ...TYPE.eyebrow, letterSpacing: "0.04em",
                                     padding: "2px 9px", borderRadius: 99,
                                     color: accent, border: `1px solid ${accent}44`, background: accent + "14" }}>
                        {confirmed ? "Confirmed" : "Tentative"}
                      </span>
                    </div>
                    <div style={{ ...TYPE.small, color: T.mutedLt, marginTop: 5 }}>{why}</div>
                    {d.prompt && (
                      <div style={{ ...TYPE.caption, color: T.muted, marginTop: 6, fontFamily: FONT_MONO,
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

// ── Section label (gold rule, matches HomeTab/Consensus convention) ──
function SectionLabel({ children }) {
  return (
    <div style={{
      ...TYPE.eyebrow, color: T.accent,
      marginBottom: 12, display: "flex", alignItems: "center", gap: 12,
    }}>
      <span>{children}</span>
      <span style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${GOLD.g2}55 0%, ${T.border} 60%, transparent 100%)` }} />
    </div>
  );
}
