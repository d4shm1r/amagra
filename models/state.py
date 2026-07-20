from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages:       Annotated[list, add_messages]
    active_agent:   str
    task:           str
    result:         str
    next_agent:     str
    memory:         dict
    force_agent:    str
    # ── Set by coordinator after core_brain.think() ───────────
    brain_decision: dict   # serialized BrainDecision fields
    reflect:        bool   # True → run reflection_loop() on agent response
    reflect_type:   str    # code|research|general
    reflect_level:          str    # none|light|full  (light=grounded only, full=+LLM critique)
    contradiction_detected: bool   # True if response contradicted a stored memory
    force_reflect_level:    str    # User override: none|light|full|"" (empty = auto)
    run_id:                 str    # Trace ID from run_tracer — threads through graph
    model_tier:             str    # fast|standard|reasoning — set by coordinator
    # ── Observability: raw orchestration signals from the agent node ──
    # Declared here so LangGraph's state merge doesn't drop them. Without a
    # schema slot these keys are silently discarded before reaching the run log
    # or API response, even though the coordinator sets them. Keys are optional
    # at runtime (absent when the producing path didn't run).
    response_quality:       float  # critic-gate / reflection quality of the kept answer
    response_kept:          str    # first_attempt|reflection_rewrite|A/B — which candidate kept
    reflect_delta:          float  # score_final - score_initial when reflection ran
    gram_winner:            str    # dual-trajectory winning branch ("" when unused)
    gram_log:               str    # dual-trajectory decision log
