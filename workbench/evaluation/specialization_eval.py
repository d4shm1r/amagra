"""
specialization_eval.py — does a specialist agent actually answer better than a
generic one?

    PYTHONPATH=. python3 workbench/evaluation/specialization_eval.py --n 20
    PYTHONPATH=. python3 workbench/evaluation/specialization_eval.py            # all 91
    PYTHONPATH=. python3 workbench/evaluation/specialization_eval.py --dry-run  # wiring only

Generating and judging are separable, and for a real run they should be separated:

    ... specialization_eval.py --answers-only          # phase 1: capture, no verdicts
    ... specialization_eval.py --rate logs/spec_X.jsonl --judge qwen2.5:14b

Phase 1 is the expensive, fragile half — 91 prompts x 5 arms is 455 local
generations, and it used to hold every one of them in memory and write the file
only after the last prompt finished, so anything that died at prompt 90 threw the
lot away. Answers now stream to disk as they are produced.

Phase 2 is cheap and repeatable, which is the point: the judge is the least
trustworthy part of this harness (see SCOPE below), so re-judging the SAME answers
with a different model is how you find out whether a result is real or is just
one judge's opinion. Regenerating 455 answers to change judges is not a thing
anyone will actually do, so the harness stops asking. --rate never modifies the
answers file it reads; verdicts go to a new `_rated_` file.

WHY THIS EXISTS
---------------
Every other harness in this directory (agent_arena, ablation_eval,
semantic_route_eval, adversarial_eval, acm_rg_eval) asks the same question:

    "did the router pick the agent the label says?"

None of them asks:

    "did the pick change the answer?"

So the routing stack has been optimized for months against a proxy, while the
assumption underneath it — that routing to the right specialist produces a better
answer — has never been on the instrument. This harness puts it there.

THE ARMS
--------
Each is the SAME shipped pipeline (agents/runner.py), differing only in the spec
it is handed. That is only possible because an agent is now data.

    generic         neutral persona, no memory           <- the baseline
    persona_only    correct persona, no memory           <- persona effect, isolated
    memory_only     neutral persona, unscoped memory     <- memory effect, isolated
    specialist      correct persona + memory             <- the shipped happy path
    misrouted       WRONG persona + memory               <- the shipped failure mode

What the deltas mean:

    persona_only - generic     does the persona alone buy anything?
    memory_only  - generic     does memory alone buy anything?
    specialist   - generic     what the product actually delivers over a plain chatbot
    specialist   - misrouted   how much routing correctness is worth
    specialist   ~ memory_only if these tie, MEMORY is carrying the product and the
                               personas are decoration — and the entire routing stack
                               is machinery for a decision that does not change output

SCOPE — read this before believing the result
---------------------------------------------
1. This tests PROMPT-LEVEL specialization: a system prompt, keyword probes, and a
   memory tag. That is what Amagra's specialists actually are. A null result
   disproves *these* specialists — NOT specialization in general (different tools,
   retrieval indices, planners or verifiers per agent could still pay).
2. Single-turn. It cannot see the compounding cost of a misroute: save_to_memory()
   files the answer under the ROUTED agent, and get_memory_context() applies a
   prefer_agent boost — so a misroute mis-files memory and biases later retrieval.
   That damage accrues across sessions and is invisible here.
3. LLM-as-judge. If the judge is the same small local model being judged, treat the
   numbers as directional only. Use --judge to point at a stronger model, or rate
   the emitted JSONL by hand (that is the honest path, and rater_harness.py exists).

Memory is never written during a run: save_to_memory is stubbed out. The eval
cannot pollute the store it is measuring.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import replace
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import agents.runner as runner  # noqa: E402
from agents.spec import AgentSpec  # noqa: E402
from core.contract import Context  # noqa: E402
from workbench.evaluation.adversarial_eval import PROMPTS, wilson_interval  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, "logs")

# A deliberately neutral assistant — no domain, no persona. The control.
GENERIC_PROMPT = """
{user_profile}
You are a helpful, knowledgeable assistant. Answer the user's question directly
and accurately. Be concrete and specific. If code helps, include it."""

ARMS = ("generic", "persona_only", "memory_only", "specialist", "misrouted")


# ── the agents under test ────────────────────────────────────────────────────
def _agent_specs() -> dict[str, AgentSpec]:
    import agents.ai_ml, agents.data_analyst, agents.devops, agents.dotnet_dev  # noqa: E401
    import agents.it_networking, agents.knowledge_learning, agents.python_dev  # noqa: E401
    import agents.terse, agents.web_dev, agents.writer  # noqa: E401
    return {
        "ai_ml":              agents.ai_ml.SPEC,
        "data_analyst":       agents.data_analyst.SPEC,
        "devops":             agents.devops.SPEC,
        "dotnet_dev":         agents.dotnet_dev.SPEC,
        "it_networking":      agents.it_networking.SPEC,
        "knowledge_learning": agents.knowledge_learning.SPEC,
        "python_dev":         agents.python_dev.SPEC,
        "terse":              agents.terse.SPEC,
        "web_dev":            agents.web_dev.SPEC,
        "writer":             agents.writer.SPEC,
    }


def _misroute_to(expected: str, specs: dict[str, AgentSpec]) -> str:
    """A deterministic wrong agent: the next one alphabetically. Deterministic so a
    re-run is comparable, and never `terse` — its whole job is to answer differently,
    which would flatter the specialist arm for the wrong reason."""
    pool = sorted(a for a in specs if a not in (expected, "terse"))
    return pool[hash(expected) % len(pool)]


def _spec_for(arm: str, expected: str, specs: dict[str, AgentSpec]) -> AgentSpec:
    correct = specs[expected]
    if arm == "specialist":
        return correct
    if arm == "misrouted":
        return specs[_misroute_to(expected, specs)]
    if arm == "persona_only":
        return replace(correct, remembers=False)
    if arm == "generic":
        return AgentSpec(name="generic", prompt=GENERIC_PROMPT, remembers=False)
    if arm == "memory_only":
        # neutral persona, but memory ON — retrieval is unscoped (see _unscoped_memory)
        return AgentSpec(name="generic", prompt=GENERIC_PROMPT, remembers=True)
    raise ValueError(arm)


# ── isolation: never write to the real memory store ──────────────────────────
def _install_guards(unscoped_arms: set[str], state: dict) -> None:
    real_get = runner.get_memory_context

    def guarded_get(task: str, agent_name: str) -> str:
        # the memory_only arm must not inherit an agent's prefer_agent boost, or it
        # is not measuring "memory alone" — it is measuring memory + a routing hint.
        if state["arm"] in unscoped_arms:
            try:
                return real_get(task, None)          # prefer_agent=None → no bias
            except Exception:
                return ""
        return real_get(task, agent_name)

    runner.get_memory_context = guarded_get
    runner.save_to_memory = lambda *a, **k: None      # the eval never pollutes the store

    # after-hooks have their own side effects (knowledge_learning files a lesson to
    # disk and advances the progress json). Neutralize them too, or the eval mutates
    # real state and prints "lessons completed" mid-run.
    for name in ("save_lesson", "save_learning_progress"):
        mod = sys.modules.get("agents.knowledge_learning")
        if mod and hasattr(mod, name):
            setattr(mod, name, lambda *a, **k: "")


# ── generation ───────────────────────────────────────────────────────────────
def _answer(spec: AgentSpec, prompt: str) -> str:
    try:
        return runner.run(spec, Context(task=prompt)).output.strip()
    except Exception as e:                              # a dead arm must not kill the run
        return f"[ERROR: {type(e).__name__}: {e}]"


# ── judging ──────────────────────────────────────────────────────────────────
JUDGE_PROMPT = """You are grading two answers to the same question. Judge only which
answer better serves the person who asked: correctness first, then specificity and
actionability. Ignore length, tone, and formatting. Ignore any self-description of
expertise — grade the substance.

QUESTION:
{q}

ANSWER A:
{a}

ANSWER B:
{b}

Reply with exactly one token: A, B, or TIE."""


def _judge_once(llm, q: str, a: str, b: str) -> str:
    from langchain_core.messages import HumanMessage
    out = llm.invoke([HumanMessage(content=JUDGE_PROMPT.format(q=q, a=a, b=b))])
    verdict = (getattr(out, "content", "") or "").strip().upper()
    for token in ("TIE", "A", "B"):
        if verdict.startswith(token):
            return token
    return "TIE"


def _judge(llm, q: str, base: str, cand: str) -> str:
    """Blind pairwise, run BOTH orders. Only a verdict that survives the swap counts —
    an LLM judge has a strong position bias, and this is the cheapest way to neuter it.
    Disagreement between the two orders IS a tie: the judge cannot tell them apart."""
    first = _judge_once(llm, q, base, cand)     # base=A, cand=B
    second = _judge_once(llm, q, cand, base)    # cand=A, base=B
    if first == "B" and second == "A":
        return "cand"
    if first == "A" and second == "B":
        return "base"
    return "tie"


# ── phases ───────────────────────────────────────────────────────────────────
def _out_path(kind: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(OUT_DIR, f"specialization_{kind}{stamp}.jsonl")


def _generate(rows, specs, state, path: str) -> list[dict]:
    """Phase 1. Answers stream to `path` as they are produced — a run that dies at
    prompt 90 of 91 keeps its first 89."""
    records = []
    with open(path, "w") as f:
        for i, (pid, expected, category, prompt) in enumerate(rows, 1):
            answers = {}
            for arm in ARMS:
                state["arm"] = arm
                answers[arm] = _answer(_spec_for(arm, expected, specs), prompt)
            rec = {"id": pid, "expected": expected, "category": category,
                   "prompt": prompt, "answers": answers}
            records.append(rec)
            f.write(json.dumps(rec) + "\n")
            f.flush()
            print(f"  [{i:>3}/{len(rows)}] {pid:<8} {expected:<19} answered")
    return records


def _rate(judge, records: list[dict]) -> dict:
    """Phase 2. Judge each arm against the generic baseline. Mutates `records`
    with a `verdicts` key and returns the tally."""
    tally = {a: {"cand": 0, "base": 0, "tie": 0} for a in ARMS if a != "generic"}
    for i, rec in enumerate(records, 1):
        verdicts = {}
        for arm in tally:
            v = _judge(judge, rec["prompt"], rec["answers"]["generic"], rec["answers"][arm])
            verdicts[arm] = v
            tally[arm][v] += 1
        rec["verdicts"] = verdicts
        won = " ".join(f"{a}:{verdicts[a][0]}" for a in tally)
        print(f"  [{i:>3}/{len(records)}] {rec['id']:<8} {rec['expected']:<19} {won}")
    return tally


def _report(tally: dict, n: int) -> None:
    print("\n" + "=" * 74)
    print("  vs GENERIC BASELINE   (a win must survive an A/B order swap)")
    print("=" * 74)
    print(f"  {'arm':<14} {'wins':>5} {'ties':>5} {'loss':>5} {'net':>7}   {'95% CI on net':>18}")
    print("  " + "-" * 70)
    for arm in tally:
        w, l, t = tally[arm]["cand"], tally[arm]["base"], tally[arm]["tie"]
        net = (w - l) / max(1, n)
        # CI is on the win-rate among DECIDED pairs (ties excluded): 50% = no effect.
        _, lo, hi = wilson_interval(w, max(1, w + l))
        print(f"  {arm:<14} {w:>5} {t:>5} {l:>5} {net:>+7.1%}   "
              f"[{lo:>6.1%}, {hi:>6.1%}] win-rate")

    print("\n  How to read it:")
    print("    persona_only ≈ 0   the system prompts buy nothing")
    print("    memory_only  ≈ specialist   → MEMORY is the product; personas are decoration,")
    print("                                  and the routing stack decides nothing that matters")
    print("    specialist ≈ misrouted      → routing correctness is worth ~nothing")
    print("    (a null result disproves THESE prompt-level specialists, not specialization)")


def _load(path: str) -> list[dict]:
    with open(path) as f:
        records = [json.loads(line) for line in f if line.strip()]
    missing = [r["id"] for r in records if set(ARMS) - set(r.get("answers", {}))]
    if missing:
        raise SystemExit(f"{path}: {len(missing)} record(s) missing arms, e.g. {missing[:3]}")
    return records


def _make_judge(model_id: str):
    import models.llm as _m
    if not model_id:
        return _m.llm
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model_id, temperature=0)


# ── run ──────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="subsample N prompts (0 = all 91)")
    ap.add_argument("--judge", default="", help="judge model id (default: the app's llm)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true", help="stub the model; check wiring only")
    ap.add_argument("--answers-only", action="store_true",
                    help="phase 1 only: generate and save answers, judge nothing")
    ap.add_argument("--rate", default="",
                    help="phase 2 only: judge an existing answers .jsonl and report")
    args = ap.parse_args()

    if args.rate:
        if args.answers_only:
            raise SystemExit("--rate and --answers-only are opposite halves; pick one")
        records = _load(args.rate)
        print(f"rating {len(records)} prompts from {os.path.relpath(args.rate, ROOT)}   "
              f"judge: {args.judge or 'the app llm'}   judgements: {len(records) * 8}\n")
        tally = _rate(_make_judge(args.judge), records)
        _report(tally, len(records))
        path = _out_path("rated_")
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"\n  verdicts written to {os.path.relpath(path, ROOT)}")
        return

    random.seed(args.seed)
    specs = _agent_specs()
    rows = [p for p in PROMPTS if p[1] in specs]
    if args.n:
        rows = random.sample(rows, min(args.n, len(rows)))

    state = {"arm": ""}
    _install_guards(unscoped_arms={"memory_only"}, state=state)

    if args.dry_run:
        class _Stub:
            def invoke(self, messages):
                from langchain_core.messages import AIMessage
                return AIMessage(content="stub answer")
        runner._llm.llm = _Stub()
        judge = _Stub()
        print("DRY RUN — stubbed model, verdicts are meaningless\n")
    else:
        judge = _make_judge(args.judge)

    print(f"prompts: {len(rows)}   arms: {len(ARMS)}   "
          f"generations: {len(rows) * len(ARMS)}   "
          f"judgements: {0 if args.answers_only else len(rows) * 8}\n")

    path = _out_path("")
    records = _generate(rows, specs, state, path)
    print(f"\n  answers written to {os.path.relpath(path, ROOT)}")

    if args.answers_only:
        print("  → phase 1 done. Judge them with:")
        print(f"       --rate {os.path.relpath(path, ROOT)} --judge <model>")
        print("  → or rate them by hand. That is the honest path, and the answers "
              "are on disk now\n    precisely so a judge you do not trust cannot "
              "cost you the generation again.")
        return

    print()
    tally = _rate(judge, records)
    _report(tally, len(rows))

    rated = _out_path("rated_")
    with open(rated, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"\n  verdicts written to {os.path.relpath(rated, ROOT)}")
    print("  → rate them by hand before you trust an LLM judge that grades its own output.")


if __name__ == "__main__":
    main()
