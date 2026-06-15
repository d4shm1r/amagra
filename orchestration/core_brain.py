# ~/agentic-ai/core_brain.py
# ─────────────────────────────────────────────────────────────
# The reasoning and decision authority of the system.
#
# Fills the gap between:
#   router.py  →  decides WHO acts (keyword scoring)
#   agents/    →  decide HOW to respond (specialist logic)
#
# core_brain decides HOW THE SYSTEM THINKS before any agent acts:
#   1. Intent clarification  — what does the user actually want to DO?
#   2. Complexity assessment — simple, compound, or ambiguous?
#   3. Agent strategy        — which agent(s) and in what order?
#   4. Reflection gating     — is this response worth checking?
#
# Integration in coordinator.py:
#   from orchestration.core_brain import think, BrainDecision
#   decision = think(task, state)
#   # decision.agent_strategy[0] → primary agent
#   # decision.reflect           → run reflection_loop() on response
#   # decision.needs_plan        → log plan before dispatching
# ─────────────────────────────────────────────────────────────

import os
import re
import json
import sys
from dataclasses import dataclass, field
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from orchestration.query_normalizer import normalize, DOMAIN_TO_AGENT


# ── ACTION TYPE PATTERNS ─────────────────────────────────────
# Identifies WHAT the user wants to do, independent of domain.
# Order matters — checked top to bottom, first match wins.

ACTION_PATTERNS: dict[str, list[str]] = {
    "lookup":   [
        r"\b(give me the command|command for|command to|syntax for|syntax of)\b",
        r"\b(one.?liner|just give me|quick answer|short answer|terse)\b",
        r"\b(show me|list all|list the|what.?s the command|what.?s the syntax)\b",
    ],
    "debug":    [
        # checked before "build" — "debug my component" should not hit the build path
        r"\b(debug|fix|error|broken|not working|fails|crash|issue|bug|wrong|traceback)\b",
        r"\b(not propagating|bad gateway|connection refused|timed out|refused to connect)\b",
        r"\b(troubleshoot|diagnose|why (is|does|won.?t|isn.?t|can.?t))\b",
    ],
    "build":    [
        r"\b(write|create|build|implement|make|generate)\b",
        r"\b(code|script|function|class|component|endpoint|module)\b",
        r"\b(set up|setup|configure|deploy|install)\b",
        r"\b(update|modify|change|refactor|optimize|improve|enhance|extend|add to)\b",
    ],
    "explain":  [
        r"\b(explain|what is|what are|how does|tell me about|describe|definition of)\b",
        r"\b(why does|why is|why would|what does|meaning of|help me understand)\b",
    ],
    "compare":  [
        r"\b(compare|vs\.?|versus|difference between|better than|which is|pros and cons)\b",
    ],
    "research": [
        r"\b(research|analyze|analysis|investigate|review|survey|summarize)\b",
        r"\b(formulate|derive|prove|given a |given that )\b",
    ],
    "plan":     [
        r"\b(plan|roadmap|approach|steps to|guide me|best way to|how should I)\b",
        r"\b(how to|help me|walk me through|best practice|recommend|how do I)\b",
    ],
}

# ── DOMAIN SIGNALS ───────────────────────────────────────────
# Maps query content to agent domains.
# knowledge_learning is explicitly excluded from complexity scoring
# (it co-fires on almost every query via "explain", "what is", etc.)

DOMAIN_SIGNALS: dict[str, list[str]] = {
    "it_networking":     [
        r"\b(network|wifi|wi-fi|router|dns|dhcp|ssh|ip address|ping|firewall|vpn|ethernet|subnet|vlan)\b",
        r"\b(nginx|ssl|tls|certbot|wireguard|firewalld|iptables|reverse proxy|load balancer|proxy)\b",
    ],
    "python_dev":        [r"\b(python|flask|fastapi|asyncio|pytest|pip|django|pydantic|decorator|pandas|numpy|requests)\b"],
    "dotnet_dev":        [
        r"\b(blazor|razor|webassembly|wasm|dotnet|csharp|signalr|nuget|maui)\b",
        r"c#",          # \b doesn't work after '#' (non-word char) — separate pattern
        r"\.net\b",     # matches .NET / .net
        r"asp\.net",
    ],
    "ai_ml":             [r"\b(neural network|pytorch|tensorflow|machine learning|deep learning|llm|embedding|transformer|dataset|gradient|huggingface|langchain|langgraph)\b"],
    "knowledge_learning":[r"\b(explain|what is|what are|how does|how do|tutorial|teach|lesson|understand|concept|fundamentals|basics)\b"],
}

# ── COMPOUND SIGNALS ─────────────────────────────────────────
# Structural markers that a task has multiple distinct steps or outputs.

COMPOUND_SIGNALS = [
    r"\band then\b",
    r"\bfirst.*then\b",
    r"\bstep by step\b",
    r"\balso.*and\b",
    r"\bboth.*and\b",
    r"\bfollowed by\b",
    r"\bafter that\b",
    r"\bthen also\b",
    r"\bmultiple (steps|parts|things)\b",
]

# ── CODE-PRODUCING AGENTS ────────────────────────────────────
# Responses from these agents that are "build" or "debug" actions
# are worth running through reflection.py (code execution check).

CODE_AGENTS = {"python_dev", "dotnet_dev"}

# ── CODE NOUNS ───────────────────────────────────────────────
# Nouns that signal a genuine coding task. Used to guard against the LLM
# classifier returning action="build" for plain imperative prose
# ("repeat the months of the year backward"), which would otherwise route
# to a code agent + code reflection and waste ~80s on a one-line answer.
CODE_NOUN = re.compile(
    r"\b(code|script|function|class|component|endpoint|module|api|app|"
    r"program|cli|library|package|regex|algorithm|website|webpage|page|"
    r"test|schema|query|migration|dockerfile|pipeline|config)\b",
    re.I,
)

VALID_AGENTS = [
    "it_networking", "python_dev", "dotnet_dev",
    "ai_ml", "knowledge_learning", "terse",
]


# ── BRAIN DECISION ───────────────────────────────────────────

@dataclass
class BrainDecision:
    """
    The complete reasoning output of the core brain.
    Coordinator reads this to control routing and quality gates.
    """
    intent:          str            # What the user actually wants (clarified sentence)
    action:          str            # lookup|build|debug|explain|compare|research|plan|unknown
    complexity:      str            # simple|compound|ambiguous
    agent_strategy:  List[str]      # Ordered agents — [0] is primary

    needs_plan:      bool           # True → log the step plan before dispatching
    plan:            List[str] = field(default_factory=list)

    reflect:         bool  = False      # True when reflect_level != "none"
    reflect_type:    str   = "general"  # code|research|general
    reflect_level:   str   = "none"     # none|light|full

    confidence:      float = 0.67   # [0.3–1.0] derived from agent's historical weight
                                    # <0.4 → consider clarification, >0.7 → execute directly

    regret:          float = 0.0    # max(alt confidences) - chosen confidence
                                    # 0.0 = optimal routing; >0.3 = better option existed

    clarify_needed:  bool = False   # True → respond with a clarifying question
    clarification_q: str  = ""

    # QuerySignal fields — passed back to UI for transparency
    signal_domain:    str   = "general"
    signal_shape:     str   = "explanation"
    signal_verbosity: str   = "normal"
    signal_conf:      float = 0.0


# ── HELPERS ──────────────────────────────────────────────────

def _detect_action(query: str) -> str:
    """First matching action type wins. Ordered by priority (lookup first)."""
    q = query.lower()
    for action, patterns in ACTION_PATTERNS.items():
        for p in patterns:
            if re.search(p, q):
                return action
    return "unknown"


def _detect_domains(query: str) -> List[str]:
    """
    Ordered list of agent domains hit by the query. No duplicates.
    When multiple domains fire, sort by historical weight descending so
    that agents with a stronger coherence record get priority in tiebreaks.
    Single-domain queries are unaffected.
    """
    from decision.weights import get as get_weight
    q = query.lower()
    hit, seen = [], set()
    for agent, patterns in DOMAIN_SIGNALS.items():
        for p in patterns:
            if re.search(p, q) and agent not in seen:
                hit.append(agent)
                seen.add(agent)
                break
    if len(hit) > 1:
        hit.sort(key=lambda a: get_weight(a), reverse=True)
    return hit


def _detect_complexity(query: str, domains: List[str]) -> str:
    """
    simple   — one domain, one action, no structural compound signals
    compound — multiple distinct domains OR compound connectives present
    ambiguous — very short query with no recognizable domain
    """
    q = query.lower()

    # Multiple non-tutorial domains → compound
    core_domains = [d for d in domains if d != "knowledge_learning"]
    if len(core_domains) >= 2:
        return "compound"

    # Explicit compound structure words
    for pattern in COMPOUND_SIGNALS:
        if re.search(pattern, q):
            return "compound"

    # Too short and no domain signal → ambiguous
    if len(query.split()) <= 3 and not domains:
        return "ambiguous"

    return "simple"


def _reflect_level(action: str, primary_agent: str,
                   confidence: float, complexity: str,
                   regret: float = 0.0,
                   planner_uncertainty: float = 0.0) -> tuple[str, str]:
    """
    Evidence-driven reflection triage (Phase 34).

    Delegates to risk_gate.compute_risk() which weighs:
      action_risk, routing_uncertainty, planner_uncertainty, complexity_risk

    Falls back to the static rule table if risk_gate is unavailable.

    Returns (level, reflect_type).
    """
    try:
        from cognition.risk_gate import compute_risk
        signal = compute_risk(
            action              = action,
            primary_agent       = primary_agent,
            confidence          = confidence,
            regret              = regret,
            complexity          = complexity,
            planner_uncertainty = planner_uncertainty,
            log                 = True,
        )
        print(f"[risk_gate] {signal}")
        try:
            from models.cognitive_state import get_session_state
            get_session_state("cos-session-main").set_risk(signal)
        except Exception:
            pass
        return signal.reflect_level, signal.reflect_type
    except Exception as e:
        print(f"[risk_gate] unavailable ({e}) — using static fallback")

    # ── Static fallback (original logic) ─────────────────────
    if action in {"build", "debug"} and primary_agent in CODE_AGENTS:
        if action == "debug" or complexity == "compound" or confidence < 0.50:
            return "full", "code"
        return "light", "code"
    if action == "research":
        return "light", "research"
    return "none", "general"


def _build_plan(agents: List[str]) -> List[str]:
    """Minimal execution plan for compound tasks."""
    return [
        f"{i}. [{agent.replace('_', ' ').title()}] handle its part of the request"
        for i, agent in enumerate(agents, 1)
    ]


def _llm_clarify(query: str) -> dict:
    """
    LLM fallback for genuinely ambiguous queries.
    Returns {intent, action, agents, complexity}.
    Only called when rule-based analysis cannot produce a confident result.
    Uses the provider configured for the "brain" role (BRAIN_PROVIDER env var).
    """
    from providers.registry import get_provider

    agent_list = "\n".join(f"- {a}" for a in VALID_AGENTS)
    user_prompt = f"""Analyze this user request. Return ONLY a JSON object, no explanation.

User request: {query}

JSON to return:
{{
  "intent": "one sentence — what the user wants to accomplish",
  "action": "one of: build|debug|explain|compare|lookup|research|plan|unknown",
  "agents": ["agent names in order of importance"],
  "complexity": "one of: simple|compound|ambiguous"
}}

Available agents:
{agent_list}

Rules: agents must be from the list. Return JSON only."""

    try:
        provider = get_provider("brain")
        raw = provider.generate(
            prompt=user_prompt,
            system_prompt="You are a request classifier. Return JSON only.",
        ).strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        agents = [a for a in data.get("agents", []) if a in VALID_AGENTS]
        if not agents:
            agents = ["knowledge_learning"]
        action = data.get("action", "unknown")
        # Guard: the classifier over-fires "build" on plain imperative prose
        # ("repeat the months of the year backward"). With no code noun present
        # it isn't a coding task — downgrade to "explain" so it skips the code
        # agent + reflection pipeline.
        if action == "build" and not CODE_NOUN.search(query):
            action = "explain"
        return {
            "intent":     data.get("intent", query[:80]),
            "action":     action,
            "agents":     agents,
            "complexity": data.get("complexity", "simple"),
        }
    except Exception as e:
        print(f"[core_brain] LLM fallback error: {e}")
        return {
            "intent":     query[:80],
            "action":     "unknown",
            "agents":     ["knowledge_learning"],
            "complexity": "simple",
        }


# ── MAIN ENTRY POINT ─────────────────────────────────────────

def think(task: str, state: AgentState) -> BrainDecision:
    """
    The system's reasoning pass before any agent acts.

    Fast path (no LLM call): clear single-domain tasks — runs in <1ms.
    LLM path: only for ambiguous tasks that rules cannot resolve.

    The coordinator uses the returned BrainDecision to:
      - Select the primary agent  (agent_strategy[0])
      - Log a step plan           (needs_plan + plan)
      - Gate response quality     (reflect + reflect_type)
    """
    query = task.strip() if task else ""

    # ── Guard: empty input ────────────────────────────────────
    if not query:
        return BrainDecision(
            intent="no input provided",
            action="unknown",
            complexity="ambiguous",
            agent_strategy=["knowledge_learning"],
            needs_plan=False,
            clarify_needed=True,
            clarification_q="What would you like help with?",
        )

    # ── Context stratification: isolate primary task for routing ─
    # Prevents dependency outputs and historical context from contaminating
    # routing signals (e.g., "router.py" in a step description → it_networking).
    routing_query = query
    try:
        from cognition.context_stratifier import stratify, routing_text
        _ctx = stratify(state, task=query)
        routing_query = routing_text(_ctx)   # primary task only, weight=1.0
    except Exception:
        pass   # fall back to raw query — safe degradation

    # ── Rule-based analysis ───────────────────────────────────
    action       = _detect_action(routing_query)
    signal       = normalize(routing_query, action)   # structured intent signal
    domains      = _detect_domains(routing_query)
    complexity   = _detect_complexity(routing_query, domains)
    core_domains = [d for d in domains if d != "knowledge_learning"]

    from decision.weights import to_confidence

    # Lookup is a hard override — deterministic, always confidence 1.0
    if action == "lookup":
        print("[core_brain] lookup → terse (fast path, no LLM)")
        return BrainDecision(
            intent=f"quick lookup: {query[:60]}",
            action="lookup",
            complexity="simple",
            agent_strategy=["terse"],
            needs_plan=False,
            reflect=False,
            confidence=1.0,
            signal_domain=signal.domain, signal_conf=signal.domain_conf,
            signal_shape=signal.answer_shape, signal_verbosity=signal.verbosity,
        )

    # ── Terse routing: factual queries ───────────────────────
    # Single-fact answers (shape=factual, capped at ≤10 tokens by the
    # normalizer) always go to terse — the answer is one word or number,
    # not a domain explanation. Verbosity not checked: a 7-word factual
    # query still wants a one-word answer.
    if signal.answer_shape == "factual":
        print(
            f"[core_brain] terse path | factual | "
            f"domain={signal.domain}({signal.domain_conf:.2f}) | conf=0.90"
        )
        return BrainDecision(
            intent=f"factual answer: {query[:60]}",
            action=action,
            complexity="simple",
            agent_strategy=["terse"],
            needs_plan=False,
            reflect=False,
            confidence=0.90,
            signal_domain=signal.domain, signal_conf=signal.domain_conf,
            signal_shape=signal.answer_shape, signal_verbosity=signal.verbosity,
        )

    # Short queries with no domain go to terse — but NOT when the action requires
    # substantive content. "Give me a summarize on X" is 6 tokens (verbosity=terse)
    # but needs a real answer from knowledge_learning, not a one-liner.
    if (signal.verbosity == "terse"
            and signal.answer_shape == "explanation"
            and signal.domain == "general"
            and action not in {"research", "explain", "compare"}):
        print(
            "[core_brain] terse path | short query, no domain | conf=0.85"
        )
        return BrainDecision(
            intent=f"brief answer: {query[:60]}",
            action=action,
            complexity="simple",
            agent_strategy=["terse"],
            needs_plan=False,
            reflect=False,
            confidence=0.85,
            signal_domain=signal.domain, signal_conf=signal.domain_conf,
            signal_shape=signal.answer_shape, signal_verbosity=signal.verbosity,
        )

    # ── Fast path: known domain or clear structure ────────────
    # AGENTIC_USE_SIGNAL=0 disables signal-first routing for ablation measurements.
    import os as _os
    use_signal = signal.domain_conf > 0.3 and _os.getenv("AGENTIC_USE_SIGNAL", "1") != "0"

    if complexity != "ambiguous" and (use_signal or domains):

        # Primary agent selection: signal-driven when confident;
        # fall back to keyword-domain list for weaker signals.
        if use_signal:
            # .get() guard: a normalizer domain missing from DOMAIN_TO_AGENT must
            # not raise — a KeyError here would crash think() and dump the whole
            # query onto the (discarded) keyword router with reflection disabled.
            primary = DOMAIN_TO_AGENT.get(signal.domain, "knowledge_learning")
        elif core_domains:
            # Regret-weighted sort before selecting primary
            if len(core_domains) > 1:
                try:
                    from decision.log import agent_regret_mean as _arm
                    LAMBDA = 0.5
                    core_domains = sorted(
                        core_domains,
                        key=lambda d: to_confidence(d) - LAMBDA * _arm(d, 50),
                        reverse=True,
                    )
                except Exception:
                    pass
            primary = core_domains[0]
        else:
            primary = domains[0] if domains else "knowledge_learning"

        # Compound tasks: include all real-domain agents in the plan.
        if complexity == "compound" and len(core_domains) > 1:
            agents = core_domains[:]
            if use_signal and primary not in agents:
                agents = [primary] + agents
        else:
            agents = [primary]

        # Regret-weighted sort on the full domains list (for signal path,
        # this sorts the original DOMAIN_SIGNALS hits, not the signal domain).
        if not use_signal and len(domains) > 1:
            try:
                from decision.log import agent_regret_mean as _arm
                LAMBDA = 0.5
                domains = sorted(
                    domains,
                    key=lambda d: to_confidence(d) - LAMBDA * _arm(d, 50),
                    reverse=True,
                )
            except Exception:
                pass

        needs_plan = complexity == "compound" and len(agents) > 1
        confidence = to_confidence(primary)
        # Regret = opportunity cost of not choosing the best alternative agent
        alt_confs  = [to_confidence(a) for a in agents[1:]] if len(agents) > 1 else []
        regret     = round(max(alt_confs) - confidence, 3) if alt_confs else 0.0
        regret     = max(0.0, regret)
        level, reflect_type = _reflect_level(
            action, primary, confidence, complexity, regret=regret
        )
        reflect = level != "none"

        # Reflection history bias: if this agent scored poorly on similar tasks
        # in the past, swap to the next best domain or force a reflection cycle.
        try:
            from memory_core.db import search as _mem_search
            refl_hits = _mem_search(query, top_k=5, mem_type="reflection",
                                    caller="core_brain.fast_path")
            for hit in refl_hits:
                if hit["score"] < 0.65:
                    continue
                meta       = hit.get("metadata", {})
                past_agent = meta.get("agent", "")
                past_score = float(meta.get("reflection_score", 1.0))
                if past_agent == primary and past_score < 0.60:
                    if len(domains) > 1:
                        # When signal-based routing chose the primary, never swap
                        # to knowledge_learning — that domain fires on generic verbs
                        # ("explain", "what is") and is not a real competitor.
                        alt = next(
                            (d for d in domains if d != primary
                             and (not use_signal or d != "knowledge_learning")),
                            None
                        )
                        if alt:
                            print(
                                f"[core_brain] reflection bias: {primary} → {alt} "
                                f"(past score {past_score:.2f})"
                            )
                            primary    = alt
                            agents     = [primary] + [a for a in agents if a != primary]
                            confidence = to_confidence(primary)
                            level, reflect_type = _reflect_level(action, primary, confidence, complexity)
                            reflect = level != "none"
                    elif level == "none":
                        level   = "full"
                        reflect = True
                        print(
                            f"[core_brain] reflection bias: forcing full reflect for "
                            f"{primary} (past score {past_score:.2f})"
                        )
                    break
        except Exception:
            pass

        # Regret: confidence left on the table vs best alternative.
        # Computed over real-domain competitors (knowledge_learning excluded).
        competitors = [d for d in (core_domains if use_signal else domains)
                       if d != primary and d != "knowledge_learning"]
        if competitors:
            best_alt = max(to_confidence(d) for d in competitors)
            regret   = round(max(0.0, best_alt - confidence), 3)
        else:
            regret = 0.0

        # ── Episodic signal: adjust confidence/level from past outcomes ──
        # Look up how this agent performed on similar queries before.
        # Successful past episodes boost routing confidence by a small amount.
        # Failed past episodes add light verification if none is scheduled.
        try:
            from memory_core.db import search as _ep_search
            ep_hits = _ep_search(query, top_k=5, mem_type="episodic",
                                 caller="core_brain.episodic")
            for hit in ep_hits:
                if hit["score"] < 0.72:
                    continue
                meta        = hit.get("metadata", {})
                past_agent  = meta.get("agent", "")
                past_outcome = meta.get("outcome", "")
                past_regret = float(meta.get("regret", 0.0))
                if past_agent != primary:
                    continue
                if past_outcome == "successful" and past_regret < 0.10:
                    confidence = round(min(1.0, confidence + 0.04), 3)
                    print(
                        f"[core_brain] episodic boost: {primary} solved "
                        f"similar query (regret={past_regret:.2f})"
                    )
                elif past_outcome == "failed" and level == "none":
                    level   = "light"
                    reflect = True
                    print(
                        f"[core_brain] episodic flag: {primary} failed "
                        f"on similar query → adding light reflection"
                    )
                break
        except Exception:
            pass

        # ── Learned router: ensemble confidence signal ────────
        # predict() is <1ms; never crashes (returns fallback on error).
        # Agree → small confidence boost.
        # Disagree + high model conf + weak signal → model wins.
        try:
            from orchestration.learned_router import predict as _lr_predict
            lr_agent, lr_conf = _lr_predict(
                signal.domain, signal.domain_conf,
                signal.answer_shape, signal.verbosity, action,
            )
            if lr_agent == primary:
                confidence = round(min(1.0, confidence + 0.05), 3)
                print(f"[core_brain] learned_router agrees ({lr_agent} {lr_conf:.0%}) → conf+0.05")
            elif lr_conf > 0.85 and signal.domain_conf < 0.50 and lr_agent in VALID_AGENTS:
                print(
                    f"[core_brain] learned_router override: "
                    f"{primary} → {lr_agent} (lr_conf={lr_conf:.0%}, sig_conf={signal.domain_conf:.2f})"
                )
                primary    = lr_agent
                agents     = [primary] + [a for a in agents if a != primary]
                confidence = round(to_confidence(primary) + 0.05, 3)
                level, reflect_type = _reflect_level(
                    action, primary, confidence, complexity, regret=regret
                )
                reflect = level != "none"
        except Exception:
            pass

        # ── Final reflect re-evaluation ───────────────────────────
        # _reflect_level was called with base confidence before episodic/
        # learned_router boosts. If those boosts pushed the final confidence
        # above the full→light threshold, downgrade to light for build tasks.
        # Never upgrade (light→full) here — keep this conservative.
        if level == "full" and action == "build" and primary in CODE_AGENTS:
            new_level, _ = _reflect_level(action, primary, confidence, complexity, regret=regret)
            if new_level == "light":
                level   = "light"
                reflect = True   # light still runs grounded evaluation
                print(
                    f"[core_brain] reflect downgrade: full→light after boosts "
                    f"(final conf={confidence:.2f})"
                )

        intent = f"{action} via {', '.join(agents)}"

        print(
            f"[core_brain] fast path | action={action} | "
            f"domain={signal.domain}({signal.domain_conf:.2f}) | shape={signal.answer_shape} | "
            f"complexity={complexity} | agents={agents} | "
            f"reflect={level}({reflect_type}) | conf={confidence} | regret={regret}"
        )

        return BrainDecision(
            intent=intent,
            action=action,
            complexity=complexity,
            agent_strategy=agents,
            needs_plan=needs_plan,
            plan=_build_plan(agents) if needs_plan else [],
            reflect=reflect,
            reflect_type=reflect_type,
            reflect_level=level,
            confidence=confidence,
            regret=regret,
            signal_domain=signal.domain, signal_conf=signal.domain_conf,
            signal_shape=signal.answer_shape, signal_verbosity=signal.verbosity,
        )

    # ── LLM path: ambiguous or no domain detected ─────────────
    print(
        f"[core_brain] LLM path | action={action} | "
        f"domain={signal.domain}({signal.domain_conf:.2f}) | "
        f"domains={domains} | complexity={complexity}"
    )
    llm_result  = _llm_clarify(query)
    action      = llm_result["action"]
    agents      = llm_result["agents"]
    complexity  = llm_result["complexity"]
    intent      = llm_result["intent"]
    primary     = agents[0]
    needs_plan  = complexity == "compound" and len(agents) > 1
    confidence  = round(to_confidence(primary) * 0.75, 2)  # LLM path = less certain
    level, reflect_type = _reflect_level(action, primary, confidence, complexity, regret=0.15)
    reflect = level != "none"

    print(
        f"[core_brain] LLM result | intent='{intent}' | "
        f"agents={agents} | reflect={level}({reflect_type}) | confidence={confidence}"
    )

    return BrainDecision(
        intent=intent,
        action=action,
        complexity=complexity,
        agent_strategy=agents,
        needs_plan=needs_plan,
        plan=_build_plan(agents) if needs_plan else [],
        reflect=reflect,
        reflect_type=reflect_type,
        reflect_level=level,
        confidence=confidence,
        signal_domain=signal.domain, signal_conf=signal.domain_conf,
        signal_shape=signal.answer_shape, signal_verbosity=signal.verbosity,
    )


# ── STANDALONE TEST ──────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("core_brain.py — fast-path tests (no Ollama needed)")
    print("=" * 65)

    def make_state(text: str) -> dict:
        from langchain_core.messages import HumanMessage
        return {
            "messages":     [HumanMessage(content=text)],
            "active_agent": "",
            "task":         text,
            "result":       "",
            "next_agent":   "",
            "memory":       {},
            "force_agent":  "",
        }

    # (query, expected_agent, expected_reflect, expected_action)
    tests = [
        ("Write a Python script to check disk usage",       "python_dev",         True,  "build"),
        ("Debug this Python error: TypeError on line 12",   "python_dev",         True,  "debug"),
        ("Explain how DNS works",                           "it_networking",      False, "explain"),
        ("give me the command to restart nginx",            "terse",              False, "lookup"),
        ("command to list open ports",                      "terse",              False, "lookup"),
        ("Build a Blazor WebAssembly component",            "dotnet_dev",         True,  "build"),
        ("What is a transformer model",                     "ai_ml",              False, "explain"),
        ("Compare PyTorch vs TensorFlow for training",      "ai_ml",              False, "compare"),
        ("Research LangGraph state management",             "ai_ml",              True,  "research"),
        ("Fix my C# null reference exception",              "dotnet_dev",         True,  "debug"),
        ("",                                                "knowledge_learning", False, "unknown"),
    ]

    passed = total = 0
    for query, exp_agent, exp_reflect, exp_action in tests:
        state = make_state(query)
        d = think(query, state)

        ok_agent   = d.agent_strategy[0] == exp_agent
        ok_reflect = d.reflect == exp_reflect
        ok_action  = d.action == exp_action
        all_ok     = ok_agent and ok_reflect and ok_action

        label = (query[:50] + "…") if len(query) > 50 else query or "(empty)"
        print(f"\n  {'✓' if all_ok else '✗'} '{label}'")
        if not ok_action:  print(f"      action:   got={d.action!r:<12} expected={exp_action!r}")
        if not ok_agent:   print(f"      agent[0]: got={d.agent_strategy[0]!r:<20} expected={exp_agent!r}")
        if not ok_reflect: print(f"      reflect:  got={d.reflect!r:<8} expected={exp_reflect!r}")

        total  += 1
        passed += int(all_ok)

    print(f"\n{'='*65}")
    print(f"  Result: {passed}/{total} passed {'✅' if passed == total else '⚠️'}")
    print()
    print("  LLM path test (requires Ollama running):")
    print("    from orchestration.core_brain import think")
    print("    d = think('something unclear', state)")
    print("    print(d.intent, d.agent_strategy)")
