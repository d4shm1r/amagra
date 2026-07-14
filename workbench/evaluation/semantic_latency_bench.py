"""
semantic_latency_bench.py — what does the semantic fallback COST on the hot path?

The fallback (orchestration/semantic_fallback.py) is off by default; before it can
be flipped on, we need the added per-query latency, not a hand-wave. This measures:

  1. boot        — one-time exemplar index build (cold vs warm/cached)
  2. route()     — the marginal work the hook adds when it FIRES: one embed() of
                   the query + an O(n) cosine scan over n=138 exemplars.
                   Reported as a distribution (p50/p90/p99), because a mean hides
                   the tail that actually matters for latency budgets.
  3. embed vs scan — the split, so we know whether the cost is the Ollama round-trip
                   (network-bound, cache-friendly) or the pure-Python cosine scan
                   (CPU-bound, grows with exemplar count).

The hook only fires on queries the keyword router could not place, so this cost is
paid on a MINORITY of traffic. Multiply by that share for the real fleet impact.

Run:
    PYTHONPATH=. python3 evaluation/semantic_latency_bench.py
    PYTHONPATH=. python3 evaluation/semantic_latency_bench.py --n 300
"""

import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("AGENTIC_SEMANTIC_FALLBACK", "1")   # enable for the bench

from workbench.evaluation.adversarial_eval import PROMPTS as ADV
import orchestration.semantic_fallback as sf


def _pct(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def _stats(name, xs_ms):
    print(f"  {name:22s}  n={len(xs_ms):4d}  "
          f"mean={sum(xs_ms)/len(xs_ms):6.1f}  "
          f"p50={_pct(xs_ms,50):6.1f}  "
          f"p90={_pct(xs_ms,90):6.1f}  "
          f"p99={_pct(xs_ms,99):6.1f}  (ms)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="total route() samples")
    args = ap.parse_args()

    print("=" * 74)
    print("  Semantic fallback — hot-path latency")
    print("=" * 74)

    # 1. boot: force a cold build, then a warm (cached) one.
    sf._EX_VECS = None
    sf._DISABLED = False
    t = time.time()
    ok = sf._build_index(rebuild=True)
    cold = time.time() - t
    if not ok:
        print("\n  ✗ index build failed (is Ollama up on :11434?) — cannot measure route().")
        return
    sf._EX_VECS = None                       # drop in-memory, keep disk cache
    t = time.time()
    sf._build_index()
    warm = time.time() - t
    print(f"\n  boot: cold build {cold:5.1f}s   |   warm (cached) {warm*1000:5.1f}ms   "
          f"|   exemplars={len(sf._EX_LABELS)}")

    # 2. route() distribution over repeated held-out prompts.
    queries = [p[3] for p in ADV]
    reps = (args.n + len(queries) - 1) // len(queries)
    sample = (queries * reps)[:args.n]

    route_ms, embed_ms, scan_ms = [], [], []
    provider = sf._provider()
    ex_vecs, ex_labels = sf._EX_VECS, sf._EX_LABELS

    for q in sample:
        t0 = time.time()
        r = sf.route(q)
        route_ms.append(1000 * (time.time() - t0))

        # isolate embed vs scan on the same query
        t1 = time.time()
        qv = sf._norm(provider.embed(q))
        embed_ms.append(1000 * (time.time() - t1))
        t2 = time.time()
        _ = sorted(((sum(a * b for a, b in zip(qv, ev)), lab)
                    for ev, lab in zip(ex_vecs, ex_labels)), key=lambda z: -z[0])[:5]
        scan_ms.append(1000 * (time.time() - t2))
        assert r is not None

    print()
    _stats("route() total", route_ms)
    _stats("  embed() only", embed_ms)
    _stats("  cosine scan only", scan_ms)

    # 3. fleet framing
    p99 = _pct(route_ms, 99)
    print("\n  Fleet framing (hook fires only on queries the keyword router can't place):")
    for share in (0.10, 0.25, 0.50):
        print(f"    if {share:>4.0%} of traffic is unrouted → +{share*sum(route_ms)/len(route_ms):5.1f}ms "
              f"average added latency per request")
    print(f"\n  Verdict inputs: p99 route() = {p99:.0f}ms; scan is "
          f"{100*(sum(scan_ms)/len(scan_ms))/(sum(route_ms)/len(route_ms)):.0f}% of it "
          f"(rest is the Ollama embed round-trip). Scan grows O(n_exemplars); embed is "
          f"network-bound and independent of n.")


if __name__ == "__main__":
    main()
