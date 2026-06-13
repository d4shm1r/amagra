"""
Tests for infrastructure/dispatch.py — the delta-algebra reducer (spec §13).

Every case here is a proof obligation from delta-algebra-spec.md. A change to
reduce() that breaks one of these is a change to the frozen contract and must
update the spec first.
"""
import math

from infrastructure.dispatch import (
    Delta, DeltaBuilder, Tier, reduce, dispatch, register, unregister,
)


def _b(hook_id, tier=Tier.EXTENSION):
    return DeltaBuilder(hook_id, tier)


def argmax(dist):
    return max(dist, key=dist.get)


# ── §2/§3 core algebra ─────────────────────────────────────────────────
def test_bias_is_additive_and_picks_winner():
    base = {"a": 1.0, "b": 0.0}
    probs, _, _ = reduce(base, [_b("h").bias("b", 5.0).build()])
    assert argmax(probs) == "b"


def test_order_invariant_bit_identical():
    # §6: same biases, reversed hook order → bit-for-bit identical result.
    base = {"a": 1.0, "b": 2.0}
    h1 = _b("a").bias("a", 0.1).bias("b", 0.2).build()
    h2 = _b("b").bias("b", 0.3).bias("a", 0.7).build()
    p1, _, _ = reduce(base, [h1, h2])
    p2, _, _ = reduce(base, [h2, h1])
    assert p1 == p2
    assert p1["a"] == p2["a"]   # exact float equality, not approx


def test_veto_beats_bias():
    base = {"a": 1.0, "b": 1.0}
    probs, _, _ = reduce(base, [_b("h").veto("a").bias("a", 99.0).build()])
    assert probs["a"] == 0.0


# ── §13 bug #1: veto + scale(0) must not NaN ───────────────────────────
def test_scale_zero_is_rejected_at_build():
    try:
        _b("h").scale("a", 0.0)
        assert False, "scale(0) should raise"
    except ValueError:
        pass


def test_veto_then_scale_no_nan():
    # Even constructing the delta directly (bypassing the builder guard),
    # the reducer must not produce NaN on a vetoed key.
    d = Delta("h", Tier.EXTENSION, vetoes=("a",), scales=(("a", 0.0),))
    probs, _, _ = reduce({"a": 1.0, "b": 1.0}, [d])
    assert not any(math.isnan(x) for x in probs.values())
    assert probs["a"] == 0.0


# ── §13 bug #2: veto + pin must NOT resurrect ──────────────────────────
def test_veto_beats_pin():
    base = {"a": 1.0, "b": 1.0}
    probs, _, conflicts = reduce(base, [_b("h").veto("a").pin("a").build()])
    assert probs["a"] == 0.0, "veto is absolute; pin must not resurrect it"
    assert any(c[0] == "veto_beats_pin" for c in conflicts)


# ── §5 competing pins ──────────────────────────────────────────────────
def test_competing_pins_deterministic_and_recorded():
    base = {"a": 1.0, "b": 1.0, "c": 1.0}
    probs, _, conflicts = reduce(base, [
        _b("z").pin("a").build(),
        _b("y").pin("b").build(),
    ])
    assert any(c[0] == "competing_pins" for c in conflicts)
    # deterministic winner: top tier (equal) → lowest hook_id "y"
    assert argmax(probs) == "b"


def test_higher_tier_pin_wins_over_lower():
    base = {"a": 1.0, "b": 1.0}
    probs, _, _ = reduce(base, [
        _b("ext", Tier.EXTENSION).pin("a").build(),
        _b("core", Tier.CORE).pin("b").build(),
    ])
    assert argmax(probs) == "b"


# ── §10 dispatch: fault isolation + record ─────────────────────────────
def test_dispatch_isolates_faulty_hook():
    def boom(_event):
        raise RuntimeError("nope")
    def good(_event):
        return _b("good").bias("b", 10.0).build()
    register("test.evt", boom, hook_id="boom", tier=Tier.EXTENSION)
    register("test.evt", good, hook_id="good", tier=Tier.EXTENSION)
    try:
        res = dispatch("test.evt", {}, {"a": 1.0, "b": 0.0})
        assert res.decision == "b"
        assert any(c[0] == "hook_error" for c in res.conflicts)
    finally:
        unregister("test.evt", "boom")
        unregister("test.evt", "good")


def test_dispatch_rejects_non_delta_return():
    register("test.evt2", lambda e: "not a delta", hook_id="bad", tier=Tier.EXTENSION)
    try:
        res = dispatch("test.evt2", {}, {"a": 1.0})
        assert any(c[0] == "hook_bad_return" for c in res.conflicts)
    finally:
        unregister("test.evt2", "bad")
