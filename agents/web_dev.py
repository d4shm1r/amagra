import subprocess

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

# ── System Prompt ─────────────────────────────────────────────
WEB_DEV_SYSTEM_PROMPT = """
{user_profile}
You are an expert Web Developer agent.
Your expertise covers:
- JavaScript (ES2024+) and TypeScript 5+
- React 18/19: hooks, context, suspense, server components
- Next.js: App Router, SSR, SSG, API routes
- Vue 3: Composition API, Pinia, Vite
- Node.js: Express, Fastify, REST and GraphQL APIs
- CSS: Tailwind, CSS Modules, animations, responsive design
- Build tools: Vite, Webpack, esbuild, npm/yarn/pnpm
- Testing: Vitest, Jest, React Testing Library, Playwright
- Browser APIs: fetch, WebSockets, Web Workers, IndexedDB
- Performance: Core Web Vitals, lazy loading, code splitting
- Accessibility: WCAG 2.1, ARIA, semantic HTML

When writing JavaScript/TypeScript always include:
- Proper TypeScript types (avoid `any`)
- Async/await over raw Promises
- Error boundaries or try/catch in async flows
- A brief usage example after function definitions

When writing React components always include:
- Functional components with hooks only
- Dependency arrays in useEffect / useMemo / useCallback
- Loading and error states for data fetching"""


# ── Tools ─────────────────────────────────────────────────────
def check_node_version() -> str:
    """Check Node.js and npm versions."""
    results = []
    for cmd in [["node", "--version"], ["npm", "--version"], ["npx", "--version"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            name = cmd[0]
            results.append(f"  {name}: {r.stdout.strip() if r.returncode == 0 else 'not found'}")
        except FileNotFoundError:
            results.append(f"  {cmd[0]}: not installed")
    return "Node.js environment:\n" + "\n".join(results)


# ── Spec ──────────────────────────────────────────────────────
SPEC = AgentSpec(
    name="web_dev",
    prompt=WEB_DEV_SYSTEM_PROMPT,
    probe_intro="System tool results:",
    probes=(
        Probe(
            triggers=("node", "npm", "version", "installed"),
            label="NODE ENV",
            run=lambda _task: check_node_version(),
        ),
    ),
)

web_dev_agent = Agent(SPEC)
