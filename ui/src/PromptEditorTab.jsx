import { useState, useRef, useEffect, useCallback, useMemo } from "react";

const FONT    = "'Consolas', 'Cascadia Code', 'Droid Sans Mono', monospace";
const LINE_H  = 20;
const FONT_SZ = 13;

// Same origin the rest of the UI talks to (see ProviderSettingsTab).
const API = "http://localhost:8000";

const T = {
  bg:            "#F4F0E8",
  surface:       "#FAF7F2",
  surface2:      "#F4F0E8",
  border:        "#E0D6C4",
  text:          "#2E2010",
  muted:         "#9A7A60",
  mutedLt:       "#8A7058",
  accent:        "#C48808",
  tabActiveBg:   "#F4F0E8",
  tabInactiveBg: "#F4F0E8",
  statusBg:      "#FAF7F2",
  success:       "#15803D",
  warn:          "#9A6C00",
  error:         "#B42318",
  gutterBorder:  "#D6C9B2",
  lineNumActive: "#8A7058",
};

// ─────────────────────────────────────────────────────────────
// Domain definitions — powers detection, context gaps, repair
// ─────────────────────────────────────────────────────────────
const DOMAINS = [
  {
    id: "software",
    label: "Software / Architecture",
    confidence: 0,
    keywords: ["architecture", "system design", "api", "database", "backend", "frontend",
      "microservice", "deployment", "scalable", "latency", "throughput", "auth",
      "authentication", "service", "endpoint", "schema", "migration", "refactor",
      "production", "infrastructure", "codebase", "repository", "monolith"],
    agents: ["Systems Architect", "Backend Engineer", "Infrastructure Engineer", "Security Reviewer"],
    contextGaps: ["Target user load (RPS / DAU)", "Latency & throughput requirements",
      "Infrastructure budget", "Availability SLA (%)", "Security / compliance needs", "Existing tech stack"],
    repairRole: "You are a senior systems architect with expertise in production-grade software design.",
    repairFormat: ["Architecture overview with key components", "Technology recommendations with rationale",
      "Migration / implementation strategy", "Risk assessment and mitigations", "Success metrics"],
    repairConstraints: ["Ensure backward compatibility during transition",
      "Optimize for the stated scale requirements", "Follow security best practices"],
  },
  {
    id: "ml",
    label: "Machine Learning / AI",
    confidence: 0,
    keywords: ["model", "training", "dataset", "neural", "machine learning", "deep learning",
      "llm", "embedding", "inference", "accuracy", "precision", "recall", "fine-tuning",
      "pytorch", "tensorflow", "classifier", "regression", "overfitting", "transformer",
      "prompt engineering", "retrieval", "rag", "vector"],
    agents: ["ML Engineer", "Data Scientist", "AI Researcher", "MLOps Engineer"],
    contextGaps: ["Dataset size, format, and quality", "Target accuracy / F1 / other metrics",
      "Compute budget (GPU hours)", "Inference latency requirements",
      "Data privacy and compliance constraints", "Evaluation methodology"],
    repairRole: "You are a senior machine learning engineer with production ML experience.",
    repairFormat: ["Model architecture and approach", "Training methodology",
      "Evaluation strategy and metrics", "Deployment and serving plan", "Known limitations"],
    repairConstraints: ["Define measurable evaluation criteria",
      "Address data quality and bias", "Consider inference cost at scale"],
  },
  {
    id: "python",
    label: "Python / Development",
    confidence: 0,
    keywords: ["python", "function", "class", "script", "algorithm", "data structure",
      "async", "pytest", "fastapi", "django", "pandas", "numpy", "type hint",
      "decorator", "recursion", "generator", "asyncio", "pydantic", "list comprehension"],
    agents: ["Python Developer", "Code Reviewer", "Testing Engineer", "DevOps Engineer"],
    contextGaps: ["Python version (3.x)", "Performance requirements",
      "Error handling expectations", "Test coverage requirements",
      "External dependencies allowed", "Integration points"],
    repairRole: "You are an expert Python developer who writes clean, idiomatic, well-tested code.",
    repairFormat: ["Working implementation with type hints", "Usage example",
      "Unit tests for core logic", "Edge cases handled", "Complexity analysis"],
    repairConstraints: ["Follow PEP 8 and Python idioms",
      "Include docstring and type annotations", "Handle errors explicitly"],
  },
  {
    id: "networking",
    label: "Networking / Infrastructure",
    confidence: 0,
    keywords: ["network", "dns", "firewall", "vpc", "subnet", "routing", "load balancer",
      "cdn", "ssl", "vpn", "kubernetes", "docker", "nginx", "proxy", "bandwidth",
      "packet", "iptables", "wireguard", "tcp", "udp", "bgp", "ospf"],
    agents: ["Network Engineer", "Cloud Architect", "DevOps Engineer", "Security Engineer"],
    contextGaps: ["Network topology and scale", "Traffic volume and patterns",
      "Security and compliance requirements", "Redundancy / HA requirements",
      "Budget and cloud provider constraints", "Current pain points"],
    repairRole: "You are a senior network engineer and cloud architect.",
    repairFormat: ["Network diagram description", "Configuration steps",
      "Security considerations", "Testing and validation plan", "Rollback procedure"],
    repairConstraints: ["Ensure zero-downtime implementation where possible",
      "Document all firewall rule changes", "Validate with a test environment first"],
  },
  {
    id: "writing",
    label: "Writing / Content",
    confidence: 0,
    keywords: ["write", "article", "blog", "content", "copy", "essay", "documentation",
      "readme", "report", "summary", "proposal", "draft", "tone", "audience",
      "seo", "headline", "paragraph", "narrative", "editorial"],
    agents: ["Content Strategist", "Technical Writer", "Copy Editor", "SEO Specialist"],
    contextGaps: ["Target audience and expertise level", "Tone and voice (formal / casual / technical)",
      "Publication channel and format", "Word count / length target",
      "SEO keywords if applicable", "Brand or style guidelines"],
    repairRole: "You are an expert content strategist and technical writer.",
    repairFormat: ["Complete draft meeting the brief",
      "Key messages clearly communicated", "CTA or next steps if applicable"],
    repairConstraints: ["Match target audience reading level",
      "Use active voice throughout", "Stay within specified length"],
  },
  {
    id: "business",
    label: "Business / Strategy",
    confidence: 0,
    keywords: ["business", "strategy", "market", "revenue", "growth", "customer", "product",
      "roadmap", "kpi", "metrics", "budget", "roi", "stakeholder", "go-to-market",
      "competitive", "analysis", "forecast", "pricing", "acquisition"],
    agents: ["Business Analyst", "Strategy Consultant", "Product Manager", "Financial Analyst"],
    contextGaps: ["Company stage and size", "Target market and segment",
      "Timeline and deadline", "Budget or resource constraints",
      "Success metrics and OKRs", "Key stakeholders and decision-makers"],
    repairRole: "You are a senior business analyst and strategy consultant.",
    repairFormat: ["Executive summary (3–5 sentences)", "Situational analysis",
      "Recommendations with rationale", "Implementation roadmap", "Risk and mitigation"],
    repairConstraints: ["Base recommendations on stated data",
      "Quantify impact where possible", "Address feasibility and risks explicitly"],
  },
];

// ─────────────────────────────────────────────────────────────
// Prompt templates — domain-matched starters
// ─────────────────────────────────────────────────────────────

const PROMPT_TEMPLATES = {
  software: [
    {
      label: "System Design",
      content: `You are a senior systems architect.

## Context
[Describe the system / feature you're designing]

## Requirements
- Scale: [e.g., 10k RPS, 1M DAU]
- Latency: [e.g., < 200ms p99]
- Availability: [e.g., 99.9% SLA]

## Constraints
- Existing stack: [languages, frameworks, cloud provider]
- Budget: [compute / infrastructure limit]
- Ensure backward compatibility during transition

## Output Format
1. Architecture overview with key components
2. Technology recommendations with rationale
3. Data flow and API contracts
4. Risk assessment and mitigations
5. Implementation roadmap`,
    },
    {
      label: "API Design",
      content: `Design a RESTful API for [feature].

## Context
[Describe the product and its consumers]

## Requirements
- Endpoints: [list key operations]
- Auth: [JWT / API key / OAuth]
- Rate limits: [requests per minute per user]

## Constraints
- Do not break existing clients
- Follow REST conventions (correct status codes)
- Include pagination for all list endpoints

## Output Format
Return OpenAPI-style endpoint specs with request/response schemas and a curl example.`,
    },
  ],
  ml: [
    {
      label: "Model Evaluation",
      content: `You are a senior ML engineer.

## Task
Evaluate [model / approach] for [use case].

## Dataset
- Size: [N samples]
- Features: [describe input shape]
- Label distribution: [balanced / imbalanced; class ratio]
- Split: [80 / 10 / 10 train/val/test]

## Constraints
- Primary metric: [accuracy / F1 / AUC-ROC — explain why]
- Inference latency budget: [< X ms p99]
- Address data quality and bias

## Output Format
1. Evaluation methodology
2. Baseline vs. proposed metrics table
3. Error analysis on failure cases
4. Recommendations for improvement`,
    },
    {
      label: "RAG Pipeline",
      content: `Design a Retrieval-Augmented Generation pipeline for [use case].

## Context
[Describe the knowledge base and expected query types]

## Requirements
- Chunk size: [tokens per chunk]
- Embedding model: [e.g., nomic-embed-text]
- Vector store: [FAISS / Chroma / Pinecone]
- LLM: [model name and size]

## Constraints
- Retrieval latency < 100ms, generation < 3s
- All data must stay on-premise
- Evaluate recall@k and faithfulness separately

## Output Format
1. Pipeline architecture (text diagram)
2. Chunking and embedding strategy
3. Retrieval and reranking approach
4. Evaluation plan`,
    },
  ],
  python: [
    {
      label: "Function / Module",
      content: `You are an expert Python developer who writes clean, idiomatic, well-tested code.

## Task
Implement [function / module name] that [describe the behavior].

## Requirements
- Input: [parameter names, types, constraints]
- Output: [return type and shape]
- Edge cases to handle: [empty input, None, overflow, etc.]

## Constraints
- Python 3.11+, type hints required
- No external dependencies beyond [list allowed libs]
- Handle errors explicitly — no silent failures
- Follow PEP 8

## Output Format
1. Working implementation with type hints and docstring
2. Usage example
3. Unit tests for core logic and edge cases
4. Time / space complexity note`,
    },
    {
      label: "FastAPI Endpoint",
      content: `Write a FastAPI endpoint for [feature].

## Context
[Describe the API and its consumers]

## Requirements
- Method: [GET / POST / PUT / DELETE]
- Path: /api/v1/[resource]
- Auth: [API key header / JWT bearer / none]
- Request body: [describe fields and types]
- Response: [describe fields and HTTP status codes]

## Constraints
- Use Pydantic v2 models for all validation
- Return appropriate HTTP status codes
- Include error handling for invalid input

## Output Format
Complete FastAPI route with Pydantic models, error handling, and a curl example.`,
    },
  ],
  networking: [
    {
      label: "Network Config",
      content: `You are a senior network engineer and cloud architect.

## Task
Configure [service / component] for [environment].

## Context
- OS: [Ubuntu 22.04 / RHEL 9 / other]
- Network topology: [describe relevant layout]
- Traffic volume: [requests/s or Mbps]

## Requirements
- Security: [firewall rules, encryption, auth method]
- Redundancy: [HA / failover requirements]
- Zero-downtime migration: [yes / no]

## Constraints
- Document all firewall rule changes before applying
- Validate in a test environment first
- Follow principle of least privilege

## Output Format
1. Configuration steps with exact commands
2. Verification commands to confirm correct state
3. Rollback procedure
4. Security considerations`,
    },
    {
      label: "Troubleshoot",
      content: `Diagnose and fix [networking issue].

## Symptoms
- What is failing: [describe]
- When it started: [timestamp / event]
- Scope: [single host / subnet / all users]

## Environment
- OS: [Ubuntu / RHEL / other]
- Services: [nginx / firewalld / wireguard / etc.]
- Exact error: [paste here]

## Already tried
- [Step 1]
- [Step 2]

## Output Format
1. Root cause analysis
2. Fix commands (ready to paste)
3. Verification steps
4. Prevention / monitoring recommendation`,
    },
  ],
  writing: [
    {
      label: "Technical Doc",
      content: `You are an expert technical writer.

## Task
Write [README / API docs / tutorial / architecture doc] for [project / feature].

## Audience
[Developer familiarity: beginner / senior / mixed team]

## Requirements
- Sections to cover: [list them]
- Target length: [word count or section count]
- Tone: [formal / conversational / concise]

## Constraints
- Use active voice throughout
- All code examples must be runnable
- Avoid marketing language

## Output Format
Complete document in Markdown with H2/H3 headers.`,
    },
    {
      label: "Blog Post",
      content: `Write a technical blog post about [topic].

## Audience
[Developers / non-technical / mixed]

## Angle
[What is the unique insight: problem solved / lesson learned / benchmark result]

## Requirements
- Target length: [~800 / ~1500 / ~2500 words]
- Include: [code examples / benchmarks / personal anecdote]
- SEO keyword: [primary keyword]

## Constraints
- Hook in the first 2 sentences — no slow wind-ups
- One concrete example per major claim
- End with a clear takeaway or call to action

## Output Format
Full draft with H2/H3 headers, code blocks, and a summary paragraph.`,
    },
  ],
  business: [
    {
      label: "Strategy Brief",
      content: `You are a senior business analyst and strategy consultant.

## Context
[Company stage, size, and current market position]

## Problem / Opportunity
[Describe what needs to be addressed and why now]

## Constraints
- Timeline: [weeks / months]
- Budget: [range]
- Key stakeholders who must approve: [names / roles]

## Output Format
1. Executive summary (3–5 sentences)
2. Situational analysis
3. Recommendations with rationale
4. Implementation roadmap with milestones
5. Risk assessment and mitigations`,
    },
  ],
};

const GENERIC_TEMPLATES = [
  {
    label: "Chain of Thought",
    content: `Think step by step to answer the following:

[Your question here]

Before giving your final answer:
1. Break the problem into sub-problems
2. Solve each sub-problem
3. Check your reasoning for errors
4. State your final answer clearly`,
  },
  {
    label: "Few-Shot",
    content: `[Task description]

Examples:
Input: [example 1 input]
Output: [example 1 output]

Input: [example 2 input]
Output: [example 2 output]

Now complete this:
Input: [your actual input]
Output:`,
  },
  {
    label: "Role + Task",
    content: `You are a [role with specific expertise].

## Task
[Write / Analyze / Design / Explain] [the deliverable].

## Context
[Background the model needs to answer well]

## Constraints
- [Limit 1: do not include X]
- [Limit 2: stay under N words]
- [Limit 3: must handle Y edge case]

## Output Format
[Specify: JSON / markdown / numbered list / prose]`,
  },
];

// ─────────────────────────────────────────────────────────────
// Core analysis functions
// ─────────────────────────────────────────────────────────────

const VAGUE   = ["something","things","stuff","etc","maybe","perhaps","kind of","sort of","a bit","somehow","basically","generally","usually","quite","simply","obviously","actually","literally","very","really","just"];
const PASSIVE = ["should be","would be","could be","might be","seems to","appears to","tends to"];
const FILLER  = ["please note","as mentioned","it goes without saying","feel free","of course","needless to say"];
const DIRECT  = /^(write|create|analyze|explain|list|generate|compare|summarize|identify|evaluate|describe|design|build|find|give|make|provide|draft|outline|review|classify|translate|extract|format|calculate|suggest|return|produce|convert|refactor|implement|fix|debug|test|validate|parse|transform|propose|recommend)\b/im;

function clamp(n) { return Math.max(0, Math.min(100, Math.round(n))); }
function sColor(n) { return n >= 75 ? T.success : n >= 45 ? T.warn : T.error; }
function sLabel(n) { return n >= 80 ? "Excellent" : n >= 65 ? "Good" : n >= 45 ? "Fair" : "Weak"; }
function hallucColor(risk) { return risk <= 25 ? T.success : risk <= 50 ? T.warn : T.error; }
function tokenColor(t)    { return t < 2000 ? T.success : t < 8000 ? T.warn : T.error; }

function computeMetrics(text) {
  if (!text.trim()) return null;
  const lower = text.toLowerCase();
  const words = text.trim().split(/\s+/);
  const wc    = words.length;
  const sentences = text.split(/(?<=[.!?])\s+/).filter(s => s.trim().length > 2);

  // Clarity
  const vagueHits   = VAGUE.filter(w => lower.includes(w));
  const passiveHits = PASSIVE.filter(p => lower.includes(p));
  const longSents   = sentences.filter(s => s.split(/\s+/).length > 28);
  const fillerHits  = FILLER.filter(f => lower.includes(f));
  let clarity = 100;
  clarity -= vagueHits.length * 9;
  clarity -= passiveHits.length * 7;
  clarity -= longSents.length * 6;
  clarity -= fillerHits.length * 5;
  if (wc > 0 && wc < 8) clarity -= 20;
  clarity = clamp(clarity);

  const clarityFindings = [
    ...vagueHits.slice(0, 2).map(w => ({ ok: false, text: `Vague: "${w}"` })),
    ...passiveHits.slice(0, 1).map(p => ({ ok: false, text: `Passive: "${p}"` })),
    ...longSents.length ? [{ ok: false, text: `${longSents.length} sentence${longSents.length > 1 ? "s" : ""} over 28 words` }] : [],
    ...fillerHits.length ? [{ ok: false, text: `Filler: "${fillerHits[0]}"` }] : [],
    ...(vagueHits.length === 0 && passiveHits.length === 0 ? [{ ok: true, text: "No vague or passive language" }] : []),
  ].slice(0, 4);
  const clarityTip = vagueHits.length ? `Replace "${vagueHits[0]}" with a specific noun.`
    : passiveHits.length ? `Rewrite "${passiveHits[0]}" as a direct imperative.`
    : longSents.length ? "Split overly long sentences into focused ones."
    : "Language is direct and unambiguous.";

  // Structure
  const structChecks = [
    { key: "role",        label: "Role / persona",      tip: '"You are a [role]…" anchors model behavior',             pass: /\b(you are|act as|your role|as a|you're a|you will be|pretend you|assume the role)\b/i.test(text) },
    { key: "task",        label: "Task verb",            tip: "Open with an imperative: Write, Analyze, List…",         pass: DIRECT.test(text) },
    { key: "context",     label: "Context / background", tip: "Provide the background the model needs to answer well",  pass: /\b(context|background|here is|following|given that|based on|consider|note that|assume|the following)\b/i.test(text) },
    { key: "format",      label: "Output format",        tip: "Specify: list, JSON, markdown, numbered steps…",         pass: /\b(format|output|respond with|structure|json|bullet|table|step by step|numbered|markdown|paragraph|in \d+|use \d+)\b/i.test(text) },
    { key: "constraints", label: "Constraints",          tip: "Add limits: 'under 200 words', 'do not include X'",      pass: /\b(do not|don't|avoid|must|should not|limit|maximum|minimum|only|never|always|no more than|at most|at least)\b/i.test(text) },
  ];
  const structPassed = structChecks.filter(c => c.pass).length;
  const structure    = clamp((structPassed / structChecks.length) * 100);
  const missingCheck = structChecks.find(c => !c.pass);
  const structTip    = missingCheck ? missingCheck.tip : "All five structural components present.";

  // Specificity
  const hasNumbers   = /\b\d+\b/.test(text);
  const hasExamples  = /\b(for example|e\.g\.|such as|for instance|like this)\b/i.test(text) || /"[^"]{3,50}"/.test(text);
  const hasTech      = /\b(python|javascript|typescript|react|node|fastapi|django|sql|postgres|redis|docker|kubernetes|git|json|html|css|llm|gpt|claude|pytorch|tensorflow|pandas|bash|aws|gcp|azure)\b/i.test(text);
  const hasQuantLen  = /\b(under|over|more than|less than|at least|at most|exactly|around|up to|no more than)\s+\d+\b/i.test(text);
  const hasScope     = /\b(include|exclude|only|except|focus on|skip|without)\b/i.test(text);
  const hasAudience  = /\b(for (a |an |the )?(beginner|expert|developer|senior|junior|student|user|team|client|non.technical))\b/i.test(text);
  let specificity = 25;
  if (hasNumbers)  specificity += 18;
  if (hasExamples) specificity += 22;
  if (hasTech)     specificity += 14;
  if (hasQuantLen) specificity += 14;
  if (hasScope)    specificity += 10;
  if (hasAudience) specificity += 8;
  if (!hasNumbers && !hasExamples && !hasTech && wc > 20) specificity -= 15;
  specificity = clamp(specificity);
  const specFindings = [
    hasNumbers   ? { ok: true,  text: "Quantified requirements" }  : { ok: false, text: "No numbers or quantities" },
    hasExamples  ? { ok: true,  text: "Examples provided" }         : { ok: false, text: "No examples or quoted strings" },
    hasTech      ? { ok: true,  text: "Named technology / tool" }   : { ok: false, text: "No specific technology named" },
    hasQuantLen  ? { ok: true,  text: "Length / size constraints" } : null,
    hasScope     ? { ok: true,  text: "Scope boundaries defined" }  : null,
  ].filter(Boolean).slice(0, 4);
  const specTip = !hasExamples ? "Add a concrete example or quoted string to anchor expectations."
    : !hasNumbers ? "Add a quantity: word count, item count, time limit."
    : !hasTech ? "Name the specific language, framework, or tool."
    : "Prompt is concrete and well-specified.";

  // Actionability
  const hasImperative  = DIRECT.test(text.trim());
  const hasOutputSpec  = /\b(return|the output|your response|the result|should produce|expected output|respond with|the answer)\b/i.test(text);
  const hasNumberedReq = /^\s*\d+[\.)]\s/m.test(text) || /^\s*[-•*]\s/m.test(text);
  const hasSuccessCrit = /\b(ensure|make sure|verify|confirm|check that|the response should|it should|must be|needs to be)\b/i.test(text);
  const hasSections    = /^#{1,3}\s\S/m.test(text) || /^(step \d|part \d|section \d)/im.test(text);
  const actChecks = [hasImperative, hasOutputSpec, hasNumberedReq, hasSuccessCrit, hasSections];
  let actionability = clamp((actChecks.filter(Boolean).length / actChecks.length) * 100);
  if (hasImperative && hasOutputSpec) actionability = clamp(actionability + 10);
  actionability = clamp(actionability);
  const actFindings = [
    hasImperative  ? { ok: true,  text: "Starts with action verb" }      : { ok: false, text: "No clear imperative opener" },
    hasOutputSpec  ? { ok: true,  text: "Output described" }             : { ok: false, text: "Output not described" },
    hasNumberedReq ? { ok: true,  text: "Structured requirement list" }  : { ok: false, text: "No list or numbered steps" },
    hasSuccessCrit ? { ok: true,  text: "Success criteria defined" }     : { ok: false, text: "No success criteria" },
  ].slice(0, 4);
  const actTip = !hasImperative ? "Start with a clear action verb: Write, Analyze, List…"
    : !hasOutputSpec ? "Describe the expected output: 'Return a JSON object…'"
    : !hasNumberedReq ? "Use a numbered list to separate distinct requirements."
    : "Instructions are clear and actionable.";

  // Token estimate
  const tokenEst = Math.max(1, Math.round(text.length / 4));
  let tokenScore, tokenLabel, tokenTip;
  if      (tokenEst < 50)   { tokenScore = 30; tokenLabel = "Too sparse"; tokenTip = "Too short — likely missing essential context."; }
  else if (tokenEst < 200)  { tokenScore = 55; tokenLabel = "Sparse";     tokenTip = "Add more detail for richer model responses."; }
  else if (tokenEst < 600)  { tokenScore = 95; tokenLabel = "Concise";    tokenTip = "Ideal length — specific without overwhelming."; }
  else if (tokenEst < 1500) { tokenScore = 80; tokenLabel = "Detailed";   tokenTip = "Rich context — ensure each sentence earns its place."; }
  else if (tokenEst < 3000) { tokenScore = 55; tokenLabel = "Long";       tokenTip = "Getting long — remove redundancy and filler."; }
  else                      { tokenScore = 30; tokenLabel = "Very long";  tokenTip = "Dilution risk — consider splitting into sections."; }

  const overall = clamp(clarity * 0.22 + structure * 0.22 + specificity * 0.20 + actionability * 0.20 + tokenScore * 0.16);

  return { overall, clarity, clarityFindings, clarityTip, structure, structChecks, structTip, specificity, specFindings, specTip, actionability, actFindings, actTip, tokenEst, tokenScore, tokenLabel, tokenTip };
}

function detectDomain(text) {
  const lower = text.toLowerCase();
  let best = null, bestHits = 0;
  for (const d of DOMAINS) {
    const hits = d.keywords.filter(kw => lower.includes(kw)).length;
    if (hits > bestHits) { bestHits = hits; best = d; }
  }
  if (!best || bestHits === 0) return null;
  const confidence = clamp(30 + (bestHits / Math.max(1, best.keywords.length * 0.25)) * 70);
  return { ...best, confidence, hits: bestHits };
}

function computeForecast(m) {
  const { clarity, structure, specificity, actionability } = m;
  const accuracy      = clamp(specificity * 0.50 + clarity * 0.30 + structure * 0.20);
  const reasoning     = clamp(structure   * 0.40 + actionability * 0.40 + specificity * 0.20);
  const consistency   = clamp(clarity     * 0.45 + structure     * 0.35 + actionability * 0.20);
  const hallucination = clamp(100 - (specificity * 0.50 + structure * 0.30 + clarity * 0.20));
  return { accuracy, reasoning, consistency, hallucination };
}

function detectMissingContext(domain, text) {
  if (!domain) return [];
  const lower = text.toLowerCase();
  return domain.contextGaps.filter(gap => {
    const keyword = gap.split(" ")[0].toLowerCase().replace(/[^a-z]/g, "");
    return !lower.includes(keyword);
  }).slice(0, 5);
}

function generateRepair(text, m, domain) {
  const missing = new Set(m.structChecks.filter(c => !c.pass).map(c => c.key));
  const d       = domain || DOMAINS[DOMAINS.length - 1]; // fallback to business/general
  const lines   = [];

  if (missing.has("role")) {
    lines.push(d.repairRole);
    lines.push("");
  }

  if (missing.has("context")) {
    lines.push("## Context");
    lines.push(text.trim());
  } else {
    lines.push(text.trim());
  }
  lines.push("");

  if (missing.has("constraints")) {
    lines.push("## Constraints");
    d.repairConstraints.forEach(c => lines.push(`- ${c}`));
    lines.push("");
  }

  if (missing.has("format")) {
    lines.push("## Output Format");
    lines.push("Provide a structured response covering:");
    d.repairFormat.forEach((f, i) => lines.push(`${i + 1}. ${f}`));
    lines.push("");
  }

  lines.push("## Evaluation Criteria");
  lines.push("A strong response should:");
  d.repairFormat.slice(0, 3).forEach(f => lines.push(`- Address: ${f}`));

  return lines.join("\n").trim();
}

// ─────────────────────────────────────────────────────────────
// UI atoms
// ─────────────────────────────────────────────────────────────

function Bar({ pct, color, h = 3 }) {
  return (
    <div style={{ height: h, background: "#1F14080D", borderRadius: 2, overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.35s ease" }} />
    </div>
  );
}

function MetricRow({ label, score, inverted = false, unit = "" }) {
  const color = inverted ? hallucColor(score) : sColor(score);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
      <span style={{ fontSize: 9, color: T.muted, width: 80, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1 }}><Bar pct={inverted ? 100 - score : score} color={color} /></div>
      <span style={{ fontSize: 10, fontWeight: 700, color, fontFamily: FONT, width: 28, textAlign: "right", flexShrink: 0 }}>
        {score}{unit}
      </span>
    </div>
  );
}

// Collapsible panel section
function Section({ title, badge, badgeColor, right, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  const bc = badgeColor || T.muted;
  return (
    <div style={{ borderBottom: `1px solid ${T.border}` }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 7,
          padding: "9px 15px 9px 15px", background: "transparent",
          border: "none", cursor: "pointer", textAlign: "left",
          transition: "background 0.1s",
        }}
        onMouseEnter={e => e.currentTarget.style.background = "#1F140807"}
        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
      >
        <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: T.muted, flex: 1 }}>
          {title}
        </span>
        {badge != null && (
          <span style={{
            fontSize: 9, fontWeight: 700, color: bc,
            background: `${bc}20`, border: `1px solid ${bc}44`,
            borderRadius: 8, padding: "1px 6px",
          }}>
            {badge}
          </span>
        )}
        {right}
        <span style={{ fontSize: 9, color: T.muted }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && <div style={{ padding: "0 15px 13px" }}>{children}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Panel sections
// ─────────────────────────────────────────────────────────────

function PromptHealthSection({ m }) {
  const overallColor = sColor(m.overall);
  return (
    <Section title="Prompt Health" badge={m.overall} badgeColor={overallColor}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          <span style={{ fontSize: 22, fontWeight: 900, color: overallColor, fontFamily: FONT, lineHeight: 1 }}>{m.overall}</span>
          <span style={{ fontSize: 10, color: overallColor, fontWeight: 600 }}>{sLabel(m.overall)}</span>
          <div style={{ flex: 1 }}><Bar pct={m.overall} color={overallColor} h={4} /></div>
        </div>
      </div>
      <MetricRow label="Clarity"       score={m.clarity}      />
      <MetricRow label="Structure"     score={m.structure}    />
      <MetricRow label="Specificity"   score={m.specificity}  />
      <MetricRow label="Actionability" score={m.actionability}/>
      <MetricRow label="Token Quality" score={m.tokenScore}   />
    </Section>
  );
}

function ExecutionForecastSection({ forecast }) {
  const { accuracy, reasoning, consistency, hallucination } = forecast;
  return (
    <Section title="Execution Forecast" defaultOpen={true}>
      <div style={{ fontSize: 9, color: T.muted, marginBottom: 9, lineHeight: 1.5 }}>
        Predicted output characteristics based on input quality signals.
      </div>
      <MetricRow label="Accuracy"        score={accuracy}     />
      <MetricRow label="Reasoning Depth" score={reasoning}    />
      <MetricRow label="Consistency"     score={consistency}  />
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 9, color: T.muted, width: 80, flexShrink: 0 }}>Hallucination</span>
        <div style={{ flex: 1 }}><Bar pct={hallucination} color={hallucColor(hallucination)} h={3} /></div>
        <span style={{ fontSize: 10, fontWeight: 700, color: hallucColor(hallucination), fontFamily: FONT, width: 28, textAlign: "right", flexShrink: 0 }}>
          {hallucination}
        </span>
      </div>
      <div style={{ fontSize: 9, color: T.muted, marginTop: 6, lineHeight: 1.5, borderTop: `1px solid ${T.border}`, paddingTop: 7 }}>
        Hallucination risk: lower is better. High specificity and structure reduce invented content.
      </div>
    </Section>
  );
}

function MissingContextSection({ m, domain, missingCtx }) {
  const allGaps = [
    ...m.structChecks.filter(c => !c.pass).map(c => ({ src: "structure", text: c.label, tip: c.tip })),
    ...(missingCtx || []).map(text => ({ src: "context", text })),
  ];
  const count = allGaps.length;

  return (
    <Section title="Missing Context" badge={count > 0 ? `${count} gaps` : "Complete"} badgeColor={count > 0 ? T.error : T.success}>
      {count === 0 ? (
        <div style={{ fontSize: 10, color: T.success }}>No critical gaps detected.</div>
      ) : (
        <>
          <div style={{ fontSize: 9, color: T.muted, marginBottom: 9, lineHeight: 1.5 }}>
            Filling these gaps will directly raise Structure and Specificity scores.
          </div>
          {allGaps.map((gap, i) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 9, color: T.error, marginTop: 1, flexShrink: 0 }}>✗</span>
              <div>
                <div style={{ fontSize: 10.5, color: "#D4A0A0" }}>{gap.text}</div>
                {gap.tip && <div style={{ fontSize: 9.5, color: T.muted, lineHeight: 1.4, marginTop: 1 }}>{gap.tip}</div>}
              </div>
            </div>
          ))}
        </>
      )}
    </Section>
  );
}

function SuggestedAgentsSection({ domain }) {
  if (!domain) {
    return (
      <Section title="Suggested Agents" badge="Undetected" badgeColor={T.muted}>
        <div style={{ fontSize: 10, color: T.muted, lineHeight: 1.6 }}>
          Domain undetected. Add technical keywords or a role statement to enable agent matching.
        </div>
      </Section>
    );
  }
  return (
    <Section title="Suggested Agents" badge={`${domain.confidence}% conf`} badgeColor={T.accent}>
      <div style={{ marginBottom: 9 }}>
        <div style={{ fontSize: 10.5, fontWeight: 700, color: T.text, marginBottom: 2 }}>{domain.label}</div>
        <Bar pct={domain.confidence} color={T.accent} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {domain.agents.map((agent, i) => (
          <div key={agent} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 10, color: i === 0 ? T.success : T.muted }}>
              {i === 0 ? "✓" : "○"}
            </span>
            <span style={{ fontSize: 10.5, color: i === 0 ? T.text : T.mutedLt }}>{agent}</span>
            {i === 0 && (
              <span style={{ marginLeft: "auto", fontSize: 9, color: T.accent, background: `${T.accent}18`, border: `1px solid ${T.accent}33`, borderRadius: 8, padding: "1px 5px" }}>
                Primary
              </span>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

function PromptUpgradeSection({ m, domain, content, onApply }) {
  const [repair,    setRepair]    = useState(null);
  const [loading,   setLoading]   = useState(false);

  async function handleFix() {
    setLoading(true);
    await new Promise(r => setTimeout(r, 280));
    const improved       = generateRepair(content, m, domain);
    const improvedMet    = computeMetrics(improved);
    setRepair({ original: content, improved, originalScore: m.overall, improvedScore: improvedMet?.overall ?? 0 });
    setLoading(false);
  }

  const delta = repair ? repair.improvedScore - repair.originalScore : null;

  return (
    <Section title="Prompt Upgrade" badge={delta != null ? `+${delta}` : null} badgeColor={T.success} defaultOpen={true}>
      {!repair ? (
        <>
          <div style={{ fontSize: 9, color: T.muted, marginBottom: 10, lineHeight: 1.6 }}>
            Adds missing structure, role, output format, and constraints based on detected domain and gaps.
          </div>
          <button
            onClick={handleFix}
            disabled={loading || m.overall >= 90}
            style={{
              width: "100%", padding: "8px 0",
              background: m.overall >= 90 ? "#1F140808" : `${T.accent}22`,
              border: `1px solid ${m.overall >= 90 ? T.border : T.accent + "66"}`,
              color: m.overall >= 90 ? T.muted : T.accent,
              borderRadius: 3, fontSize: 11, fontWeight: 600, fontFamily: "inherit",
              cursor: m.overall >= 90 ? "default" : "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={e => { if (m.overall < 90) e.currentTarget.style.background = `${T.accent}38`; }}
            onMouseLeave={e => { if (m.overall < 90) e.currentTarget.style.background = `${T.accent}22`; }}
          >
            {loading ? "Analyzing…" : m.overall >= 90 ? "Prompt already strong" : "Auto Fix Prompt"}
          </button>
        </>
      ) : (
        <>
          {/* Score trajectory */}
          <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 12 }}>
            <div style={{ textAlign: "center", flex: 1 }}>
              <div style={{ fontSize: 18, fontWeight: 900, color: sColor(repair.originalScore), fontFamily: FONT }}>{repair.originalScore}</div>
              <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>v1 · Original</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
              <span style={{ fontSize: 9, color: T.success, fontWeight: 700 }}>+{delta}</span>
              <span style={{ fontSize: 14, color: T.muted }}>→</span>
            </div>
            <div style={{ textAlign: "center", flex: 1 }}>
              <div style={{ fontSize: 18, fontWeight: 900, color: sColor(repair.improvedScore), fontFamily: FONT }}>{repair.improvedScore}</div>
              <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>v2 · Repaired</div>
            </div>
          </div>

          {/* Repaired prompt preview */}
          <div style={{ fontSize: 9, color: T.muted, marginBottom: 4, letterSpacing: "0.05em", textTransform: "uppercase" }}>Preview</div>
          <div style={{
            background: `${T.success}09`, border: `1px solid ${T.success}33`,
            borderRadius: 3, padding: "8px 10px",
            fontSize: 10, color: "#2A6030", fontFamily: FONT,
            lineHeight: 1.6, maxHeight: 160, overflowY: "auto",
            whiteSpace: "pre-wrap", marginBottom: 10,
          }}>
            {repair.improved}
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => { onApply(repair.improved); setRepair(null); }}
              style={{
                flex: 2, padding: "7px 0",
                background: `${T.success}22`, border: `1px solid ${T.success}55`,
                color: T.success, borderRadius: 3, fontSize: 11, fontWeight: 700,
                fontFamily: "inherit", cursor: "pointer", transition: "background 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = `${T.success}38`}
              onMouseLeave={e => e.currentTarget.style.background = `${T.success}22`}
            >
              Apply Fix
            </button>
            <button
              onClick={() => setRepair(null)}
              style={{
                flex: 1, padding: "7px 0",
                background: "transparent", border: `1px solid ${T.border}`,
                color: T.muted, borderRadius: 3, fontSize: 11,
                fontFamily: "inherit", cursor: "pointer",
              }}
            >
              Dismiss
            </button>
          </div>
        </>
      )}
    </Section>
  );
}

function TemplatesSection({ domain, currentContent, onApply }) {
  const key = domain?.id;
  const templates = (key && PROMPT_TEMPLATES[key]) ? PROMPT_TEMPLATES[key] : GENERIC_TEMPLATES;
  const label     = domain ? `${domain.label}` : "Generic";

  function insert(tpl) {
    onApply(currentContent.trim() ? `${currentContent.trimEnd()}\n\n${tpl.content}` : tpl.content);
  }

  return (
    <Section title="Templates" badge={templates.length} badgeColor={T.muted} defaultOpen={false}>
      <div style={{ fontSize: 9, color: T.muted, marginBottom: 9, lineHeight: 1.5 }}>
        {label} starters. Click to insert at end of editor.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {templates.map((tpl, i) => (
          <button
            key={i}
            onClick={() => insert(tpl)}
            style={{
              width: "100%", textAlign: "left", padding: "6px 9px",
              background: "#1F140808", border: `1px solid ${T.border}`,
              borderRadius: 3, color: T.mutedLt, fontSize: 10.5,
              fontFamily: "inherit", cursor: "pointer",
              transition: "background 0.12s, color 0.12s",
            }}
            onMouseEnter={e => { e.currentTarget.style.background = "#1F140814"; e.currentTarget.style.color = T.text; }}
            onMouseLeave={e => { e.currentTarget.style.background = "#1F140808"; e.currentTarget.style.color = T.mutedLt; }}
          >
            {tpl.label}
          </button>
        ))}
      </div>
    </Section>
  );
}

// ─────────────────────────────────────────────────────────────
// Run Across Models — actually executes the prompt (POST /debug/prompt)
// The static sections above say *why* a prompt is weak; this one runs it,
// against the configured model by default and any extras side by side.
// ─────────────────────────────────────────────────────────────

// Optional comparison targets. "Current" (the saved provider) is added first
// at runtime; these only run if the matching provider/key is configured —
// otherwise the result slot carries the error, which is the point of a debugger.
const COMPARE_TARGETS = [
  { id: "ollama",    label: "Local · phi4-mini",  cfg: { provider: "ollama",    model: "phi4-mini:latest" } },
  { id: "anthropic", label: "Claude Sonnet 4.6",  cfg: { provider: "anthropic", model: "claude-sonnet-4-6" } },
  { id: "openai",    label: "GPT-4o-mini",        cfg: { provider: "openai",    model: "gpt-4o-mini", base_url: "https://api.openai.com/v1" } },
];

// Divergence highlight — the point of running side by side is to SEE where the
// models disagree. We measure it client-side: each output becomes a set of
// normalized word tokens, and we average the pairwise Jaccard overlap. High
// overlap = the models converged on the same answer; low = the prompt is
// under-specified enough that model choice changes the result.
function tokenSet(text) {
  return new Set(
    (text || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter(w => w.length > 2)   // drop noise words / punctuation fragments
  );
}

function computeDivergence(results) {
  const ok = (results || []).filter(r => !r.error && r.output);
  if (ok.length < 2) return null;

  const sets = ok.map(r => tokenSet(r.output));
  let total = 0, pairs = 0;
  for (let i = 0; i < sets.length; i++) {
    for (let j = i + 1; j < sets.length; j++) {
      const a = sets[i], b = sets[j];
      let inter = 0;
      for (const w of a) if (b.has(w)) inter++;
      const union = a.size + b.size - inter;
      total += union === 0 ? 1 : inter / union;
      pairs++;
    }
  }
  const agreement = pairs ? total / pairs : 1;   // 0..1

  const wordCounts = ok.map(r => r.words ?? (r.output || "").split(/\s+/).filter(Boolean).length);
  const minW = Math.min(...wordCounts);
  const maxW = Math.max(...wordCounts);

  let verdict, color;
  if (agreement >= 0.6)      { verdict = "Aligned";   color = T.success; }
  else if (agreement >= 0.3) { verdict = "Mixed";     color = T.accent;  }
  else                       { verdict = "Divergent"; color = T.error;   }

  return { count: ok.length, agreement, minW, maxW, verdict, color };
}

// Quick rationale tags — clean, classifiable signal alongside free text. The
// "why?" is the activation moment: the user teaches the system which output won
// and what mattered, turning a throwaway run into a durable decision record.
const WHY_TAGS = ["Accuracy", "Formatting", "Reasoning", "Speed", "Concise", "Tone"];

function RunAcrossModelsSection({ content }) {
  const [current, setCurrent] = useState(null);   // { provider, model, base_url }
  const [sel,     setSel]     = useState(() => new Set(["current"]));
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error,   setError]   = useState(null);
  // Decision capture (the bridge): which result won, and why.
  const [chosen,  setChosen]  = useState(null);   // index into results
  const [why,     setWhy]     = useState("");
  const [whyTags, setWhyTags] = useState(() => new Set());
  const [savedId, setSavedId] = useState(null);   // decision id once persisted
  const [saving,  setSaving]  = useState(false);
  // Sticky project tag — without it every decision lands in "(all)" and
  // per-project briefings are meaningless. Persisted so it carries across runs.
  const [project, setProject] = useState(() => {
    try { return localStorage.getItem("amagra_project") || ""; } catch { return ""; }
  });
  const updateProject = (v) => {
    setProject(v);
    try { localStorage.setItem("amagra_project", v); } catch {}
  };

  const resetCapture = () => { setChosen(null); setWhy(""); setWhyTags(new Set()); setSavedId(null); };
  const toggleTag = (t) => setWhyTags(prev => {
    const n = new Set(prev); n.has(t) ? n.delete(t) : n.add(t); return n;
  });

  async function saveDecision() {
    if (chosen == null || !results) return;
    setSaving(true);
    const win = results[chosen];
    try {
      const r = await fetch(`${API}/debug/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: content,
          chosen_provider: win.provider,
          chosen_model: win.model || "",
          temperature: 0.2,
          candidates: results.map(x => ({
            provider: x.provider, model: x.model, latency_ms: x.latency_ms,
            chars: x.chars, words: x.words, error: x.error,
          })),
          rationale: why.trim(),
          rationale_tags: Array.from(whyTags),
          project: project.trim(),
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setSavedId(d.decision_id ?? true);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    fetch(`${API}/settings/llm`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.current) setCurrent(d.current); })
      .catch(() => {});
  }, []);

  // Current first; drop any extra that duplicates the saved model.
  const targets = useMemo(() => {
    const list = [];
    if (current?.provider) {
      list.push({
        id: "current",
        label: `Current · ${current.provider}${current.model ? " / " + current.model : ""}`,
        cfg: { provider: current.provider, model: current.model, base_url: current.base_url },
      });
    }
    for (const t of COMPARE_TARGETS) {
      if (current && t.cfg.provider === current.provider && t.cfg.model === current.model) continue;
      list.push(t);
    }
    return list;
  }, [current]);

  const toggle = (id) => setSel(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  async function run() {
    setRunning(true); setError(null); setResults(null); resetCapture();
    const models = targets.filter(t => sel.has(t.id)).map(t => t.cfg);
    try {
      const r = await fetch(`${API}/debug/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: content, temperature: 0.2, models }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResults(await r.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setRunning(false);
    }
  }

  const canRun = content.trim().length > 0 && !running;

  return (
    <Section title="Run Across Models" badge={results ? results.length : null} badgeColor={T.accent} defaultOpen={true}>
      <div style={{ fontSize: 9, color: T.muted, marginBottom: 9, lineHeight: 1.6 }}>
        Runs this exact prompt and shows real output. Pick targets — unconfigured ones report their error.
      </div>

      {/* Target checkboxes */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 10 }}>
        {targets.length === 0 && (
          <div style={{ fontSize: 9.5, color: T.muted }}>Loading configured model…</div>
        )}
        {targets.map(t => (
          <label key={t.id} style={{ display: "flex", alignItems: "center", gap: 7, cursor: "pointer", fontSize: 10.5, color: T.mutedLt }}>
            <input type="checkbox" checked={sel.has(t.id)} onChange={() => toggle(t.id)}
                   style={{ accentColor: T.accent, width: 13, height: 13 }} />
            {t.label}
          </label>
        ))}
      </div>

      <button
        onClick={run}
        disabled={!canRun}
        style={{
          width: "100%", padding: "8px 0",
          background: canRun ? `${T.accent}22` : "#1F140808",
          border: `1px solid ${canRun ? T.accent + "66" : T.border}`,
          color: canRun ? T.accent : T.muted,
          borderRadius: 3, fontSize: 11, fontWeight: 600, fontFamily: "inherit",
          cursor: canRun ? "pointer" : "default", transition: "background 0.15s",
        }}
        onMouseEnter={e => { if (canRun) e.currentTarget.style.background = `${T.accent}38`; }}
        onMouseLeave={e => { if (canRun) e.currentTarget.style.background = `${T.accent}22`; }}
      >
        {running ? "Running…" : content.trim() ? "Run Prompt" : "Write a prompt first"}
      </button>

      {error && (
        <div style={{ marginTop: 10, fontSize: 10, color: T.error, background: `${T.error}0E`,
                      border: `1px solid ${T.error}33`, borderRadius: 3, padding: "7px 9px", lineHeight: 1.5 }}>
          {error}
        </div>
      )}

      {/* Divergence highlight — how much the models actually agree */}
      {results && (() => {
        const d = computeDivergence(results);
        if (!d) return null;
        const pct = Math.round(d.agreement * 100);
        return (
          <div style={{ marginTop: 12, border: `1px solid ${d.color}33`, borderRadius: 3,
                        background: `${d.color}0C`, padding: "7px 9px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 6 }}>
              <span style={{ fontSize: 9.5, fontWeight: 700, color: d.color, fontFamily: FONT }}>
                {d.verdict} · {pct}% agreement
              </span>
              <span style={{ fontSize: 8.5, color: T.muted, fontFamily: FONT, flexShrink: 0 }}>
                {d.count} models · {d.minW === d.maxW ? `${d.minW}w` : `${d.minW}–${d.maxW}w`}
              </span>
            </div>
            {/* agreement bar */}
            <div style={{ marginTop: 5, height: 3, background: `${d.color}22`, borderRadius: 2, overflow: "hidden" }}>
              <div style={{ width: `${pct}%`, height: "100%", background: d.color }} />
            </div>
            <div style={{ marginTop: 5, fontSize: 8.5, color: T.muted, lineHeight: 1.5 }}>
              {d.agreement >= 0.6
                ? "Models converged — the prompt pins the answer down."
                : d.agreement >= 0.3
                ? "Partial overlap — model choice shifts the result."
                : "Outputs diverge — the prompt is under-specified for cross-model use."}
            </div>
          </div>
        );
      })()}

      {/* Result cards, stacked to fit the narrow rail */}
      {results && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
          {results.map((res, i) => {
            const ok = !res.error;
            const c  = ok ? T.success : T.error;
            const isChosen = chosen === i;
            return (
              <div key={i} style={{ border: `1px solid ${isChosen ? T.accent : c}${isChosen ? "88" : "33"}`,
                                    borderRadius: 3, background: isChosen ? `${T.accent}10` : `${c}08`, overflow: "hidden" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
                              padding: "5px 8px", borderBottom: `1px solid ${c}22`, gap: 6 }}>
                  <span style={{ fontSize: 9.5, fontWeight: 700, color: c, fontFamily: FONT, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {res.provider}{res.model ? " / " + res.model : ""}
                  </span>
                  <span style={{ fontSize: 8.5, color: T.muted, fontFamily: FONT, flexShrink: 0 }}>
                    {res.latency_ms != null ? `${res.latency_ms}ms` : ""}{ok && res.words != null ? ` · ${res.words}w` : ""}
                  </span>
                </div>
                <div style={{ padding: "7px 9px", fontSize: 10, color: ok ? "#2A4030" : T.error,
                              fontFamily: FONT, lineHeight: 1.6, maxHeight: 200, overflowY: "auto", whiteSpace: "pre-wrap" }}>
                  {ok ? res.output : res.error}
                </div>
                {ok && savedId == null && (
                  <button
                    onClick={() => setChosen(isChosen ? null : i)}
                    style={{ width: "100%", padding: "4px 0", border: "none", borderTop: `1px solid ${c}22`,
                             background: isChosen ? `${T.accent}22` : "transparent",
                             color: isChosen ? T.accent : T.muted, fontSize: 9, fontWeight: 700,
                             fontFamily: FONT, cursor: "pointer", letterSpacing: 0.3 }}>
                    {isChosen ? "✓ CHOSEN" : "CHOOSE THIS"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* The "why?" tap — capture rationale on the chosen output. One interaction
          that yields better memory, better recall, more trust, and activation. */}
      {results && chosen != null && savedId == null && (
        <div style={{ marginTop: 12, border: `1px solid ${T.accent}44`, borderRadius: 3,
                      background: `${T.accent}0A`, padding: "9px 10px" }}>
          <div style={{ fontSize: 9.5, fontWeight: 700, color: T.accent, fontFamily: FONT, marginBottom: 7 }}>
            Why this one?
          </div>
          <input
            value={project} onChange={e => updateProject(e.target.value)}
            placeholder="Project (optional — groups this decision)"
            style={{ width: "100%", boxSizing: "border-box", fontFamily: FONT, fontSize: 9.5,
                     padding: "5px 8px", borderRadius: 3, border: `1px solid ${T.border}`,
                     background: T.surface, color: T.mutedLt, marginBottom: 8 }} />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 8 }}>
            {WHY_TAGS.map(t => {
              const on = whyTags.has(t);
              return (
                <button key={t} onClick={() => toggleTag(t)}
                  style={{ padding: "3px 8px", borderRadius: 10, fontSize: 9, fontWeight: 600, fontFamily: FONT,
                           cursor: "pointer", border: `1px solid ${on ? T.accent : T.border}`,
                           background: on ? `${T.accent}22` : "transparent", color: on ? T.accent : T.muted }}>
                  {t}
                </button>
              );
            })}
          </div>
          <textarea
            value={why} onChange={e => setWhy(e.target.value)} rows={2}
            placeholder="Optional: a sentence on what made this output better…"
            style={{ width: "100%", boxSizing: "border-box", resize: "vertical", fontFamily: FONT,
                     fontSize: 10, lineHeight: 1.5, padding: "6px 8px", borderRadius: 3,
                     border: `1px solid ${T.border}`, background: T.surface, color: T.mutedLt, marginBottom: 8 }} />
          <button
            onClick={saveDecision} disabled={saving}
            style={{ width: "100%", padding: "7px 0", border: `1px solid ${T.accent}66`,
                     background: `${T.accent}22`, color: T.accent, borderRadius: 3,
                     fontSize: 10.5, fontWeight: 700, fontFamily: "inherit", cursor: saving ? "default" : "pointer" }}>
            {saving ? "Saving…" : "Remember this decision"}
          </button>
          <div style={{ marginTop: 6, fontSize: 8.5, color: T.muted, lineHeight: 1.5 }}>
            A reason is captured as <strong>explicit</strong> (trusted) memory; a bare choice is <strong>derived</strong> (tentative).
          </div>
        </div>
      )}

      {/* Activation payoff — the user sees the workspace got smarter. */}
      {savedId != null && (
        <div style={{ marginTop: 12, border: `1px solid ${T.success}44`, borderRadius: 3,
                      background: `${T.success}0E`, padding: "8px 10px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: T.success, fontFamily: FONT, marginBottom: 3 }}>
            ✓ Decision remembered
          </div>
          <div style={{ fontSize: 9, color: T.muted, lineHeight: 1.5 }}>
            Amagra now knows you chose <strong>{results[chosen]?.provider}{results[chosen]?.model ? " / " + results[chosen].model : ""}</strong> for this kind of work. It will surface when you ask about this project.
          </div>
        </div>
      )}
    </Section>
  );
}

// ─────────────────────────────────────────────────────────────
// Metrics panel — assembles all sections
// ─────────────────────────────────────────────────────────────

function MetricsPanel({ metrics, content, onApply }) {
  const domain     = useMemo(() => detectDomain(content), [content]);
  const forecast   = useMemo(() => metrics ? computeForecast(metrics) : null, [metrics]);
  const missingCtx = useMemo(() => {
    if (!metrics || !domain) return [];
    return detectMissingContext(domain, content);
  }, [metrics, domain, content]);

  if (!metrics) {
    return (
      <div style={{ width: 272, flexShrink: 0, borderLeft: `1px solid ${T.border}`, background: T.surface, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
        <div style={{ textAlign: "center", color: T.muted, fontSize: 11, lineHeight: 1.9 }}>
          Start writing<br />to activate the<br />Prompt IDE.
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: 272, flexShrink: 0, borderLeft: `1px solid ${T.border}`, background: T.surface, overflowY: "auto", overflowX: "hidden", display: "flex", flexDirection: "column" }}>
      <PromptHealthSection    m={metrics} />
      <ExecutionForecastSection forecast={forecast} />
      <MissingContextSection  m={metrics} domain={domain} missingCtx={missingCtx} />
      <SuggestedAgentsSection domain={domain} />
      <TemplatesSection       domain={domain} currentContent={content} onApply={onApply} />
      <PromptUpgradeSection   m={metrics} domain={domain} content={content} onApply={onApply} />
      <RunAcrossModelsSection content={content} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Editor helpers
// ─────────────────────────────────────────────────────────────

function makeTab(id) { return { id, title: `Prompt ${id}`, content: "" }; }

function loadSaved() {
  try {
    const raw = localStorage.getItem("prompt_editor_v1");
    if (!raw) return null;
    const { tabs, activeId, showMetrics } = JSON.parse(raw);
    if (Array.isArray(tabs) && tabs.length > 0) return { tabs, activeId, showMetrics };
  } catch {}
  return null;
}

function persist(tabs, activeId, showMetrics) {
  try { localStorage.setItem("prompt_editor_v1", JSON.stringify({ tabs, activeId, showMetrics })); } catch {}
}

function getCursorPos(ta) {
  const before = ta.value.substring(0, ta.selectionStart);
  const ls = before.split("\n");
  return { line: ls.length, col: ls[ls.length - 1].length + 1 };
}

// ─────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────

export default function PromptEditorTab() {
  const saved   = loadSaved();
  const nextRef = useRef(saved ? Math.max(...saved.tabs.map(t => t.id)) + 1 : 2);

  const [tabs,        setTabs]        = useState(saved?.tabs        ?? [makeTab(1)]);
  const [activeId,    setActiveId]    = useState(saved?.activeId    ?? 1);
  const [showMetrics, setShowMetrics] = useState(saved?.showMetrics ?? true);
  const [editingId,   setEditingId]   = useState(null);
  const [editingTitle,setEditingTitle]= useState("");
  const [cursor,      setCursor]      = useState({ line: 1, col: 1 });

  const textareaRef    = useRef(null);
  const lineNumRef     = useRef(null);
  const pendingCursor  = useRef(null);
  const copyTimerRef   = useRef(null);
  const [copied, setCopied] = useState(false);

  const activeTab = tabs.find(t => t.id === activeId) ?? tabs[0];
  const content   = activeTab?.content ?? "";
  const lines     = content.split("\n");
  const metrics   = useMemo(() => computeMetrics(content), [content]);

  useEffect(() => { persist(tabs, activeId, showMetrics); }, [tabs, activeId, showMetrics]);
  useEffect(() => { textareaRef.current?.focus(); }, [activeId]);

  const updateContent = useCallback((val) => {
    setTabs(prev => prev.map(t => t.id === activeId ? { ...t, content: val } : t));
  }, [activeId]);

  const syncScroll = useCallback(() => {
    if (lineNumRef.current && textareaRef.current)
      lineNumRef.current.scrollTop = textareaRef.current.scrollTop;
  }, []);

  // Restore cursor position after Tab-key insertion (React resets it on state update)
  useEffect(() => {
    if (pendingCursor.current !== null && textareaRef.current) {
      textareaRef.current.setSelectionRange(pendingCursor.current, pendingCursor.current);
      pendingCursor.current = null;
    }
  }, [content]);

  function handleCopy() {
    if (!content.trim()) return;
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), 1500);
    });
  }

  function handleKeyDown(e) {
    // Tab → insert 2 spaces (preserve cursor position via pendingCursor ref)
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = e.target;
      const s  = ta.selectionStart;
      const end = ta.selectionEnd;
      updateContent(ta.value.substring(0, s) + "  " + ta.value.substring(end));
      pendingCursor.current = s + 2;
      return;
    }
    // Ctrl+Enter → copy to clipboard
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleCopy();
      return;
    }
    // Ctrl+Shift+K → clear current tab
    if (e.key.toLowerCase() === "k" && (e.ctrlKey || e.metaKey) && e.shiftKey) {
      e.preventDefault();
      updateContent("");
    }
  }

  function addTab() {
    const id = nextRef.current++;
    setTabs(prev => [...prev, makeTab(id)]);
    setActiveId(id);
  }

  function closeTab(id, e) {
    e.stopPropagation();
    setTabs(prev => {
      const next = prev.filter(t => t.id !== id);
      if (next.length === 0) {
        const fresh = makeTab(nextRef.current++);
        setActiveId(fresh.id);
        return [fresh];
      }
      if (activeId === id) {
        const idx = prev.findIndex(t => t.id === id);
        setActiveId(next[Math.min(idx, next.length - 1)].id);
      }
      return next;
    });
  }

  function startRename(tab, e) {
    e.stopPropagation();
    setEditingId(tab.id);
    setEditingTitle(tab.title);
  }

  function commitRename() {
    const title = editingTitle.trim();
    if (title) setTabs(prev => prev.map(t => t.id === editingId ? { ...t, title } : t));
    setEditingId(null);
  }

  function trackCursor(e) { setCursor(getCursorPos(e.target)); }

  const wordCount    = content.trim() ? content.trim().split(/\s+/).length : 0;
  const overallScore = metrics?.overall ?? null;
  const overallColor = overallScore != null ? sColor(overallScore) : T.muted;

  // Status bar metric pips
  const statusPips = metrics ? [
    { k: "CLR", v: metrics.clarity,       c: sColor(metrics.clarity) },
    { k: "STR", v: metrics.structure,     c: sColor(metrics.structure) },
    { k: "SPC", v: metrics.specificity,   c: sColor(metrics.specificity) },
    { k: "ACT", v: metrics.actionability, c: sColor(metrics.actionability) },
    { k: "TOK", v: metrics.tokenScore,    c: sColor(metrics.tokenScore) },
  ] : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: T.bg, overflow: "hidden" }}>

      {/* ── Tab strip ── */}
      <div style={{ display: "flex", alignItems: "stretch", flexShrink: 0, background: T.surface2, borderBottom: `1px solid ${T.border}` }}>
        <div style={{ display: "flex", alignItems: "stretch", flex: 1, overflowX: "auto", overflowY: "hidden", scrollbarWidth: "none" }}>
          {tabs.map(tab => {
            const isActive = tab.id === activeId;
            return (
              <div key={tab.id} onClick={() => setActiveId(tab.id)} onDoubleClick={e => startRename(tab, e)} title="Double-click to rename"
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 10px 0 16px", height: 35, flexShrink: 0, background: isActive ? T.tabActiveBg : T.tabInactiveBg, borderRight: `1px solid ${T.border}`, borderTop: `1.5px solid ${isActive ? T.accent : "transparent"}`, cursor: "pointer", color: isActive ? T.text : T.muted, fontSize: 12, fontFamily: "inherit", userSelect: "none", transition: "color 0.1s" }}>
                {editingId === tab.id ? (
                  <input autoFocus value={editingTitle} onChange={e => setEditingTitle(e.target.value)} onBlur={commitRename}
                    onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); commitRename(); } if (e.key === "Escape") setEditingId(null); }}
                    onClick={e => e.stopPropagation()}
                    style={{ background: "transparent", border: "none", borderBottom: `1px solid ${T.accent}`, outline: "none", color: T.text, fontSize: 12, fontFamily: "inherit", width: Math.max(60, editingTitle.length * 7.5 + 8) }} />
                ) : (
                  <span style={{ whiteSpace: "nowrap", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis" }}>{tab.title}</span>
                )}
                <button onClick={e => closeTab(tab.id, e)} title="Close"
                  style={{ background: "none", border: "none", color: "transparent", cursor: "pointer", padding: 0, fontSize: 14, lineHeight: 1, width: 16, height: 16, flexShrink: 0, borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "center", transition: "color 0.1s, background 0.1s" }}
                  onMouseEnter={e => { e.currentTarget.style.color = T.text; e.currentTarget.style.background = "#1F140818"; }}
                  onMouseLeave={e => { e.currentTarget.style.color = isActive ? "#A08868" : "transparent"; e.currentTarget.style.background = "transparent"; }}
                >×</button>
              </div>
            );
          })}
          <button onClick={addTab} title="New prompt" style={{ background: "none", border: "none", color: T.muted, cursor: "pointer", padding: "0 14px", fontSize: 20, lineHeight: 1, flexShrink: 0, fontFamily: "inherit", transition: "color 0.1s" }}
            onMouseEnter={e => e.currentTarget.style.color = T.text} onMouseLeave={e => e.currentTarget.style.color = T.muted}>+</button>
        </div>

        <button onClick={handleCopy} disabled={!content.trim()} title="Copy prompt (Ctrl+Enter)"
          style={{ display: "flex", alignItems: "center", gap: 5, padding: "0 13px", flexShrink: 0, background: copied ? `${T.success}18` : "transparent", border: "none", borderLeft: `1px solid ${T.border}`, color: copied ? T.success : content.trim() ? T.mutedLt : T.muted, cursor: content.trim() ? "pointer" : "default", fontSize: 11, fontFamily: "inherit", transition: "color 0.15s, background 0.15s" }}>
          <span style={{ fontSize: 12 }}>{copied ? "✓" : "⎘"}</span>
          <span>{copied ? "Copied!" : "Copy"}</span>
        </button>
        <button onClick={() => setShowMetrics(v => !v)} title={showMetrics ? "Hide Prompt IDE" : "Show Prompt IDE"}
          style={{ display: "flex", alignItems: "center", gap: 7, padding: "0 14px", flexShrink: 0, background: showMetrics ? `${T.accent}15` : "transparent", border: "none", borderLeft: `1px solid ${T.border}`, borderTop: `1.5px solid ${showMetrics ? T.accent : "transparent"}`, color: showMetrics ? T.accent : T.muted, cursor: "pointer", fontSize: 11, fontFamily: "inherit", transition: "color 0.1s, background 0.1s" }}>
          {overallScore != null && <span style={{ fontSize: 12, fontWeight: 800, color: overallColor, fontFamily: FONT }}>{overallScore}</span>}
          <span>Prompt IDE</span>
        </button>
      </div>

      {/* ── Editor + Panel ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <div ref={lineNumRef} style={{ width: 52, flexShrink: 0, background: T.bg, borderRight: `1px solid ${T.gutterBorder}`, overflow: "hidden", paddingTop: 12, paddingRight: 10, fontFamily: FONT, fontSize: FONT_SZ, lineHeight: `${LINE_H}px`, userSelect: "none", textAlign: "right" }}>
            {lines.map((_, i) => (
              <div key={i} style={{ color: i + 1 === cursor.line ? T.lineNumActive : T.muted, fontWeight: i + 1 === cursor.line ? 600 : 400 }}>{i + 1}</div>
            ))}
          </div>
          <textarea ref={textareaRef} value={content} onChange={e => updateContent(e.target.value)} onScroll={syncScroll} onClick={trackCursor} onKeyUp={trackCursor} onSelect={trackCursor} onKeyDown={handleKeyDown}
            spellCheck={false} autoComplete="off" autoCorrect="off" autoCapitalize="off" placeholder="Write your prompt here…"
            style={{ flex: 1, background: T.bg, border: "none", outline: "none", color: T.text, fontFamily: FONT, fontSize: FONT_SZ, lineHeight: `${LINE_H}px`, padding: "12px 20px", resize: "none", overflowY: "auto", overflowX: "auto", whiteSpace: "pre", tabSize: 2, caretColor: "#1F1408" }}
          />
        </div>

        {showMetrics && <MetricsPanel metrics={metrics} content={content} onApply={updateContent} />}
      </div>

      {/* ── Status bar ── */}
      <div style={{ height: 24, background: T.statusBg, flexShrink: 0, display: "flex", alignItems: "center", padding: "0 14px", fontSize: 11, color: T.muted, borderTop: `1px solid ${T.border}`, userSelect: "none" }}>
        <span style={{ color: T.mutedLt, marginRight: 12, fontFamily: FONT }}>Ln {cursor.line}, Col {cursor.col}</span>
        <span style={{ color: T.border, marginRight: 12 }}>│</span>
        {statusPips.map(({ k, v, c }) => (
          <span key={k} style={{ display: "flex", alignItems: "center", gap: 3, marginRight: 9 }}>
            <span style={{ fontSize: 9, color: T.muted, fontFamily: FONT }}>{k}</span>
            <span style={{ fontSize: 10, fontWeight: 700, color: c, fontFamily: FONT }}>{v}</span>
          </span>
        ))}
        {overallScore != null && (
          <>
            <span style={{ color: T.border, margin: "0 10px" }}>│</span>
            <span style={{ fontSize: 10, fontWeight: 700, color: overallColor, fontFamily: FONT }}>{overallScore} overall</span>
          </>
        )}
        <div style={{ flex: 1 }} />
        {metrics && <span style={{ color: tokenColor(metrics.tokenEst), marginRight: 12, fontFamily: FONT }}>~{metrics.tokenEst} tokens</span>}
        <span style={{ color: T.muted, marginRight: 10 }}>Ln {lines.length}</span>
        <span style={{ color: T.muted, marginRight: 10 }}>{wordCount}w</span>
        <span style={{ color: T.muted }}>{content.length}ch</span>
      </div>
    </div>
  );
}
