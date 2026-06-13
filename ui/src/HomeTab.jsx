import { useState, useEffect } from "react";
import { T } from "./theme";
import { BUILD_PHASES, ROADMAP } from "./constants";

// ── Feature pillars ─────────────────────────────────────────────
const FEATURES = [
  {
    sym: "⊕",
    color: "#C48808",
    title: "Signal-First Routing",
    body: "Classifies every query by domain, shape, and verbosity before reaching the LLM — routing happens in under 1ms. Verified at 99% accuracy via ablation eval against 3,400+ test cases.",
    pills: ["99% accuracy", "<1ms routing", "Ablation-verified"],
  },
  {
    sym: "⬡",
    color: "#1E5A8A",
    title: "10 Specialist Agents",
    body: "Python Dev, .NET/Blazor Dev, IT Networking, AI/ML, Web Dev, DevOps, Data Analyst, Writer, Knowledge Learning, and Terse — each domain-tuned with per-agent memory and tooling via LangGraph.",
    pills: ["LangGraph", "Domain-tuned", "Per-agent memory"],
  },
  {
    sym: "⊞",
    color: "#047857",
    title: "Semantic Memory",
    body: "FAISS vector index with nomic-embed-text embeddings. LRU cache delivers 52× retrieval speedup. Automatic dedup (cosine > 0.93) keeps vectors clean. Outcome-weighted quality scoring.",
    pills: ["FAISS vectors", "52× LRU speedup", "Outcome-weighted"],
  },
  {
    sym: "◷",
    color: "#BE185D",
    title: "Reflection & Learning",
    body: "C1-smooth learning kernel with sigmoid adaptive alpha. Triaged reflection dropped the full-reflection rate from 58% to 15%. Dual-trajectory eval for code agents picks the better of two candidates.",
    pills: ["58%→15% full-reflect", "C1-smooth kernel", "Dual-trajectory"],
  },
  {
    sym: "Ψ",
    color: "#6D28D9",
    title: "Cognitive OS",
    body: "Event bus, world model, metrics engine, and cognitive state layer provide a full observability stack. UCI dashboard tracks 4-layer intelligence: Reliability, Intelligence, Adaptation, Productivity.",
    pills: ["Event bus", "UCI dashboard", "Decision replay"],
  },
  {
    sym: "◎",
    color: "#B45309",
    title: "Open Core",
    body: "Full source MIT-licensed and self-hostable via Docker. Managed hosting, enterprise CoA audit trail, and domain agent packs are paid tiers. Privacy is verifiable — runs 100% locally.",
    pills: ["MIT licensed", "Self-hostable", "100% local"],
  },
];

// ── Stack badges ─────────────────────────────────────────────────
const STACK = [
  { label: "LangGraph",          color: "#C48808" },
  { label: "FastAPI",            color: "#00695C" },
  { label: "phi4-mini 3.8B",     color: "#047857" },
  { label: "Ollama",             color: "#15803D" },
  { label: "React + Vite",       color: "#0E7490" },
  { label: "FAISS",              color: "#6D28D9" },
  { label: "nomic-embed-text",   color: "#BE185D" },
  { label: "SQLite",             color: "#B45309" },
  { label: "Docker",             color: "#0F766E" },
];

// ── Quick nav ─────────────────────────────────────────────────────
const NAV_SHORTCUTS = [
  { sym: "↗", label: "Chat",            tab: "chat",      color: "#C48808" },
  { sym: "⬡", label: "Agents",          tab: "agents",    color: "#1E5A8A" },
  { sym: "Ψ", label: "Cognitive OS",    tab: "cognitive", color: "#6D28D9" },
  { sym: "⊙", label: "Inspector",       tab: "inspector", color: "#047857" },
  { sym: "◷", label: "Version History", tab: "history",   color: "#BE185D" },
  { sym: "▲", label: "Progress",        tab: "progress",  color: "#B45309" },
];

// ── Architecture pipeline nodes ───────────────────────────────────
const PIPELINE = [
  { label: "User Query",      sub: "natural language",      color: T.muted    },
  { label: "QuerySignal",     sub: "domain · shape · verbosity", color: T.accent  },
  { label: "Core Brain",      sub: "routing + planning",    color: "#6D28D9"  },
  { label: "LangGraph Agent", sub: "10 specialists",        color: "#1E5A8A"  },
  { label: "FAISS Memory",    sub: "retrieve + write",      color: "#047857"  },
  { label: "Response",        sub: "reflect + learn",       color: T.success  },
];

export default function HomeTab({ apiStatus, coherence, totalQueries, onNav }) {
  const online  = apiStatus === "online";
  const ct      = coherence?.C;
  const ctColor = ct == null ? T.muted : ct >= 0.82 ? T.success : ct >= 0.70 ? T.warn : T.error;
  const ctLabel = ct == null ? "—" : ct.toFixed(3);

  const [runStats, setRunStats] = useState(null);

  useEffect(() => {
    if (!online) return;
    fetch("http://localhost:8000/runs?limit=200")
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d?.runs) return;
        const runs     = d.runs;
        const total    = runs.length;
        const passing  = runs.filter(r => r.status === "pass").length;
        const failing  = runs.filter(r => r.status === "fail").length;
        const avgMs    = total > 0
          ? Math.round(runs.reduce((s, r) => s + (r.duration_ms || 0), 0) / total) : 0;
        const passRate = total > 0 ? Math.round((passing / total) * 100) : null;
        setRunStats({ total, passing, failing, avgMs, passRate });
      })
      .catch(() => {});
  }, [online]);

  const currentPhase = ROADMAP.find(p => p.status === "next");
  const latestPhase  = BUILD_PHASES[BUILD_PHASES.length - 1];

  return (
    <div style={{ animation: "fadeIn .2s", fontFamily: "inherit" }}>

      {/* ── Hero ──────────────────────────────────────────────── */}
      <div style={{ marginBottom: 44 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 20, marginBottom: 20 }}>
          <div style={{ flex: 1 }}>
            {/* Title row */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
              <h1 style={{
                margin: 0, fontSize: 28, fontWeight: 900,
                color: "#C4880A", letterSpacing: "0.06em", lineHeight: 1.05,
              }}>AMAGRA</h1>
              <span style={{ fontSize: 13, fontWeight: 400, color: T.muted, marginTop: 2 }}>
                — local agentic AI
              </span>
            </div>

            {/* Version + phase badges */}
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginBottom: 14 }}>
              <Badge label={latestPhase.version}          color={T.accent}   />
              <Badge label={`${BUILD_PHASES.length} phases`} color="#047857" />
              <Badge label="Open Core · MIT"              color="#6D28D9"    />
              <Badge label="100% local"                   color="#0F766E"    />
              {currentPhase && (
                <Badge label={`Now: ${currentPhase.title}`} color={currentPhase.color} pulse />
              )}
            </div>

            {/* Tagline */}
            <p style={{
              margin: "0 0 16px", fontSize: 13.5, color: T.mutedLt,
              lineHeight: 1.65, maxWidth: 700,
            }}>
              A locally-running multi-agent reasoning system that routes natural language queries
              to 10 specialist LLM agents using signal-first classification. No cloud dependency,
              no telemetry, no vendor lock-in. Full source on GitHub under MIT.
            </p>

            {/* Live status strip */}
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
              <StatusPill
                label="API"
                value={online ? "Online" : apiStatus === "checking" ? "Checking…" : "Offline"}
                color={online ? T.success : T.error}
                dot
              />
              {ct != null && <StatusPill label="Coherence C(t)" value={ctLabel} color={ctColor} mono />}
              {coherence?.mem_n != null && <StatusPill label="Memories" value={coherence.mem_n} color={T.muted} mono />}
              {runStats?.passRate != null && (
                <StatusPill
                  label="Pass rate"
                  value={`${runStats.passRate}%`}
                  color={runStats.passRate >= 90 ? T.success : runStats.passRate >= 70 ? T.warn : T.error}
                  mono
                />
              )}
              {runStats?.total > 0 && <StatusPill label="Runs" value={runStats.total} color={T.muted} mono />}
              {runStats?.avgMs > 0 && <StatusPill label="Avg latency" value={`${runStats.avgMs}ms`} color={T.muted} mono />}
              {!online && (
                <span style={{ fontSize: 11, color: T.error, alignSelf: "center", marginLeft: 4 }}>
                  Start with{" "}
                  <code style={{ fontFamily: "monospace", background: "#B4231818", padding: "1px 5px", borderRadius: 3 }}>
                    ai-start
                  </code>
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── How it works ── */}
      <Section title="How it works">
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 8, padding: "22px 26px",
        }}>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
            gap: "18px 36px",
          }}>
            {[
              {
                step: "01", color: T.accent,
                title: "Classify the query",
                body: "QuerySignal extracts domain, shape, verbosity, and topic keywords in under 1ms — routing happens before any LLM call is made.",
              },
              {
                step: "02", color: "#6D28D9",
                title: "Select the right agent",
                body: "Core Brain maps the signal to one of 10 specialist agents: Python Dev, .NET Dev, IT Networking, AI/ML, Web Dev, DevOps, Data Analyst, Writer, Knowledge, or Terse.",
              },
              {
                step: "03", color: "#047857",
                title: "Execute with memory",
                body: "The agent runs inside a LangGraph graph, retrieving semantically relevant memories from the FAISS index and domain-specific tools before synthesising a response.",
              },
              {
                step: "04", color: "#BE185D",
                title: "Reflect and improve",
                body: "Triaged reflection updates memory quality scores after each run. User feedback (👍/👎) and outcome weights continuously improve future routing.",
              },
            ].map(s => (
              <div key={s.step} style={{ display: "flex", gap: 14 }}>
                <div style={{
                  width: 30, height: 30, flexShrink: 0,
                  borderRadius: 4, background: `${s.color}18`,
                  border: `1px solid ${s.color}44`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 10, fontWeight: 800, color: s.color,
                  fontFamily: "monospace", letterSpacing: "0.04em",
                }}>{s.step}</div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 5 }}>{s.title}</div>
                  <div style={{ fontSize: 11.5, color: T.muted, lineHeight: 1.6 }}>{s.body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── Architecture flow ── */}
      <Section title="Architecture">
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 8, padding: "20px 26px", overflowX: "auto",
        }}>
          <div style={{ display: "flex", alignItems: "center", minWidth: 640 }}>
            {PIPELINE.map((node, i, arr) => (
              <div key={node.label} style={{ display: "flex", alignItems: "center", flex: i < arr.length - 1 ? 1 : 0 }}>
                <div style={{
                  background: T.surface2, border: `1px solid ${node.color}44`,
                  borderRadius: 6, padding: "10px 14px",
                  textAlign: "center", flexShrink: 0, minWidth: 95,
                }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: node.color, lineHeight: 1.2 }}>{node.label}</div>
                  <div style={{ fontSize: 9.5, color: T.muted, marginTop: 3 }}>{node.sub}</div>
                </div>
                {i < arr.length - 1 && (
                  <div style={{ flex: 1, height: 1, background: T.border, position: "relative", minWidth: 18 }}>
                    <span style={{ position: "absolute", right: -4, top: "50%", transform: "translateY(-50%)", color: T.border, fontSize: 10, lineHeight: 1 }}>▶</span>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div style={{ marginTop: 14, fontSize: 11, color: T.muted, lineHeight: 1.6 }}>
            All stages emit events to the Cognitive OS event bus. Coherence C(t) is tracked continuously.
            Reflection and memory updates happen after every run — the system improves from use.
          </div>
        </div>
      </Section>

      {/* ── Feature pillars ── */}
      <Section title="Core capabilities">
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 10,
        }}>
          {FEATURES.map(f => <FeatureCard key={f.title} {...f} />)}
        </div>
      </Section>

      {/* ── Tech stack ── */}
      <Section title="Stack">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {STACK.map(s => (
            <span key={s.label} style={{
              fontSize: 11, fontWeight: 600,
              color: s.color, background: `${s.color}14`,
              border: `1px solid ${s.color}30`,
              borderRadius: 4, padding: "5px 12px",
              fontFamily: "'Consolas', 'Cascadia Code', monospace",
            }}>{s.label}</span>
          ))}
        </div>
      </Section>

      {/* ── Quick nav ── */}
      <Section title="Open a view">
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
          gap: 8,
        }}>
          {NAV_SHORTCUTS.map(n => (
            <button
              key={n.tab}
              onClick={() => onNav(n.tab)}
              className="card-hover"
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "11px 14px",
                background: T.surface, border: `1px solid ${T.border}`,
                borderRadius: 6, cursor: "pointer", fontFamily: "inherit",
                transition: "background .12s, border-color .12s",
              }}
            >
              <span style={{ fontSize: 15, color: n.color, fontFamily: "monospace", flexShrink: 0, lineHeight: 1 }}>{n.sym}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{n.label}</span>
            </button>
          ))}
        </div>
      </Section>

      {/* ── Footer ── */}
      <div style={{
        marginTop: 36, paddingTop: 18,
        borderTop: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
      }}>
        <span style={{ fontSize: 10, color: T.muted }}>
          Started Dec 15 2025 · {BUILD_PHASES.length} build phases · {latestPhase.version} · MIT
        </span>
        <span style={{ color: T.border }}>·</span>
        <span
          onClick={() => onNav("history")}
          style={{ fontSize: 10, color: T.accent, cursor: "pointer", textDecoration: "underline" }}
        >
          Full version history →
        </span>
        <span
          onClick={() => onNav("progress")}
          style={{ fontSize: 10, color: T.warn, cursor: "pointer", textDecoration: "underline" }}
        >
          Open issues →
        </span>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────

function Badge({ label, color, pulse }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
      color, background: `${color}18`,
      border: `1px solid ${color}44`,
      borderRadius: 4, padding: "3px 9px",
      boxShadow: pulse ? `0 0 8px ${color}44` : "none",
    }}>{label}</span>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 10, fontWeight: 700, color: T.muted,
        letterSpacing: "0.12em", textTransform: "uppercase",
        marginBottom: 14, display: "flex", alignItems: "center", gap: 10,
      }}>
        <span>{title}</span>
        <span style={{ flex: 1, height: 1, background: T.border }} />
      </div>
      {children}
    </div>
  );
}

function StatusPill({ label, value, color, mono, dot }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      background: T.surface2, border: `1px solid ${T.border}`,
      borderRadius: 4, padding: "5px 11px",
    }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />}
      <span style={{ fontSize: 11, color: T.muted }}>{label}</span>
      <span style={{
        fontSize: 12, fontWeight: 700, color,
        fontFamily: mono ? "'Consolas', 'Cascadia Code', monospace" : "inherit",
      }}>{value}</span>
    </div>
  );
}

function FeatureCard({ sym, color, title, body, pills }) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 8, padding: "16px 18px",
      display: "flex", flexDirection: "column", gap: 10,
      transition: "border-color .15s",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          width: 34, height: 34, flexShrink: 0, borderRadius: 6,
          background: `${color}18`, border: `1px solid ${color}33`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 15, fontFamily: "monospace", color, lineHeight: 1,
        }}>{sym}</div>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, lineHeight: 1.2 }}>{title}</div>
      </div>
      <div style={{ fontSize: 11.5, color: T.muted, lineHeight: 1.65 }}>{body}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
        {pills.map(p => (
          <span key={p} style={{
            fontSize: 9.5, fontWeight: 700, letterSpacing: "0.04em",
            color, background: `${color}12`, border: `1px solid ${color}28`,
            borderRadius: 3, padding: "2px 7px",
          }}>{p}</span>
        ))}
      </div>
    </div>
  );
}
