import { useEffect, useState } from "react";
import { API } from "@/lib/api";
import { AGENTS } from "@/config/constants";
import {
  Page, PageHeader, Section, Card, Well, Grid, Row, Stack,
  Disclosure, DisclosureBody, BulletList, CommandList, Markdown,
  Tile, ListTile, Pill, Tag, Code, Subtitle, Body, Caption, Micro, Inline,
  Loading,
} from "@/components/ui";

// ── Content ───────────────────────────────────────────────────
// Data declares MEANING (a tone), never a color. "success" survives a repaint
// of the palette; "#15803D" does not.

const QUICK_START = [
  { cmd: "ai-ui",    desc: "starts React dashboard on localhost:3000", tone: "gold"  },
  { cmd: "ai-start", desc: "starts FastAPI backend on port 8000",       tone: "gold"  },
  { cmd: "ai-stop",  desc: "stops background worker",                   tone: "muted" },
  { cmd: "ai-logs",  desc: "tail the backend log",                      tone: "muted" },
];

const ENDPOINTS = [
  { label: "Dashboard", value: "localhost:3000" },
  { label: "API",       value: "localhost:8000" },
  { label: "Health",    value: "localhost:8000/health" },
  { label: "Model",     value: "phi4-mini · Setup → Model" },
];

const METRICS = [
  {
    id: "coherence", name: "C(t) — System Coherence",
    formula: "C(t) = ⅓ · [C_routing + C_calib + C_quality]",
    desc: "Composite system health score. C_routing tracks how consistent routing decisions are, C_calib measures how accurate the critic's confidence is, and C_quality averages memory quality across all stored entries. Displayed in the sidebar footer in real time.",
    thresholds: [
      { range: "≥ 0.82",    label: "Healthy",  tone: "success" },
      { range: "0.70–0.82", label: "Watch",    tone: "warn"    },
      { range: "< 0.70",    label: "Degraded", tone: "error"   },
    ],
  },
  {
    id: "confidence", name: "Routing Confidence",
    formula: "conf = base + 0.05 (learned_router) + 0.04 (episodic hit)",
    desc: "The brain's certainty in its routing decision. Starts from a base score derived from pattern matches, then gets a +0.05 boost if the learned router agrees, and +0.04 if an episodic memory matched the query. Drives reflect level and dual-trajectory activation.",
    thresholds: [
      { range: "≥ 0.70",    label: "High — direct answer",             tone: "success" },
      { range: "0.52–0.70", label: "Normal — no forced escalation",     tone: "warn"    },
      { range: "0.40–0.52", label: "Low — dual trajectory forced",      tone: "clay"    },
      { range: "< 0.40",    label: "Very low — full reflection forced", tone: "error"   },
    ],
  },
  {
    id: "reflect", name: "Reflect Level",
    formula: "none | light | full",
    desc: "Controls how deeply the agent reviews its own response before returning it. The brain assigns this automatically based on confidence, action type, and complexity. Users can override it with the System 1/2/3 toggle in Chat.",
    thresholds: [
      { range: "none",  label: "Direct answer, no self-check",        tone: "muted"  },
      { range: "light", label: "Critic gate — grounded quality score", tone: "warn"   },
      { range: "full",  label: "LLM re-evaluation + possible retry",   tone: "purple" },
    ],
  },
  {
    id: "entropy", name: "H(q) — Routing Entropy",
    formula: "H(q) = −Σ p(a|q) · log₂ p(a|q)",
    desc: "Shannon entropy over the agent probability distribution for a given query. Low entropy = the brain is sure which agent to pick. High entropy = the query is ambiguous and could go to multiple agents. Visible in Runs → Decisions per decision.",
    thresholds: [],
  },
  {
    id: "quality", name: "Memory Quality Score",
    formula: "q_new = σ(logit(q) + γ · Δf)",
    desc: "A per-memory score in [0, 1] updated via Bayesian log-odds each time the memory is retrieved and evaluated. Positive feedback (good response) pushes quality toward 1; negative feedback pushes it toward 0. Memories scoring below 0.55 are prunable.",
    thresholds: [
      { range: "> 0.70",    label: "High quality — actively reinforced", tone: "success" },
      { range: "0.55–0.70", label: "At risk — low use or poor feedback",  tone: "warn"    },
      { range: "< 0.55",    label: "Prunable — removed by Prune action",  tone: "error"   },
    ],
  },
  {
    id: "pass_at_k", name: "Pass@k",
    formula: "Pass@k = 1 − C(n−c, k) / C(n, k)",
    desc: "Unbiased estimator of the probability that at least one of k sampled code completions passes all tests. From Chen et al. (2021). Used in benchmark_eval.py to measure code agent quality across multiple samples without inflating estimates.",
    thresholds: [],
  },
  {
    id: "ece", name: "ECE — Expected Calibration Error",
    formula: "ECE = Σ |acc(Bₘ) − conf(Bₘ)| · |Bₘ|/n",
    desc: "Measures how well the critic's confidence scores match actual correctness rates. Bins predictions by confidence; for each bin, computes |accuracy − mean_confidence|. Lower ECE = better calibrated critic gate.",
    thresholds: [
      { range: "< 0.05",    label: "Well calibrated",   tone: "success" },
      { range: "0.05–0.15", label: "Acceptable",        tone: "warn"    },
      { range: "> 0.15",    label: "Poorly calibrated", tone: "error"   },
    ],
  },
  {
    id: "brier", name: "Brier Score",
    formula: "BS = (1/n) Σ (sᵢ − lᵢ)²",
    desc: "Proper scoring rule for probabilistic predictions. Each score is the squared distance between the critic's confidence (sᵢ) and the actual pass/fail label (lᵢ). Perfect calibration = 0; random guessing = 0.25. Used alongside ECE in benchmark_eval.",
    thresholds: [
      { range: "< 0.10", label: "Good",   tone: "success" },
      { range: "< 0.20", label: "Decent", tone: "warn"    },
      { range: "≥ 0.20", label: "Poor",   tone: "error"   },
    ],
  },
  {
    id: "instability", name: "Instability Index I",
    formula: "I = 0.4·r + 0.4·|cal_err| + 0.2·weight_var",
    desc: "Composite measure of system instability. Combines regret (r), calibration error, and weight variance. Used in adaptive_alpha() to reduce the learning rate when the system is unstable. I > 0.5 triggers light reflection as a safety guard.",
    thresholds: [
      { range: "< 0.3",   label: "Stable — normal learning",   tone: "success" },
      { range: "0.3–0.5", label: "Moderate — reduced α",       tone: "warn"    },
      { range: "> 0.5",   label: "Unstable — reflection added", tone: "error"   },
    ],
  },
];

const HOW_TO = [
  { title: "Chat", items: [
    "Type a message and press Enter to send. Shift+Enter for a new line.",
    "The agent icon shows which specialist answered (not always the coordinator).",
    "Click ⊞ on any response to copy the full text.",
    "Click 👍/👎 to rate a response — this updates memory quality and trains the router.",
    "Click ⬇ Export to save the session as a Markdown file.",
    "The small signal pills below each response show domain, answer shape, and verbosity.",
  ]},
  { title: "Context Pin", items: [
    "The yellow bar above the input field. Whatever you type there is prepended to EVERY message.",
    "Use it to set a working context: 'Working on Blazor login page' or 'Python FastAPI project'.",
    "The coordinator sees the context and routes accordingly — it biases agent selection.",
    "Click ✕ to clear it when switching topics.",
  ]},
  { title: "Force Route", items: [
    "Row of agent buttons above the input. Click any to bypass automatic routing.",
    "The selected agent appears highlighted — it will receive every message until cleared.",
    "Click Auto to return to the coordinator's automatic routing.",
    "Useful when you know exactly which specialist you need and want to skip routing overhead.",
  ]},
  { title: "Reflect Mode", items: [
    "The System 1 / System 2 / System 3 toggle in the Chat settings.",
    "System 1 = no reflection (fastest, direct answer).",
    "System 2 = light reflection (critic quality gate, +5–15s).",
    "System 3 = full reflection (LLM self-evaluation + possible retry, +20–60s).",
    "The brain sets this automatically; the toggle forces it regardless of brain decision.",
  ]},
  { title: "Task Queue", items: [
    "Create tasks with a title, full prompt, priority, and target agent.",
    "Queue multiple tasks in advance. They run sequentially in the background.",
    "Click RUN ALL PENDING to start execution — results appear in the task list.",
    "Click any completed task to read the full agent response.",
  ]},
  { title: "Goals", items: [
    "Track project goals with title, description, and deadline.",
    "Goals are stored persistently in tasks.db — they survive restarts.",
    "Use alongside Task Queue: create a goal, then queue tasks that advance it.",
  ]},
  { title: "Setup → Progress", items: [
    "System metrics, memory health, and build history in one place.",
    "⊕ Consolidate: removes near-duplicate memories (cosine > 0.93) — run periodically.",
    "✂ Prune: deletes low-quality memories that have never been recalled.",
    "Roadmap shows upcoming phases with priority and status.",
    "Known Issues tracks bugs and outstanding items.",
  ]},
  { title: "Runs → Decisions", items: [
    "Shows every routing decision the brain made, with confidence and reflect level.",
    "Color-coded by routing indecision (low brain confidence) — yellow = indecisive.",
    "Use it to spot routing patterns and debug misroutes.",
    "Regret column shows how much the brain 'regretted' each decision in hindsight.",
  ]},
];

const ARCH = [
  { title: "Request Flow", steps: [
    "User message → ChatTab → POST /ask/stream (SSE)",
    "Coordinator receives AgentState",
    "Core Brain (think()) decides agent, action, complexity, reflect level",
    "Hybrid router runs in parallel for diagnostics (brain always wins)",
    "Chosen agent runs with memory context injected",
    "Optional: grounded_evaluate critic scores response",
    "Optional: dual-trajectory for code agents (A vs B + critic pick)",
    "Response + signal metadata streamed back to the UI",
  ]},
  { title: "Memory Pipeline", steps: [
    "Query embedded by nomic-embed-text (cached 512 entries)",
    "FAISSBackend.retrieve() → IndexIDMap search → cosine rerank with quality × freshness × type_weight",
    "Top-k injected into agent system prompt",
    "Agent response saved via memory_filter → dedup check (cos > 0.93) → SQLite + FAISS incremental add",
    "Quality updated per retrieval via Bayesian log-odds",
    "Auto-promotion at use_count = 5 (+0.03 log-odds boost)",
  ]},
  { title: "Learning Loop", steps: [
    "Every decision logged to logs/decisions.db",
    "apply_learning_update() runs after each response",
    "Weight delta = clip(α × (L − w), −0.02, +0.02)",
    "Adaptive α from instability index: low I → high learning rate",
    "Learned router model persisted under logs/ — retrained from trace_dataset.jsonl",
    "Regret estimated from coherence drift or user feedback",
    "Brain decisions calibrated against calibration.db over time",
  ]},
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

// ── Live documentation ────────────────────────────────────────
function DocsSection() {
  const [docs,    setDocs]    = useState(null);   // null = loading, [] = unavailable
  const [openDoc, setOpenDoc] = useState(null);
  const [content, setContent] = useState({});     // name → markdown

  useEffect(() => {
    fetch(`${API}/docs/index`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setDocs(d?.docs || []))
      .catch(() => setDocs([]));
  }, []);

  const toggle = async (name) => {
    if (openDoc === name) { setOpenDoc(null); return; }
    setOpenDoc(name);
    if (content[name]) return;
    try {
      const r = await fetch(`${API}/docs/${name}`);
      const body = r.ok ? (await r.json()).content : "*Couldn't load this document.*";
      setContent(prev => ({ ...prev, [name]: body }));
    } catch {
      setContent(prev => ({ ...prev, [name]: "*Backend offline — couldn't load this document.*" }));
    }
  };

  if (docs !== null && docs.length === 0) return null;   // API unavailable — stay quiet

  return (
    <Section title="Documentation" hint="The project's own docs, served live by the backend — always current">
      {docs === null ? (
        <Loading msg="Loading documentation…" />
      ) : (
        <Stack gap="xs">
          {docs.map(d => (
            <Disclosure
              key={d.name}
              title={<Inline role="small" tone="gold" weight={700}>{DOC_LABELS[d.name] || d.name}</Inline>}
              meta={<Micro mono>{(d.size / 1024).toFixed(1)} KB</Micro>}
              open={openDoc === d.name}
              onToggle={() => toggle(d.name)}
            >
              {content[d.name] ? <Markdown maxHeight={480}>{content[d.name]}</Markdown> : <Loading />}
            </Disclosure>
          ))}
        </Stack>
      )}
    </Section>
  );
}

// ── Guide ─────────────────────────────────────────────────────
export default function GuideTab() {
  const [openAgent,  setOpenAgent]  = useState(null);
  const [openMetric, setOpenMetric] = useState(null);
  const [openHowTo,  setOpenHowTo]  = useState(null);
  const [openArch,   setOpenArch]   = useState(null);

  const coordinator = AGENTS[0];
  const specialists = AGENTS.slice(1);

  return (
    <Page>
      <PageHeader center title="Guide" subtitle="Commands, agents, and how to get the most out of Amagra." />

      <Stack gap="xl">
        {/* Quick start */}
        <Card accent pad="md">
          <Stack gap="lg">
            <Subtitle tone="gold" weight={800}>Quick Start</Subtitle>
            <CommandList items={QUICK_START} />
            <Grid cols={4} gap="sm">
              {ENDPOINTS.map(e => <Tile key={e.label} label={e.label} value={e.value} />)}
            </Grid>
          </Stack>
        </Card>

        {/* How to use */}
        <Section title="How to Use" hint="Click any feature to expand its guide">
          <Stack gap="xs">
            {HOW_TO.map(s => (
              <Disclosure
                key={s.title}
                title={s.title}
                meta={<Caption>{s.items.length} tips</Caption>}
                open={openHowTo === s.title}
                onToggle={() => setOpenHowTo(openHowTo === s.title ? null : s.title)}
              >
                <BulletList items={s.items} />
              </Disclosure>
            ))}
          </Stack>
        </Section>

        {/* Agent reference */}
        <Section title="Agent Reference" hint={`All ${specialists.length} specialist agents + coordinator`}>
          <Stack gap="md">
            <Well tone="accent">
              <Row gap="md" align="flex-start">
                <Inline role="display" tone="gold">{coordinator.icon}</Inline>
                <Stack gap="xs">
                  <Row gap="sm">
                    <Inline role="lead" tone="gold" weight={700}>Coordinator</Inline>
                    <Pill tone="gold" strong>SUPERVISOR</Pill>
                  </Row>
                  <Caption tone="default">{coordinator.role}</Caption>
                  <Micro>
                    Runs core_brain (think()) to decide routing, then uses hybrid_router as a
                    diagnostic check. Brain always wins on conflicts.
                  </Micro>
                </Stack>
              </Row>
            </Well>

            <Grid cols={2} gap="sm">
              {specialists.map(agent => (
                <Disclosure
                  key={agent.id}
                  icon={agent.icon}
                  title={agent.label}
                  subtitle={agent.focus}
                  open={openAgent === agent.id}
                  onToggle={() => setOpenAgent(openAgent === agent.id ? null : agent.id)}
                >
                  <DisclosureBody>
                    <Stack gap="sm">
                      <Body>{agent.role}</Body>
                      <Row gap="xs" wrap>
                        {agent.keywords.map(kw => <Tag key={kw}>{kw}</Tag>)}
                      </Row>
                    </Stack>
                  </DisclosureBody>
                </Disclosure>
              ))}
            </Grid>
          </Stack>
        </Section>

        {/* Metric glossary */}
        <Section title="Metric Glossary" hint="Every number the system produces — what it means and when it matters">
          <Stack gap="xs">
            {METRICS.map(m => (
              <Disclosure
                key={m.id}
                title={m.name}
                meta={<Code truncate={220}>{m.formula}</Code>}
                open={openMetric === m.id}
                onToggle={() => setOpenMetric(openMetric === m.id ? null : m.id)}
              >
                <DisclosureBody>
                  <Stack gap="md">
                    <Code tone="gold">{m.formula}</Code>
                    <Body>{m.desc}</Body>
                    {m.thresholds.length > 0 && (
                      <Stack gap="xs">
                        {m.thresholds.map(t => (
                          <Row key={t.range} gap="md">
                            <Inline role="micro" tone={t.tone} weight={700} mono>{t.range}</Inline>
                            <Caption>{t.label}</Caption>
                          </Row>
                        ))}
                      </Stack>
                    )}
                  </Stack>
                </DisclosureBody>
              </Disclosure>
            ))}
          </Stack>
        </Section>

        {/* Architecture */}
        <Section title="System Architecture" hint="How the three main pipelines work">
          <Stack gap="sm">
            {ARCH.map(s => (
              <Disclosure
                key={s.title}
                title={s.title}
                meta={<Caption>{s.steps.length} steps</Caption>}
                open={openArch === s.title}
                onToggle={() => setOpenArch(openArch === s.title ? null : s.title)}
              >
                <BulletList ordered items={s.steps} />
              </Disclosure>
            ))}
          </Stack>
        </Section>

        {/* Live documentation */}
        <DocsSection />

        {/* Tech stack */}
        <Section title="Tech Stack">
          <Grid cols={4} gap="md">
            {TECH.map(g => <ListTile key={g.group} label={g.group} items={g.items} />)}
          </Grid>
        </Section>
      </Stack>
    </Page>
  );
}
