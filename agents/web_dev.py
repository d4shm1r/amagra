from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import subprocess
import sys
from memory_core.context import get_memory_context, save_to_memory
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from core.context_tools import trim_messages

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

# ── Agent Node ────────────────────────────────────────────────
def web_dev_agent_node(state: AgentState):
    task = state.get("task", "")

    _mem_ctx = get_memory_context(task, "web_dev")
    from core.user_profile import get_profile_context
    _effective_prompt = WEB_DEV_SYSTEM_PROMPT.format(user_profile=get_profile_context(task))
    if _mem_ctx:
        _effective_prompt += f"\n\n{_mem_ctx}"

    tool_context = ""

    if any(w in task.lower() for w in ["node", "npm", "version", "installed"]):
        tool_context += f"\n[NODE ENV]\n{check_node_version()}"

    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    if tool_context:
        messages.append(HumanMessage(
            content=f"System tool results:\n{tool_context}\n\nUse these in your response."
        ))

    from tools.agent_runtime import respond_with_optional_tools
    response = respond_with_optional_tools(messages, _effective_prompt, task)

    save_to_memory("web_dev", "chat", response.content,
                   {"task": task[:120] if task else ""})

    return {
        "messages":     [response],
        "active_agent": "web_dev",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_web_dev_agent():
    graph = StateGraph(AgentState)
    graph.add_node("web_dev_agent", web_dev_agent_node)
    graph.add_edge(START, "web_dev_agent")
    graph.add_edge("web_dev_agent", END)
    return graph.compile()

web_dev_agent = build_web_dev_agent()

if __name__ == "__main__":
    result = web_dev_agent.invoke({
        "messages": [{"role": "user", "content": "Write a React hook that debounces a search input value."}],
        "active_agent": "", "task": "react debounce hook", "result": "", "next_agent": "", "memory": {},
    })
    print(result["messages"][-1].content)
