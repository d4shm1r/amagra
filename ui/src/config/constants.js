// Single source of truth for the app version. Keep in lockstep with the latest
// GitHub release, api.py FastAPI version, and ui/package.json on every release.
export const VERSION = "1.8.0";

export const AGENTS = [
  { id: "coordinator",        label: "Coordinator",         icon: "◈", color: "#9A6C00", focus: "Delegation & orchestration of all agents", role: "Reads every message, runs keyword routing first, falls back to phi4-mini for ambiguous queries. Routes to the correct specialist in under 1 second for known keywords.", keywords: ["any message — it decides where it goes"], phase: 4 },
  { id: "python_dev",         label: "Python Dev",           icon: "λ", color: "#C48808", focus: "Python code, scripts, automation, debugging, FastAPI, asyncio", role: "Writes complete working Python code. Give it a specific task with inputs, outputs, and edge cases — it returns runnable code you can copy and execute.", keywords: ["python","flask","fastapi","script","automation","pip"], phase: 3 },
  { id: "web_dev",            label: "Web Dev",              icon: "⊹", color: "#C2410C", focus: "JavaScript, TypeScript, React, Next.js, Vue, Node.js, CSS", role: "Full-stack web specialist. Writes React components, TypeScript types, Node.js APIs, and Tailwind layouts. Handles hooks, async state, and build tooling.", keywords: ["javascript","typescript","react","nextjs","vue","nodejs","npm","css","html"], phase: 36 },
  { id: "dotnet_dev",         label: ".NET Dev",             icon: "⬡", color: "#7C3AED", focus: ".NET, C#, ASP.NET Core, Blazor, Entity Framework, xUnit", role: "Expert in the .NET ecosystem. Writes C# classes, ASP.NET Core APIs, Blazor components, and EF Core queries. Handles DI, async patterns, and testing.", keywords: ["blazor","dotnet","c#","csharp","entity framework","asp.net","nuget"], phase: 36 },
  { id: "devops",             label: "DevOps",               icon: "⚙", color: "#047857", focus: "Docker, Kubernetes, CI/CD, GitHub Actions, Bash, Linux admin", role: "Infrastructure and deployment specialist. Writes Dockerfiles, Compose configs, GitHub Actions pipelines, and systemd units. Runs real docker and systemctl commands.", keywords: ["docker","kubernetes","ci/cd","github actions","bash","deploy","pipeline"], phase: 36 },
  { id: "data_analyst",       label: "Data Analyst",         icon: "∑", color: "#1E5A8A", focus: "pandas, SQL, NumPy, matplotlib, seaborn, statistics, data cleaning", role: "Data analysis specialist. Writes pandas transformations, SQL queries, and visualization code. Handles EDA, data cleaning, and statistical summaries.", keywords: ["pandas","sql","dataframe","csv","matplotlib","statistics","data analysis"], phase: 36 },
  { id: "writer",             label: "Writer",               icon: "¶", color: "#6D28D9", focus: "Technical docs, READMEs, blog posts, commit messages, editing", role: "Technical writing specialist. Writes READMEs, API docs, blog posts, and commit messages. Also edits and proofreads existing text for clarity and conciseness.", keywords: ["documentation","readme","technical writing","blog post","proofread","edit"], phase: 36 },
  { id: "ai_ml",              label: "AI & ML",              icon: "∴", color: "#BE185D", focus: "AI concepts, ML frameworks, PyTorch, TensorFlow, LLMs, embeddings", role: "Explains AI and ML concepts clearly. Helps with model architecture, training pipelines, and working with local LLMs like Ollama.", keywords: ["tensorflow","pytorch","neural network","machine learning","llm","embedding"], phase: 3 },
  { id: "it_networking",      label: "IT & Networking",      icon: "⊃", color: "#15803D", focus: "Wi-Fi, routers, network diagnostics, DNS, SSH, ports, Linux networking", role: "Networking and sysadmin specialist. Runs real commands — ping, ip addr, nslookup — and gives specific, actionable advice based on real output.", keywords: ["wifi","router","network","dns","ip address","ssh","port","vpn"], phase: 3 },
  { id: "terse",              label: "Terse",                icon: "▸", color: "#9A6C00", focus: "One-line answers: commands, syntax, code snippets", role: "Fast lookup agent. Answers commands, syntax, and quick definitions in one line. No explanation, no analogies — just the answer.", keywords: ["give me the command","command for","syntax for","one line","just give me"], phase: 5 },
  { id: "knowledge_learning", label: "Knowledge",            icon: "§", color: "#1E5A8A", focus: "IT fundamentals, learning concepts, tutorials, explanations, study plans", role: "General knowledge and learning agent. Explains complex concepts clearly, corrects wrong analogies directly, and saves lessons to memory.", keywords: ["explain","how does","tutorial","teach me","what is","learn"], phase: 3 },
];

// ── Facts derived from history.js, kept here so eager tabs stay light ────────
// HomeTab paints on first load and needs two numbers out of the release record.
// Importing BUILD_PHASES/ROADMAP for them would drag ~1,200 lines of prose into
// the first-paint chunk, so they are mirrored as literals instead.
// history.sync.test.js fails if these drift from the arrays they came from.
export const PHASE_COUNT   = 79;
export const CURRENT_FOCUS = "Workspaces & RBAC";


export const AGENT_ID_REVERSE = {
  it_networking:      "it_networking",
  python_dev:         "python_dev",
  dotnet_dev:         "dotnet_dev",
  ai_ml:              "ai_ml",
  knowledge_learning: "knowledge_learning",
  terse:              "terse",
  coordinator:        "coordinator",
};
