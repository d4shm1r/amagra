"""
Regression guard for the compound-query detection benchmark (issue #11).

The benchmark itself lives in evaluation/compound_eval.py. These tests pin the
metric the issue cares about — the false-positive rate (simple queries wrongly
sent to the deep pipeline) — so a future change to COMPOUND_SIGNALS or the
domain threshold can't silently regress it.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workbench.evaluation.compound_eval import evaluate, is_compound


def test_false_positive_rate_within_budget():
    r = evaluate()
    # Over-routing simple queries is the regression we are guarding against.
    assert r["false_positive_rate"] <= 0.20, r["false_positives"]


def test_clear_multidomain_is_compound():
    assert is_compound("Set up nginx and then write a Python script to monitor it")


def test_connective_shaped_simple_not_compound():
    # "and"/"then" inside a single-task query must not trip the detector.
    assert not is_compound("Explain the pros and cons of TCP")
    assert not is_compound("What's the difference between threads and processes?")


def test_metrics_are_complete():
    r = evaluate()
    for key in ("precision", "recall", "f1", "false_positive_rate", "accuracy"):
        assert key in r and 0.0 <= r[key] <= 1.0
