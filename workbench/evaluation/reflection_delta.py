"""
reflection_delta.py — does reflection earn its cost? A controlled on/off A/B.

Step-3's run log showed reflection's *self-scored* delta was 0.0 every time. That
is the reflection loop grading its own work, so it is not trustworthy. This runs
the honest experiment: each prompt twice through the REAL pipeline — reflection
forced OFF vs forced ON — and compares the outcomes against gold.

Controls (so OFF is truly OFF and prompts stay independent):
  * force_reflect_level = "none" | "full" via the same override the API exposes;
  * the contradiction gate is monkeypatched off — otherwise it silently
    re-escalates the OFF arm back to full reflection (observed in step 3);
  * the memories table is cleared between every run, so nothing is retrieved
    from a previous arm and no cross-prompt contamination leaks in.

Isolation: requires AMAGRA_DATA_DIR (writes its own memory/logs, never touches
the real tree). Run under the venv:

  AMAGRA_DATA_DIR=/tmp/adb_refl \
  ~/.venvs/langgraph-env/bin/python -m workbench.evaluation.reflection_delta --n 8
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

GOLD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "decision_gold.json")
GOOD_QUALITY = 0.60


def _clear_memories() -> None:
    """Wipe the memories table between runs so each arm starts blank."""
    try:
        import memory_core.db as mdb
        con = sqlite3.connect(mdb.DB_PATH)
        con.execute("DELETE FROM memories")
        con.commit()
        con.close()
    except Exception:
        pass


def _judge(gold_answer: str, text: str, quality: float | None) -> bool | None:
    if gold_answer == "rubric":
        return (quality >= GOOD_QUALITY) if isinstance(quality, (int, float)) else None
    if not text:
        return None
    return gold_answer.lower() in text.lower()


def main() -> None:
    ap = argparse.ArgumentParser(description="Reflection on/off delta A/B")
    ap.add_argument("--n", type=int, default=0, help="limit to first N prompts (0 = all)")
    args = ap.parse_args()

    if not os.environ.get("AMAGRA_DATA_DIR"):
        print("Set AMAGRA_DATA_DIR to an isolated dir first.", file=sys.stderr)
        sys.exit(2)

    from workbench.evaluation.agent_arena import EXTRA_PROMPTS
    from routes.ask_pipeline import base_state
    import routes.core as core
    import orchestration.coordinator as coord
    import memory_core.db as mdb
    mdb.init_db()

    # Neutralise the contradiction gate so the OFF arm cannot be re-escalated.
    coord._check_contradiction = lambda *a, **k: False

    gold = {k: v for k, v in json.load(open(GOLD_PATH)).items() if not k.startswith("_")}
    prompts = [(p[0], p[3]) for p in EXTRA_PROMPTS if p[0] in gold]
    if args.n:
        prompts = prompts[: args.n]

    def run(prompt: str, level: str) -> dict:
        _clear_memories()
        state = base_state(prompt, f"ab_{level}",
                           messages=[{"role": "user", "content": prompt}],
                           force_reflect_level=level)
        t0 = time.time()
        res = core.coordinator.invoke(state)
        return {
            "reflect_level": res.get("reflect_level"),
            "quality": res.get("response_quality"),
            "text": res["messages"][-1].content,
            "ms": int((time.time() - t0) * 1000),
        }

    print(f"  Reflection on/off A/B — {len(prompts)} prompts × 2 runs\n")
    records = []
    for i, (pid, prompt) in enumerate(prompts, 1):
        off = run(prompt, "none")
        on = run(prompt, "full")
        ga = gold[pid]["answer"]
        rec = {
            "pid": pid,
            "gold_answer": ga,
            "off_level": off["reflect_level"], "on_level": on["reflect_level"],
            "off_correct": _judge(ga, off["text"], off["quality"]),
            "on_correct": _judge(ga, on["text"], on["quality"]),
            "off_quality": off["quality"], "on_quality": on["quality"],
            "off_ms": off["ms"], "on_ms": on["ms"],
            "changed": off["text"].strip() != on["text"].strip(),
        }
        records.append(rec)
        oc, nc = rec["off_correct"], rec["on_correct"]
        flip = ("rescued" if oc is False and nc is True else
                "broke" if oc is True and nc is False else "")
        print(f"  [{i:>2}/{len(prompts)}] {pid:<8} off={str(oc):<5} on={str(nc):<5} "
              f"changed={str(rec['changed']):<5} +{on['ms']-off['ms']:>6}ms {flip}")

    _report(records)


def _report(records: list[dict]) -> None:
    n = len(records)
    concrete = [r for r in records if r["gold_answer"] != "rubric"
                and r["off_correct"] is not None and r["on_correct"] is not None]
    sep = "─" * 66
    print(f"\n{sep}\n  Reflection on/off delta — {n} prompts\n{sep}")

    if concrete:
        off_c = sum(r["off_correct"] for r in concrete)
        on_c = sum(r["on_correct"] for r in concrete)
        rescued = [r["pid"] for r in concrete if not r["off_correct"] and r["on_correct"]]
        broke = [r["pid"] for r in concrete if r["off_correct"] and not r["on_correct"]]
        print(f"  Correctness (concrete-answer subset, n={len(concrete)}):")
        print(f"    OFF: {off_c}/{len(concrete)}    ON: {on_c}/{len(concrete)}    "
              f"delta: {on_c - off_c:+d}")
        print(f"    reflection rescued: {len(rescued)} {rescued or ''}")
        print(f"    reflection broke  : {len(broke)} {broke or ''}")
    else:
        print("  Correctness: no concrete-answer prompts in this run.")

    qpairs = [(r["off_quality"], r["on_quality"]) for r in records
              if isinstance(r["off_quality"], (int, float))
              and isinstance(r["on_quality"], (int, float))]
    if qpairs:
        moff = sum(a for a, _ in qpairs) / len(qpairs)
        mon = sum(b for _, b in qpairs) / len(qpairs)
        print(f"\n  Self-scored quality (n={len(qpairs)}):  OFF {moff:.3f}  "
              f"ON {mon:.3f}  delta {mon - moff:+.3f}")
        print("    (this is the reflection loop grading itself — weak signal)")

    changed = sum(1 for r in records if r["changed"])
    print(f"\n  Answer text differs OFF vs ON: {changed}/{n}")
    print("    (confounded — OFF and ON are independent generations, so LLM "
          "sampling alone changes the text; not evidence reflection did work)")

    off_ms = sum(r["off_ms"] for r in records)
    on_ms = sum(r["on_ms"] for r in records)
    print(f"  Latency: OFF {off_ms/n/1000:.1f}s/q  ON {on_ms/n/1000:.1f}s/q  "
          f"overhead {(on_ms-off_ms)/n/1000:+.1f}s/q  ({(on_ms-off_ms)/1000:.0f}s total)")

    # Verdict
    net = None
    if concrete:
        net = sum(r["on_correct"] for r in concrete) - sum(r["off_correct"] for r in concrete)
    print(f"\n{sep}")
    if net is not None and net > 0:
        print(f"  VERDICT: reflection is net-positive (+{net} correct) — worth its cost")
        print("           where it fires. Consider routing it to those task types.")
    elif changed == 0:
        print("  VERDICT: reflection changed NO answers and improved NO scores while")
        print("           adding latency — pure cost on this workload. Gate it off")
        print("           for these task types until a case that benefits is found.")
    else:
        print("  VERDICT: reflection changed some answers but produced no net")
        print("           correctness gain — cost not yet justified; needs a")
        print("           workload where it demonstrably rescues wrong answers.")
    print(sep)

    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs",
                       f"reflection_delta_{ts}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"n": n, "records": records}, f, indent=2)
    print(f"\n  Results → {out}")


if __name__ == "__main__":
    main()
