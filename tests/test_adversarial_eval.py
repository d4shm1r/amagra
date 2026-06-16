"""
Regression guard for the held-out adversarial routing eval (issue #20).

The benchmark lives in evaluation/adversarial_eval.py. It exists to expose the
gap between curated accuracy (~99%) and accuracy on deliberately hard, keyword-free
prompts. These tests pin the harness's invariants — NOT a high score. The whole
point of the set is that signal-only routing does poorly on it; if a future change
makes it suspiciously easy, that's a sign the prompts drifted toward the rules.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.adversarial_eval import PROMPTS, wilson_interval, run_adversarial


def test_wilson_interval_matches_known_values():
    # 50/100 → centre 0.5, symmetric ~[0.404, 0.596] (textbook Wilson 95%).
    p, lo, hi = wilson_interval(50, 100)
    assert p == 0.5
    assert abs(lo - 0.404) < 0.005
    assert abs(hi - 0.596) < 0.005
    # bounds stay in [0, 1] at the extremes
    _, lo0, _ = wilson_interval(0, 10)
    assert lo0 == 0.0
    _, _, hi1 = wilson_interval(10, 10)
    assert hi1 == 1.0


def test_prompts_are_held_out_from_training():
    # The adversarial prompts must NOT leak back into the rule-authoring set,
    # or the benchmark stops measuring generalisation.
    from training.auto_train import PROMPTS as TRAIN
    train_texts = {p[3].strip().lower() for p in TRAIN}
    adv_texts = {p[3].strip().lower() for p in PROMPTS}
    assert train_texts.isdisjoint(adv_texts)


def test_labels_use_valid_agents():
    valid = {
        "it_networking", "python_dev", "dotnet_dev", "ai_ml", "web_dev",
        "devops", "data_analyst", "writer", "knowledge_learning", "terse",
    }
    assert all(p[1] in valid for p in PROMPTS)


def test_genuine_terse_prompts_still_collapse():
    # Sanity floor: the 4 genuinely-terse prompts must route to `terse`. If even
    # these break, the fast path is broken, not just under-generalising.
    correct, n = run_adversarial()
    assert n == len(PROMPTS)
    assert correct >= 4  # at minimum the genuine-terse cases land
