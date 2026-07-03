"""
semantic_threshold_study.py — pick AGENTIC_SEMANTIC_MIN_SIM with evidence.

The semantic fallback (semantic_fallback.py) is built, tested, and its latency is
acceptable. The last gate before flipping AGENTIC_SEMANTIC_FALLBACK on by default
is the similarity floor `_MIN_SIM`: below it, route() declines (returns None) and
the query keeps its baseline behaviour instead of forcing a route.

The question this answers: do WRONG semantic routes score a lower cosine
similarity than RIGHT ones? If they separate, a floor buys accuracy for free —
it drops confident-wrong routes while keeping the good ones. If they don't
separate, no single floor helps and `_MIN_SIM` should stay 0 (let hybrid ride).

Method (highest fidelity — uses the REAL production module):
  * For each held-out adversarial prompt, call semantic_fallback.route() to get
    (agent, similarity), and signal_route() for the keyword baseline.
  * Model the shipped hook exactly: final(T) = keyword route, EXCEPT when the
    keyword route is the knowledge_learning fallthrough — then use the semantic
    route if similarity >= T, else decline back to knowledge_learning.
  * Sweep T, report accuracy(T), and the right/wrong similarity distributions.

Requires Ollama (nomic-embed-text). ~6s for 91 query embeds.

Run:
    PYTHONPATH=. python3 evaluation/semantic_threshold_study.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AGENTIC_SEMANTIC_FALLBACK"] = "1"
os.environ["AGENTIC_SEMANTIC_MIN_SIM"] = "0.0"    # study applies the floor itself

from evaluation.ablation_eval import signal_route
from evaluation.adversarial_eval import PROMPTS as ADV
import orchestration.semantic_fallback as sf


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    print("=" * 70)
    print("  Semantic MIN_SIM threshold study")
    print("=" * 70)

    if not sf._build_index():
        print("\n  ✗ index build failed — is Ollama up on :11434?")
        return

    # Per-prompt: (expected, keyword_route, semantic_agent, sim)
    rows = []
    for pid, expected, category, prompt in ADV:
        kw = signal_route(prompt)
        r = sf.route(prompt)
        if r is None:
            continue
        sem_agent, sim = r
        rows.append((expected, kw, sem_agent, sim))

    # Separation: similarity of the SEMANTIC route when it is right vs wrong.
    right = [sim for exp, kw, sa, sim in rows if sa == exp]
    wrong = [sim for exp, kw, sa, sim in rows if sa != exp]
    print("\n  Semantic-route similarity — does it separate right from wrong?")
    print(f"    RIGHT routes: n={len(right):3d}  mean={_mean(right):.3f}  "
          f"min={min(right):.3f}  max={max(right):.3f}")
    print(f"    WRONG routes: n={len(wrong):3d}  mean={_mean(wrong):.3f}  "
          f"min={min(wrong):.3f}  max={max(wrong):.3f}")
    gap = _mean(right) - _mean(wrong)
    print(f"    mean gap (right − wrong): {gap:+.3f}   "
          f"{'→ separable, a floor can help' if gap > 0.03 else '→ weak/no separation'}")

    # AUC (prob. a random right-route outscores a random wrong-route).
    if right and wrong:
        wins = sum(1 for r in right for w in wrong if r > w)
        ties = sum(1 for r in right for w in wrong if r == w)
        auc = (wins + 0.5 * ties) / (len(right) * len(wrong))
        print(f"    ranking AUC: {auc:.3f}   (0.5 = floor useless, 1.0 = perfect gate)")

    # Threshold sweep on the shipped hybrid hook.
    def hybrid_final(T):
        correct = 0
        for exp, kw, sa, sim in rows:
            if kw != "knowledge_learning":
                final = kw                      # confident keyword route — untouched
            elif sim >= T:
                final = sa                      # semantic rescue clears the floor
            else:
                final = "knowledge_learning"    # declined → baseline fallthrough
            correct += (final == exp)
        return correct / len(rows)

    print("\n  Threshold sweep (hybrid_fix, floor applied to the rescue only):")
    print("    T       acc    kept-rescues   right-kept  wrong-kept")
    print("    " + "-" * 52)
    best = (-1.0, 0.0)
    for T in [round(0.30 + 0.02 * i, 2) for i in range(21)]:   # 0.30 … 0.70
        acc = hybrid_final(T)
        rescues = [(exp, sa, sim) for exp, kw, sa, sim in rows if kw == "knowledge_learning"]
        kept = [(exp, sa, sim) for exp, sa, sim in rescues if sim >= T]
        rk = sum(1 for exp, sa, sim in kept if sa == exp)
        wk = sum(1 for exp, sa, sim in kept if sa != exp)
        if acc > best[0]:
            best = (acc, T)
        print(f"    {T:.2f}   {acc:5.1%}   {len(kept):3d}/{len(rescues):<3d}"
              f"        {rk:3d}         {wk:3d}")

    print(f"\n  Best floor: T={best[1]:.2f} → hybrid accuracy {best[0]:.1%}")
    print("  (T=0.30 ≈ current behaviour; if best T is at the low end, the floor")
    print("   buys little and MIN_SIM should stay near 0 — let the hybrid ride.)")

    # Net effect + regression risk — the numbers that actually gate shipping.
    kw_acc = sum(1 for exp, kw, sa, sim in rows if kw == exp) / len(rows)
    rescued = [(exp, sa) for exp, kw, sa, sim in rows if kw == "knowledge_learning"]
    gains = sum(1 for exp, sa in rescued if sa == exp)            # KL→correct
    # Regression: keyword got KL and that was RIGHT, rescue pulled it away → now wrong.
    regressions = sum(1 for exp, sa in rescued if exp == "knowledge_learning" and sa != exp)
    print("\n  Ship gate:")
    print(f"    keyword baseline accuracy : {kw_acc:5.1%}")
    print(f"    hybrid (no floor)         : {best[0]:5.1%}   (net {best[0]-kw_acc:+.1%})")
    print(f"    rescues that turned KL→correct : {gains}")
    print(f"    regressions (correct-KL pulled away) : {regressions}")
    print("    → net is strongly positive iff gains ≫ regressions.")


if __name__ == "__main__":
    main()
