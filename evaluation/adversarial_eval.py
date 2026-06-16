"""
Adversarial / held-out routing eval — the credibility counterweight to ablation_eval.

WHY THIS EXISTS
---------------
`ablation_eval.py` reports ~98% signal-only accuracy on `training.auto_train.PROMPTS`.
That number is an INTERNAL DEVELOPMENT METRIC, not a validated one: the prompts and
the routing rules were authored by the same person, so the benchmark largely measures
"can the rules recognise examples that resemble the examples used to write the rules?"
(evaluation-on-development-distribution). An external eval-methodology review flagged
this circularity — see REVIEW_FINDINGS §2 / issue #20.

This file is the honest counterweight. Its prompts are written to be HARD and to NOT
reuse the trigger keywords baked into QuerySignal:

  * cross-domain      — two plausible specialists compete; label = the primary intent
  * keyword-decoy     — contains a keyword that pulls toward the WRONG domain
  * paraphrase        — the real domain, phrased without its usual trigger words
                        (tests generalisation, not keyword memorisation)
  * terse-trap        — phrased like a one-liner ("show me the command…") but actually
                        a substantive question that should NOT collapse to `terse`

HONESTY CAVEATS (read before quoting the number)
------------------------------------------------
  * Labels here are SINGLE-RATER (the author's best call). A defensible public number
    needs ≥3 independent raters + an inter-rater agreement statistic (Cohen's/Fleiss' κ)
    to show the routing target is even well-defined. This set does not have that yet.
  * The expected accuracy here is LOWER than ablation_eval — that is the point. A lower
    number on genuinely ambiguous, keyword-free prompts is far more credible than 98%
    on prompts that echo the rules.
  * We report a Wilson 95% confidence interval, not a bare point estimate. With n this
    small the interval is wide on purpose — it is honest about what n buys you.

Run:
    PYTHONPATH=. python3 evaluation/adversarial_eval.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.ablation_eval import signal_route  # reuse the exact production fast path

# ---------------------------------------------------------------------------
# Held-out adversarial prompts.  (pid, expected_agent, category, prompt)
#
# Expected agent ∈ {it_networking, python_dev, dotnet_dev, ai_ml, web_dev,
#                   devops, data_analyst, writer, knowledge_learning, terse}
# `category` documents WHY the prompt is hard, for error analysis — not used in scoring.
#
# These prompts are deliberately NOT in training.auto_train.PROMPTS. Do not copy them
# back into the rules; that would re-introduce the circularity this set exists to expose.
# ---------------------------------------------------------------------------
PROMPTS = [
    # --- cross-domain: two specialists compete; label = primary intent ----------
    ("adv_x01", "ai_ml",         "cross-domain",
     "My training job keeps getting OOM-killed inside the container — should I shard the model or the batch?"),
    ("adv_x02", "devops",        "cross-domain",
     "I need to spin up containers to run an AI experiment overnight and tear them down after."),
    ("adv_x03", "data_analyst",  "cross-domain",
     "The feature pipeline that feeds my model is slow because of how it reads from the warehouse — where do I optimise?"),
    ("adv_x04", "dotnet_dev",    "cross-domain",
     "My C# service calls a hosted language model and the responses time out under load — how do I make the client resilient?"),
    ("adv_x05", "web_dev",       "cross-domain",
     "Users see a blank page while my model streams its answer — how do I render tokens as they arrive in the browser?"),
    ("adv_x06", "python_dev",    "cross-domain",
     "Compare the trade-offs between a Flask backend and an ASP.NET one for a small internal tool I'm writing in Python."),
    ("adv_x07", "it_networking", "cross-domain",
     "My Kubernetes pods can reach the internet but not each other — is this a CNI or a service issue?"),
    ("adv_x08", "ai_ml",         "cross-domain",
     "Should I store my embeddings in Postgres or a dedicated vector store for a 2M-document corpus?"),
    ("adv_x09", "devops",        "cross-domain",
     "Every deploy of my Django app needs a database migration to run exactly once across three replicas — how?"),
    ("adv_x10", "data_analyst",  "cross-domain",
     "I have a SQL query feeding an ML feature and the numbers look wrong — walk me through validating the aggregation."),

    # --- keyword-decoy: a trigger word pulls toward the WRONG domain ------------
    ("adv_d01", "writer",        "keyword-decoy",
     "Write a friendly onboarding email explaining our new VPN policy to non-technical staff."),
    ("adv_d02", "data_analyst",  "keyword-decoy",
     "Summarise the key trends in this quarter's churn numbers for a slide."),
    ("adv_d03", "knowledge_learning", "keyword-decoy",
     "Explain, in plain terms, why everyone keeps saying containers aren't really virtual machines."),
    ("adv_d04", "writer",        "keyword-decoy",
     "Draft release notes for a Python library update aimed at end users, not developers."),
    ("adv_d05", "knowledge_learning", "keyword-decoy",
     "What does it actually mean when people describe a model as 'overfitting'? I'm not building one, just curious."),
    ("adv_d06", "it_networking", "keyword-decoy",
     "My API is unreachable from outside the office but fine internally — start with the firewall or the routing table?"),
    ("adv_d07", "writer",        "keyword-decoy",
     "Turn these terse server error logs into a clear incident summary a manager can read."),

    # --- paraphrase: real domain, no trigger keywords --------------------------
    ("adv_p01", "it_networking", "paraphrase",
     "Two machines on the same office switch can't see each other even though both reach the gateway. Where do I look?"),
    ("adv_p02", "python_dev",    "paraphrase",
     "My script silently stops halfway through a big loop and leaves no error — how do I find what's swallowing it?"),
    ("adv_p03", "dotnet_dev",    "paraphrase",
     "An object I expected the runtime to clean up is sticking around forever and memory creeps up over days."),
    ("adv_p04", "web_dev",       "paraphrase",
     "Clicking the button twice fast submits the form twice and creates duplicate orders — how do I stop that on the page?"),
    ("adv_p05", "devops",        "paraphrase",
     "I want every push to main to build, test, and ship to staging without me touching anything."),
    ("adv_p06", "data_analyst",  "paraphrase",
     "Half my rows have blanks where a number should be and it's throwing off the averages — how should I handle them?"),
    ("adv_p07", "ai_ml",         "paraphrase",
     "My assistant keeps confidently making up facts that aren't in the documents I gave it — how do I ground it?"),
    ("adv_p08", "writer",        "paraphrase",
     "Make this paragraph less stiff and corporate without losing the meaning."),

    # --- terse-trap: looks like a one-liner, is actually substantive ------------
    ("adv_t01", "it_networking", "terse-trap",
     "Show me the command to diagnose why packets to one specific host are being dropped intermittently."),
    ("adv_t02", "devops",        "terse-trap",
     "Give me the one-liner — but also explain why my rolling deploy leaves two old pods running."),
    ("adv_t03", "python_dev",    "terse-trap",
     "Quick: why does my list comprehension allocate twice the memory of the equivalent generator, and when does it matter?"),
    ("adv_t04", "data_analyst",  "terse-trap",
     "Just tell me which join — but my left join is multiplying rows and I don't understand why."),

    # --- genuine terse: SHOULD collapse to a one-liner --------------------------
    ("adv_terse01", "terse", "terse", "what port does ssh use"),
    ("adv_terse02", "terse", "terse", "convert 17:00 UTC to PST"),
    ("adv_terse03", "terse", "terse", "what's the capital of australia"),
    ("adv_terse04", "terse", "terse", "define idempotent"),
]

assert len({p[0] for p in PROMPTS}) == len(PROMPTS), "duplicate pid in adversarial set"


def wilson_interval(correct: int, n: int, z: float = 1.96):
    """Wilson score 95% CI for a binomial proportion. Pure stdlib, no scipy."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = correct / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def run_adversarial():
    print("=" * 64)
    print("  Adversarial / held-out routing eval (signal-only, no LLM)")
    print(f"  Prompts: {len(PROMPTS)}   (SINGLE-RATER labels — see module docstring)")
    print("=" * 64)

    cat_stats: dict = {}
    correct = 0
    misses = []

    for pid, expected, category, prompt in PROMPTS:
        got = signal_route(prompt)
        ok = (got == expected)
        correct += ok
        cs = cat_stats.setdefault(category, {"correct": 0, "total": 0})
        cs["total"] += 1
        cs["correct"] += ok
        if not ok:
            misses.append((pid, category, expected, got, prompt))

    n = len(PROMPTS)
    p, lo, hi = wilson_interval(correct, n)

    print(f"\n  Accuracy: {correct}/{n} = {100*p:.1f}%")
    print(f"  Wilson 95% CI: [{100*lo:.1f}%, {100*hi:.1f}%]   (wide on purpose at n={n})")

    print("\n  By adversarial category:")
    for cat, cs in sorted(cat_stats.items()):
        c, t = cs["correct"], cs["total"]
        bar = "█" * c + "░" * (t - c)
        print(f"    {cat:14s}: {c:2d}/{t:2d}  {bar}")

    if misses:
        print("\n  Misroutes (the interesting part — read these, not the headline number):")
        for pid, cat, expected, got, prompt in misses:
            print(f"    ✗ [{pid}] ({cat}) expected={expected} got={got}")
            print(f"        “{prompt}”")

    print("\n  NOTE: this is an internal development metric. A public claim needs")
    print("  ≥3 independent raters + inter-rater κ. Do NOT quote this as validated.")
    return correct, n


if __name__ == "__main__":
    run_adversarial()
