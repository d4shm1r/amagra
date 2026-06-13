"""
Routing seam tests (rollout step 2) — what dispatch() actually buys at the
routing decision, and the boundary it does NOT yet cross.

These pin down BEHAVIOR, including a deliberate limitation, so that lifting the
limitation later is a reviewed change rather than an accident.
"""
from infrastructure.dispatch import (
    DeltaBuilder, Tier, dispatch, register, unregister,
)
from orchestration.router import (
    ROUTING_EVENT, RoutingEvent, score, decide,
)


def _base(scores):
    return {a: float(s) for a, s in scores.items()}


# ── what step 2 delivers: CORE pin governs the terse/factual bypass ────
def test_factual_query_pinned_to_terse_via_core_hook():
    q = "what does dns stand for?"
    assert decide(q, score(q)) == "terse"


def test_terse_keyword_pinned_via_core_hook():
    q = "just give me the code to read a file"
    assert decide(q, score(q)) == "terse"


# ── the delta REACHES the reducer: an extension bias does move the vector ──
def test_extension_bias_moves_the_reduced_vector():
    q = "set up nginx and write a python script"   # it_networking vs python_dev tie
    sc = score(q)

    def boost(_ev):
        return DeltaBuilder("ext.boost", Tier.EXTENSION).bias("python_dev", 9.0).build()

    register(ROUTING_EVENT, boost, hook_id="ext.boost", tier=Tier.EXTENSION)
    try:
        res = dispatch(ROUTING_EVENT, RoutingEvent(q, dict(sc)), _base(sc))
    finally:
        unregister(ROUTING_EVENT, "ext.boost")
    # the seam carried the delta: python_dev now dominates the distribution
    assert max(res.vector, key=res.vector.get) == "python_dev"


# ── the BOUNDARY: decide() does NOT yet consume bias (cardinal projection) ──
def test_extension_bias_is_inert_at_the_decision_today():
    """
    KNOWN LIMITATION (step 2). decide()'s threshold/default projection is
    cardinal — integer keyword counts, with quirks like "2-2 tie → default"
    and "==1 → return best" — and it reads the RAW scores, not the reduced
    vector. So `bias`/`scale`/`veto` flow through the reducer (test above)
    but do not yet change the routed node. Only CORE pins are honored.

    Making bias live means redefining the projection to consume the reduced
    vector, which WILL change tie-break behavior. That is a deliberate step 3
    decision; this test exists so it cannot happen silently.
    """
    q = "set up nginx and write a python script"
    sc = score(q)
    before = decide(q, sc)

    def boost(_ev):
        return DeltaBuilder("ext.boost", Tier.EXTENSION).bias("python_dev", 9.0).build()

    register(ROUTING_EVENT, boost, hook_id="ext.boost", tier=Tier.EXTENSION)
    try:
        after = decide(q, sc)
    finally:
        unregister(ROUTING_EVENT, "ext.boost")

    assert before == after, "if this fails, bias became live — update step 3 spec"


# ── CORE pin outranks an extension that tries to pin elsewhere (§7 tiers) ──
def test_core_tier_pin_outranks_extension_pin():
    q = "what does dns stand for?"   # CORE hook pins terse
    sc = score(q)

    def ext_pin(_ev):
        return DeltaBuilder("ext.grab", Tier.EXTENSION).pin("it_networking").build()

    register(ROUTING_EVENT, ext_pin, hook_id="ext.grab", tier=Tier.EXTENSION)
    try:
        assert decide(q, sc) == "terse"   # CORE tier wins (§7)
    finally:
        unregister(ROUTING_EVENT, "ext.grab")
