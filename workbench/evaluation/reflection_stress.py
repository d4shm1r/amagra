"""
reflection_stress.py — reflection on/off A/B on the STRESS set.

reflection_delta.py showed reflection = +0 on easy prompts, but that was
ceiling-bound (OFF already 8/8 — no failures to rescue). This runs the same
controlled A/B on reflection_stress.json: prompts the base model can plausibly
fail, so reflection has a real chance to help. Reports per-category correctness
OFF vs ON and capability ROI (Δcorrect per extra second), separating rigorous
checks from heuristic (marker-based) ones.

Same controls as reflection_delta: force_reflect_level none vs full, contradiction
gate neutralised (else the OFF arm re-escalates), memory cleared between runs.

  AMAGRA_DATA_DIR=/tmp/adb_stress \
  ~/.venvs/langgraph-env/bin/python -m workbench.evaluation.reflection_stress --n 4
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reflection_stress.json")


def _clear_memories() -> None:
    try:
        import memory_core.db as mdb
        con = sqlite3.connect(mdb.DB_PATH)
        con.execute("DELETE FROM memories")
        con.commit()
        con.close()
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Reflection on/off A/B — stress set")
    ap.add_argument("--n", type=int, default=0, help="limit to first N items (0 = all)")
    args = ap.parse_args()

    if not os.environ.get("AMAGRA_DATA_DIR"):
        print("Set AMAGRA_DATA_DIR to an isolated dir first.", file=sys.stderr)
        sys.exit(2)

    from routes.ask_pipeline import base_state
    import routes.core as core
    import orchestration.coordinator as coord
    import memory_core.db as mdb
    from workbench.evaluation import answer_checkers as ck
    mdb.init_db()
    coord._check_contradiction = lambda *a, **k: False

    items = {k: v for k, v in json.load(open(DATA)).items() if not k.startswith("_")}
    ids = list(items)[: args.n] if args.n else list(items)

    def _ollama_up() -> bool:
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            return True
        except Exception:
            return False

    def run(prompt: str, level: str, retries: int = 3) -> dict:
        """Resilient arm: Ollama OOM-crashes under this workload, so on failure
        wait for it to come back (a keeper loop restarts it) and retry rather
        than losing the whole run."""
        last = None
        for attempt in range(retries + 1):
            try:
                _clear_memories()
                state = base_state(prompt, f"stress_{level}",
                                   messages=[{"role": "user", "content": prompt}],
                                   force_reflect_level=level)
                t0 = time.time()
                res = core.coordinator.invoke(state)
                return {"text": res["messages"][-1].content,
                        "ms": int((time.time() - t0) * 1000)}
            except Exception as e:
                last = e
                if attempt >= retries:
                    break
                # Wait up to ~60s for Ollama to be restarted by the keeper.
                for _ in range(30):
                    if _ollama_up():
                        break
                    time.sleep(2)
        raise last

    print(f"  Reflection stress A/B — {len(ids)} items × 2 runs\n")
    records = []
    errored = 0
    for i, iid in enumerate(ids, 1):
        item = items[iid]
        spec = item["check"]
        try:
            off = run(item["prompt"], "none")
            on = run(item["prompt"], "full")
        except Exception as e:
            errored += 1
            print(f"  [{i:>2}/{len(ids)}] {iid:<7} ERRORED (skipped): {str(e)[:60]}")
            continue
        oc = ck.check(spec, off["text"])
        nc = ck.check(spec, on["text"])
        rec = {
            "id": iid, "category": item["category"],
            "heuristic": ck.is_heuristic(spec),
            "off_correct": oc, "on_correct": nc,
            "off_ms": off["ms"], "on_ms": on["ms"],
            # Keep the responses so None/BROKE cases are auditable post-hoc
            # (this run showed numeric grading returning None — needs inspection).
            "off_text": off["text"][:400], "on_text": on["text"][:400],
        }
        records.append(rec)
        flip = ("RESCUED" if oc is False and nc is True else
                "BROKE" if oc is True and nc is False else "")
        print(f"  [{i:>2}/{len(ids)}] {iid:<7} {item['category']:<22} "
              f"off={str(oc):<5} on={str(nc):<5} +{on['ms']-off['ms']:>7}ms {flip}")

    _report(records)


def _rate(recs: list[dict], key: str):
    gradeable = [r for r in recs if r[key] is not None]
    if not gradeable:
        return None, 0
    return sum(1 for r in gradeable if r[key]) / len(gradeable), len(gradeable)


def _report(records: list[dict]) -> None:
    sep = "─" * 72
    print(f"\n{sep}\n  Reflection stress A/B — {len(records)} items\n{sep}")

    # Per-category correctness OFF vs ON.
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    print(f"  {'Category':<24}{'OFF':>8}{'ON':>8}{'Δ':>7}  rescued/broke")
    print("  " + "-" * 62)
    for cat in sorted(by_cat):
        recs = by_cat[cat]
        off_r, no = _rate(recs, "off_correct")
        on_r, nn = _rate(recs, "on_correct")
        if off_r is None or on_r is None:
            continue
        resc = sum(1 for r in recs if r["off_correct"] is False and r["on_correct"] is True)
        brk = sum(1 for r in recs if r["off_correct"] is True and r["on_correct"] is False)
        heur = " *" if any(r["heuristic"] for r in recs) else ""
        print(f"  {cat:<24}{off_r*100:6.0f}% {on_r*100:6.0f}% {(on_r-off_r)*100:+6.0f}%  "
              f"{resc}/{brk}{heur}")
    print("  " + "-" * 62)
    print("  * category uses heuristic (marker-based) grading — weaker signal")

    # Overall, split rigorous vs heuristic.
    rig = [r for r in records if not r["heuristic"]]
    for label, subset in (("ALL", records), ("rigorous-only", rig)):
        off_r, no = _rate(subset, "off_correct")
        on_r, nn = _rate(subset, "on_correct")
        if off_r is None:
            continue
        resc = sum(1 for r in subset if r["off_correct"] is False and r["on_correct"] is True)
        brk = sum(1 for r in subset if r["off_correct"] is True and r["on_correct"] is False)
        print(f"\n  {label}: OFF {off_r*100:.0f}% ({no})  ON {on_r*100:.0f}% ({nn})  "
              f"Δ {(on_r-off_r)*100:+.0f}%   rescued {resc}  broke {brk}")

    # Capability ROI.
    off_ms = sum(r["off_ms"] for r in records)
    on_ms = sum(r["on_ms"] for r in records)
    n = len(records)
    overhead_s = (on_ms - off_ms) / 1000
    graded = [r for r in records if r["off_correct"] is not None and r["on_correct"] is not None]
    net = sum(1 for r in graded if not r["off_correct"] and r["on_correct"]) \
        - sum(1 for r in graded if r["off_correct"] and not r["on_correct"])
    print(f"\n  Latency: OFF {off_ms/n/1000:.1f}s/q  ON {on_ms/n/1000:.1f}s/q  "
          f"overhead +{overhead_s/n:.1f}s/q ({overhead_s:.0f}s total)")
    print(f"  Capability ROI: net {net:+d} correct for +{overhead_s:.0f}s "
          f"= {net/overhead_s if overhead_s else 0:+.3f} correct/sec")

    print(f"\n{sep}")
    if net > 0:
        print(f"  VERDICT: reflection is NET-POSITIVE (+{net}) on hard prompts. Route it")
        print("           to the categories with the largest positive delta; gate it off")
        print("           for easy/factual tasks where the earlier A/B showed +0.")
    elif net == 0:
        print("  VERDICT: even on stress prompts reflection nets 0 — strong evidence it")
        print("           is not earning its cost with the current reflection loop.")
    else:
        print(f"  VERDICT: reflection is NET-NEGATIVE ({net}) — it breaks more than it")
        print("           rescues. Do not auto-reflect; investigate the loop itself.")
    print(sep)

    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs",
                       f"reflection_stress_{ts}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"n": n, "records": records}, f, indent=2)
    print(f"\n  Results → {out}")


if __name__ == "__main__":
    main()
