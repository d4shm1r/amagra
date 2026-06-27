import { useState } from "react";
import { T, LUX, GOLD, FONT_DISPLAY } from "./theme";
import { BUILD_PHASES, ROADMAP, VERSION } from "./constants";

// ── Feature pillars ─────────────────────────────────────────────
const FEATURES = [
  {
    sym: "⊕",
    color: "#C48808",
    title: "Fast when it's obvious, careful when it isn't",
    body: "Simple questions are answered at once. Harder ones get more thought — the system decides how much effort each query deserves, on its own.",
    pills: ["Instant on the simple", "Deeper on the hard", "Always private"],
  },
  {
    sym: "⬡",
    color: "#1E5A8A",
    title: "Specialists, not a generalist",
    body: "The right expert handles each question — code, infrastructure, data, writing, and more — each carrying its own memory of your work.",
    pills: ["The right expert, every time", "Knows your context", "Automatic"],
  },
  {
    sym: "⊞",
    color: "#047857",
    title: "It remembers your work",
    body: "Context carries across sessions, so you stop re-explaining yourself. The more you use it, the better it recalls what matters.",
    pills: ["Across sessions", "Instant recall", "Gets sharper over time"],
  },
  {
    sym: "◷",
    color: "#BE185D",
    title: "Reviews its work before answering",
    body: "Before it responds, it checks its own reasoning — and learns from what worked. Quietly, in the background, with no tuning from you.",
    pills: ["Self-checks", "Learns from outcomes", "No tuning needed"],
  },
  {
    sym: "Ψ",
    color: "#6D28D9",
    title: "Nothing is hidden",
    body: "Every answer can be inspected, replayed, and understood. See exactly why the system did what it did — never a black box.",
    pills: ["Inspect any answer", "Replay decisions", "Full transparency"],
  },
  {
    sym: "◎",
    color: "#B45309",
    title: "Yours to run",
    body: "Full source, MIT-licensed, self-hosted in one command. Runs entirely on your hardware — privacy you can verify, not just trust.",
    pills: ["MIT licensed", "Self-hosted", "100% local"],
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
const SIMPLE_NAV_SHORTCUTS = [
  { sym: "↗", label: "Chat",       tab: "chat",      color: "#C48808" },
  { sym: "⌘", label: "Prompt IDE", tab: "prompt",    color: "#1E5A8A" },
  { sym: "◎", label: "Consensus",  tab: "consensus", color: "#7E3F8F" },
  { sym: "◈", label: "Library",    tab: "library",   color: "#047857" },
  { sym: "⚙", label: "Model",      tab: "model",     color: "#B45309" },
  { sym: "?", label: "Guide",      tab: "guide",     color: "#9A6C00" },
];

const ADVANCED_NAV_SHORTCUTS = [
  { sym: "↗", label: "Chat",            tab: "chat",      color: "#C48808" },
  { sym: "⬡", label: "Skills",          tab: "skills",    color: "#1E5A8A" },
  { sym: "Ψ", label: "Cognitive OS",    tab: "cognitive", color: "#6D28D9" },
  { sym: "⊙", label: "Inspector",       tab: "inspector", color: "#047857" },
  { sym: "◷", label: "Version History", tab: "releases",  color: "#BE185D" },
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

export default function HomeTab({ apiStatus, coherence, totalQueries, onNav, mode = "advanced" }) {
  const online  = apiStatus === "online";

  const [showInternals, setShowInternals] = useState(false);

  const currentPhase = ROADMAP.find(p => p.status === "next");
  const navShortcuts = mode === "simple" ? SIMPLE_NAV_SHORTCUTS : ADVANCED_NAV_SHORTCUTS;

  return (
    <div style={{ animation: "fadeIn .2s", fontFamily: "inherit" }}>

      {/* ── Hero ──────────────────────────────────────────────── */}
      <div style={{ marginBottom: 44 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 20, marginBottom: 20 }}>
          <div style={{ flex: 1 }}>
            {/* Title row */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
              <h1 style={{
                margin: 0, fontSize: 38, fontWeight: 600,
                fontFamily: FONT_DISPLAY, letterSpacing: "0.07em", lineHeight: 1.05,
                ...LUX.goldText,
              }}>AMAGRA</h1>
            </div>

            {/* Version + phase badges */}
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginBottom: 14 }}>
              <Badge label={`v${VERSION}`}                color={T.accent}   />
              <Badge label={`${BUILD_PHASES.length} phases`} color="#047857" />
              <Badge label="Open Core · MIT"              color="#6D28D9"    />
              <Badge label="100% local"                   color="#0F766E"    />
              {currentPhase && (
                <Badge label={`Now: ${currentPhase.title}`} color={currentPhase.color} pulse />
              )}
            </div>

            {/* Tagline — brand anchor (lead with trust, not machinery) */}
            <p style={{
              margin: "0 0 8px", fontSize: 19, color: T.text,
              fontFamily: FONT_DISPLAY, fontWeight: 500,
              lineHeight: 1.3, maxWidth: 640, letterSpacing: "0.005em",
            }}>
              The AI you can trust with long-term work.
            </p>
            <p style={{
              margin: "0 0 16px", fontSize: 13.5, color: T.mutedLt,
              lineHeight: 1.65, maxWidth: 640,
            }}>
              It remembers what you've done, explains every decision, and runs entirely on your
              hardware.
            </p>

            {/* Live status — one calm reassurance, not a metrics pile.
                The real numbers live in Cognition; keep the hero serene. */}
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap", alignItems: "center" }}>
              <StatusPill
                label="Status"
                value={online ? "Ready · 100% local" : apiStatus === "checking" ? "Connecting…" : "Offline"}
                color={online ? T.success : T.error}
                dot
              />
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
        {/* gold hero rule */}
        <div style={{
          height: 2, borderRadius: 2,
          background: `linear-gradient(90deg, ${GOLD.g3} 0%, ${GOLD.g2} 22%, ${T.border} 70%, transparent 100%)`,
          opacity: 0.7,
        }} />
      </div>

      {/* ── Feature pillars (experience first — the point of the product) ── */}
      <Section title="What it does for you">
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 10,
        }}>
          {FEATURES.map(f => <FeatureCard key={f.title} {...f} />)}
        </div>
      </Section>

      {/* ── Quick nav ── */}
      <Section title="Open a view">
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
          gap: 8,
        }}>
          {navShortcuts.map(n => (
            <button
              key={n.tab}
              onClick={() => onNav(n.tab)}
              className="lux-card lux-card-i"
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "12px 15px",
                cursor: "pointer", fontFamily: "inherit", textAlign: "left",
              }}
            >
              <span style={{ fontSize: 15, color: T.accent, fontFamily: "monospace", flexShrink: 0, lineHeight: 1 }}>{n.sym}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{n.label}</span>
            </button>
          ))}
        </div>
      </Section>

      {/* ── Under the hood (collapsed — the experience is the point; ─────────
              the machinery is reassurance, available on demand, not the pitch) */}
      <div style={{ marginBottom: 36 }}>
        <button
          onClick={() => setShowInternals(v => !v)}
          className="nav-btn"
          style={{
            display: "flex", alignItems: "center", gap: 12, width: "100%",
            background: "transparent", border: "none", cursor: "pointer",
            padding: "2px 0", marginBottom: 14, fontFamily: "inherit",
            fontSize: 10, fontWeight: 800, color: T.muted,
            letterSpacing: "0.16em", textTransform: "uppercase",
          }}
        >
          <span>Under the hood</span>
          <span style={{
            flex: 1, height: 1,
            background: `linear-gradient(90deg, ${T.border} 0%, ${T.border} 60%, transparent 100%)`,
          }} />
          <span style={{
            fontSize: 9, color: T.muted, transition: "transform .2s",
            transform: showInternals ? "rotate(180deg)" : "none",
          }}>▾</span>
        </button>

        {showInternals && (
          <div style={{ animation: "fadeIn .2s" }}>
            <p style={{ margin: "0 0 22px", fontSize: 12, color: T.muted, lineHeight: 1.6, fontStyle: "italic", maxWidth: 640 }}>
              The experience is the point — the mechanics below are here if you want them.
            </p>

            {/* How it works */}
            <Section title="How it works">
              <div className="lux-card" style={{ padding: "22px 26px" }}>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                  gap: "18px 36px",
                }}>
                  {[
                    {
                      step: "01",
                      title: "Classify the query",
                      body: "QuerySignal extracts domain, shape, verbosity, and topic keywords in under 1ms — routing happens before any LLM call is made.",
                    },
                    {
                      step: "02",
                      title: "Select the right agent",
                      body: "Core Brain maps the signal to one of 10 specialist agents: Python Dev, .NET Dev, IT Networking, AI/ML, Web Dev, DevOps, Data Analyst, Writer, Knowledge, or Terse.",
                    },
                    {
                      step: "03",
                      title: "Execute with memory",
                      body: "The agent runs inside a LangGraph graph, retrieving semantically relevant memories from the FAISS index and domain-specific tools before synthesising a response.",
                    },
                    {
                      step: "04",
                      title: "Reflect and improve",
                      body: "Triaged reflection updates memory quality scores after each run. User feedback (👍/👎) and outcome weights continuously improve future routing.",
                    },
                  ].map(s => (
                    <div key={s.step} style={{ display: "flex", gap: 14 }}>
                      <div style={{
                        width: 32, height: 32, flexShrink: 0,
                        borderRadius: "50%", background: LUX.goldTint,
                        border: `1px solid ${GOLD.g2}55`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 10, fontWeight: 800, color: T.accent,
                        fontVariantNumeric: "tabular-nums", letterSpacing: "0.04em",
                        boxShadow: "inset 0 1px 1px rgba(255,255,255,0.7)",
                      }}>{s.step}</div>
                      <div>
                        <div style={{
                          fontSize: 12.5, fontWeight: 700, color: T.accent,
                          marginBottom: 5, letterSpacing: "-0.01em",
                        }}>{s.title}</div>
                        <div style={{ fontSize: 11.5, color: T.mutedLt, lineHeight: 1.6 }}>{s.body}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Section>

            {/* Architecture flow */}
            <Section title="Architecture">
              <div className="lux-card" style={{ padding: "20px 26px", overflowX: "auto" }}>
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

            {/* Tech stack */}
            <Section title="Stack">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {STACK.map(s => (
                  <span key={s.label} style={{
                    fontSize: 11, fontWeight: 600,
                    color: s.color, background: `${s.color}14`,
                    border: `1px solid ${s.color}30`,
                    borderRadius: 99, padding: "5px 13px",
                    fontFamily: "'Consolas', 'Cascadia Code', monospace",
                  }}>{s.label}</span>
                ))}
              </div>
            </Section>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div style={{
        marginTop: 36, paddingTop: 18,
        borderTop: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
      }}>
        <span style={{ fontSize: 10, color: T.muted }}>
          Started Dec 15 2025 · {BUILD_PHASES.length} build phases · v{VERSION} · MIT
        </span>
        <span style={{ color: T.border }}>·</span>
        <span
          onClick={() => onNav("releases")}
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
      borderRadius: 99, padding: "3px 11px",
      boxShadow: pulse ? `0 0 8px ${color}44` : "none",
    }}>{label}</span>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 10, fontWeight: 800, color: T.accent,
        letterSpacing: "0.16em", textTransform: "uppercase",
        marginBottom: 14, display: "flex", alignItems: "center", gap: 12,
      }}>
        <span>{title}</span>
        <span style={{
          flex: 1, height: 1,
          background: `linear-gradient(90deg, ${GOLD.g2}66 0%, ${T.border} 60%, transparent 100%)`,
        }} />
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
      borderRadius: 99, padding: "5px 12px",
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

function FeatureCard({ sym, title, body, pills }) {
  // Unified gold treatment — mirrors landing .for-card / .for-title (var(--g3)).
  return (
    <div className="lux-card lux-card-i" style={{
      padding: "17px 19px",
      display: "flex", flexDirection: "column", gap: 10,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <div style={{
          width: 34, height: 34, flexShrink: 0, borderRadius: 8,
          background: LUX.goldTint, border: `1px solid ${GOLD.g2}55`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 15, fontFamily: "monospace", color: T.accent, lineHeight: 1,
          boxShadow: "inset 0 1px 1px rgba(255,255,255,0.7)",
        }}>{sym}</div>
        <div style={{
          fontSize: 14, fontWeight: 700, color: T.accent,
          lineHeight: 1.2, letterSpacing: "-0.02em",
        }}>{title}</div>
      </div>
      <div style={{ fontSize: 11.5, color: T.mutedLt, lineHeight: 1.65 }}>{body}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
        {pills.map(p => (
          <span key={p} style={{
            fontSize: 9.5, fontWeight: 700, letterSpacing: "0.04em",
            color: T.accent2, background: LUX.goldTint,
            border: `1px solid ${GOLD.g2}40`,
            borderRadius: 99, padding: "2px 9px",
          }}>{p}</span>
        ))}
      </div>
    </div>
  );
}
