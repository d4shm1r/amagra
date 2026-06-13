"""
benchmark_eval.py
─────────────────────────────────────────────────────────────────
Measures Pass@1 on HumanEval for two conditions:

  baseline  — raw phi4-mini, no critic
  gated     — phi4-mini + critic gate (grounded_evaluate + one retry)

Usage:
  python3 benchmark_eval.py                  # both modes, 50 problems
  python3 benchmark_eval.py --n 20           # quicker run
  python3 benchmark_eval.py --mode baseline  # one mode only
  python3 benchmark_eval.py --n 164          # full HumanEval

Results saved to logs/benchmark_<timestamp>.json
"""

import argparse, gzip, json, os, re, subprocess, sys, tempfile, textwrap, time
from datetime import datetime
from pathlib import Path

import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GATE_THRESHOLD = 0.70
_ROOT          = Path(__file__).parent.parent
DATA_CACHE     = _ROOT / 'logs' / 'HumanEval.jsonl'
RESULTS_DIR    = _ROOT / 'logs'
HE_URL         = (
    "https://raw.githubusercontent.com/openai/"
    "human-eval/master/data/HumanEval.jsonl.gz"
)

# ── Dataset ───────────────────────────────────────────────────

def _download_humaneval():
    import requests
    print("[data] downloading HumanEval …", flush=True)
    r = requests.get(HE_URL, timeout=30)
    r.raise_for_status()
    DATA_CACHE.write_text(gzip.decompress(r.content).decode())
    print(f"[data] saved {DATA_CACHE}")


def load_humaneval(n: int = 50) -> list[dict]:
    if not DATA_CACHE.exists():
        _download_humaneval()
    return [
        json.loads(l)
        for l in DATA_CACHE.read_text().splitlines() if l.strip()
    ][:n]


# ── LLM ───────────────────────────────────────────────────────

def _make_llm(temperature: float = 0.7):
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model="phi4-mini:latest",
        temperature=temperature,
        num_ctx=2048,
        num_thread=6,
        num_predict=768,
    )

_llm_cache: dict = {}

def generate(prompt: str, temperature: float = 0.7) -> str:
    key = round(temperature, 2)
    if key not in _llm_cache:
        _llm_cache[key] = _make_llm(temperature)
    return _llm_cache[key].invoke(prompt).content.strip()


# ── Code extraction ────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    # Properly closed fence
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Unclosed fence (model hit token limit before closing)
    m = re.match(r"```(?:python)?\s*(.*)", text, re.DOTALL)
    if m:
        return m.group(1).rstrip("`").strip()
    return text


def _extract_code(text: str, entry_point: str) -> str:
    """
    Return code suitable for assembly with the problem prompt.

    phi4-mini sometimes returns:
    (a) just the body (indented lines, no def)
    (b) the complete function (def + body)
    (c) the complete file (imports + def + body)

    We normalise all cases to a single string that run_tests can handle via
    textwrap.dedent + def-detection.
    """
    raw = _strip_fences(text).strip()
    return textwrap.dedent(raw)


# ── Test execution ─────────────────────────────────────────────

def run_tests(code: str, problem: dict) -> tuple[bool, str]:
    """
    Assemble a runnable program and execute it.

    If `code` contains the entry-point function definition → use it as-is
    (extract imports from the problem prompt so typing/etc. are available).
    Otherwise → prepend the problem prompt (which contains the def + docstring)
    and treat `code` as the body continuation.
    """
    entry = problem["entry_point"]

    has_def = bool(re.search(
        rf"def\s+{re.escape(entry)}\s*\(",
        code,
    ))

    if has_def:
        # Model gave us a full function.  Pull imports from the problem prompt.
        import_lines = "\n".join(
            line for line in problem["prompt"].splitlines()
            if line.strip().startswith(("from ", "import "))
        )
        program = f"{import_lines}\n\n{code}\n\n{problem['test']}\n\ncheck({entry})\n"
    else:
        # Body only: prepend the prompt (signature + docstring).
        # Ensure the body has at least one level of indentation.
        body_lines = code.splitlines()
        indented = "\n".join(
            ("    " + l) if (l and not l[0].isspace()) else l
            for l in body_lines
        )
        program = f"{problem['prompt']}{indented}\n\n{problem['test']}\n\ncheck({entry})\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=15,
        )
        return (True, "") if r.returncode == 0 else (False, (r.stderr or r.stdout).strip()[:300])
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)
    finally:
        os.unlink(path)


# ── Critic gate ────────────────────────────────────────────────

def critic_gate(prompt: str, code: str, problem: dict) -> tuple[str, dict]:
    """
    Score `code` with grounded_evaluate.
    If score < GATE_THRESHOLD: regenerate once at temperature=0.9.
    Returns (final_code, gate_record).
    """
    from cognition.reflection import grounded_evaluate

    eval1  = grounded_evaluate(prompt, code, "code")
    score1 = eval1["score"]

    record: dict = {
        "score_initial":     score1,
        "score_retry":       None,
        "accepted_on_first": score1 >= GATE_THRESHOLD,
        "retry_improved":    None,
    }

    if score1 >= GATE_THRESHOLD:
        return code, record

    retry_raw   = generate(prompt, temperature=0.9)
    retry_code  = _extract_code(retry_raw, problem["entry_point"])
    eval2       = grounded_evaluate(prompt, retry_code, "code")
    score2      = eval2["score"]

    record["score_retry"]    = score2
    record["retry_improved"] = score2 > score1

    return (retry_code if score2 >= score1 else code), record


# ── Prompt builder ─────────────────────────────────────────────

def _make_prompt(problem: dict) -> str:
    return (
        "Complete the following Python function. "
        "Return the COMPLETE function (including the def line) inside a ```python``` block.\n\n"
        f"{problem['prompt']}"
    )


# ── Single problem runner ──────────────────────────────────────

def _run_problem(problem: dict, mode: str) -> dict:
    from cognition.reflection import grounded_evaluate

    t0     = time.time()
    prompt = _make_prompt(problem)
    raw    = generate(prompt)
    code   = _extract_code(raw, problem["entry_point"])

    if mode == "gated":
        code, gate_record = critic_gate(prompt, code, problem)
    else:
        # Score without gating so baseline shares the calibration curve data
        eval1      = grounded_evaluate(prompt, code, "code")
        gate_record = {
            "score_initial":     eval1["score"],
            "score_retry":       None,
            "accepted_on_first": True,
            "retry_improved":    None,
        }

    passed, error = run_tests(code, problem)
    return {
        "task_id":   problem["task_id"],
        "passed":    passed,
        "error":     error if not passed else "",
        "elapsed_s": round(time.time() - t0, 2),
        "mode":      mode,
        **gate_record,
    }


# ── Metrics ────────────────────────────────────────────────────

def _brier(scores: list[float], labels: list[bool]) -> float:
    if not scores:
        return 0.0
    return sum((s - int(l)) ** 2 for s, l in zip(scores, labels)) / len(scores)


def _calibration_curve(scores: list[float], labels: list[bool],
                        n_buckets: int = 5) -> list[dict]:
    """
    P(pass | C in bucket) for n_buckets equal-width buckets over [0, 1].
    A monotonically increasing curve means the critic score is predictive.
    """
    width   = 1.0 / n_buckets
    buckets = []
    for i in range(n_buckets):
        lo   = round(i * width, 2)
        hi   = round((i + 1) * width, 2)
        pairs = [
            l for s, l in zip(scores, labels)
            if lo <= s < hi or (i == n_buckets - 1 and s == 1.0)
        ]
        n    = len(pairs)
        rate = round(sum(pairs) / n, 3) if n else None
        buckets.append({"range": f"{lo:.1f}–{hi:.1f}", "n": n, "pass_rate": rate})
    return buckets


def _compute_metrics(results: list[dict], mode: str) -> dict:
    n      = len(results)
    passed = [r for r in results if r["passed"]]
    c      = len(passed)

    scores = [r.get("score_initial", 0.75) for r in results]
    labels = [r["passed"] for r in results]

    m: dict = {
        "mode":             mode,
        "n":                n,
        "pass_count":       c,
        "pass_at_1":        round(c / n, 4) if n else 0,
        "avg_score":        round(sum(scores) / len(scores), 4) if scores else 0,
        "brier_score":      round(_brier(scores, labels), 4),
        "calibration_curve": _calibration_curve(scores, labels),
    }

    if mode == "gated":
        retried        = [r for r in results if not r.get("accepted_on_first", True)]
        improved       = [r for r in retried  if r.get("retry_improved")]
        accepted_first = [r for r in results  if r.get("accepted_on_first", True)]
        false_rejects  = [r for r in retried  if r["passed"]]
        false_accepts  = [r for r in accepted_first if not r["passed"]]
        gate_rate      = len(retried) / n if n else 0

        uplifts = [
            r["score_retry"] - r["score_initial"]
            for r in retried if r.get("score_retry") is not None
        ]
        mean_uplift = round(sum(uplifts) / len(uplifts), 4) if uplifts else 0.0

        m.update({
            "gate_trigger_count":   len(retried),
            "gate_trigger_rate":    round(gate_rate, 4),
            # Key metric: P(improvement | gate triggered)
            "p_improve_given_gate": round(len(improved) / len(retried), 4) if retried else 0,
            "false_reject_count":   len(false_rejects),
            "false_reject_rate":    round(len(false_rejects) / max(c, 1), 4),
            "false_accept_count":   len(false_accepts),
            "false_accept_rate":    round(len(false_accepts) / max(len(accepted_first), 1), 4),
            "mean_uplift":          mean_uplift,
        })

    return m


# ── Print report ───────────────────────────────────────────────

def _print_report(m: dict):
    sep = "─" * 52
    print(f"\n{sep}")
    print(f"  Mode     : {m['mode'].upper()}")
    print(f"  Problems : {m['n']}")
    print(f"  Pass@1   : {m['pass_count']}/{m['n']} = {m['pass_at_1']*100:.1f}%")
    print(f"  Avg C(y) : {m['avg_score']:.4f}   Brier: {m['brier_score']:.4f}")

    if m["mode"] == "gated":
        gr = m["gate_trigger_rate"] * 100
        pi = m["p_improve_given_gate"] * 100
        fr = m["false_reject_rate"] * 100
        fa = m["false_accept_rate"] * 100
        print(f"  ── Critic gate ──────────────────────────────")
        print(f"  Triggered             : {m['gate_trigger_count']}/{m['n']} ({gr:.1f}%)")
        print(f"  P(improve|triggered)  : {pi:.1f}%  ← key metric")
        print(f"  False reject rate     : {fr:.1f}%  (good solutions discarded)")
        print(f"  False accept rate     : {fa:.1f}%  (bad solutions passed)")
        print(f"  Mean score uplift     : {m['mean_uplift']:+.4f}")

    # Calibration curve — printed for both modes
    # This is the core empirical test: does C(y) predict correctness?
    curve = m.get("calibration_curve", [])
    if any(b["n"] > 0 for b in curve):
        print(f"  ── P(pass | score bucket) ───────────────────")
        print(f"  {'Score':8}  {'N':>4}  {'Pass%':>6}  {'Bar'}")
        for b in curve:
            if b["n"] == 0:
                continue
            pct   = b["pass_rate"] * 100 if b["pass_rate"] is not None else 0
            bar   = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            pct_s = f"{pct:.0f}%" if b["pass_rate"] is not None else "  —"
            print(f"  {b['range']:8}  {b['n']:>4}  {pct_s:>6}  {bar}")
    print(sep)


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HumanEval benchmark for critic-gated stack")
    parser.add_argument("--n",    type=int, default=50,  help="Problems to run (max 164)")
    parser.add_argument("--mode", default="both",        help="baseline | gated | both")
    args = parser.parse_args()

    modes    = ["baseline", "gated"] if args.mode == "both" else [args.mode]
    problems = load_humaneval(args.n)
    print(f"[bench] {len(problems)} problems · modes: {modes}")

    all_results: dict = {}
    all_metrics: dict = {}

    for mode in modes:
        print(f"\n[bench] === {mode.upper()} ===")
        results = []
        for i, p in enumerate(problems):
            prefix = f"  [{i+1:>3}/{len(problems)}] {p['task_id']}"
            try:
                rec    = _run_problem(p, mode)
                status = "PASS" if rec["passed"] else "fail"
                gate_s = ""
                if mode == "gated" and not rec.get("accepted_on_first", True):
                    gate_s = f"  gate↑{rec.get('score_retry', 0):.2f}"
                print(f"{prefix}  {status}{gate_s}", flush=True)
            except Exception as e:
                print(f"{prefix}  ERROR: {e}", flush=True)
                rec = {"task_id": p["task_id"], "passed": False, "error": str(e), "mode": mode}
            results.append(rec)

        metrics = _compute_metrics(results, mode)
        _print_report(metrics)
        all_results[mode] = results
        all_metrics[mode] = metrics

    if "baseline" in all_metrics and "gated" in all_metrics:
        delta = all_metrics["gated"]["pass_at_1"] - all_metrics["baseline"]["pass_at_1"]
        verdict = (
            "Critic gate improved pass rate."
            if delta > 0 else
            "No change in pass rate." if delta == 0 else
            "Critic gate degraded pass rate — review threshold or retry logic."
        )
        print(f"\n  Pass@1 delta (gated − baseline): {delta:+.1%}")
        print(f"  {verdict}")

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"benchmark_{ts}.json"
    outpath.write_text(json.dumps(
        {"timestamp": ts, "n": args.n, "metrics": all_metrics, "results": all_results},
        indent=2,
    ))
    print(f"\n[bench] results → {outpath}")


if __name__ == "__main__":
    main()
