# pip install: no new packages needed

import re
import json
from typing import Dict, List, Optional
from langchain_core.messages import HumanMessage
from llm import llm  # your shared ChatOllama instance
from state import AgentState

# ── KEYWORD MAP ─────────────────────────────────────────────
# Uses (?<!\w)word(?!\w) to avoid partial matches
# Example: "research" will NOT match "researcher"
# All 8 agents from your actual system — no invented ones

KEYWORD_MAP: Dict[str, List[str]] = {
    "it_networking": [
        r"(?<!\w)network(?!\w)", r"(?<!\w)wi-fi(?!\w)", r"(?<!\w)wifi(?!\w)",
        r"(?<!\w)router(?!\w)", r"(?<!\w)firewall(?!\w)", r"(?<!\w)subnet(?!\w)",
        r"(?<!\w)dns(?!\w)", r"(?<!\w)dhcp(?!\w)", r"(?<!\w)vpn(?!\w)",
        r"(?<!\w)ip address(?!\w)", r"(?<!\w)ssh(?!\w)", r"(?<!\w)ping(?!\w)",
        r"(?<!\w)latency(?!\w)", r"(?<!\w)bandwidth(?!\w)", r"(?<!\w)ethernet(?!\w)",
        r"(?<!\w)packet(?!\w)", r"(?<!\w)vlan(?!\w)",
    ],
    "python_dev": [
        r"(?<!\w)python(?!\w)", r"(?<!\w)flask(?!\w)", r"(?<!\w)django(?!\w)",
        r"(?<!\w)fastapi(?!\w)", r"(?<!\w)pytest(?!\w)", r"(?<!\w)asyncio(?!\w)",
        r"(?<!\w)decorator(?!\w)", r"(?<!\w)generator(?!\w)",
        r"(?<!\w)list comprehension(?!\w)", r"(?<!\w)virtualenv(?!\w)",
        r"(?<!\w)pip install(?!\w)", r"(?<!\w)pydantic(?!\w)",
    ],
    "blazor_dev": [
        r"(?<!\w)blazor(?!\w)", r"(?<!\w)razor(?!\w)", r"(?<!\w)webassembly(?!\w)",
        r"(?<!\w)wasm(?!\w)", r"(?<!\w)dotnet(?!\w)", r"(?<!\w)\.net(?!\w)",
        r"(?<!\w)c#(?!\w)", r"(?<!\w)csharp(?!\w)", r"(?<!\w)entity framework(?!\w)",
        r"(?<!\w)maui(?!\w)", r"(?<!\w)signalr(?!\w)", r"(?<!\w)nuget(?!\w)",
    ],
    "ai_ml": [
        r"(?<!\w)tensorflow(?!\w)", r"(?<!\w)pytorch(?!\w)", r"(?<!\w)neural network(?!\w)",
        r"(?<!\w)machine learning(?!\w)", r"(?<!\w)deep learning(?!\w)",
        r"(?<!\w)transformer(?!\w)", r"(?<!\w)training(?!\w)", r"(?<!\w)inference(?!\w)",
        r"(?<!\w)gradient(?!\w)", r"(?<!\w)embedding(?!\w)", r"(?<!\w)dataset(?!\w)",
        r"(?<!\w)langchain(?!\w)", r"(?<!\w)langgraph(?!\w)", r"(?<!\w)huggingface(?!\w)",
    ],
    "documents": [
        r"(?<!\w)document(?!\w)", r"(?<!\w)report(?!\w)", r"(?<!\w)proposal(?!\w)",
        r"(?<!\w)template(?!\w)", r"(?<!\w)letter(?!\w)", r"(?<!\w)draft(?!\w)",
        r"(?<!\w)docx(?!\w)", r"(?<!\w)pdf(?!\w)", r"(?<!\w)presentation(?!\w)",
        r"(?<!\w)spreadsheet(?!\w)", r"(?<!\w)invoice(?!\w)", r"(?<!\w)memo(?!\w)",
    ],
    "personal_projects": [
        r"(?<!\w)my project(?!\w)", r"(?<!\w)side project(?!\w)",
        r"(?<!\w)deadline(?!\w)", r"(?<!\w)roadmap(?!\w)", r"(?<!\w)milestone(?!\w)",
        r"(?<!\w)track(?!\w)", r"(?<!\w)mushroom(?!\w)", r"(?<!\w)game dev(?!\w)",
        r"(?<!\w)side hustle(?!\w)", r"(?<!\w)personal goal(?!\w)",
    ],
    "research": [
        r"(?<!\w)research(?!\w)", r"(?<!\w)investigate(?!\w)", r"(?<!\w)analysis(?!\w)",
        r"(?<!\w)compare(?!\w)", r"(?<!\w)deep dive(?!\w)", r"(?<!\w)survey(?!\w)",
        r"(?<!\w)literature(?!\w)", r"(?<!\w)findings(?!\w)", r"(?<!\w)evidence(?!\w)",
        r"(?<!\w)study shows(?!\w)", r"(?<!\w)best practices(?!\w)",
    ],
    "knowledge_learning": [
        r"(?<!\w)explain(?!\w)", r"(?<!\w)how does(?!\w)", r"(?<!\w)tutorial(?!\w)",
        r"(?<!\w)teach me(?!\w)", r"(?<!\w)lesson(?!\w)", r"(?<!\w)understand(?!\w)",
        r"(?<!\w)concept(?!\w)", r"(?<!\w)what is(?!\w)", r"(?<!\w)study(?!\w)",
        r"(?<!\w)learn(?!\w)", r"(?<!\w)guide(?!\w)", r"(?<!\w)fundamentals(?!\w)",
    ],
}

# Must match exactly the node names in your coordinator.py
VALID_AGENTS = list(KEYWORD_MAP.keys()) + ["coordinator"]


def hybrid_router(state: AgentState) -> str:
    """
    Rule-based keyword router with LLM fallback.
    Returns exact node name string for LangGraph conditional_edges.
    Threshold: >= 2 keyword hits required for confident routing.
    """
    # Guard: empty or missing messages
    messages = state.get("messages")
    if not messages:
        return "coordinator"

    last = messages[-1]
    # Only route on human messages
    if not isinstance(last, HumanMessage):
        return "coordinator"

    query = last.content.lower()
    scores: Dict[str, int] = {agent: 0 for agent in KEYWORD_MAP}

    for agent, patterns in KEYWORD_MAP.items():
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                scores[agent] += 1

    best_agent = max(scores, key=scores.get)
    best_score = scores[best_agent]
    sorted_scores = sorted(scores.values(), reverse=True)
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0

    # Confident match: >= 2 hits AND clear winner
    if best_score >= 2 and best_score > second_score:
        return best_agent

    # 1 hit with no tie — still use it (optional, conservative)
    if best_score == 1 and second_score == 0:
        return best_agent

    # Ambiguous or no match — fall back to LLM
    return _llm_fallback(query)


def _llm_fallback(query: str) -> str:
    """
    LLM-based routing for ambiguous queries.
    Only called when keyword router is not confident.
    """
    agent_list = "\n".join(f"- {a}" for a in KEYWORD_MAP.keys())
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
        # Partial match fallback
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

    # Mock LLM so test runs WITHOUT Ollama
    import llm as llm_module
    llm_module.llm = MagicMock()
    llm_module.llm.invoke.return_value = MagicMock(content="knowledge_learning")

    print("=" * 65)
    print("HYBRID ROUTER TEST — agent names match your coordinator.py")
    print("=" * 65)

    def make_state(text):
        return {"messages": [HumanMessage(content=text)]}

    tests = [
        # (query, expected_agent)
        ("My Wi-Fi router keeps dropping the connection", "it_networking"),
        ("How do I configure DNS and DHCP on my subnet?", "it_networking"),
        ("Write a Python FastAPI endpoint with async", "python_dev"),
        ("How do I use list comprehension in Python?", "python_dev"),
        ("Build a Blazor WebAssembly component in .NET", "blazor_dev"),
        ("C# entity framework query with razor pages", "blazor_dev"),
        ("Train a neural network with PyTorch and gradient descent", "ai_ml"),
        ("Explain transformers and deep learning inference", "ai_ml"),
        ("Write a business proposal document template", "documents"),
        ("Create a PDF report with proper formatting", "documents"),
        ("Track my side project roadmap and milestones", "personal_projects"),
        ("What is the deadline for my mushroom game?", "personal_projects"),
        ("Research and compare local LLM deployment options", "research"),
        ("Deep dive analysis of best practices for containers", "research"),
        ("Explain how neural networks work as a tutorial", "knowledge_learning"),
        ("Teach me what DNS fundamentals are", "knowledge_learning"),
        ("", "coordinator"),  # empty query guard
    ]

    passed = 0
    failed = 0
    for query, expected in tests:
        result = hybrid_router(make_state(query))
        ok = result == expected
        status = "✓" if ok else "✗"
        if ok:
            passed += 1
        else:
            failed += 1
        label = query[:52] + "…" if len(query) > 52 else query or "(empty)"
        print(f"  {status} [{expected:<20}] {label}")

    print(f"\n  Result: {passed}/{len(tests)} passed", "✅" if failed == 0 else "⚠️ fix failures before wiring")
