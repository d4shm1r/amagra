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

from workbench.evaluation.ablation_eval import hybrid_route  # production-faithful: keyword baseline + semantic rescue (flag-gated)

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

    # ═══════════════════════════════════════════════════════════════════════════
    # EXTENDED SET v2 (2026-07-03) — scales n from 33 → ~150 so the accuracy
    # figure and, more importantly, the per-category and CONFUSION-MATRIX
    # structure are statistically legible. Same discipline as above: keyword-free,
    # held-out, single-rater labels. Written to over-sample `paraphrase` because
    # that is where the v1 run revealed the `knowledge_learning` attractor sink.
    # ═══════════════════════════════════════════════════════════════════════════

    # --- paraphrase :: it_networking (connectivity, no "network/DNS/firewall") ---
    ("adv_p10", "it_networking", "paraphrase",
     "Devices on the ground floor reach the server fine but the floor above drops out at random times of day."),
    ("adv_p11", "it_networking", "paraphrase",
     "After we swapped the office box by the door, laptops load email but can't open the shared drive."),
    ("adv_p12", "it_networking", "paraphrase",
     "A colleague in the next building opens our internal site instantly; for me it spins half a minute then loads."),
    ("adv_p13", "it_networking", "paraphrase",
     "Copying a large file between two machines crawls, but only while a third is running its backup."),
    ("adv_p14", "it_networking", "paraphrase",
     "Some websites resolve to the wrong address on my laptop until I reboot, then they're fine for a while."),

    # --- paraphrase :: python_dev ----------------------------------------------
    ("adv_p20", "python_dev", "paraphrase",
     "My loop that reads a giant file eats all the memory and the machine freezes before it finishes."),
    ("adv_p21", "python_dev", "paraphrase",
     "A routine works on its own but returns stale results the moment several callers hit it at once."),
    ("adv_p22", "python_dev", "paraphrase",
     "The bit that interprets timestamps is right on my laptop and wrong on the server for the same input."),
    ("adv_p23", "python_dev", "paraphrase",
     "My long-running worker slowly holds onto open files until it can't open any more and dies."),
    ("adv_p24", "python_dev", "paraphrase",
     "Importing one of my own modules quietly runs code I didn't expect and changes a global value."),

    # --- paraphrase :: dotnet_dev ----------------------------------------------
    ("adv_p30", "dotnet_dev", "paraphrase",
     "My background processor on the server quietly stops after a few hours with nothing in the log."),
    ("adv_p31", "dotnet_dev", "paraphrase",
     "A value I set while handling one request bleeds into the next person's request on the same box."),
    ("adv_p32", "dotnet_dev", "paraphrase",
     "The service keeps grabbing database connections and never gives them back until the pool runs dry."),
    ("adv_p33", "dotnet_dev", "paraphrase",
     "An object I assumed the runtime would reclaim hangs around for days and memory keeps creeping up."),

    # --- paraphrase :: ai_ml ---------------------------------------------------
    ("adv_p40", "ai_ml", "paraphrase",
     "My assistant nails the examples I showed it and falls apart on anything even slightly different."),
    ("adv_p41", "ai_ml", "paraphrase",
     "It gives a different answer every time to the exact same question and I need it to be stable."),
    ("adv_p42", "ai_ml", "paraphrase",
     "The right document comes back from the lookup but the final answer still ignores what's in it."),
    ("adv_p43", "ai_ml", "paraphrase",
     "It scores almost perfectly on my held-back examples and is useless the moment real users arrive."),

    # --- paraphrase :: web_dev -------------------------------------------------
    ("adv_p50", "web_dev", "paraphrase",
     "The layout is perfect on my monitor and spills off the side of a phone screen."),
    ("adv_p51", "web_dev", "paraphrase",
     "A returning visitor keeps seeing yesterday's prices until they force a full reload."),
    ("adv_p52", "web_dev", "paraphrase",
     "Two people editing the same form at once silently overwrite each other's changes."),
    ("adv_p53", "web_dev", "paraphrase",
     "The little spinner never goes away even though the data clearly arrived and shows underneath it."),

    # --- paraphrase :: devops --------------------------------------------------
    ("adv_p60", "devops", "paraphrase",
     "I want a bad release to undo itself the moment error rates start climbing, with no one watching."),
    ("adv_p61", "devops", "paraphrase",
     "Our nightly job occasionally fires twice and mails everyone duplicate reports."),
    ("adv_p62", "devops", "paraphrase",
     "Every engineer sets the project up a little differently and it breaks on somebody's laptop each time."),

    # --- paraphrase :: data_analyst --------------------------------------------
    ("adv_p70", "data_analyst", "paraphrase",
     "My monthly totals disagree with finance's and I can't find where the two versions diverge."),
    ("adv_p71", "data_analyst", "paraphrase",
     "A handful of impossible values I didn't notice are dragging my averages way off."),
    ("adv_p72", "data_analyst", "paraphrase",
     "Combining two exports somehow doubled my customer count and I don't see why."),

    # --- paraphrase :: writer --------------------------------------------------
    ("adv_p80", "writer", "paraphrase",
     "This apology to customers reads cold and robotic; make it sound like a person wrote it."),
    ("adv_p81", "writer", "paraphrase",
     "Tighten this rambling three-paragraph update into something an executive will actually finish."),
    ("adv_p82", "writer", "paraphrase",
     "Rework this rejection so it stays honest without leaving the reader feeling crushed."),

    # --- paraphrase :: knowledge_learning (genuinely conceptual) ---------------
    ("adv_p90", "knowledge_learning", "paraphrase",
     "In plain terms, what's the real difference between a queue and a stream, and when do I reach for each?"),
    ("adv_p91", "knowledge_learning", "paraphrase",
     "Help me understand why adding a tenth and two tenths on a computer doesn't come out to exactly three tenths."),
    ("adv_p92", "knowledge_learning", "paraphrase",
     "Why do people insist you should never keep passwords the obvious way, even scrambled?"),

    # --- cross-domain (two specialists compete; label = primary intent) --------
    ("adv_x11", "ai_ml", "cross-domain",
     "My model server falls over under load — is the fix a bigger box, or batching the requests it gets?"),
    ("adv_x12", "web_dev", "cross-domain",
     "The dashboard is slow, and I can't tell if it's the query behind it or how the page fetches and paints."),
    ("adv_x13", "python_dev", "cross-domain",
     "My data-cleaning script is correct but takes an hour; where's the time actually going in the code?"),
    ("adv_x14", "devops", "cross-domain",
     "I need my test database to come up fresh for every branch's pipeline and vanish when it's done."),
    ("adv_x15", "it_networking", "cross-domain",
     "The app's fine locally but times out in the cloud — do I chase the code or how the boxes talk to each other?"),
    ("adv_x16", "data_analyst", "cross-domain",
     "The report and the raw export disagree on revenue; is my chart lying or is the underlying number wrong?"),
    ("adv_x17", "dotnet_dev", "cross-domain",
     "My C# API is fast in isolation and slow behind the load balancer — client code or the deployment?"),

    # --- keyword-decoy (a trigger word pulls toward the WRONG domain) ----------
    ("adv_d10", "writer", "keyword-decoy",
     "Draft a calm status-page notice about our database outage that a nervous customer can read without panicking."),
    ("adv_d11", "knowledge_learning", "keyword-decoy",
     "I'm not deploying anything — just explain what people mean when they say a system is 'eventually consistent'."),
    ("adv_d12", "writer", "keyword-decoy",
     "Write the changelog entry for a networking bugfix in language a salesperson could repeat to a client."),
    ("adv_d13", "data_analyst", "keyword-decoy",
     "Forget the model for a second — I just need the average order value trend broken out by region."),
    ("adv_d14", "knowledge_learning", "keyword-decoy",
     "Curiosity question, not a project: why is hashing not the same thing as encrypting?"),
    ("adv_d15", "writer", "keyword-decoy",
     "Rewrite this Python tutorial intro so a complete beginner isn't scared off by the jargon."),
    ("adv_d16", "it_networking", "keyword-decoy",
     "My git pushes hang halfway, but only from the office — is this really a version-control problem or the connection?"),

    # --- terse-trap (looks like a one-liner, is actually substantive) ----------
    ("adv_t10", "python_dev", "terse-trap",
     "Quick one: why is my recursive function fine for small inputs and blowing the stack at scale?"),
    ("adv_t11", "it_networking", "terse-trap",
     "Just the command — but also why do pings to one host succeed while a trace to it dies partway?"),
    ("adv_t12", "data_analyst", "terse-trap",
     "One line if you can, but explain why my grouped average changes when I add a filter that shouldn't touch it."),
    ("adv_t13", "devops", "terse-trap",
     "Give me the flag, and tell me why my container works locally but exits immediately in the pipeline."),
    ("adv_t14", "web_dev", "terse-trap",
     "Short answer plus reason: why does my fetch work in dev and get blocked in production?"),

    # --- genuine terse (extra) — SHOULD collapse to a one-liner -----------------
    ("adv_terse10", "terse", "terse", "what port does postgres use"),
    ("adv_terse11", "terse", "terse", "how many bytes in a kilobyte"),
    ("adv_terse12", "terse", "terse", "what's 15% of 240"),
    ("adv_terse13", "terse", "terse", "expand the acronym RAID"),
    ("adv_terse14", "terse", "terse", "what year did python 3 release"),
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
        got = hybrid_route(prompt)
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

    # --- attractor analysis: where do misroutes LAND? --------------------------
    # v1 revealed that keyword-free prompts collapse into `knowledge_learning`.
    # Quantify that sink so the fix can be measured, not eyeballed.
    got_hist: dict = {}
    sink_by_cat: dict = {}
    for pid, cat, expected, got, prompt in misses:
        got_hist[got] = got_hist.get(got, 0) + 1
        if got == "knowledge_learning":
            sink_by_cat[cat] = sink_by_cat.get(cat, 0) + 1

    if got_hist:
        total_miss = len(misses)
        print("\n  Misroute attractors (what wrong bucket they fall INTO):")
        for got, cnt in sorted(got_hist.items(), key=lambda kv: -kv[1]):
            share = 100 * cnt / total_miss
            bar = "█" * round(share / 5)
            flag = "  ← SINK" if got == "knowledge_learning" else ""
            print(f"    {got:20s}: {cnt:2d}/{total_miss}  {share:4.0f}%  {bar}{flag}")

        kl = got_hist.get("knowledge_learning", 0)
        print(f"\n  knowledge_learning sink: {kl}/{total_miss} of all misroutes "
              f"({100*kl/total_miss:.0f}%) land there.")
        if sink_by_cat:
            parts = ", ".join(f"{c}={n}" for c, n in sorted(sink_by_cat.items(), key=lambda kv: -kv[1]))
            print(f"    by category: {parts}")

    # --- confusion matrix (expected rows × got cols) ---------------------------
    labels = sorted({p[1] for p in PROMPTS} | {hybrid_route(p[3]) for p in PROMPTS})
    conf: dict = {e: {g: 0 for g in labels} for e in labels}
    for pid, expected, category, prompt in PROMPTS:
        conf[expected][hybrid_route(prompt)] += 1
    _bold = (lambda s: f"\033[1m{s}\033[0m") if sys.stdout.isatty() else (lambda s: s)
    short = {lab: lab[:4] for lab in labels}
    print("\n  Confusion matrix  (row = expected, col = routed-to; diagonal = correct):")
    header = "        " + "".join(f"{short[g]:>5s}" for g in labels)
    print(header)
    for e in labels:
        row_total = sum(conf[e].values())
        if row_total == 0:
            continue
        cells = "".join(
            (f"  {_bold(f'{conf[e][g]:2d}')} " if g == e and conf[e][g]
             else f"  {conf[e][g]:2d} " if conf[e][g] else "   . ")
            for g in labels
        )
        print(f"  {short[e]:>5s}{cells}  ({conf[e][e]}/{row_total})")

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
