from fastapi import APIRouter, HTTPException

from orchestration.coordinator import coordinator
import cognition.run_tracer as run_tracer

from .deps import ForkRequest

router = APIRouter()


@router.get("/snapshots")
def get_snapshots(n: int = 50):
    import cognition.context_snapshot as _cs
    return {"snapshots": _cs.recent(n)}


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int):
    import cognition.context_snapshot as _cs
    s = _cs.get_by_id(snapshot_id)
    if not s:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return s


@router.get("/snapshots/by-context/{context_id}")
def get_snapshot_by_context(context_id: str):
    import cognition.context_snapshot as _cs
    s = _cs.get_by_context_id(context_id)
    if not s:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return s


@router.get("/snapshots/diff/{id_a}/{id_b}")
def diff_snapshots(id_a: int, id_b: int):
    import cognition.context_snapshot as _cs
    return _cs.diff(id_a, id_b)


def _run_fork_impl(context_id: str, req: ForkRequest) -> dict:
    import cognition.context_snapshot as _cs

    original = _cs.get_by_context_id(context_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original snapshot not found")

    original_query   = original.get("input", {}).get("query", "")
    original_sid     = original["_snapshot_id"]
    original_preview = original.get("output", {}).get("response_preview", "")

    import memory_core.context as _mc
    if req.exclude_memory_ids:
        _mc._set_fork_excluded_ids(req.exclude_memory_ids)

    fork_run_id = run_tracer.start(f"[fork] {original_query}")

    try:
        _cs.begin_fork(
            fork_run_id, original_query,
            parent_context_id=context_id,
            overrides={
                "agent":         req.agent_override,
                "exclude_mems":  req.exclude_memory_ids,
                "reflect_level": req.force_reflect_level,
                "note":          req.note,
            },
        )
    except Exception:
        pass

    try:
        fork_result = coordinator.invoke({
            "messages":               [{"role": "user", "content": original_query}],
            "active_agent":           "",
            "task":                   original_query,
            "result":                 "",
            "next_agent":             "",
            "memory":                 {},
            "force_agent":            req.agent_override or "",
            "brain_decision":         {},
            "reflect":                False,
            "reflect_type":           "general",
            "reflect_level":          "none",
            "contradiction_detected": False,
            "force_reflect_level":    req.force_reflect_level or "",
            "run_id":                 fork_run_id,
        })
    except ConnectionRefusedError:
        run_tracer.mark_failed(fork_run_id, "LLM backend offline")
        raise HTTPException(status_code=503, detail="LLM backend offline")
    except Exception as e:
        run_tracer.mark_failed(fork_run_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _mc._clear_fork_excluded_ids()

    response = fork_result["messages"][-1].content if fork_result.get("messages") else ""

    fork_snap = {}
    fork_sid  = None
    try:
        fork_snap = _cs.finalize(fork_run_id, response)
        fork_sid  = fork_snap.get("_snapshot_id")
    except Exception:
        pass

    diff_data = {}
    if original_sid and fork_sid:
        try:
            diff_data = _cs.diff(original_sid, fork_sid)
        except Exception:
            pass

    return {
        "original_context_id":       context_id,
        "fork_context_id":           fork_run_id,
        "original_snapshot_id":      original_sid,
        "fork_snapshot_id":          fork_sid,
        "response":                  response,
        "original_agent":            original.get("routing", {}).get("agent", ""),
        "fork_agent":                fork_result.get("active_agent", ""),
        "original_response_preview": original_preview,
        "overrides_applied": {
            "agent":         req.agent_override,
            "excl_mems":     req.exclude_memory_ids,
            "reflect_level": req.force_reflect_level,
            "note":          req.note,
        },
        "diff": diff_data,
    }


@router.post("/replay/{context_id}")
def replay(context_id: str):
    return _run_fork_impl(context_id, ForkRequest())


@router.post("/replay/{context_id}/fork")
def fork_replay(context_id: str, req: ForkRequest):
    return _run_fork_impl(context_id, req)
