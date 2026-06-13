import asyncio
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter()

MAINTENANCE_INTERVAL = 300

_maintenance_state: dict = {
    "last_run":     None,
    "last_actions": [],
    "runs_total":   0,
    "next_run_in":  MAINTENANCE_INTERVAL,
}

_ROUTER_RETRAIN_EVERY    = 50
_router_retrain_baseline = 0


async def maintenance_loop():
    global _router_retrain_baseline
    await asyncio.sleep(30)

    while True:
        actions = []
        ts = datetime.now(timezone.utc).isoformat()

        try:
            import memory_core.db as _mdb
            stats = _mdb.memory_stats()
            candidates = stats.get("prune_candidates", 0)
            if candidates >= 20:
                result  = _mdb.prune(dry_run=False)
                removed = result.get("deleted", 0)
                if removed:
                    actions.append(f"pruned {removed} low-quality memories ({candidates} candidates)")
        except Exception as e:
            actions.append(f"prune error: {e}")

        try:
            result  = _mdb.consolidate(threshold=0.93, dry_run=False)
            removed = result.get("removed", 0)
            if removed:
                actions.append(f"consolidated {removed} near-duplicate memories")
        except Exception as e:
            actions.append(f"consolidate error: {e}")

        try:
            from cognition.failure_miner import mine
            report = mine(limit=500)
            os.makedirs("logs", exist_ok=True)
            with open("logs/failure_report.json", "w") as f:
                json.dump({**report, "_ts": ts}, f, indent=2)
            actions.append("failure report written")
        except Exception as e:
            actions.append(f"failure miner error: {e}")

        try:
            from decision.log import conflict_rate as _cr
            from decision.analyzer import rebuild_from_history
            from decision.weights import load as _load_w, adjust as _adjust_w
            cr = _cr(100)
            if cr.get("conflict_rate", 0) > 0.35 and cr.get("total", 0) >= 20:
                new_weights = rebuild_from_history(500)
                current_w   = _load_w()
                for agent, new_w in new_weights.items():
                    delta = round(new_w - current_w.get(agent, 1.0), 4)
                    if abs(delta) > 0.001:
                        _adjust_w(agent, delta)
                actions.append(f"weights rebuilt (conflict rate {cr['conflict_rate']:.0%})")
        except Exception as e:
            actions.append(f"weight rebuild error: {e}")

        try:
            from decision.log import conflict_rate as _cr2
            current_total = _cr2(10000).get("total", 0)
            if current_total - _router_retrain_baseline >= _ROUTER_RETRAIN_EVERY:
                from orchestration.learned_router import _MODEL_PATH, train, invalidate_cache
                from cognition.trace_builder import load_cached_traces, build_traces
                if os.path.exists(_MODEL_PATH):
                    os.remove(_MODEL_PATH)
                invalidate_cache()
                traces = load_cached_traces() or build_traces()
                result = train(traces, verbose=False)
                _router_retrain_baseline = current_total
                actions.append(
                    f"learned router retrained (acc={result.get('accuracy', 0):.0%}, "
                    f"n={result.get('n_samples', 0)})"
                )
        except Exception as e:
            actions.append(f"router retrain error: {e}")

        _maintenance_state["last_run"]     = ts
        _maintenance_state["last_actions"] = actions
        _maintenance_state["runs_total"]  += 1
        _maintenance_state["next_run_in"]  = MAINTENANCE_INTERVAL

        if actions:
            print(f"[maintenance] {ts}: {'; '.join(actions)}")
        else:
            print(f"[maintenance] {ts}: nothing to do")

        await asyncio.sleep(MAINTENANCE_INTERVAL)


@router.get("/maintenance/status")
def get_maintenance_status():
    return {
        "interval_s":   MAINTENANCE_INTERVAL,
        "runs_total":   _maintenance_state["runs_total"],
        "last_run":     _maintenance_state["last_run"],
        "last_actions": _maintenance_state["last_actions"],
    }


@router.post("/maintenance/run")
async def run_maintenance_now():
    async def _one_shot():
        actions = []
        ts = datetime.now(timezone.utc).isoformat()
        try:
            import memory_core.db as _mdb
            stats = _mdb.memory_stats()
            if stats.get("prune_candidates", 0) >= 1:
                result  = _mdb.prune(dry_run=False)
                removed = result.get("deleted", 0)
                if removed:
                    actions.append(f"pruned {removed} memories")
            result = _mdb.consolidate(threshold=0.93, dry_run=False)
            if result.get("removed", 0):
                actions.append(f"consolidated {result['removed']} duplicates")
        except Exception as e:
            actions.append(f"memory error: {e}")
        try:
            from cognition.failure_miner import mine
            report = mine(limit=500)
            os.makedirs("logs", exist_ok=True)
            with open("logs/failure_report.json", "w") as f:
                json.dump({**report, "_ts": ts}, f, indent=2)
            actions.append("failure report written")
        except Exception as e:
            actions.append(f"failure miner error: {e}")
        _maintenance_state["last_run"]     = ts
        _maintenance_state["last_actions"] = actions
        _maintenance_state["runs_total"]  += 1
        print(f"[maintenance/manual] {ts}: {'; '.join(actions) or 'nothing to do'}")

    asyncio.create_task(_one_shot())
    return {"status": "triggered", "message": "maintenance running in background — check /maintenance/status"}
