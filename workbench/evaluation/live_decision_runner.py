"""
live_decision_runner.py — drive real pipeline runs for the Decision Quality Benchmark.

Runs the gold-annotated prompts through the REAL coordinator (same path as
POST /ask: begin_run → base_state → coordinator.invoke → finish_run), so every
run persists its raw orchestration observations to the run log. Point
decision_quality.py --runlog at the resulting runtime.db to get a real report.

Isolation: set AMAGRA_DATA_DIR before running so the benchmark writes its own
runtime.db / memory / weights and never touches the real logs/ tree. Example:

  AMAGRA_DATA_DIR=/tmp/adb_run \
  ~/.venvs/langgraph-env/bin/python -m workbench.evaluation.live_decision_runner --n 10

Then:

  PYTHONPATH=. python3 -m workbench.evaluation.decision_quality \
      --prompts extra --gold workbench/evaluation/data/decision_gold.json \
      --runlog "$AMAGRA_DATA_DIR/logs/runtime.db"
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def main() -> None:
    ap = argparse.ArgumentParser(description="Live pipeline runner for the ADB")
    ap.add_argument("--n", type=int, default=0, help="limit to first N prompts (0 = all)")
    ap.add_argument("--start", type=int, default=0, help="skip the first START prompts")
    args = ap.parse_args()

    if not os.environ.get("AMAGRA_DATA_DIR"):
        print("Refusing to run without AMAGRA_DATA_DIR set — it would write into the "
              "real logs/ and memory. Set it to an isolated dir first.", file=sys.stderr)
        sys.exit(2)

    # Imports happen AFTER the env guard so paths resolve to the isolated dir.
    from workbench.evaluation.agent_arena import EXTRA_PROMPTS
    from routes import ask_pipeline as pipeline
    from routes.deps import AskRequest
    from routes.core import coordinator
    from routes.ask_pipeline import base_state

    # Fresh isolated dir has no schema — bootstrap the memory table (mirrors the
    # test conftest) so finish_run's memory writes don't fail.
    import memory_core.db as _mdb
    _mdb.init_db()

    prompts = list(EXTRA_PROMPTS)[args.start:]
    if args.n:
        prompts = prompts[: args.n]

    data_dir = os.environ["AMAGRA_DATA_DIR"]
    print(f"  Data dir : {data_dir}")
    print(f"  Prompts  : {len(prompts)}")
    print(f"  Run log  : {os.path.join(data_dir, 'logs', 'runtime.db')}\n")

    ok = fail = 0
    t_all = time.time()
    for i, (pid, _expected, _domain, prompt) in enumerate(prompts, 1):
        t0 = time.time()
        try:
            req = AskRequest(message=prompt)
            run = pipeline.begin_run(req, key_id=None)
            state = base_state(run.task_msg, run.run_id, messages=run.provider_messages)
            run.result = coordinator.invoke(state)
            run.agent_used = run.result.get("active_agent", "unknown")
            run.response = run.result["messages"][-1].content
            run.bd = run.result.get("brain_decision", {})
            run.model_used = "phi4-mini"
            pipeline.finish_run(run)
            dt = time.time() - t0
            rl = run.result.get("reflect_level", "none")
            print(f"  [{i:>2}/{len(prompts)}] {pid:<8} → {run.agent_used:<18} "
                  f"reflect={rl:<5} {dt:5.1f}s")
            ok += 1
        except Exception as e:
            print(f"  [{i:>2}/{len(prompts)}] {pid:<8} FAILED: {e}")
            fail += 1

    print(f"\n  Done: {ok} ok, {fail} failed in {time.time()-t_all:.0f}s")


if __name__ == "__main__":
    main()
