import re
from dataclasses import dataclass
from typing import Dict, List
from langchain_core.messages import HumanMessage
from models.llm import llm
from models.state import AgentState
from infrastructure.dispatch import (
    Delta, DeltaBuilder, Tier, dispatch, register, unregister,
)

# ── KEYWORD MAP ──────────────────────────────────────────────
# Uses (?<!\w)word(?!\w) to avoid partial matches.
# Agent names must match node names in coordinator.py exactly.

KEYWORD_MAP: Dict[str, List[str]] = {
    # knowledge_learning is intentionally absent — it is the default fallback
    # at the end of hybrid_router(). Including it here would let broad phrases
    # ("what is", "how does") beat domain-specific keywords on score.
    "it_networking": [
        r"(?<!\w)network(?!\w)", r"(?<!\w)wi-fi(?!\w)", r"(?<!\w)wifi(?!\w)",
        r"(?<!\w)router(?!\w)", r"(?<!\w)firewall(?!\w)", r"(?<!\w)subnet(?!\w)",
        r"(?<!\w)dns(?!\w)", r"(?<!\w)dhcp(?!\w)", r"(?<!\w)vpn(?!\w)",
        r"(?<!\w)ip address(?!\w)", r"(?<!\w)ssh(?!\w)", r"(?<!\w)ping(?!\w)",
        r"(?<!\w)latency(?!\w)", r"(?<!\w)bandwidth(?!\w)", r"(?<!\w)ethernet(?!\w)",
        r"(?<!\w)packet(?!\w)", r"(?<!\w)vlan(?!\w)",
        r"(?<!\w)nginx(?!\w)", r"(?<!\w)ssl(?!\w)", r"(?<!\w)tls(?!\w)",
        r"(?<!\w)certbot(?!\w)", r"(?<!\w)wireguard(?!\w)", r"(?<!\w)firewalld(?!\w)",
        r"(?<!\w)iptables(?!\w)", r"(?<!\w)reverse proxy(?!\w)", r"(?<!\w)load balancer(?!\w)",
        # Protocol names missed by previous version
        r"(?<!\w)tcp(?!\w)", r"(?<!\w)udp(?!\w)", r"(?<!\w)bgp(?!\w)",
        r"(?<!\w)ospf(?!\w)", r"(?<!\w)nat(?!\w)",
        r"(?<!\w)webrtc(?!\w)", r"(?<!\w)coturn(?!\w)",
        r"(?<!\w)autonomous system(?!\w)", r"(?<!\w)packet loss(?!\w)",
        r"(?<!\w)traceroute(?!\w)", r"(?<!\w)netstat(?!\w)",
    ],
    "python_dev": [
        r"(?<!\w)python(?!\w)", r"(?<!\w)flask(?!\w)", r"(?<!\w)django(?!\w)",
        r"(?<!\w)fastapi(?!\w)", r"(?<!\w)pytest(?!\w)", r"(?<!\w)asyncio(?!\w)",
        r"(?<!\w)decorator(?!\w)", r"(?<!\w)generator(?!\w)",
        r"(?<!\w)list comprehension(?!\w)", r"(?<!\w)virtualenv(?!\w)",
        r"(?<!\w)pip install(?!\w)", r"(?<!\w)pydantic(?!\w)",
        # Exception class names and Python-specific error patterns
        r"(?<!\w)recursionerror(?!\w)", r"(?<!\w)maximum recursion(?!\w)",
        r"(?<!\w)typeerror(?!\w)", r"(?<!\w)attributeerror(?!\w)",
        r"(?<!\w)importerror(?!\w)", r"(?<!\w)nameerror(?!\w)",
        r"(?<!\w)context manager(?!\w)", r"(?<!\w)dataclass(?!\w)",
        r"(?<!\w)coroutine(?!\w)", r"(?<!\w)async/await(?!\w)",
        r"(?<!\w)dunder(?!\w)", r"(?<!\w)__str__(?!\w)", r"(?<!\w)__repr__(?!\w)",
    ],
    "dotnet_dev": [
        r"(?<!\w)blazor(?!\w)", r"(?<!\w)razor(?!\w)", r"(?<!\w)webassembly(?!\w)",
        r"(?<!\w)wasm(?!\w)", r"(?<!\w)dotnet(?!\w)", r"(?<!\w)\.net(?!\w)",
        r"(?<!\w)c#(?!\w)", r"(?<!\w)csharp(?!\w)", r"(?<!\w)entity framework(?!\w)",
        r"(?<!\w)maui(?!\w)", r"(?<!\w)signalr(?!\w)", r"(?<!\w)nuget(?!\w)",
        r"(?<!\w)asp\.net(?!\w)", r"(?<!\w)xunit(?!\w)", r"(?<!\w)nunit(?!\w)",
        r"(?<!\w)minimal api(?!\w)",
        r"(?<!\w)statehaschanged(?!\w)", r"(?<!\w)oninitialized(?!\w)",
        r"(?<!\w)editform(?!\w)", r"(?<!\w)ijsruntime(?!\w)",
        r"(?<!\w)cascading parameter(?!\w)",
    ],
    "ai_ml": [
        r"(?<!\w)tensorflow(?!\w)", r"(?<!\w)pytorch(?!\w)", r"(?<!\w)neural network(?!\w)",
        r"(?<!\w)machine learning(?!\w)", r"(?<!\w)deep learning(?!\w)",
        r"(?<!\w)transformer(?!\w)", r"(?<!\w)training(?!\w)", r"(?<!\w)inference(?!\w)",
        r"(?<!\w)gradient(?!\w)", r"(?<!\w)embedding(?!\w)", r"(?<!\w)dataset(?!\w)",
        r"(?<!\w)langchain(?!\w)", r"(?<!\w)langgraph(?!\w)", r"(?<!\w)huggingface(?!\w)",
        r"(?<!\w)llm(?!\w)", r"(?<!\w)fine.tun(?!\w)", r"(?<!\w)rag(?!\w)",
        # Model names and ML concepts missed by previous version
        r"(?<!\w)bert(?!\w)", r"(?<!\w)gpt(?!\w)",
        r"(?<!\w)supervised(?!\w)", r"(?<!\w)unsupervised(?!\w)",
        r"(?<!\w)reinforcement learning(?!\w)", r"(?<!\w)binary classifier(?!\w)",
        r"(?<!\w)batch normalization(?!\w)", r"(?<!\w)layer normalization(?!\w)",
        r"(?<!\w)quantization(?!\w)", r"(?<!\w)vector databases?(?!\w)",
        r"(?<!\w)prompt engineering(?!\w)", r"(?<!\w)attention mechanism(?!\w)",
        r"(?<!\w)backpropagation(?!\w)", r"(?<!\w)overfitting(?!\w)",
        r"(?<!\w)semantic search(?!\w)",
    ],
    "web_dev": [
        r"(?<!\w)javascript(?!\w)", r"(?<!\w)typescript(?!\w)",
        r"(?<!\w)react(?!\w)", r"(?<!\w)vue(?!\w)", r"(?<!\w)angular(?!\w)",
        r"(?<!\w)next\.?js(?!\w)", r"(?<!\w)node\.?js(?!\w)", r"(?<!\w)express(?!\w)",
        r"(?<!\w)webpack(?!\w)", r"(?<!\w)vite(?!\w)", r"(?<!\w)tailwind(?!\w)",
        r"(?<!\w)npm(?!\w)", r"(?<!\w)yarn(?!\w)", r"(?<!\w)jsx(?!\w)",
        r"(?<!\w)tsx(?!\w)", r"(?<!\w)frontend(?!\w)", r"(?<!\w)css(?!\w)",
        r"(?<!\w)html(?!\w)", r"(?<!\w)dom(?!\w)", r"(?<!\w)graphql(?!\w)",
    ],
    "devops": [
        r"(?<!\w)docker(?!\w)", r"(?<!\w)kubernetes(?!\w)", r"(?<!\w)k8s(?!\w)",
        r"(?<!\w)container(?!\w)", r"(?<!\w)dockerfile(?!\w)",
        r"(?<!\w)ci/cd(?!\w)", r"(?<!\w)github actions(?!\w)", r"(?<!\w)pipeline(?!\w)",
        r"(?<!\w)terraform(?!\w)", r"(?<!\w)ansible(?!\w)",
        r"(?<!\w)systemd(?!\w)", r"(?<!\w)crontab(?!\w)", r"(?<!\w)bash script(?!\w)",
        r"(?<!\w)deploy(?!\w)", r"(?<!\w)helm(?!\w)", r"(?<!\w)devops(?!\w)",
    ],
    "data_analyst": [
        r"(?<!\w)pandas(?!\w)", r"(?<!\w)dataframe(?!\w)", r"(?<!\w)numpy(?!\w)",
        r"(?<!\w)matplotlib(?!\w)", r"(?<!\w)seaborn(?!\w)", r"(?<!\w)plotly(?!\w)",
        r"(?<!\w)sql(?!\w)", r"(?<!\w)postgresql(?!\w)", r"(?<!\w)sqlite(?!\w)",
        r"(?<!\w)csv(?!\w)", r"(?<!\w)excel(?!\w)", r"(?<!\w)parquet(?!\w)",
        r"(?<!\w)data analysis(?!\w)", r"(?<!\w)data cleaning(?!\w)",
        r"(?<!\w)statistics(?!\w)", r"(?<!\w)correlation(?!\w)", r"(?<!\w)regression(?!\w)",
    ],
    "writer": [
        r"(?<!\w)documentation(?!\w)", r"(?<!\w)readme(?!\w)",
        r"(?<!\w)technical writing(?!\w)", r"(?<!\w)blog post(?!\w)",
        r"(?<!\w)write an article(?!\w)", r"(?<!\w)proofread(?!\w)",
        r"(?<!\w)edit my(?!\w)", r"(?<!\w)copywriting(?!\w)",
        r"(?<!\w)commit message(?!\w)", r"(?<!\w)pull request description(?!\w)",
        r"(?<!\w)docstring(?!\w)", r"(?<!\w)api docs(?!\w)",
    ],
    "terse": [
        r"(?<!\w)give me the command(?!\w)",
        r"(?<!\w)give me command(?!\w)",
        r"(?<!\w)give me the code(?!\w)",
        r"(?<!\w)command for(?!\w)",
        r"(?<!\w)command to(?!\w)",
        r"(?<!\w)syntax for(?!\w)",
        r"(?<!\w)syntax of(?!\w)",
        r"(?<!\w)one line(?!\w)",
        r"(?<!\w)one-liner(?!\w)",
        r"(?<!\w)just give me(?!\w)",
        r"(?<!\w)short answer(?!\w)",
        r"(?<!\w)quick answer(?!\w)",
        r"(?<!\w)terse(?!\w)",
    ],
}

# knowledge_learning is the default fallback — keep it in VALID_AGENTS even
# though it was removed from KEYWORD_MAP to prevent generic phrases from
# winning the keyword competition against domain-specific agents.
VALID_AGENTS = list(KEYWORD_MAP.keys()) + ["coordinator", "knowledge_learning"]


def score(query: str) -> Dict[str, int]:
    """
    Pure keyword scoring — the FULL candidate vector, no early exits.

    `query` must already be lowercased. This is §0 of the delta-algebra
    spec: the single place a complete score vector exists, so a future
    reduction seam has something to reduce over. It makes NO decision.
    """
    scores: Dict[str, int] = {agent: 0 for agent in KEYWORD_MAP}
    for agent, patterns in KEYWORD_MAP.items():
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                scores[agent] += 1
    return scores


ROUTING_EVENT = "routing.decision"


@dataclass(frozen=True)
class RoutingEvent:
    """Immutable input handed to every routing hook (§2: hooks read, never mutate)."""
    query:  str
    scores: dict


def _terse_policy_hook(event: RoutingEvent) -> Delta:
    """
    CORE-tier hook re-expressing the old terse/factual short-circuits as a
    `pin` delta (rollout step 2). Pure: a deterministic function of (query,
    scores) — no LLM, no IO — so it is replay-safe (§8).

    This is the ~30% "bypass" slice from the §0 measurement, pulled under the
    algebra. A CORE pin outranks any extension bias/scale, exactly preserving
    "terse wins over everything" without a hardcoded early return.
    """
    b = DeltaBuilder("core.terse", Tier.CORE)

    # Terse priority — any single keyword match wins over all other agents
    if event.scores.get("terse", 0) >= 1:
        return b.pin("terse").build()

    # Signal-based terse: factual shape or short generic query
    try:
        from orchestration.query_normalizer import normalize as _norm
        sig = _norm(event.query, "unknown")
        if sig.answer_shape == "factual":
            return b.pin("terse").build()
        content_heavy = re.search(
            r"\b(summarize|summary|explain|research|analyze|compare|review|describe)\b",
            event.query, re.IGNORECASE,
        )
        if (sig.verbosity == "terse"
                and sig.answer_shape == "explanation"
                and sig.domain == "general"
                and not content_heavy):
            return b.pin("terse").build()
    except Exception:
        pass

    return Delta.empty("core.terse", Tier.CORE)


# Register the CORE policy hook at import (idempotent across reloads).
unregister(ROUTING_EVENT, "core.terse")
register(ROUTING_EVENT, _terse_policy_hook,
         hook_id="core.terse", tier=Tier.CORE, pure=True)


def decide(query: str, scores: Dict[str, int]) -> str:
    """
    Runtime-owned decision over the score vector + query signals.

    `query` must already be lowercased. The terse/factual policy now flows
    through dispatch() as a CORE `pin` delta rather than a hardcoded early
    return; extension hooks registered on ROUTING_EVENT can bias the vector,
    but a CORE pin (and any veto) still wins. The threshold/default projection
    over the RAW integer scores stays here — it is cardinal (counts, "all
    zeros → default") and is not recoverable from a normalized distribution.
    """
    base = {agent: float(s) for agent, s in scores.items()}
    result = dispatch(ROUTING_EVENT, RoutingEvent(query, dict(scores)), base)

    # A committed pin sets exactly one logit to +inf (§3 Phase E).
    pinned = [k for k, logit in result.raw.items() if logit == float("inf")]
    if pinned:
        return pinned[0]

    best_agent = max(scores, key=scores.get)
    best_score = scores[best_agent]
    sorted_scores = sorted(scores.values(), reverse=True)
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0

    if best_score >= 2 and best_score > second_score:
        return best_agent

    if best_score == 1:
        return best_agent

    print("[router] no keyword match → knowledge_learning (default)")
    return "knowledge_learning"


def hybrid_router(state: AgentState) -> str:
    """
    Rule-based keyword router with LLM fallback.
    Returns exact node name string for LangGraph conditional_edges.

    Thin wrapper: extract the query, then score() → decide() (§0 split).
    """
    messages = state.get("messages")
    if not messages:
        return "coordinator"

    last = messages[-1]
    if not isinstance(last, HumanMessage):
        return "coordinator"

    query = last.content.lower()
    if not query.strip():
        return "coordinator"

    return decide(query, score(query))


def _llm_fallback(query: str) -> str:
    agent_list = "\n".join(f"- {a}" for a in (list(KEYWORD_MAP.keys()) + ["knowledge_learning"]))
    prompt = f"""You are a routing assistant. Given the user query below,
return ONLY the name of the most appropriate specialist agent.
Choose from exactly these options:
{agent_list}

Return ONLY the agent name, nothing else. No explanation.

User query: {query}

Agent:"""
    try:
        response = llm.invoke(prompt)
        result = response.content.strip().lower().replace(" ", "_").replace("-", "_")
        if result in VALID_AGENTS:
            return result
        for agent in KEYWORD_MAP:
            if agent in result:
                return agent
        return "coordinator"
    except Exception as e:
        print(f"[router] LLM fallback error: {e}")
        return "coordinator"


# ── TEST SUITE ───────────────────────────────────────────────
if __name__ == "__main__":
    from unittest.mock import MagicMock
    import models.llm as llm_module
    llm_module.llm = MagicMock()
    llm_module.llm.invoke.return_value = MagicMock(content="knowledge_learning")

    print("=" * 65)
    print("HYBRID ROUTER TEST — 10 agents")
    print("=" * 65)

    def make_state(text):
        return {"messages": [HumanMessage(content=text)]}

    tests = [
        ("My Wi-Fi router keeps dropping the connection",         "it_networking"),
        ("How do I configure DNS and DHCP on my subnet?",         "it_networking"),
        ("Write a Python FastAPI endpoint with async",            "python_dev"),
        ("How do I use list comprehension in Python?",            "python_dev"),
        ("Build a Blazor WebAssembly component in .NET",          "dotnet_dev"),
        ("C# entity framework query with razor pages",            "dotnet_dev"),
        ("Train a neural network with PyTorch",                   "ai_ml"),
        ("Explain transformers and deep learning inference",      "ai_ml"),
        ("Write a React hook that debounces search input",        "web_dev"),
        ("Fix this TypeScript error in my Next.js app",           "web_dev"),
        ("Create a Dockerfile and GitHub Actions pipeline for deploy","devops"),
        ("Set up a GitHub Actions CI pipeline",                   "devops"),
        ("Write pandas code to group by customer and sum spend",  "data_analyst"),
        ("Write a SQL query to find duplicate rows",              "data_analyst"),
        ("Write a README and documentation for my project",       "writer"),
        ("Proofread and edit my blog post for grammar",           "writer"),
        ("Explain how neural networks work as a tutorial",        "knowledge_learning"),
        ("Teach me what DNS fundamentals are",                    "it_networking"),
        ("",                                                      "coordinator"),
        ("give me the command for new dotnet blazor project",     "terse"),
        ("just give me the code to read a file",                  "terse"),
        ("What does DNS stand for?",                              "terse"),
        ("What port does SSH use?",                               "terse"),
    ]

    passed = 0
    for query, expected in tests:
        result = hybrid_router(make_state(query))
        ok = result == expected
        status = "✓" if ok else "✗"
        passed += ok
        label = query[:52] + "…" if len(query) > 52 else query or "(empty)"
        print(f"  {status} [{expected:<20}] {label}")

    print(f"\n  Result: {passed}/{len(tests)} passed", "✅" if passed == len(tests) else "⚠️")
