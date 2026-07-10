import { useEffect, useState } from "react";
import { T, SEM } from "./theme";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AGENTS } from "./constants";
import { PageHeader } from "./ObsShared";
import { API } from "./api";

// ── Metric glossary ────────────────────────────────────────────
const METRICS = [
  {
    id: "coherence", name: "C(t) — System Coherence", color: T.success,
    formula: "C(t) = ⅓ · [C_routing + C_calib + C_quality]",
    desc: "Composite system health score. C_routing tracks how consistent routing decisions are, C_calib measures how accurate the critic's confidence is, and C_quality averages memory quality across all stored entries. Displayed in the sidebar footer in real time.",
    thresholds: [
      { range: "≥ 0.82", label: "Healthy",  color: T.success },
      { range: "0.70–0.82", label: "Watch",  color: T.accent2 },
      { range: "< 0.70",  label: "Degraded", color: T.error },
    ],
  },
  {
    id: "confidence", name: "Routing Confidence", color: T.accent2,
    formula: "conf = base + 0.05 (learned_router) + 0.04 (episodic hit)",
    desc: "The brain's certainty in its routing decision. Starts from a base score derived from pattern matches, then gets a +0.05 boost if the learned router agrees, and +0.04 if an episodic memory matched the query. Drives reflect level and dual-trajectory activation.",
    thresholds: [
      { range: "≥ 0.70",      label: "High — direct answer",              color: T.success },
      { range: "0.52–0.70",   label: "Normal — no forced escalation",     color: T.accent2 },
      { range: "0.40–0.52",   label: "Low — dual trajectory forced",      color: SEM.clay },
      { range: "< 0.40",      label: "Very low — full reflection forced",  color: T.error },
    ],
  },
  {
    id: "reflect", name: "Reflect Level", color: SEM.teal,
    formula: "none | light | full",
    desc: "Controls how deeply the agent reviews its own response before returning it. The brain assigns this automatically based on confidence, action type, and complexity. Users can override it with the System 1/2/3 toggle in Chat.",
    thresholds: [
      { range: "none",  label: "Direct answer, no self-check",         color: T.muted },
      { range: "light", label: "Critic gate — grounded quality score", color: T.accent2 },
      { range: "full",  label: "LLM re-evaluation + possible retry",   color: SEM.purple },
    ],
  },
  {
    id: "entropy", name: "H(q) — Routing Entropy", color: SEM.teal,
    formula: "H(q) = −Σ p(a|q) · log₂ p(a|q)",
    desc: "Shannon entropy over the agent probability distribution for a given query. Low entropy = the brain is sure which agent to pick. High entropy = the query is ambiguous and could go to multiple agents. Visible in Runs → Decisions per decision.",
    thresholds: [],
  },
  {
    id: "quality", name: "Memory Quality Score", color: SEM.blue,
    formula: "q_new = σ(logit(q) + γ · Δf)",
    desc: "A per-memory score in [0, 1] updated via Bayesian log-odds each time the memory is retrieved and evaluated. Positive feedback (good response) pushes quality toward 1; negative feedback pushes it toward 0. Memories scoring below 0.55 are prunable.",
    thresholds: [
      { range: "> 0.70",    label: "High quality — actively reinforced",  color: T.success },
      { range: "0.55–0.70", label: "At risk — low use or poor feedback",   color: T.accent2 },
      { range: "< 0.55",    label: "Prunable — removed by Prune action",   color: T.error },
    ],
  },
  {
    id: "pass_at_k", name: "Pass@k", color: SEM.purple,
    formula: "Pass@k = 1 − C(n−c, k) / C(n, k)",
    desc: "Unbiased estimator of the probability that at least one of k sampled code completions passes all tests. From Chen et al. (2021). Used in benchmark_eval.py to measure code agent quality across multiple samples without inflating estimates.",
    thresholds: [],
  },
  {
    id: "ece", name: "ECE — Expected Calibration Error", color: SEM.magenta,
    formula: "ECE = Σ |acc(Bₘ) − conf(Bₘ)| · |Bₘ|/n",
    desc: "Measures how well the critic's confidence scores match actual correctness rates. Bins predictions by confidence; for each bin, computes |accuracy − mean_confidence|. Lower ECE = better calibrated critic gate.",
    thresholds: [
      { range: "< 0.05",    label: "Well calibrated",     color: T.success },
      { range: "0.05–0.15", label: "Acceptable",          color: T.accent2 },
      { range: "> 0.15",    label: "Poorly calibrated",   color: T.error },
    ],
  },
  {
    id: "brier", name: "Brier Score", color: SEM.clay,
    formula: "BS = (1/n) Σ (sᵢ − lᵢ)²",
    desc: "Proper scoring rule for probabilistic predictions. Each score is the squared distance between the critic's confidence (sᵢ) and the actual pass/fail label (lᵢ). Perfect calibration = 0; random guessing = 0.25. Used alongside ECE in benchmark_eval.",
    thresholds: [
      { range: "< 0.10", label: "Good",    color: T.success },
      { range: "< 0.20", label: "Decent",  color: T.accent2 },
      { range: "≥ 0.20", label: "Poor",    color: T.error },
    ],
  },
  {
    id: "instability", name: "Instability Index I", color: T.error,
    formula: "I = 0.4·r + 0.4·|cal_err| + 0.2·weight_var",
    desc: "Composite measure of system instability. Combines regret (r), calibration error, and weight variance. Used in adaptive_alpha() to reduce the learning rate when the system is unstable. I > 0.5 triggers light reflection as a safety guard.",
    thresholds: [
      { range: "< 0.3",    label: "Stable — normal learning",    color: T.success },
      { range: "0.3–0.5",  label: "Moderate — reduced α",        color: T.accent2 },
      { range: "> 0.5",    label: "Unstable — reflection added",  color: T.error },
    ],
  },
];

// ── How-to sections ───────────────────────────────────────────
const HOW_TO = [
  {
    title: "Chat", color: T.success,
    items: [
      "Type a message and press Enter to send. Shift+Enter for a new line.",
      "The agent icon shows which specialist answered (not always the coordinator).",
      "Click ⊞ on any response to copy the full text.",
      "Click 👍/👎 to rate a response — this updates memory quality and trains the router.",
      "Click ⬇ Export to save the session as a Markdown file.",
      "The small signal pills below each response show domain, answer shape, and verbosity.",
    ],
  },
  {
    title: "Context Pin", color: T.accent2,
    items: [
      "The yellow bar above the input field. Whatever you type there is prepended to EVERY message.",
      "Use it to set a working context: 'Working on Blazor login page' or 'Python FastAPI project'.",
      "The coordinator sees the context and routes accordingly — it biases agent selection.",
      "Click ✕ to clear it when switching topics.",
    ],
  },
  {
    title: "Force Route", color: SEM.purple,
    items: [
      "Row of agent buttons above the input. Click any to bypass automatic routing.",
      "The selected agent appears highlighted — it will receive every message until cleared.",
      "Click Auto to return to the coordinator's automatic routing.",
      "Useful when you know exactly which specialist you need and want to skip routing overhead.",
    ],
  },
  {
    title: "Reflect Mode", color: SEM.teal,
    items: [
      "The System 1 / System 2 / System 3 toggle in the Chat settings.",
      "System 1 = no reflection (fastest, direct answer).",
      "System 2 = light reflection (critic quality gate, +5–15s).",
      "System 3 = full reflection (LLM self-evaluation + possible retry, +20–60s).",
      "The brain sets this automatically; the toggle forces it regardless of brain decision.",
    ],
  },
  {
    title: "Task Queue", color: SEM.teal,
    items: [
      "Create tasks with a title, full prompt, priority, and target agent.",
      "Queue multiple tasks in advance. They run sequentially in the background.",
      "Click RUN ALL PENDING to start execution — results appear in the task list.",
      "Click any completed task to read the full agent response.",
    ],
  },
  {
    title: "Goals", color: SEM.clay,
    items: [
      "Track project goals with title, description, and deadline.",
      "Goals are stored persistently in tasks.db — they survive restarts.",
      "Use alongside Task Queue: create a goal, then queue tasks that advance it.",
    ],
  },
  {
    title: "Setup → Progress", color: SEM.blue,
    items: [
      "System metrics, memory health, and build history in one place.",
      "⊕ Consolidate: removes near-duplicate memories (cosine > 0.93) — run periodically.",
      "✂ Prune: deletes low-quality memories that have never been recalled.",
      "Roadmap shows upcoming phases with priority and status.",
      "Known Issues tracks bugs and outstanding items.",
    ],
  },
  {
    title: "Runs → Decisions", color: SEM.purple,
    items: [
      "Shows every routing decision the brain made, with confidence and reflect level.",
      "Color-coded by conflict (brain vs router disagreement) — yellow = conflicted.",
      "Use it to spot routing patterns and debug misroutes.",
      "Regret column shows how much the brain 'regretted' each decision in hindsight.",
    ],
  },
];

// ── Arch sections ─────────────────────────────────────────────
const ARCH = [
  { title: "Request Flow", color: T.success, steps: ["User message → ChatTab → POST /ask/stream (SSE)", "Coordinator receives AgentState", "Core Brain (think()) decides agent, action, complexity, reflect level", "Hybrid router runs in parallel for diagnostics (brain always wins)", "Chosen agent runs with memory context injected", "Optional: grounded_evaluate critic scores response", "Optional: dual-trajectory for code agents (A vs B + critic pick)", "Response + signal metadata streamed back to the UI"] },
  { title: "Memory Pipeline", color: SEM.blue, steps: ["Query embedded by nomic-embed-text (cached 512 entries)", "FAISSBackend.retrieve() → IndexIDMap search → cosine rerank with quality × freshness × type_weight", "Top-k injected into agent system prompt", "Agent response saved via memory_filter → dedup check (cos > 0.93) → SQLite + FAISS incremental add", "Quality updated per retrieval via Bayesian log-odds", "Auto-promotion at use_count = 5 (+0.03 log-odds boost)"] },
  { title: "Learning Loop", color: T.accent2, steps: ["Every decision logged to logs/decisions.db", "apply_learning_update() runs after each response", "Weight delta = clip(α × (L − w), −0.02, +0.02)", "Adaptive α from instability index: low I → high learning rate", "Learned router model persisted under logs/ — retrained from trace_dataset.jsonl", "Regret estimated from coherence drift or user feedback", "Brain decisions calibrated against calibration.db over time"] },
];

const TECH = [
  { group: "Core",      items: ["LangGraph v1.0.8", "phi4-mini via Ollama", "Python 3.12+"] },
  { group: "Inference", items: ["Ollama (local, default)", "Cloud: Claude / GPT / Gemini (BYO key)", "Hybrid escalation (AMAGRA_HYBRID)"] },
  { group: "Backend",   items: ["FastAPI + uvicorn", "asyncio task queue", "SQLite + WAL mode"] },
  { group: "Memory",    items: ["nomic-embed-text", "faiss-cpu 1.14.2", "LRU embedding cache (512)"] },
  { group: "Routing",   items: ["QuerySignal normalizer", "core_brain (BrainDecision)", "hybrid_router (keyword + signal)"] },
  { group: "Quality",   items: ["grounded_evaluate critic", "dual-trajectory GRAM", "reflection triage (none/light/full)"] },
  { group: "Frontend",  items: ["React 19 + Vite", "ReactMarkdown + GFM", "Monaco (Prompt IDE, bundled)"] },
  { group: "System",    items: ["Ubuntu Linux", "Electron desktop shell", "AppImage packaging"] },
];

// ── Live documentation (served by the backend) ────────────────
// The runtime ships its own manual: GET /docs/index lists the curated project
// docs and GET /docs/{name} returns the markdown. Reading them here means the
// in-app guide can never drift from the repo docs the way hardcoded text does.
const DOC_LABELS = {
  "project-map":         "Project Map",
  "guide":               "User Guide",
  "architecture":        "Architecture",
  "reference":           "Technical Reference",
  "roadmap":             "Roadmap",
  "design-principles":   "Design Principles",
  "identity":            "Identity Contract",
  "plugin-architecture": "Plugin Architecture",
  "history":             "Build History",
  "findings":            "Routing Findings",
  "failures":            "Failure Modes & Invariants",
  "issues":              "Known Issues",
  "vision":              "Vision",
  "comparison":          "Comparison",
  "deploy":              "Deploy",
  "providers":           "Cloud Providers",
};

function DocsSection() {
  const [docs, setDocs]         = useState(null);   // null = loading, [] = unavailable
  const [openDoc, setOpenDoc]   = useState(null);
  const [content, setContent]   = useState({});     // name → markdown

  useEffect(() => {
    fetch(`${API}/docs/index`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setDocs(d?.docs || []))
      .catch(() => setDocs([]));
  }, []);

  const toggle = async (name) => {
    if (openDoc === name) { setOpenDoc(null); return; }
    setOpenDoc(name);
    if (!content[name]) {
      try {
        const r = await fetch(`${API}/docs/${name}`);
        if (r.ok) {
          const d = await r.json();
          setContent(prev => ({ ...prev, [name]: d.content }));
        } else {
          setContent(prev => ({ ...prev, [name]: "*Couldn't load this document.*" }));
        }
      } catch {
        setContent(prev => ({ ...prev, [name]: "*Backend offline — couldn't load this document.*" }));
      }
    }
  };

  if (docs !== null && docs.length === 0) return null;   // API unavailable — stay quiet

  return (
    <Card mb={20}>
      <SectionHead title="Documentation" sub="The project's own docs, served live by the backend — always current" />
      {docs === null ? (
        <div style={{ fontSize: 12, color: T.muted, fontStyle: "italic", padding: "6px 0" }}>Loading documentation…</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {docs.map(d => {
            const isOpen = openDoc === d.name;
            const label  = DOC_LABELS[d.name] || d.name;
            return (
              <div key={d.name}
                style={{ background: T.surface2, border: `1.5px solid ${T.accent2}${isOpen ? "66" : "22"}`, borderRadius: 12, padding: "10px 14px", transition: "all .2s" }}>
                <div className="hoverable" onClick={() => toggle(d.name)}
                  style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: T.accent2, flex: 1 }}>{label}</span>
                  <span style={{ fontSize: 10, color: T.muted, fontFamily: "monospace" }}>{(d.size / 1024).toFixed(1)} KB</span>
                  <span style={{ color: T.accent2, opacity: .5, fontSize: 11 }}>{isOpen ? "▲" : "▼"}</span>
                </div>
                {isOpen && (
                  <div className="doc-reader" style={{
                    marginTop: 10, padding: "14px 18px", background: T.surface,
                    borderRadius: 7, border: `1px solid ${T.accent2}22`,
                    fontSize: 13, color: T.text, lineHeight: 1.7,
                    maxHeight: 480, overflowY: "auto", overflowX: "auto",
                  }}>
                    {content[d.name]
                      ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{content[d.name]}</ReactMarkdown>
                      : <span style={{ fontStyle: "italic", color: T.muted }}>Loading…</span>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ── Shared helpers ────────────────────────────────────────────
function SectionHead({ title, sub }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase" }}>{title}</div>
      {sub && <div style={{ fontSize: 12, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function Card({ children, mb = 20, accent }) {
  return (
    <div style={{ background: T.surface, border: `2px solid ${accent || T.border}`, borderRadius: 14, padding: "18px 22px", marginBottom: mb }}>
      {children}
    </div>
  );
}

function Threshold({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
      {items.map((t, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 10, fontWeight: 700, fontFamily: "monospace", color: t.color, minWidth: 70 }}>{t.range}</span>
          <span style={{ fontSize: 12, color: T.muted }}>{t.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function GuideTab() {
  const [openAgent,   setOpenAgent]   = useState(null);
  const [openMetric,  setOpenMetric]  = useState(null);
  const [openHowTo,   setOpenHowTo]   = useState(null);
  const [openArch,    setOpenArch]    = useState(null);

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      <PageHeader title="Guide" subtitle="Commands, agents, and how to get the most out of Amagra." />

      {/* ── Quick start ── */}
      <Card mb={20} accent={`${T.success}33`}>
        <div style={{ fontSize: 16, fontWeight: 800, color: T.success, marginBottom: 14 }}>Quick Start</div>
        <div style={{ fontFamily: "monospace", fontSize: 12, background: "#E7F2E6", borderRadius: 8, padding: "12px 16px", marginBottom: 14 }}>
          {[
            { cmd: "ai-ui",    desc: "starts React dashboard on localhost:3000", color: T.accent2 },
            { cmd: "ai-start", desc: "starts FastAPI backend on port 8000",       color: T.accent2 },
            { cmd: "ai-stop",  desc: "stops background worker",                   color: T.muted },
            { cmd: "ai-logs",  desc: "tail the backend log",                      color: T.muted },
          ].map(r => (
            <div key={r.cmd} style={{ marginBottom: 6, display: "flex", gap: 12, alignItems: "baseline" }}>
              <span style={{ color: r.color, minWidth: 80 }}>{r.cmd}</span>
              <span style={{ color: T.muted }}>→</span>
              <span style={{ color: T.muted }}>{r.desc}</span>
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
          {[
            { label: "Dashboard", value: "localhost:3000" },
            { label: "API",       value: "localhost:8000" },
            { label: "Health",    value: "localhost:8000/health" },
            { label: "Model",     value: "phi4-mini · Setup → Model" },
          ].map(item => (
            <div key={item.label} style={{ background: T.surface2, borderRadius: 10, padding: "8px 12px", border: `1px solid ${T.success}20` }}>
              <div style={{ fontSize: 10, color: T.muted, marginBottom: 2 }}>{item.label}</div>
              <div style={{ fontSize: 11, color: T.success, fontFamily: "monospace" }}>{item.value}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* ── How to use ── */}
      <Card mb={20}>
        <SectionHead title="How to Use" sub="Click any feature to expand its guide" />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {HOW_TO.map(section => {
            const isOpen = openHowTo === section.title;
            return (
              <div key={section.title} className="hoverable"
                onClick={() => setOpenHowTo(isOpen ? null : section.title)}
                style={{ background: T.surface2, border: `1.5px solid ${section.color}${isOpen ? "66" : "22"}`, borderRadius: 12, padding: "10px 14px", cursor: "pointer", transition: "all .2s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: section.color, flex: 1 }}>{section.title}</span>
                  <span style={{ fontSize: 11, color: T.muted }}>{section.items.length} tips</span>
                  <span style={{ color: section.color, opacity: .5, fontSize: 11 }}>{isOpen ? "▲" : "▼"}</span>
                </div>
                {isOpen && (
                  <ul style={{ margin: "10px 0 0", padding: "0 0 0 18px" }}>
                    {section.items.map((item, i) => (
                      <li key={i} style={{ fontSize: 12, color: T.text, lineHeight: 1.8, marginBottom: 2 }}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── Agent reference ── */}
      <Card mb={20}>
        <SectionHead title="Agent Reference" sub={`All ${AGENTS.length - 1} specialist agents + coordinator`} />

        {/* Coordinator special card */}
        <div style={{ background: `linear-gradient(135deg,#F5EDD6,${T.surface2})`, border: `2px solid ${T.accent2}66`, borderRadius: 12, padding: "14px 18px", marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 28, color: T.accent2 }}>{AGENTS[0].icon}</span>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: T.accent2 }}>Coordinator</span>
                <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 99, background: `${T.accent2}18`, color: T.accent2, border: `1px solid ${T.accent2}40`, fontWeight: 700 }}>SUPERVISOR</span>
              </div>
              <div style={{ fontSize: 12, color: T.text, lineHeight: 1.6 }}>{AGENTS[0].role}</div>
              <div style={{ fontSize: 11, color: T.muted, marginTop: 6 }}>
                Runs core_brain (think()) to decide routing, then uses hybrid_router as a diagnostic check. Brain always wins on conflicts.
              </div>
            </div>
          </div>
        </div>

        {/* Specialist agents */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 8 }}>
          {AGENTS.slice(1).map(agent => {
            const isOpen = openAgent === agent.id;
            return (
              <div key={agent.id} className="hoverable"
                onClick={() => setOpenAgent(isOpen ? null : agent.id)}
                style={{ background: T.surface2, border: `1.5px solid ${agent.color}${isOpen ? "88" : "33"}`, borderRadius: 12, padding: "12px 14px", cursor: "pointer", transition: "all .2s" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <span style={{ fontSize: 20 }}>{agent.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: agent.color, marginBottom: 2 }}>{agent.label}</div>
                    <div style={{ fontSize: 11, color: T.muted, lineHeight: 1.5 }}>{agent.focus}</div>
                    {isOpen && (
                      <div style={{ marginTop: 10, fontSize: 12, color: T.text, lineHeight: 1.65, padding: "10px 12px", background: T.surface, borderRadius: 7, border: `1px solid ${agent.color}22` }}>
                        <div style={{ marginBottom: 8 }}>{agent.role}</div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {agent.keywords.map(kw => (
                            <span key={kw} style={{ fontSize: 10, color: agent.color, background: `${agent.color}12`, padding: "2px 8px", borderRadius: 99, border: `1px solid ${agent.color}30`, fontFamily: "monospace" }}>{kw}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <span style={{ color: agent.color, opacity: .5, fontSize: 11 }}>{isOpen ? "▲" : "▼"}</span>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── Metric glossary ── */}
      <Card mb={20}>
        <SectionHead title="Metric Glossary" sub="Every number the system produces — what it means and when it matters" />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {METRICS.map(m => {
            const isOpen = openMetric === m.id;
            return (
              <div key={m.id} className="hoverable"
                onClick={() => setOpenMetric(isOpen ? null : m.id)}
                style={{ background: T.surface2, border: `1.5px solid ${m.color}${isOpen ? "66" : "22"}`, borderRadius: 12, padding: "10px 14px", cursor: "pointer", transition: "all .2s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: m.color, flex: 1 }}>{m.name}</span>
                  <code style={{ fontSize: 11, color: T.muted, background: T.border, padding: "2px 8px", borderRadius: 4, fontFamily: "monospace", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.formula}</code>
                  <span style={{ color: m.color, opacity: .5, fontSize: 11 }}>{isOpen ? "▲" : "▼"}</span>
                </div>
                {isOpen && (
                  <div style={{ marginTop: 10, padding: "10px 12px", background: T.surface, borderRadius: 7, border: `1px solid ${m.color}22` }}>
                    <code style={{ display: "block", fontSize: 12, color: m.color, background: T.surface2, padding: "6px 10px", borderRadius: 8, fontFamily: "monospace", marginBottom: 10 }}>{m.formula}</code>
                    <div style={{ fontSize: 12, color: T.text, lineHeight: 1.7, marginBottom: 8 }}>{m.desc}</div>
                    <Threshold items={m.thresholds} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── Architecture ── */}
      <Card mb={20}>
        <SectionHead title="System Architecture" sub="How the three main pipelines work" />
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {ARCH.map(section => {
            const isOpen = openArch === section.title;
            return (
              <div key={section.title} className="hoverable"
                onClick={() => setOpenArch(isOpen ? null : section.title)}
                style={{ background: T.surface2, border: `1.5px solid ${section.color}${isOpen ? "66" : "22"}`, borderRadius: 12, padding: "10px 14px", cursor: "pointer", transition: "all .2s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: section.color, flex: 1 }}>{section.title}</span>
                  <span style={{ fontSize: 11, color: T.muted }}>{section.steps.length} steps</span>
                  <span style={{ color: section.color, opacity: .5, fontSize: 11 }}>{isOpen ? "▲" : "▼"}</span>
                </div>
                {isOpen && (
                  <ol style={{ margin: "10px 0 0", padding: "0 0 0 20px" }}>
                    {section.steps.map((step, i) => (
                      <li key={i} style={{ fontSize: 12, color: T.text, lineHeight: 1.8, marginBottom: 2 }}>{step}</li>
                    ))}
                  </ol>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── Live documentation ── */}
      <style>{`
        .doc-reader table { border-collapse: collapse; margin: 10px 0; }
        .doc-reader th, .doc-reader td { border: 1px solid ${T.border}; padding: 5px 10px; font-size: 12px; text-align: left; }
        .doc-reader th { background: ${T.surface2}; }
        .doc-reader code { background: ${T.surface2}; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
        .doc-reader pre { background: ${T.surface2}; padding: 10px 14px; border-radius: 6px; overflow-x: auto; }
        .doc-reader pre code { background: transparent; padding: 0; }
        .doc-reader h1, .doc-reader h2, .doc-reader h3 { color: ${T.text}; margin: 14px 0 8px; }
        .doc-reader img { max-width: 100%; }
      `}</style>
      <DocsSection />

      {/* ── Tech stack ── */}
      <Card mb={0}>
        <SectionHead title="Tech Stack" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
          {TECH.map(group => (
            <div key={group.group} style={{ background: T.surface2, borderRadius: 10, padding: "10px 12px", border: `1px solid ${T.border}` }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>{group.group}</div>
              {group.items.map(item => (
                <div key={item} style={{ fontSize: 11, color: T.text, padding: "3px 0", borderBottom: `1px solid ${T.border}22`, lineHeight: 1.6 }}>{item}</div>
              ))}
            </div>
          ))}
        </div>
      </Card>

    </div>
  );
}
