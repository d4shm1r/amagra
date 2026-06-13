"""
dispatch.py — Control-plane primitive (delta-algebra-spec.md, step 1)

This is the OTHER bus. event_bus.py is the observability plane: emit() is
fire-and-forget telemetry, handlers cannot influence the emitter. THIS module
is the control plane: dispatch() runs registered hooks, each hook returns a
Delta (never mutates anything), and a deterministic runtime-owned reducer
commits those deltas to a final vector.

Hard rules this module exists to enforce (do not relax without a red-then-green
case in tests/test_dispatch_reducer.py — see spec §13):

  - Extensions emit deltas; only reduce() mutates state.            (invariant)
  - The op set is CLOSED: bias, scale(>0), veto, pin, floor, ceil.  (§2)
  - Reduction is phased, not priority-sorted: A veto → B scale →
    C bias → D clamp → E pin, each phase internally commutative.    (§3/§4)
  - veto is absolute: never resurrected by scale/bias/clamp/pin.    (§4)
  - Canonical summation order (target, hook_id, seq) → bit-stable.  (§6)
  - Priority is operator-assigned tiers, not self-declared.        (§7)
  - dispatch() records the materialized deltas BEFORE reducing.    (§8/§10)

Types and the reduce() contract are FROZEN as of this commit. Everything
downstream (every hook, the routing seam, replay) assumes them.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Callable

NEG = float("-inf")
POS = float("inf")


# ── §7 priority tiers (operator-assigned, not self-declared) ───────────
class Tier(IntEnum):
    EXTENSION = 1   # third-party / marketplace hooks
    OPERATOR  = 2   # deployment-local hooks the operator trusts
    CORE      = 3   # built-in runtime behavior


# ── §2 the delta: an immutable bundle of typed ops ─────────────────────
@dataclass(frozen=True)
class Delta:
    """
    The ONLY thing a hook may return. Immutable. Build one with DeltaBuilder.

    Each op list holds (key, value) tuples except vetoes/pins which hold keys.
    `scale` values must be > 0 (§2): scale-to-zero is elimination, spelled veto;
    and -inf * 0 = NaN poisons the softmax.
    """
    hook_id: str
    tier:    Tier = Tier.EXTENSION
    biases:  tuple = ()    # ((key, float), ...)
    scales:  tuple = ()    # ((key, float>0), ...)
    vetoes:  tuple = ()    # (key, ...)
    pins:    tuple = ()    # (key, ...)
    floors:  tuple = ()    # ((key, float), ...)
    ceils:   tuple = ()    # ((key, float), ...)

    @staticmethod
    def empty(hook_id: str = "_", tier: Tier = Tier.EXTENSION) -> "Delta":
        return Delta(hook_id, tier)


class DeltaBuilder:
    """Fluent, mutable builder → frozen Delta. Hooks use this, then .build()."""

    def __init__(self, hook_id: str, tier: Tier = Tier.EXTENSION):
        self.hook_id, self.tier = hook_id, tier
        self._b, self._s, self._v, self._p, self._f, self._c = [], [], [], [], [], []

    def bias(self, k: str, v: float) -> "DeltaBuilder":
        self._b.append((k, float(v))); return self

    def scale(self, k: str, f: float) -> "DeltaBuilder":
        if f <= 0:
            raise ValueError(f"scale factor must be > 0 (got {f}); "
                             f"scale-to-zero is elimination — use veto({k!r})")
        self._s.append((k, float(f))); return self

    def veto(self, k: str) -> "DeltaBuilder":
        self._v.append(k); return self

    def pin(self, k: str) -> "DeltaBuilder":
        self._p.append(k); return self

    def floor(self, k: str, v: float) -> "DeltaBuilder":
        self._f.append((k, float(v))); return self

    def ceil(self, k: str, v: float) -> "DeltaBuilder":
        self._c.append((k, float(v))); return self

    def build(self) -> Delta:
        return Delta(self.hook_id, self.tier,
                     tuple(self._b), tuple(self._s), tuple(self._v),
                     tuple(self._p), tuple(self._f), tuple(self._c))


# ── reduction result ───────────────────────────────────────────────────
@dataclass(frozen=True)
class ReductionResult:
    vector:    dict          # post-softmax probability distribution
    raw:       dict          # pre-softmax logits (for the Decision Explorer)
    deltas:    tuple         # materialized (hook_id, tier, Delta) — the trace
    conflicts: tuple         # (kind, detail, winner) tuples (§5)
    decision:  str = ""      # set by caller's decide(), or argmax fallback


# ── §3/§6 the reducer. Deterministic. Runtime-owned. The whole point. ──
def reduce(base: dict[str, float],
           deltas: list[Delta]) -> tuple[dict, dict, list]:
    """
    Reduce deltas over a base logit vector. Returns (probs, raw_logits, conflicts).

    Phases run in fixed order (A→E); within each phase, ops are applied in
    canonical (key, hook_id, seq) order so float summation is bit-stable
    regardless of hook registration order (§6).
    """
    v: dict[str, float] = dict(base)
    conflicts: list[tuple] = []
    vetoed = {k for d in deltas for k in d.vetoes}

    def canonical(select: Callable[[Delta], tuple]) -> list[tuple]:
        items = []
        for d in deltas:
            for seq, op in enumerate(select(d)):
                items.append((op[0], d.hook_id, seq, op))
        items.sort(key=lambda it: (it[0], it[1], it[2]))   # (key, hook_id, seq)
        return [it[3] for it in items]

    # Phase A — vetoes (idempotent, order-free)
    for k in sorted(vetoed):
        v[k] = NEG
    # Phase B — scales (multiplicative; skip vetoed → never -inf*f, incl. NaN)
    for k, f in canonical(lambda d: d.scales):
        if k in vetoed:
            continue
        v[k] = v.get(k, 0.0) * f
    # Phase C — biases (additive; skip vetoed → never -inf + v)
    for k, val in canonical(lambda d: d.biases):
        if k in vetoed:
            continue
        v[k] = v.get(k, 0.0) + val
    # Phase D — clamps (max/min; floors skip vetoed, ceils are harmless on -inf)
    for k, val in canonical(lambda d: d.floors):
        if k not in vetoed:
            v[k] = max(v.get(k, 0.0), val)
    for k, val in canonical(lambda d: d.ceils):
        v[k] = min(v.get(k, 0.0), val)
    # Phase E — pins. veto beats pin (§4): drop pins on vetoed keys, record it.
    pins = []
    for d in deltas:
        for k in d.pins:
            if k in vetoed:
                conflicts.append(("veto_beats_pin", k, None))
            else:
                pins.append((int(d.tier), d.hook_id, k))
    if pins:
        top_tier = max(t for t, _, _ in pins)
        tied = sorted((p for p in pins if p[0] == top_tier), key=lambda p: p[1])
        if len({k for _, _, k in tied}) > 1:                # competing pins (§5)
            winner = tied[0][2]
            conflicts.append(("competing_pins", [k for _, _, k in tied], winner))
        else:
            winner = tied[0][2]
        v[winner] = POS

    return _softmax(v), v, conflicts


def _softmax(v: dict[str, float]) -> dict[str, float]:
    """Single normalization point (§1). Handles -inf (→0) and a winning +inf pin."""
    keys = list(v)
    if any(v[k] == POS for k in keys):
        winners = [k for k in keys if v[k] == POS]
        return {k: (1.0 / len(winners) if v[k] == POS else 0.0) for k in keys}
    finite = [v[k] for k in keys if v[k] != NEG]
    mx = max(finite) if finite else 0.0
    exps = {k: (0.0 if v[k] == NEG else math.exp(v[k] - mx)) for k in keys}
    s = sum(exps.values()) or 1.0
    return {k: exps[k] / s for k in keys}


# ── §10 dispatch: run hooks → record → reduce. Separate from emit(). ───
_HOOKS: dict[str, list] = defaultdict(list)   # event_type -> [(hook_id, tier, pure, fn)]


def register(event_type: str, fn: Callable, *, hook_id: str,
             tier: Tier = Tier.EXTENSION, pure: bool = False) -> None:
    """
    Register a control hook. Priority is the operator-assigned `tier`, NOT a
    field the hook sets on itself (§7). `pure=False` by default — a hook is
    assumed impure (LLM/clock/RNG/IO) unless the operator vouches otherwise,
    which matters for replay (§8).
    """
    _HOOKS[event_type].append((hook_id, tier, pure, fn))
    # stable order: tier desc, then registration order (recorded, §7)
    _HOOKS[event_type].sort(key=lambda h: -int(h[1]))


def unregister(event_type: str, hook_id: str) -> None:
    _HOOKS[event_type] = [h for h in _HOOKS[event_type] if h[0] != hook_id]


def dispatch(event_type: str, event: object,
             base: dict[str, float],
             decide: Callable[[dict], str] | None = None) -> ReductionResult:
    """
    Run all hooks for event_type over `event`, reduce their deltas onto `base`.

    Hooks that raise, or return anything other than a Delta, are dropped with a
    recorded conflict — a misbehaving extension can never crash the control path
    or smuggle in a side effect.
    """
    materialized: list[tuple] = []
    deltas: list[Delta] = []
    conflicts: list[tuple] = []

    for hook_id, tier, _pure, fn in _HOOKS.get(event_type, []):
        try:
            d = fn(event)
        except Exception as e:                       # extension fault isolation
            conflicts.append(("hook_error", hook_id, repr(e)))
            continue
        if not isinstance(d, Delta):
            conflicts.append(("hook_bad_return", hook_id, type(d).__name__))
            continue
        d = replace(d, hook_id=hook_id, tier=tier)   # runtime owns id/tier (§7)
        deltas.append(d)
        materialized.append((hook_id, int(tier), d))

    _record(event_type, base, materialized)          # trace BEFORE reduce (§8)

    probs, raw, conf = reduce(base, deltas)
    conflicts.extend(conf)
    decision = decide(probs) if decide else (max(probs, key=probs.get) if probs else "")
    return ReductionResult(probs, raw, tuple(materialized), tuple(conflicts), decision)


def _record(event_type: str, base: dict, materialized: list) -> None:
    """
    Persist the materialized deltas to the observability plane (§8/§10).
    The control happens via dispatch()'s RETURN value; this is pure trace —
    so it legitimately rides event_bus.emit without violating plane separation.
    """
    try:
        from infrastructure.event_bus import emit
        emit("delta.dispatched", {
            "event_type": event_type,
            "base": base,
            "deltas": [
                {"hook_id": h, "tier": t,
                 "biases": list(d.biases), "scales": list(d.scales),
                 "vetoes": list(d.vetoes), "pins": list(d.pins),
                 "floors": list(d.floors), "ceils": list(d.ceils)}
                for h, t, d in materialized
            ],
        })
    except Exception:
        pass   # trace failure must never break the control path
