# coordinator_patch.py
# ─────────────────────────────────────────────────────────────
# HOW TO USE THIS FILE
#
# This is NOT runnable code. It shows the exact lines to
# ADD and CHANGE in your existing ~/agentic-ai/coordinator.py.
#
# Apply in this order:
#   1. Add import at top of coordinator.py
#   2. Replace your existing route_to_agent function
#   3. Verify add_conditional_edges mapping (no change needed)
#   4. Test with: python3 router.py first
# ─────────────────────────────────────────────────────────────


# ══ STEP 1 ══ Add this import at the TOP of coordinator.py ═══
#
# ADD this line alongside your other imports:

from router import hybrid_router

# ─────────────────────────────────────────────────────────────


# ══ STEP 2 ══ Replace route_to_agent in coordinator.py ══════
#
# BEFORE — your current function (probably looks like this):

# def route_to_agent(state: AgentState) -> str:
#     messages = state["messages"]
#     task = messages[-1].content
#     prompt = f"""..."""
#     response = llm.invoke(prompt)
#     try:
#         data = json.loads(response.content)
#         return data.get("agent", "knowledge_learning")
#     except:
#         return "knowledge_learning"


# AFTER — replace the entire function with exactly this:

# def route_to_agent(state: AgentState) -> str:
#     return hybrid_router(state)


# ─────────────────────────────────────────────────────────────


# ══ STEP 3 ══ Verify add_conditional_edges mapping ══════════
#
# Your existing call should already look like this.
# Only verify — DO NOT change unless a node name is wrong.
#
# graph.add_conditional_edges("coordinator", route_to_agent, {
#     "it_networking":      "it_networking",
#     "python_dev":         "python_dev",
#     "blazor_dev":         "blazor_dev",
#     "ai_ml":              "ai_ml",
#     "documents":          "documents",
#     "personal_projects":  "personal_projects",
#     "research":           "research",
#     "knowledge_learning": "knowledge_learning",
#     "coordinator":        "coordinator",  # ← add this fallback if missing
# })
#
# The key "coordinator" maps back to itself when hybrid_router
# cannot find a confident match. Make sure it is registered
# with add_node("coordinator", coordinator_node) — it likely
# already is since coordinator IS your entry point.

# ─────────────────────────────────────────────────────────────


# ══ STEP 4 ══ Test order (do not skip) ══════════════════════
#
# 1. Test router in isolation FIRST:
#    cd ~/agentic-ai
#    source ~/langgraph-env/bin/activate
#    python3 router.py
#    → All tests should pass before touching coordinator.py
#
# 2. Apply the two changes above to coordinator.py
#
# 3. Test coordinator:
#    python3 main.py
#    Ask: "My Wi-Fi keeps dropping"
#    → Should route to it_networking without LLM delay
#
# 4. Ask ambiguous query:
#    "Help me with my project"
#    → Should fall back to LLM and pick personal_projects
#
# ─────────────────────────────────────────────────────────────


# ══ ROLLBACK ════════════════════════════════════════════════
#
# If anything breaks, revert coordinator.py route_to_agent
# to the original LLM-only version and remove the import.
# Nothing else changes — agents, state, graph all untouched.
