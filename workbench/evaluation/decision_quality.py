"""
decision_quality.py — Amagra Decision Quality Benchmark (ADB)

The composite the routing/calibration/ablation evals never assembled: it scores
a *decision*, not just an answer. For every prompt it asks the seven questions
that match Amagra's actual pitch — did the orchestrator make good choices along
the way — and reports one per-dimension scorecard plus a composite.

    1. routing_correct        did it pick the right route?
    2. confidence_calibrated  was the confidence signal honest for THIS example?
    3. efficient              could the same correct result have been reached cheaper?
    4. reflection_necessary   was reflection used only when it earned its cost?
    5. memory_useful          was memory used when (and only when) it helped?
    6. correct_tool           was the right tool (or no tool) chosen?
    7. correct_final_answer   was the final answer correct?

Honesty over completeness — the whole point of this benchmark.
Dimensions 1-3 are graded deterministically today from the gold-labeled arena
substrate (zero LLM calls, < 2s). Dimensions 4-7 need per-run execution
telemetry joined to gold annotations that the full-pipeline harness does not yet
emit; they are first-class slots on DecisionRecord and report as PENDING with an
explicit coverage line rather than being faked. When the full-pipeline harness
lands, populate those fields and the same scorer grades them with no changes.

Usage
─────
  python3 -m workbench.evaluation.decision_quality                 # signal_only, core prompts
  python3 -m workbench.evaluation.decision_quality --strategy hybrid
  python3 -m workbench.evaluation.decision_quality --prompts all   # core + extra
  python3 -m workbench.evaluation.decision_quality --worst 15      # show worst decisions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workbench.auto_train import PROMPTS
from workbench.evaluation.agent_arena import (
    EXTRA_PROMPTS,
    _LATENCY_MS,
    _STRATEGIES,
    run_arena,
)

_LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_LOGS_DIR, exist_ok=True)

# Confidence below which "wrong" is forgiven as appropriately-uncertain, and at
# or above which a correct answer counts as confidently-right. Mirrors the
# [0.30, 1.00] confidence band used by decision.weights.to_confidence.
CONF_MID = 0.50

# Efficiency counts an alternative as "cheaper" only when the saving is material,
# not sub-millisecond noise between equally-cheap deterministic routes. An
# alternative must be BOTH at most half the chosen route's cost AND absolutely
# cheaper by this many ms. With the no-LLM latency table (0.3-0.6ms) nothing
# clears this bar — efficiency is only discriminating once the LLM tier
# (~18000ms) is a candidate route. See the degenerate-substrate note in output.
MATERIAL_SAVING_RATIO = 0.50
MATERIAL_SAVING_MS = 1.0


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"  # dimension not yet observable — never scored, never faked

    @property
    def graded(self) -> bool:
        return self is not Verdict.PENDING


# The seven canonical decision dimensions, in report order.
DIMENSIONS = [
    "routing_correct",
    "confidence_calibrated",
    "efficient",
    "reflection_necessary",
    "memory_useful",
    "correct_tool",
    "correct_final_answer",
]

# Dimensions with no observable data source yet. Kept as data (not hardcoded in
# the scorer) so a future full-pipeline builder promotes them by simply filling
# the fields — the scorer needs no edit.
_PENDING_DIMENSIONS = frozenset({
    "reflection_necessary",
    "memory_useful",
    "correct_tool",
    "correct_final_answer",
})


@dataclass
class DecisionRecord:
    """One decision under test. Fields for all seven dimensions; the ones a data
    source cannot observe stay None and grade as PENDING."""
    prompt_id: str
    domain: str
    prompt: str

    # Routing
    expected_agent: str
    chosen_agent: str

    # Calibration
    confidence: float | None = None

    # Efficiency — latency of the chosen route, and the cheapest latency among
    # all strategies that answered THIS example correctly (None if none did).
    chosen_latency_ms: float | None = None
    cheapest_correct_latency_ms: float | None = None

    # Slots for the pending tier (populated by the full-pipeline harness).
    reflection_used: bool | None = None
    reflection_helped: bool | None = None
    memory_used: bool | None = None
    memory_helped: bool | None = None
    tool_chosen: str | None = None
    tool_expected: str | None = None
    answer_correct: bool | None = None

    def grade(self) -> dict[str, Verdict]:
        return {
            "routing_correct":       self._routing(),
            "confidence_calibrated": self._calibration(),
            "efficient":             self._efficient(),
            "reflection_necessary":  self._reflection(),
            "memory_useful":         self._memory(),
            "correct_tool":          self._tool(),
            "correct_final_answer":  self._answer(),
        }

    # ── graded-today tier ─────────────────────────────────────────
    def _routing(self) -> Verdict:
        return Verdict.PASS if self.chosen_agent == self.expected_agent else Verdict.FAIL

    def _calibration(self) -> Verdict:
        """Per-example calibration. The only true failure is confident-and-wrong
        (overconfidence — the dangerous case). Being unsure and wrong, or right
        at any confidence, is honest signalling."""
        if self.confidence is None:
            return Verdict.PENDING
        correct = self.chosen_agent == self.expected_agent
        overconfident = (not correct) and self.confidence >= CONF_MID
        return Verdict.FAIL if overconfident else Verdict.PASS

    def _efficient(self) -> Verdict:
        """Could the same correct result have been reached more cheaply? FAIL when
        another strategy answered this example correctly at strictly lower cost
        than the chosen route. If the route was wrong or was already the cheapest
        correct option, there is nothing cheaper to prefer → PASS."""
        if self.chosen_latency_ms is None or self.cheapest_correct_latency_ms is None:
            return Verdict.PASS
        if self.chosen_agent != self.expected_agent:
            return Verdict.PASS  # efficiency is moot when the route is wrong
        cheaper = self.cheapest_correct_latency_ms
        saving = self.chosen_latency_ms - cheaper
        material = (cheaper <= self.chosen_latency_ms * MATERIAL_SAVING_RATIO
                    and saving >= MATERIAL_SAVING_MS)
        return Verdict.FAIL if material else Verdict.PASS

    # ── pending tier — observable only via the full-pipeline harness ──
    def _reflection(self) -> Verdict:
        """Reflection earned its cost iff it ran AND improved the answer, or was
        skipped AND the answer was still right. Missing sub-signals stay PENDING
        rather than being scored on a guess."""
        if self.reflection_used is None:
            return Verdict.PENDING
        if self.reflection_used:
            if self.reflection_helped is None:
                return Verdict.PENDING
            return Verdict.PASS if self.reflection_helped else Verdict.FAIL
        if self.answer_correct is None:
            return Verdict.PENDING
        return Verdict.PASS if self.answer_correct else Verdict.FAIL

    def _memory(self) -> Verdict:
        """Using memory is good only when it helped; not using it is fine. When
        memory was used but 'helped' is unobserved, stay PENDING — don't fail it
        on a missing signal."""
        if self.memory_used is None:
            return Verdict.PENDING
        if self.memory_used:
            if self.memory_helped is None:
                return Verdict.PENDING
            return Verdict.PASS if self.memory_helped else Verdict.FAIL
        return Verdict.PASS

    def _tool(self) -> Verdict:
        if self.tool_chosen is None or self.tool_expected is None:
            return Verdict.PENDING
        return Verdict.PASS if self.tool_chosen == self.tool_expected else Verdict.FAIL

    def _answer(self) -> Verdict:
        if self.answer_correct is None:
            return Verdict.PENDING
        return Verdict.PASS if self.answer_correct else Verdict.FAIL


# ── Building records from the arena substrate ─────────────────────

def records_from_arena(prompts: list[tuple], strategy: str) -> list[DecisionRecord]:
    """Run every strategy once (cheap, no LLM), then build one DecisionRecord per
    prompt for the strategy under test. Efficiency needs the cross-strategy view,
    so we score all strategies and keep the cheapest correct latency per prompt."""
    all_strategies = list(_STRATEGIES.keys())
    results = run_arena(prompts, all_strategies, quiet=True)

    # Index rows by (strategy, prompt_id) for O(1) lookup.
    by_key: dict[tuple[str, str], dict] = {}
    for s in all_strategies:
        for row in results[s]["rows"]:
            by_key[(s, row["prompt_id"])] = row

    records: list[DecisionRecord] = []
    for pid, expected, domain, prompt in prompts:
        chosen_row = by_key[(strategy, pid)]

        # Cheapest latency among strategies that got THIS example right.
        cheapest = None
        for s in all_strategies:
            row = by_key[(s, pid)]
            if row["correct"]:
                lat = _LATENCY_MS.get(s, 0.5)
                cheapest = lat if cheapest is None else min(cheapest, lat)

        records.append(DecisionRecord(
            prompt_id=pid,
            domain=domain,
            prompt=prompt,
            expected_agent=expected,
            chosen_agent=chosen_row["chosen_agent"],
            confidence=chosen_row["signal_conf"],
            chosen_latency_ms=_LATENCY_MS.get(strategy, 0.5),
            cheapest_correct_latency_ms=cheapest,
        ))
    return records


# ── Pending tier: gold annotations + observed telemetry ───────────
#
# Dimensions 4-7 need two inputs the arena substrate cannot provide: what SHOULD
# have happened (gold) and what DID happen at run time (observation). Both flow
# through one neutral schema so any run source — the coordinator result dict, the
# run_log meta subset, or a captured observations file — feeds the same grader.
#
# Observation schema (all keys optional; absent → the dependent dim stays PENDING):
#   chosen_agent, confidence, reflection_used, reflection_helped,
#   memory_used, memory_helped, response_quality, response_text
#
# Gold schema per prompt_id: {"tool": <expected agent/tool>, "answer": <str|"rubric">}

# A rubric answer counts correct when observed response_quality clears this bar.
GOOD_QUALITY = 0.60


def load_gold(path: str) -> dict[str, dict]:
    with open(path) as f:
        raw = json.load(f)
    # Underscore-prefixed keys (e.g. _readme) are documentation, not prompts.
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def observation_from_meta(meta: dict) -> dict:
    """Map a full-pipeline meta/result dict to the neutral observation schema.

    Works for both the rich coordinator result (reflect_delta, response_quality,
    memory_*) and the leaner run_log meta (agent, signal_conf). Every field that
    is not present stays None — the grader turns that into PENDING, never a guess.
    """
    obs: dict = {}
    obs["chosen_agent"] = meta.get("agent")
    obs["confidence"] = meta.get("confidence", meta.get("signal_conf"))

    # Reflection: prefer explicit level, fall back to derived signals.
    reflected: bool | None = None
    if "reflect_level" in meta:
        reflected = meta["reflect_level"] in ("light", "full")
    elif "reflected" in meta:
        reflected = bool(meta["reflected"])
    elif "reflect_delta" in meta or meta.get("response_kept") == "reflection_rewrite":
        reflected = True
    obs["reflection_used"] = reflected
    delta = meta.get("reflect_delta")
    obs["reflection_helped"] = (delta > 0) if isinstance(delta, (int, float)) else None

    # Memory: any of the memory-provenance keys signals use.
    mem: bool | None = None
    for k in ("memory_used", "memory_id", "memory", "memory_mirrored"):
        if k in meta:
            mem = bool(meta[k])
            if mem:
                break
    obs["memory_used"] = mem
    obs["memory_helped"] = meta.get("memory_helped")

    obs["response_quality"] = meta.get("response_quality")
    obs["response_text"] = meta.get("output") or meta.get("result")
    return obs


def _judge_answer(gold_answer: str, obs: dict) -> bool | None:
    """Rubric answers grade on observed quality; concrete answers on substring
    match against the response text. Returns None when the needed signal is
    absent so the dimension stays PENDING."""
    if gold_answer == "rubric":
        q = obs.get("response_quality")
        return (q >= GOOD_QUALITY) if isinstance(q, (int, float)) else None
    text = obs.get("response_text")
    if not text:
        return None
    return gold_answer.lower() in text.lower()


def apply_annotations(records: list[DecisionRecord],
                      gold: dict[str, dict],
                      observations: dict[str, dict]) -> int:
    """Fill the pending-tier fields on records where BOTH gold and an observation
    exist for the prompt. Returns how many records were joined. Records missing
    either input are left untouched (their dims 4-7 stay PENDING)."""
    joined = 0
    for rec in records:
        g = gold.get(rec.prompt_id)
        o = observations.get(rec.prompt_id)
        if not g or not o:
            continue
        joined += 1
        # When a live observation exists, ALL dims must describe the same (live)
        # decision — otherwise routing_correct grades the arena substrate while
        # correct_tool grades the live run, and they disagree. Overwrite the
        # routing fields with what the live pipeline actually did.
        if o.get("chosen_agent") is not None:
            rec.chosen_agent = o["chosen_agent"]
        if o.get("confidence") is not None:
            rec.confidence = o["confidence"]
        rec.reflection_used = o.get("reflection_used")
        rec.reflection_helped = o.get("reflection_helped")
        rec.memory_used = o.get("memory_used")
        rec.memory_helped = o.get("memory_helped")
        if g.get("tool") is not None and o.get("chosen_agent") is not None:
            rec.tool_expected = g["tool"]
            rec.tool_chosen = o["chosen_agent"]
        if g.get("answer") is not None:
            rec.answer_correct = _judge_answer(g["answer"], o)
    return joined


def load_runlog_observations(prompts: list[tuple],
                             db_path: str | None = None) -> dict[str, dict]:
    """Join run_log rows to the prompt set by exact task text (last run wins).
    Only recovers what the log persists today — reflection/memory keys are absent
    from run_log meta, so those stay None until the pipeline logs them."""
    import sqlite3
    try:
        from core.run_log import _default_path
        path = db_path or _default_path()
    except Exception:
        path = db_path
    if not path or not os.path.exists(path):
        return {}
    text_to_pid = {(p[3] or "").strip(): p[0] for p in prompts}
    obs: dict[str, dict] = {}
    con = sqlite3.connect(path)
    try:
        for task, output, meta_json in con.execute(
            "SELECT task, output, meta FROM runs ORDER BY id"
        ):
            pid = text_to_pid.get((task or "").strip())
            if not pid:
                continue
            try:
                meta = json.loads(meta_json) if meta_json else {}
            except (ValueError, TypeError):
                meta = {}
            meta.setdefault("output", output)
            obs[pid] = observation_from_meta(meta)
    finally:
        con.close()
    return obs


# ── Scoring ───────────────────────────────────────────────────────

@dataclass
class Scorecard:
    n: int
    per_dim: dict[str, dict] = field(default_factory=dict)  # dim -> {pass,graded}
    composite: float = 0.0        # mean over graded dimensions
    clean_rate: float = 0.0       # fraction of records passing all graded dims
    ece: float | None = None      # aggregate calibration error (graded-tier)
    mean_conf: float | None = None  # mean signal_conf over records that carry it
    worst: list[dict] = field(default_factory=list)


def score(records: list[DecisionRecord]) -> Scorecard:
    n = len(records)
    per_dim = {d: {"pass": 0, "graded": 0} for d in DIMENSIONS}

    clean = 0
    dim_pass_total = 0
    dim_graded_total = 0
    worst: list[dict] = []

    for rec in records:
        grades = rec.grade()
        graded_here = [v for v in grades.values() if v.graded]
        passed_here = [v for v in graded_here if v is Verdict.PASS]

        for dim, v in grades.items():
            if v.graded:
                per_dim[dim]["graded"] += 1
                if v is Verdict.PASS:
                    per_dim[dim]["pass"] += 1

        dim_pass_total += len(passed_here)
        dim_graded_total += len(graded_here)

        fails = [d for d, v in grades.items() if v is Verdict.FAIL]
        if not fails:
            clean += 1
        else:
            worst.append({
                "pid": rec.prompt_id,
                "domain": rec.domain,
                "expected": rec.expected_agent,
                "got": rec.chosen_agent,
                "confidence": rec.confidence,
                "failed": fails,
                "prompt": rec.prompt[:70],
            })

    # Aggregate ECE over the graded tier: confidence vs. empirical correctness.
    conf_records = [r for r in records if r.confidence is not None]
    ece = _ece(conf_records)
    mean_conf = (sum(r.confidence for r in conf_records) / len(conf_records)
                 if conf_records else None)

    # Order worst by number of failed dimensions, then overconfident-wrong first.
    worst.sort(key=lambda w: (-len(w["failed"]),
                              -(w["confidence"] or 0.0)))

    return Scorecard(
        n=n,
        per_dim=per_dim,
        composite=dim_pass_total / dim_graded_total if dim_graded_total else 0.0,
        clean_rate=clean / n if n else 0.0,
        ece=ece,
        mean_conf=mean_conf,
        worst=worst,
    )


def _ece(records: list[DecisionRecord], n_bins: int = 7) -> float | None:
    """Expected calibration error over confidence bins — same shape as
    calibration_report.report, but here 'performance' is 0/1 routing correctness."""
    if not records:
        return None
    lo, hi = 0.30, 1.00
    width = (hi - lo) / n_bins
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for r in records:
        c = r.confidence
        idx = max(0, min(n_bins - 1, int((c - lo) / width) if width else 0))
        bins[idx].append((c, int(r.chosen_agent == r.expected_agent)))
    n = len(records)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        mean_conf = sum(c for c, _ in b) / len(b)
        emp = sum(p for _, p in b) / len(b)
        ece += (len(b) / n) * abs(mean_conf - emp)
    return round(ece, 4)


# ── Reporting ─────────────────────────────────────────────────────

def _bar(frac: float, width: int = 20) -> str:
    filled = min(width, round(frac * width))
    return "█" * filled + "░" * (width - filled)


def print_scorecard(sc: Scorecard, strategy: str) -> None:
    sep = "─" * 74
    n_graded = sum(1 for d in DIMENSIONS if sc.per_dim[d]["graded"] > 0)
    print(f"\n{sep}")
    print(f"  Amagra Decision Quality Benchmark — strategy: {strategy}")
    print(f"  {sc.n} decisions   ({n_graded}/{len(DIMENSIONS)} dimensions graded)")
    print(sep)
    print(f"  {'Dimension':<24}  {'Graded':>7}  {'Pass':>6}  {'Pass%':>6}  Bar")
    print(sep)
    for d in DIMENSIONS:
        g = sc.per_dim[d]["graded"]
        p = sc.per_dim[d]["pass"]
        if g == 0:
            print(f"  {d:<24}  {'—':>7}  {'—':>6}  {'PEND':>6}  {'(needs full-pipeline harness)'}")
            continue
        pct = p / g
        print(f"  {d:<24}  {g:>7}  {p:>6}  {pct*100:5.1f}%  {_bar(pct)}")
    print(sep)
    print(f"  Composite (mean over graded dims): {sc.composite*100:5.1f}%")
    print(f"  Clean decisions (all graded pass): {sc.clean_rate*100:5.1f}%  "
          f"({round(sc.clean_rate*sc.n)}/{sc.n})")
    if sc.ece is not None:
        print(f"  Calibration ECE (signal_conf→route): {sc.ece:.4f} "
              f"(0.00 = perfectly calibrated)")
        if sc.mean_conf is not None and sc.mean_conf + 0.05 < sc.per_dim["routing_correct"]["pass"] / max(1, sc.per_dim["routing_correct"]["graded"]):
            print(f"    ↳ signal_conf (mean {sc.mean_conf:.2f}) is UNDER-confident vs "
                  f"routing accuracy: it is not P(route correct).")

    # Degenerate-efficiency note: everything passed only because no materially
    # cheaper correct route existed in this substrate.
    eff = sc.per_dim["efficient"]
    if eff["graded"] and eff["pass"] == eff["graded"]:
        print("  Note: efficiency = 100% because no materially cheaper correct")
        print("        route exists among no-LLM strategies; this dimension only")
        print("        discriminates once the LLM tier is a candidate route.")

    # Honest coverage line.
    pending = [d for d in DIMENSIONS if sc.per_dim[d]["graded"] == 0]
    graded = [d for d in DIMENSIONS if sc.per_dim[d]["graded"] > 0]
    print(f"\n  Coverage: {len(graded)}/{len(DIMENSIONS)} dimensions graded.")
    if pending:
        print(f"  Pending ({len(pending)}): {', '.join(pending)}")
        print("    → need per-run execution telemetry + gold annotations the")
        print("      full-pipeline harness does not emit yet. Slots exist on")
        print("      DecisionRecord; populate them and the scorer grades them as-is.")
    print(sep)


def print_worst(sc: Scorecard, limit: int) -> None:
    if not sc.worst:
        print("\n  No failed decisions on graded dimensions. Clean sweep.")
        return
    print(f"\n  Worst decisions (by # failed dims, then overconfidence) — top {limit}:")
    sep = "─" * 74
    print(sep)
    for w in sc.worst[:limit]:
        conf = f"{w['confidence']:.2f}" if w["confidence"] is not None else "  — "
        print(f"  [{w['pid']}]  conf={conf}  failed={','.join(w['failed'])}")
        print(f"    expected={w['expected']:<18} got={w['got']:<18}")
        print(f"    \"{w['prompt']}\"")
    print(sep)


# ── Main ──────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Amagra Decision Quality Benchmark")
    ap.add_argument("--strategy", default="signal_only",
                    help=f"decision under test: {', '.join(_STRATEGIES)}")
    ap.add_argument("--prompts", default="core", choices=["core", "extra", "all"],
                    help="core (100), extra (30), all (130)")
    ap.add_argument("--gold", default=None,
                    help="path to gold annotations JSON (enables the pending tier)")
    ap.add_argument("--runlog", nargs="?", const=True, default=None,
                    help="join observed telemetry from the run log; optional db path")
    ap.add_argument("--observations", default=None,
                    help="path to a captured observations JSON (pid → observation)")
    ap.add_argument("--worst", type=int, default=10, help="show N worst decisions")
    ap.add_argument("--no-save", action="store_true", help="skip JSON snapshot")
    args = ap.parse_args()

    if args.strategy not in _STRATEGIES:
        print(f"Unknown strategy {args.strategy!r}. Choose from: {list(_STRATEGIES)}")
        sys.exit(1)

    if args.prompts == "core":
        prompts = list(PROMPTS)
    elif args.prompts == "extra":
        prompts = list(EXTRA_PROMPTS)
    else:
        prompts = list(PROMPTS) + EXTRA_PROMPTS

    t0 = time.time()
    records = records_from_arena(prompts, args.strategy)

    # Pending tier: overlay gold + observations when supplied.
    join_note = None
    if args.gold:
        gold = load_gold(args.gold)
        if args.observations:
            with open(args.observations) as f:
                observations = json.load(f)
        elif args.runlog:
            db = args.runlog if isinstance(args.runlog, str) else None
            observations = load_runlog_observations(prompts, db)
        else:
            observations = {}
        joined = apply_annotations(records, gold, observations)
        src = ("observations file" if args.observations
               else "run log" if args.runlog else "none")
        join_note = (f"Pending tier: {len(gold)} gold prompts, "
                     f"{len(observations)} observations ({src}) → "
                     f"{joined}/{len(records)} decisions joined")

    sc = score(records)
    elapsed = (time.time() - t0) * 1000

    print(f"\n  Ran {len(prompts)} decisions in {elapsed:.0f}ms")
    if join_note:
        print(f"  {join_note}")
    print_scorecard(sc, args.strategy)
    print_worst(sc, args.worst)

    if not args.no_save:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(_LOGS_DIR, f"decision_quality_{ts}.json")
        with open(out, "w") as f:
            json.dump({
                "timestamp": ts,
                "strategy": args.strategy,
                "n": sc.n,
                "composite": round(sc.composite, 4),
                "clean_rate": round(sc.clean_rate, 4),
                "ece": sc.ece,
                "per_dim": sc.per_dim,
                "worst": sc.worst,
            }, f, indent=2)
        print(f"\n  Results → {out}")


if __name__ == "__main__":
    main()
