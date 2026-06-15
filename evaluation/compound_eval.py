"""
Compound-query detection benchmark (GitHub issue #11).

core_brain._detect_complexity flags a query as "compound" when it spans ≥2 core
domains or matches a COMPOUND_SIGNALS connective. Compound queries take the deep
pipeline (slow LLM path), so a FALSE POSITIVE — a simple query wrongly flagged
compound — needlessly burns latency. This benchmark measures precision/recall of
the "compound" label against a curated labeled set, with the false-positive rate
broken out, so the threshold/signal list can be tuned with evidence rather than
guesswork.

No LLM, no I/O — runs in well under a second.

Run:
    PYTHONPATH=. python3 evaluation/compound_eval.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.core_brain import _detect_domains, _detect_complexity


# ── Labeled dataset ───────────────────────────────────────────
# (query, is_compound). Curated to stress the two compound triggers (multi-domain
# and connectives) AND the simple cases most likely to false-positive: single
# queries that merely *contain* a connective-like word ("and", "then", "also")
# without being genuinely multi-task.
LABELED = [
    # ── Genuinely compound: multi-domain ──────────────────────
    ("Set up nginx and then write a Python script to monitor it", True),
    ("Configure the firewall, then deploy the Blazor app", True),
    ("Build a REST API in Python and document the endpoints", True),
    ("Train a classifier and then expose it behind a Flask route", True),
    ("Fix my DNS and also explain how DHCP leases work", True),
    ("Write a SQL query and a Python function to run it", True),
    # ── Genuinely compound: explicit connectives ──────────────
    ("First restart the service, then check the logs", True),
    ("Install the package, followed by running the migration", True),
    ("Do this step by step: clone, build, and deploy", True),
    ("Set the env var and after that restart the container", True),
    ("Both lint and test the code before committing", True),
    ("There are multiple steps to configure the VPN", True),
    # ── Simple: single domain, no real second task ────────────
    ("How do I configure nginx as a reverse proxy?", False),
    ("Write a Python function to reverse a string", False),
    ("Explain how DNS resolution works", False),
    ("Debug this .NET null reference exception", False),
    ("What is gradient descent?", False),
    ("Restart the docker container", False),
    ("Show me my open ports", False),
    ("Summarize this article", False),
    # ── Simple but connective-shaped (false-positive bait) ────
    ("Explain the pros and cons of TCP", False),
    ("What's the difference between threads and processes?", False),
    ("How do salt and pepper noise affect images?", False),
    ("Show me a list of dos and don'ts for passwords", False),
    ("Explain command and control in security", False),
    ("Is Python faster than Go and why?", False),
    # ── Ambiguous / terse (non-compound) ──────────────────────
    ("ping google", False),
    ("vlan setup", False),
    ("hello", False),
]


def is_compound(query: str) -> bool:
    return _detect_complexity(query, _detect_domains(query)) == "compound"


def evaluate(dataset=LABELED) -> dict:
    tp = fp = tn = fn = 0
    false_positives, false_negatives = [], []
    for query, label in dataset:
        pred = is_compound(query)
        if pred and label:
            tp += 1
        elif pred and not label:
            fp += 1
            false_positives.append(query)
        elif not pred and not label:
            tn += 1
        else:
            fn += 1
            false_negatives.append(query)

    pos = tp + fn          # actual compound
    neg = tn + fp          # actual simple
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall    = tp / pos if pos else 1.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) else 0.0)
    fpr       = fp / neg if neg else 0.0
    accuracy  = (tp + tn) / len(dataset) if dataset else 0.0

    return {
        "n": len(dataset),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "false_positive_rate": round(fpr, 3),
        "accuracy": round(accuracy, 3),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def _print_report(r: dict) -> None:
    print("=" * 56)
    print("  Compound-query detection benchmark")
    print(f"  Dataset: {r['n']} queries")
    print("=" * 56)
    print(f"\n  Confusion:  TP={r['tp']}  FP={r['fp']}  TN={r['tn']}  FN={r['fn']}")
    print(f"  Precision           : {r['precision']:.3f}")
    print(f"  Recall              : {r['recall']:.3f}")
    print(f"  F1                  : {r['f1']:.3f}")
    print(f"  Accuracy            : {r['accuracy']:.3f}")
    print(f"  False-positive rate : {r['false_positive_rate']:.3f}  "
          "(simple queries wrongly sent to the deep pipeline)")
    if r["false_positives"]:
        print("\n  ⚠ False positives (over-routed to deep pipeline):")
        for q in r["false_positives"]:
            print(f"    • {q}")
    if r["false_negatives"]:
        print("\n  ⚠ False negatives (compound missed → single agent):")
        for q in r["false_negatives"]:
            print(f"    • {q}")
    print()


if __name__ == "__main__":
    report = evaluate()
    _print_report(report)
    # Non-zero exit if the false-positive rate regresses past the current budget,
    # so this can gate CI when wired in.
    sys.exit(1 if report["false_positive_rate"] > 0.20 else 0)
