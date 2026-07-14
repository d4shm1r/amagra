"""
Regression guard for the multi-rater agreement harness (issue #20).

Pins the statistics (verified against textbook values) and the harness logic.
The κ implementations are the load-bearing part — if they drift, every credibility
claim built on consensus labels drifts with them.
"""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workbench.evaluation.rater_harness import (
    fleiss_kappa, cohen_kappa, kappa_label, analyze, LABELS, AUTHOR_LABELS,
)
from workbench.evaluation.adversarial_eval import PROMPTS


def test_fleiss_kappa_wikipedia_example():
    # Canonical Fleiss (1971) worked example, 10 subjects × 5 categories, 14 raters
    # each. Wikipedia reports κ ≈ 0.210.
    counts = [
        [0, 0, 0, 0, 14],
        [0, 2, 6, 4, 2],
        [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0],
        [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0],
        [2, 5, 3, 2, 2],
        [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ]
    assert abs(fleiss_kappa(counts) - 0.210) < 0.01


def test_fleiss_perfect_agreement_is_one():
    # Every rater agrees on each subject (but subjects differ) → κ = 1.0.
    counts = [[5, 0, 0], [0, 5, 0], [0, 0, 5], [5, 0, 0]]
    assert abs(fleiss_kappa(counts) - 1.0) < 1e-9


def test_fleiss_handles_variable_raters_per_subject():
    # Rows summing to different totals must not raise (Fleiss generalisation).
    counts = [[3, 0], [1, 1], [0, 4]]
    k = fleiss_kappa(counts)
    assert not math.isnan(k)


def test_cohen_kappa_hand_computed():
    # a=[1,1,0,0] b=[1,0,0,0]: po=.75, pe=.5 → κ=.5
    assert abs(cohen_kappa(["1", "1", "0", "0"], ["1", "0", "0", "0"]) - 0.5) < 1e-9


def test_cohen_kappa_perfect_and_band():
    assert cohen_kappa(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert kappa_label(0.05) == "slight"
    assert kappa_label(0.7) == "substantial"
    assert kappa_label(0.95) == "almost perfect"


def test_analyze_single_author_rater_degrades_gracefully():
    # With only the built-in author rater, κ is undefined (NaN) but consensus
    # still equals the author labels and nothing raises.
    result = analyze({"author": dict(AUTHOR_LABELS)})
    assert result["raters"] == ["author"]
    assert math.isnan(result["kappa"])
    assert result["consensus"] == AUTHOR_LABELS


def test_analyze_two_raters_full_agreement():
    # A second rater identical to author → perfect agreement, κ = 1.0.
    result = analyze({"author": dict(AUTHOR_LABELS), "clone": dict(AUTHOR_LABELS)})
    assert abs(result["kappa"] - 1.0) < 1e-9
    assert all(a == 1.0 for _pid, _top, a, _n in result["per_item"])


def test_consensus_is_majority_vote():
    # Two raters say python_dev, one says terse → consensus python_dev.
    pid = PROMPTS[0][0]
    r = {
        "a": {pid: "python_dev"},
        "b": {pid: "python_dev"},
        "c": {pid: "terse"},
    }
    result = analyze(r)
    assert result["consensus"][pid] == "python_dev"


def test_author_labels_are_in_label_space():
    assert set(AUTHOR_LABELS.values()) <= set(LABELS)
