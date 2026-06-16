"""
Multi-rater agreement harness for the adversarial routing set (issue #20).

WHY THIS EXISTS
---------------
`adversarial_eval.py` reports ~42% signal-only accuracy against SINGLE-RATER labels
(the author's best call). The external eval-methodology review (REVIEW_FINDINGS §2)
asked the prior question: is the routing target even well-defined? If three competent
people can't agree which specialist a prompt belongs to, then *no* accuracy number
means much — you'd be measuring against one person's taste, not a ground truth.

This harness answers that with inter-rater agreement. Multiple raters label the same
held-out prompts BLIND (no system output, no existing label, no other rater's answers),
and we compute Fleiss' κ across them:

  κ < 0.00  worse than chance      0.41–0.60  moderate
  0.00–0.20 slight                 0.61–0.80  substantial
  0.21–0.40 fair                   0.81–1.00  almost perfect   (Landis & Koch 1977)

Only once κ shows the target is well-defined (≳0.6) does the 42% become a number worth
defending — and the per-rater majority vote then gives *consensus gold labels* that can
replace the author's single-rater labels (and feed learned-router training, which the
review wanted restricted to gold/feedback-confirmed labels).

USAGE
-----
  # 1. Each rater labels blind (shuffled order, no hints), writes a ratings file:
  PYTHONPATH=. python3 evaluation/rater_harness.py collect --rater alice
  PYTHONPATH=. python3 evaluation/rater_harness.py collect --rater bob

  # 2. (optional) add the local model as one more rater — labelled non-human:
  PYTHONPATH=. python3 evaluation/rater_harness.py llm-rate --model phi4-mini

  # 3. Compute agreement + consensus gold labels over everyone collected:
  PYTHONPATH=. python3 evaluation/rater_harness.py analyze

The author's own labels (from adversarial_eval.PROMPTS) are always included as the
built-in rater `author`, so analysis is meaningful as soon as ONE more rater exists.

HONESTY NOTE
------------
An LLM rater is NOT an independent human rater — it shares failure modes with the
system under test. Include it for a cheap signal and to demo the harness, but a
publishable κ needs ≥3 *human* raters. The harness labels each rater by source so the
distinction never gets lost.
"""

import sys
import os
import json
import random
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.adversarial_eval import PROMPTS

RATINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ratings")

# The label space a rater chooses from — the 10 routable agents.
LABELS = [
    "it_networking", "python_dev", "dotnet_dev", "ai_ml", "web_dev",
    "devops", "data_analyst", "writer", "knowledge_learning", "terse",
]

# pid → prompt text, and the built-in `author` rater derived from the eval labels.
PROMPT_TEXT = {pid: text for pid, _exp, _cat, text in PROMPTS}
AUTHOR_LABELS = {pid: exp for pid, exp, _cat, _text in PROMPTS}

_KAPPA_BANDS = [
    (-1.0, "worse than chance"), (0.0, "slight"), (0.21, "fair"),
    (0.41, "moderate"), (0.61, "substantial"), (0.81, "almost perfect"),
]


def kappa_label(k: float) -> str:
    band = _KAPPA_BANDS[0][1]
    for lo, name in _KAPPA_BANDS:
        if k >= lo:
            band = name
    return band


# ---------------------------------------------------------------------------
# Agreement statistics — pure stdlib, no numpy/scipy/sklearn.
# ---------------------------------------------------------------------------
def fleiss_kappa(counts: list[list[int]]) -> float:
    """
    Fleiss' κ for N subjects × k categories of per-category rater counts.

    Handles a VARIABLE number of raters per subject (Fleiss' generalisation):
    a subject's row need not sum to the same total as another's. Subjects with
    fewer than 2 ratings are skipped (κ is undefined for them).
    """
    rows = [row for row in counts if sum(row) >= 2]
    if not rows:
        return float("nan")
    k = len(rows[0])
    total = sum(sum(row) for row in rows)

    # P_i: agreement within each subject
    p_i = []
    for row in rows:
        n_i = sum(row)
        agree = (sum(c * c for c in row) - n_i) / (n_i * (n_i - 1))
        p_i.append(agree)
    p_bar = sum(p_i) / len(p_i)

    # P_e: expected agreement from marginal category proportions
    p_j = [sum(row[j] for row in rows) / total for j in range(k)]
    p_e = sum(p * p for p in p_j)

    if p_e >= 1.0:
        return 1.0  # all raters used one category and fully agreed
    return (p_bar - p_e) / (1 - p_e)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's κ for exactly two raters over aligned nominal labels."""
    assert len(a) == len(b) and a, "need aligned non-empty rating lists"
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


# ---------------------------------------------------------------------------
# Ratings I/O
# ---------------------------------------------------------------------------
def _rating_path(rater: str) -> str:
    return os.path.join(RATINGS_DIR, f"{rater}.json")


def save_ratings(rater: str, labels: dict[str, str]) -> str:
    os.makedirs(RATINGS_DIR, exist_ok=True)
    path = _rating_path(rater)
    with open(path, "w") as f:
        json.dump(labels, f, indent=2, sort_keys=True)
    return path


def load_all_ratings() -> dict[str, dict[str, str]]:
    """Every rater file on disk, plus the built-in `author` rater. Author never
    overwrites a real rater file of the same name."""
    raters: dict[str, dict[str, str]] = {}
    if os.path.isdir(RATINGS_DIR):
        for fn in sorted(os.listdir(RATINGS_DIR)):
            if fn.endswith(".json"):
                with open(os.path.join(RATINGS_DIR, fn)) as f:
                    raters[fn[:-5]] = json.load(f)
    raters.setdefault("author", dict(AUTHOR_LABELS))
    return raters


# ---------------------------------------------------------------------------
# Blind collection
# ---------------------------------------------------------------------------
def collect(rater: str, seed: int | None = None) -> str:
    """Interactive blind labelling. Shuffled order, no existing label or system
    output shown. Writes evaluation/ratings/<rater>.json."""
    order = list(PROMPTS)
    random.Random(seed).shuffle(order)
    print(f"\nBlind rating — rater '{rater}'. Pick the ONE best specialist per prompt.")
    print("You are not shown any existing label or system answer. Ctrl-C aborts.\n")
    menu = "  ".join(f"[{i}]{name}" for i, name in enumerate(LABELS))
    labels: dict[str, str] = {}
    for n, (pid, _exp, _cat, text) in enumerate(order, 1):
        print(f"\n({n}/{len(order)})  {text}")
        print(menu)
        while True:
            raw = input("  choice #: ").strip()
            if raw.isdigit() and 0 <= int(raw) < len(LABELS):
                labels[pid] = LABELS[int(raw)]
                break
            print("  invalid — enter a number from the menu.")
    path = save_ratings(rater, labels)
    print(f"\nSaved {len(labels)} ratings → {path}")
    return path


def llm_rate(model: str | None = None) -> str:
    """Use the local model as one (clearly non-human) rater. Imports the LLM lazily
    so this module never hard-depends on a running Ollama."""
    from models.llm import llm  # lazy: only when actually rating
    rater = f"llm_{(model or os.environ.get('OLLAMA_MODEL', 'model')).split(':')[0]}"
    menu = ", ".join(LABELS)
    labels: dict[str, str] = {}
    for pid, _exp, _cat, text in PROMPTS:
        prompt = (
            "You are routing a user request to exactly one specialist agent.\n"
            f"Agents: {menu}.\n"
            f"Request: {text!r}\n"
            "Reply with ONLY the single best agent name from the list, nothing else."
        )
        resp = llm.invoke(prompt)
        out = (getattr(resp, "content", None) or str(resp)).strip().lower()
        labels[pid] = next((a for a in LABELS if a in out), "knowledge_learning")
    path = save_ratings(rater, labels)
    print(f"Saved {len(labels)} LLM ratings ({rater}) → {path}")
    return path


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def analyze(raters: dict[str, dict[str, str]] | None = None) -> dict:
    """Compute Fleiss' κ, per-item agreement, and consensus (majority) gold labels."""
    raters = raters or load_all_ratings()
    names = sorted(raters)

    counts, per_item, consensus = [], [], {}
    for pid, _exp, _cat, _text in PROMPTS:
        votes = [raters[r][pid] for r in names if pid in raters[r]]
        if not votes:
            continue
        row = [votes.count(lbl) for lbl in LABELS]
        counts.append(row)
        top = max(LABELS, key=lambda lbl: votes.count(lbl))
        agreement = votes.count(top) / len(votes)
        consensus[pid] = top
        per_item.append((pid, top, agreement, len(votes)))

    kappa = fleiss_kappa(counts) if len(names) >= 2 else float("nan")
    return {
        "raters": names,
        "kappa": kappa,
        "per_item": per_item,
        "consensus": consensus,
    }


def print_analysis(result: dict) -> None:
    names = result["raters"]
    k = result["kappa"]
    print("=" * 64)
    print("  Inter-rater agreement — adversarial routing set (#20)")
    print(f"  Raters ({len(names)}): {', '.join(names)}")
    print("=" * 64)

    if len(names) < 2:
        print("\n  Only the built-in `author` rater is present — κ needs ≥2 raters.")
        print("  Add one:  python3 evaluation/rater_harness.py collect --rater <name>")
        print("  or:       python3 evaluation/rater_harness.py llm-rate --model phi4-mini")
        return

    print(f"\n  Fleiss' κ = {k:.3f}   ({kappa_label(k)})")
    if k < 0.41:
        print("  → Below 'moderate': the routing target is NOT well-defined across raters.")
        print("    Any single accuracy number (42% or 99%) is measuring one rater's taste.")
    elif k < 0.61:
        print("  → Moderate: target is partly shared; treat per-prompt disagreements as genuine.")
    else:
        print("  → Substantial+: target is well-defined; consensus labels are defensible gold.")

    contested = sorted((a, pid, top) for pid, top, a, _n in result["per_item"])
    print("\n  Most contested prompts (lowest agreement — where raters split):")
    for agreement, pid, top in contested[:6]:
        flag = "  ← author disagrees" if AUTHOR_LABELS.get(pid) != top else ""
        print(f"    {agreement*100:5.0f}%  [{pid}] consensus={top}{flag}")
        print(f"           “{PROMPT_TEXT[pid]}”")

    # Where the author's single-rater label diverges from the crowd consensus.
    diverge = [pid for pid, top in result["consensus"].items()
               if AUTHOR_LABELS.get(pid) != top]
    print(f"\n  Author label ≠ consensus on {len(diverge)}/{len(result['consensus'])} prompts.")
    print("  Those are the labels to revisit before quoting any accuracy number.")


def write_consensus(result: dict, path: str | None = None) -> str:
    """Persist majority-vote consensus labels as candidate gold labels."""
    path = path or os.path.join(RATINGS_DIR, "consensus_gold.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "raters": result["raters"],
        "fleiss_kappa": result["kappa"],
        "labels": result["consensus"],
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Multi-rater agreement harness (#20)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="blind interactive labelling")
    c.add_argument("--rater", required=True)
    c.add_argument("--seed", type=int, default=None)
    lr = sub.add_parser("llm-rate", help="add the local model as one (non-human) rater")
    lr.add_argument("--model", default=None)
    an = sub.add_parser("analyze", help="Fleiss κ + consensus over all raters")
    an.add_argument("--write-gold", action="store_true", help="persist consensus_gold.json")
    args = ap.parse_args(argv)

    if args.cmd == "collect":
        collect(args.rater, seed=args.seed)
    elif args.cmd == "llm-rate":
        llm_rate(args.model)
    elif args.cmd == "analyze":
        result = analyze()
        print_analysis(result)
        if args.write_gold and len(result["raters"]) >= 2:
            print(f"\n  Wrote consensus gold → {write_consensus(result)}")


if __name__ == "__main__":
    main()
